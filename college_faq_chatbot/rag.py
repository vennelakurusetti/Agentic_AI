"""
rag.py -- Retrieval-Augmented Generation pipeline.

Key features:
 - Personal queries (name, branch, language) answered from memory first, no RAG.
 - Coreference resolution rewrites "it"/"that"/"first one" to specific entities.
 - Memory context injected with higher priority than knowledge base.
 - Memory + RAG context merged before LLM generation.
"""

import os
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

import config
from prompts import SYSTEM_PROMPT, QUERY_REWRITE_PROMPT, is_personal_query
from utils import logger, Timer, format_metadata

load_dotenv()


def get_embeddings() -> OpenAIEmbeddings:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", config.EMBEDDING_MODEL),
        openai_api_key=api_key,
        openai_api_base=config.OPENROUTER_BASE_URL,
    )


def get_llm(streaming: bool = False) -> ChatOpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", config.LLM_MODEL),
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
        openai_api_key=api_key,
        openai_api_base=config.OPENROUTER_BASE_URL,
        streaming=streaming,
    )


def get_vector_store() -> Chroma:
    if not config.CHROMA_DIR.exists() or not any(config.CHROMA_DIR.iterdir()):
        raise FileNotFoundError(
            "Vector store not found. Please run `python ingest.py` first."
        )
    return Chroma(
        collection_name=config.CHROMA_COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(config.CHROMA_DIR),
    )


def get_retriever(vector_store: Chroma, top_k: int = config.TOP_K,
                  filter_metadata: Optional[Dict] = None):
    search_kwargs: Dict[str, Any] = {"k": top_k}
    if filter_metadata:
        search_kwargs["filter"] = filter_metadata
    return vector_store.as_retriever(search_kwargs=search_kwargs)


def retrieve_chunks(query: str, top_k: int = config.TOP_K,
                    filter_metadata: Optional[Dict] = None,
                    debug: bool = False) -> List[Document]:
    if not query or not query.strip():
        return []

    vector_store = get_vector_store()
    retriever = get_retriever(vector_store, top_k=top_k, filter_metadata=filter_metadata)

    with Timer("Retrieval"):
        chunks = retriever.invoke(query)

    try:
        scored = vector_store.similarity_search_with_relevance_scores(query, k=top_k)
        for i, (doc, score) in enumerate(scored):
            if i < len(chunks):
                chunks[i].metadata["relevance_score"] = round(score, 4)
    except Exception as e:
        logger.debug(f"Could not get relevance scores: {e}")

    if debug:
        for i, chunk in enumerate(chunks):
            logger.info(f"  [{i}] Score={chunk.metadata.get('relevance_score','N/A')} "
                        f"Section={chunk.metadata.get('section','?')} "
                        f"{chunk.page_content[:80]}...")
    return chunks


def rewrite_query(question: str, chat_history: List[Dict[str, str]]) -> str:
    """
    Rewrite a follow-up question to be standalone, resolving all coreferences.
    Uses the last 6 messages (3 turns) for context.

    Handles:
    - "it", "that", "this" -> specific entity from history
    - "the first one", "the previous one" -> specific item
    - "its fee" -> "What is the fee for [branch]?"
    - "tell me more about it" -> "Tell me more about [topic]"
    - "compare it with the previous one" -> "Compare X with Y"
    """
    if not chat_history or not question or not question.strip():
        return question

    import re
    ref_pattern = re.compile(
        r"\b(it|its|that|this|those|these|"
        r"the (?:first|second|third|last|previous|above|mentioned|said|same)|"
        r"tell me more|compare (?:it|them|both)|which one|"
        r"the one you mentioned|previous one|first one|second one|"
        r"what about it|more about it|what about that)\b",
        re.I,
    )
    needs_rewrite = bool(ref_pattern.search(question))
    if not needs_rewrite:
        return question

    history_lines = []
    for msg in chat_history[-6:]:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "")
        if content:
            history_lines.append(f"{role}: {content[:300]}")

    if not history_lines:
        return question

    history_str = "\n".join(history_lines)
    llm = get_llm(streaming=False)
    prompt = PromptTemplate(
        template=QUERY_REWRITE_PROMPT,
        input_variables=["history", "question"],
    )
    try:
        response = (prompt | llm).invoke({"history": history_str, "question": question})
        rewritten = response.content.strip()
        if not rewritten or len(rewritten) > 500:
            return question
        if rewritten != question:
            logger.info(f"Coreference rewrite: '{question[:60]}' -> '{rewritten[:60]}'")
        return rewritten
    except Exception as e:
        logger.warning(f"Query rewrite failed: {e}")
        return question


def _answer_from_memory(question: str, memory_context: str) -> Optional[str]:
    """
    If this is a personal query and we have memory context, answer directly
    from memory using a lightweight LLM call -- no RAG retrieval needed.

    This handles questions like:
    - "What is my name?"
    - "Which branch do I like?"
    - "What language do I prefer?"
    - "What are my interests?"
    """
    if not memory_context or not is_personal_query(question):
        return None

    llm = get_llm(streaming=False)
    prompt = (
        "You are a helpful assistant. The user has stored the following personal information:\n"
        f"{memory_context}\n\n"
        "Answer this personal question directly and concisely using ONLY the stored information above.\n"
        "If the exact information is not in the stored data, say 'I don't have that information stored yet.'\n"
        "Be friendly and personalized in your response.\n\n"
        f"Question: {question}\n"
        "Answer:"
    )
    try:
        resp = llm.invoke(prompt)
        answer = resp.content.strip()
        if answer:
            logger.info(f"Personal query answered from memory: {question[:50]}")
            return answer
    except Exception as e:
        logger.warning(f"Memory-direct answer failed: {e}")
    return None


def generate_response(
    question: str,
    chunks: List[Document],
    chat_history: Optional[List[Dict[str, str]]] = None,
    debug: bool = False,
    memory_context: str = "",
) -> Dict[str, Any]:
    """
    Generate LLM response merging memory context + RAG context.
    Memory context always has higher priority than knowledge base context.
    """
    if not question or not question.strip():
        return {"answer": "Please ask a question.", "citations": [],
                "chunks_retrieved": 0, "chunks": [], "input_tokens": 0, "output_tokens": 0}

    # Build context from chunks (skip thin chunks < 80 chars)
    context_parts, used_chunks = [], []
    for i, chunk in enumerate(chunks):
        text = chunk.page_content.strip()
        section = chunk.metadata.get("section", "General")
        score = chunk.metadata.get("relevance_score", "N/A")
        if len(text) < 80:
            continue
        context_parts.append(f"--- Chunk {i+1} [Section: {section}] (Score: {score}) ---\n{text}")
        used_chunks.append(chunk)

    context_str = "\n\n".join(context_parts)

    # Format conversation history (last 10 turns)
    history_lines = []
    if chat_history:
        for msg in reversed(chat_history[-10:]):
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            if content:
                history_lines.append(f"{role}: {content}")
    chat_history_str = (
        "Conversation History (most recent first):\n" + "\n".join(history_lines)
        if history_lines else ""
    )

    # Build memory context string -- prepend a clear header if non-empty
    formatted_memory = memory_context if memory_context else ""

    prompt = PromptTemplate(
        template=SYSTEM_PROMPT,
        input_variables=["context", "memory_context", "chat_history", "question"],
    )
    llm = get_llm(streaming=False)

    full_text = context_str + formatted_memory + chat_history_str + question
    input_tokens_est = len(full_text) // 4

    with Timer("Generation"):
        response = (prompt | llm).invoke({
            "context": context_str,
            "memory_context": formatted_memory,
            "chat_history": chat_history_str,
            "question": question,
        })

    answer = response.content
    output_tokens_est = len(answer) // 4

    input_tokens = input_tokens_est
    output_tokens = output_tokens_est
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        meta = response.usage_metadata
        input_tokens = meta.get("input_tokens", input_tokens_est) or input_tokens_est
        output_tokens = meta.get("output_tokens", output_tokens_est) or output_tokens_est

    citations = list(dict.fromkeys(
        chunk.metadata.get("section", "General") for chunk in used_chunks
    ))

    return {
        "answer": answer,
        "citations": citations,
        "chunks_retrieved": len(chunks),
        "chunks": chunks,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def answer_question(
    question: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    top_k: int = config.TOP_K,
    filter_metadata: Optional[Dict] = None,
    debug: bool = False,
    memory_context: str = "",
) -> Dict[str, Any]:
    """
    Full RAG pipeline with memory-first routing for personal queries.

    Flow:
    1. Personal query? -> Answer directly from memory (no RAG).
    2. Rewrite query   -> Resolve coreferences ("it", "that branch", etc.)
    3. Retrieve chunks -> Vector search in knowledge base.
    4. Generate answer -> Merge memory context + RAG context in one LLM call.
    """
    if not question or not question.strip():
        return {"answer": "Please ask a question about BVRIT Hyderabad.",
                "citations": [], "chunks_retrieved": 0, "chunks": [],
                "input_tokens": 0, "output_tokens": 0}

    if chat_history is None:
        chat_history = []

    # Step 1: Personal query -> answer from memory directly
    memory_answer = _answer_from_memory(question, memory_context)
    if memory_answer:
        return {
            "answer": memory_answer,
            "citations": ["User Memory"],
            "chunks_retrieved": 0,
            "chunks": [],
            "input_tokens": 0,
            "output_tokens": 0,
            "source": "memory",
        }

    # Step 2: Rewrite query (coreference resolution)
    standalone_query = rewrite_query(question, chat_history)

    # Step 3: Retrieve chunks
    chunks = retrieve_chunks(standalone_query, top_k=top_k,
                             filter_metadata=filter_metadata, debug=debug)

    if not chunks:
        # If we have memory, try to answer with memory only (no RAG context)
        if memory_context:
            return generate_response(question, [], chat_history, debug, memory_context)
        return {
            "answer": "This information is not available in the uploaded knowledge base.",
            "citations": [], "chunks_retrieved": 0, "chunks": [],
            "input_tokens": 0, "output_tokens": 0,
        }

    # Step 4: Generate response (memory + RAG context merged)
    return generate_response(standalone_query, chunks, chat_history, debug, memory_context)
