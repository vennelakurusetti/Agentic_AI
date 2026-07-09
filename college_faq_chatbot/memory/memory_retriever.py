"""
memory_retriever.py — Retrieve relevant user memories from the memory ChromaDB.

Searches the memory store by:
  1. user_id (metadata filter)
  2. semantic similarity to the current query

Returns the top-K most relevant memories (default top 5).
"""

from typing import Dict, Any, List, Optional

from langchain_chroma import Chroma
from langchain_core.documents import Document

import config
from memory.memory_store import get_memory_collection, get_embeddings
from utils import logger


def retrieve_memories(
    user_id: str,
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Retrieve the most relevant memories for a user.

    Steps:
      1. Filter by user_id via Chroma metadata filter.
      2. Perform similarity search on the filtered subset.
      3. Return top_k results with metadata.

    Returns a list of dicts, each with:
      - memory_type
      - content
      - importance
      - timestamp
      - session_id
      - memory_id
      - relevance_score
    """
    collection = get_memory_collection()

    # Step 1: Filter by user_id
    results = collection.get(where={"user_id": user_id})
    if not results["ids"]:
        logger.info(f"No memories found for user {user_id}")
        return []

    # Step 2: If there are enough memories, do a similarity search within the user's subset
    # Chroma doesn't support filtering + similarity in one call easily,
    # so we use the collection's similarity_search with a filter.
    try:
        docs_with_scores = collection.similarity_search_with_relevance_scores(
            query,
            k=top_k,
            filter={"user_id": user_id},
        )
    except Exception as e:
        logger.warning(f"Similarity search failed, falling back to get: {e}")
        # Fallback: return most recent memories without scoring
        memories = []
        for i in range(len(results["ids"])):
            memories.append({
                "memory_id": results["ids"][i],
                "content": (results["documents"] or [""])[i],
                **((results["metadatas"] or [{}])[i] or {}),
                "relevance_score": 0.0,
            })
        return memories[:top_k]

    # Step 3: Format results
    memories = []
    for doc, score in docs_with_scores:
        memories.append({
            "memory_id": doc.metadata.get("memory_id", ""),
            "memory_type": doc.metadata.get("memory_type", "unknown"),
            "content": doc.page_content,
            "importance": doc.metadata.get("importance", 0.5),
            "timestamp": doc.metadata.get("timestamp", ""),
            "session_id": doc.metadata.get("session_id", ""),
            "relevance_score": round(float(score), 4),
        })

    logger.info(f"Retrieved {len(memories)} memories for user {user_id} (query='{query[:50]}')")
    return memories


def format_memories_for_prompt(memories: List[Dict[str, Any]]) -> str:
    """
    Format retrieved memories into a readable string for injection
    into the LLM system prompt.
    """
    if not memories:
        return ""

    lines = ["\n\n--- User Memory Context ---"]
    for m in memories:
        mtype = m.get("memory_type", "unknown").replace("_", " ").title()
        content = m.get("content", "")
        imp = m.get("importance", 0.0)
        if imp >= 0.8:
            star = "⭐"
        elif imp >= 0.5:
            star = "📌"
        else:
            star = "ℹ️"
        lines.append(f"{star} {mtype}: {content}")

    return "\n".join(lines)