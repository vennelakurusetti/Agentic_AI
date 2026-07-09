"""
memory_store.py — ChromaDB-backed persistent memory store.

Provides the low-level CRUD operations for the separate memory ChromaDB:
  - init_memory_db()     — Create / load the memory collection
  - add_memory()         — Insert a new memory vector
  - update_memory()      — Overwrite an existing memory by ID
  - delete_user_memories() — Remove every vector belonging to a user
  - get_memory_collection() — Direct access to the Chroma collection

This database is completely independent from the knowledge ChromaDB.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

import config
from utils import logger

# ── Public helpers ──────────────────────────────────────────────

def get_embeddings() -> OpenAIEmbeddings:
    """Reuse the same embedding model as the knowledge base."""
    import os
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", config.EMBEDDING_MODEL),
        openai_api_key=api_key,
        openai_api_base=config.OPENROUTER_BASE_URL,
    )


def get_memory_collection() -> Chroma:
    """Return the memory Chroma collection, creating it if it doesn't exist."""
    embeddings = get_embeddings()
    return Chroma(
        collection_name=config.MEMORY_COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(config.MEMORY_DIR),
    )


def _memory_doc(
    user_id: str,
    memory_type: str,
    content: str,
    importance: float = 0.5,
    session_id: str = "",
) -> Document:
    """Build a Document with the standard memory metadata schema.
    Timestamp is stored as epoch seconds for ChromaDB $lt/$gt support."""
    return Document(
        page_content=content,
        metadata={
            "user_id": user_id,
            "memory_type": memory_type,
            "timestamp": datetime.now().timestamp(),
            "ts_iso": datetime.now().isoformat(),
            "importance": importance,
            "session_id": session_id,
        },
    )


# ── CRUD Operations ─────────────────────────────────────────────

def add_memory(
    user_id: str,
    memory_type: str,
    content: str,
    importance: float = 0.5,
    session_id: str = "",
    memory_id: Optional[str] = None,
) -> str:
    """
    Add a single memory vector to the memory ChromaDB.

    Returns the generated (or provided) memory ID.
    """
    doc = _memory_doc(user_id, memory_type, content, importance, session_id)
    mid = memory_id or str(uuid.uuid4())
    doc.metadata["memory_id"] = mid

    collection = get_memory_collection()
    collection.add_documents([doc], ids=[mid])
    logger.info(f"Memory stored: [{memory_type}] {content[:60]} (id={mid})")
    return mid


def add_memories_batch(entries: List[Dict[str, Any]], session_id: str = "") -> List[str]:
    """
    Add multiple memories in one batch call.

    Each entry must have: user_id, memory_type, content.
    Optional: importance (default 0.5), memory_id.
    """
    if not entries:
        return []

    docs = []
    ids = []
    for entry in entries:
        mid = entry.get("memory_id") or str(uuid.uuid4())
        doc = _memory_doc(
            user_id=entry["user_id"],
            memory_type=entry["memory_type"],
            content=entry["content"],
            importance=entry.get("importance", 0.5),
            session_id=session_id,
        )
        doc.metadata["memory_id"] = mid
        docs.append(doc)
        ids.append(mid)

    collection = get_memory_collection()
    collection.add_documents(docs, ids=ids)
    logger.info(f"Batch stored {len(docs)} memories")
    return ids


def update_memory(memory_id: str, **metadata_updates: Any) -> bool:
    """
    Update metadata fields of an existing memory.
    The content can be replaced via page_content=… in metadata_updates.
    """
    collection = get_memory_collection()
    results = collection.get(ids=[memory_id])
    if not results["ids"]:
        logger.warning(f"Memory {memory_id} not found for update")
        return False

    old_meta = results["metadatas"][0] if results["metadatas"] else {}
    old_content = results["documents"][0] if results["documents"] else ""

    new_content = metadata_updates.pop("page_content", old_content)
    now = datetime.now()
    new_meta = {
        **old_meta,
        **metadata_updates,
        "timestamp": now.timestamp(),
        "ts_iso": now.isoformat(),
    }

    collection.delete(ids=[memory_id])
    doc = Document(page_content=new_content, metadata=new_meta)
    collection.add_documents([doc], ids=[memory_id])
    logger.info(f"Memory updated: {memory_id}")
    return True


def find_memory_by_content(user_id: str, memory_type: str, content_substr: str) -> Optional[Dict[str, Any]]:
    """
    Check if a memory of the same type and similar content already exists.
    Returns the first matching memory dict (with id) or None.
    """
    collection = get_memory_collection()
    # Filter by user_id + memory_type via Chroma metadata filtering
    results = collection.get(
        where={"$and": [{"user_id": user_id}, {"memory_type": memory_type}]},
    )
    if not results["ids"]:
        return None

    for i, doc_text in enumerate(results["documents"] or []):
        if content_substr.lower() in doc_text.lower():
            return {
                "id": results["ids"][i],
                "page_content": doc_text,
                "metadata": results["metadatas"][i] if results["metadatas"] else {},
            }
    return None


def delete_user_memories(user_id: str) -> int:
    """
    Delete ALL memory vectors belonging to a user.
    Returns the number of deleted vectors.
    Used by the "clear my data" privacy command.
    """
    collection = get_memory_collection()
    results = collection.get(where={"user_id": user_id})
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)
        logger.info(f"Deleted {len(ids)} memories for user {user_id}")
    return len(ids)


def delete_memories_older_than(days: int = 30) -> int:
    """
    Delete memories whose timestamp is older than the given number of days.
    Uses epoch seconds comparison for ChromaDB compatibility.
    """
    from datetime import timedelta
    cutoff_epoch = (datetime.now() - timedelta(days=days)).timestamp()

    collection = get_memory_collection()
    # Chroma where clause: timestamp < cutoff (both are epoch seconds now)
    results = collection.get(where={"timestamp": {"$lt": cutoff_epoch}})
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)
        logger.info(f"Cleanup: deleted {len(ids)} memories older than {days} days")
    return len(ids)


def get_memory_count(user_id: Optional[str] = None) -> int:
    """Return the number of memory vectors, optionally filtered by user."""
    collection = get_memory_collection()
    where = {"user_id": user_id} if user_id else None
    results = collection.get(where=where)
    return len(results.get("ids", []))