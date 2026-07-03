"""
rag.py - Retrieval-Augmented Generation pipeline.
Handles retrieval from ChromaDB and response generation via OpenRouter.
"""

import os
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

import config
from prompts import SYSTEM_PROMPT, QUERY_REWRITE_PROMPT
from utils import logger, Timer, format_metadata

load_dotenv()


def get_embeddings() -> OpenAIEmbeddings:
    """Get the OpenAI embeddings model configured for OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")

    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", config.EMBEDDING_MODEL),
        openai_api_key=api_key,
        openai_api_base=config.OPENROUTER_BASE_URL,
    )


def get_llm() -> ChatOpenAI:
    """Get the ChatOpenAI LLM configured for OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")

    model = os.getenv("LLM_MODEL", config.LLM_MODEL)
    return ChatOpenAI(
        model=model,
        temperature=config.LLM_TEMPERATURE,
        max_tokens=config.LLM_MAX_TOKENS,
        openai_api_key=api_key,
        openai_api_base=config.OPENROUTER_BASE_URL,
        streaming=True,
    )


def get_vector_store() -> Chroma:
    """Load the persistent ChromaDB vector store."""
    if not config.CHROMA_DIR.exists() or not any(config.CHROMA_DIR.iterdir()):
        raise FileNotFoundError(
            "Vector store not found. Please run `python ingest.py` first."
        )

    embeddings = get_embeddings()
    return Chroma(
        collection_name=config.CHROMA_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(config.CHROMA_DIR),
    )


def get_retriever(
    vector_store: Chroma,
    top_k: int = config.TOP_K,
    filter_metadata: Optional[Dict[str, Any]] = None,
):
    """Create a retriever from the vector store."""
    search_kwargs = {"k": top_k}
    if filter_metadata:
        search_kwargs["filter"] = filter_metadata

    return vector_store.as_retriever(search_kwargs=search_kwargs)


def retrieve_chunks(
    query: str,
    top_k: int = config.TOP_K,
    filter_metadata: Optional[Dict[str, Any]] = None,
    debug: bool = False,
) -> List[Document]:
    """Retrieve relevant chunks for a query."""
    vector_store = get_vector_store()
    retriever = get_retriever(vector_store, top_k=top_k, filter_metadata=filter_metadata)

    with Timer("Retrieval"):
        chunks = retriever.invoke(query)

    # Add scores if available (Chroma returns relevance scores)
    if hasattr(vector_store, "similarity_search_with_relevance_scores"):
        scored_chunks = vector_store.similarity_search_with_relevance_scores(
            query, k=top_k
        )
        for i, (doc, score) in enumerate(scored_chunks):
            if i < len(chunks):
                chunks[i].metadata["relevance_score"] = round(score, 4)

    if debug:
        logger.info(f"Retrieved {len(chunks)} chunks for query: '{query}'")
        for i, chunk in enumerate(chunks):
            section = chunk.metadata.get("section", "Unknown")
            score = chunk.metadata.get("relevance_score", "N/A")
            text_preview = chunk.page_content[:100].replace("\n", " ")
            logger.info(f"  [{i}] Score={score} | Section={section} | {text_preview}...")

    return chunks


def rewrite_query(
    question: str,
    chat_history: List[Dict[str, str]],
) -> str:
    """Rewrite a follow-up question to be standalone using conversation context."""
    if not chat_history:
        return question  # No history, use as-is

    # Build conversation history string
    history_lines = []
    for msg in chat_history[-4:]:  # Use last 4 messages for context
        role = msg.get("role", "user")
        content = msg.get("content", "")
        history_lines.append(f"{role.capitalize()}: {content}")

    history_str = "\n".join(history_lines)

    llm = get_llm()
    prompt = PromptTemplate(
        template=QUERY_REWRITE_PROMPT,
        input_variables=["history", "question"],
    )
    chain = prompt | llm

    response = chain.invoke({"history": history_str, "question": question})
    rewritten = response.content.strip()

    logger.info(f"Original query: '{question}' -> Rewritten: '{rewritten}'")
    return rewritten


def generate_response(
    question: str,
    chunks: List[Document],
    debug: bool = False,
) -> Dict[str, Any]:
    """Generate a response using the LLM with retrieved context."""
    # Build context string from chunks (skip thin chunks with no real content)
    context_parts = []
    for i, chunk in enumerate(chunks):
        text = chunk.page_content.strip()
        section = chunk.metadata.get("section", "General")
        score = chunk.metadata.get("relevance_score", "N/A")
        # Skip chunks that are just headings with no real content (< 80 chars)
        if len(text) < 80:
            if debug:
                logger.info(f"Skipping thin chunk [{i}] Section={section} ({len(text)} chars)")
            continue
        context_parts.append(f"--- Chunk {i + 1} [Section: {section}] (Score: {score}) ---\n{text}")

    context_str = "\n\n".join(context_parts)

    # Format the system prompt
    prompt = PromptTemplate(
        template=SYSTEM_PROMPT,
        input_variables=["context", "question"],
    )

    llm = get_llm()
    chain = prompt | llm

    with Timer("Generation"):
        response = chain.invoke({"context": context_str, "question": question})

    # Extract citations from chunk metadata (always use section names)
    citations = list(dict.fromkeys(
        chunk.metadata.get("section", "General") for chunk in chunks
    ))

    return {
        "answer": response.content,
        "citations": citations,
        "chunks_retrieved": len(chunks),
        "chunks": chunks,
    }


def answer_question(
    question: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    top_k: int = config.TOP_K,
    filter_metadata: Optional[Dict[str, Any]] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """Full RAG pipeline: rewrite query -> retrieve -> generate."""
    if chat_history is None:
        chat_history = []

    # Step 1: Rewrite query if there's conversation history
    standalone_query = rewrite_query(question, chat_history)

    # Step 2: Retrieve relevant chunks
    chunks = retrieve_chunks(
        standalone_query,
        top_k=top_k,
        filter_metadata=filter_metadata,
        debug=debug,
    )

    if not chunks:
        return {
            "answer": "This information is not available in the uploaded knowledge base.",
            "citations": [],
            "chunks_retrieved": 0,
            "chunks": [],
        }

    # Step 3: Generate response
    result = generate_response(standalone_query, chunks, debug=debug)

    return result