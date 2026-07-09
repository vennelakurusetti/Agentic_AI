"""
memory_manager.py — High-level orchestrator for the memory subsystem.

Ties together:
  - memory_store.py   (CRUD)
  - memory_extractor.py (extract facts from turns)
  - memory_retriever.py (search & format)

Provides the single entry point used by app.py.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

import config
from memory.memory_store import (
    add_memory,
    add_memories_batch,
    update_memory,
    find_memory_by_content,
    delete_user_memories,
    delete_memories_older_than,
    get_memory_count,
)
from memory.memory_extractor import extract_memories
from memory.memory_retriever import retrieve_memories, format_memories_for_prompt
from utils import logger


def get_session_id() -> str:
    """Generate a unique session ID."""
    return str(uuid.uuid4())[:8]


def process_and_store_memories(
    user_input: str,
    assistant_response: str,
    user_id: str,
    session_id: str,
    use_llm_extraction: bool = True,
) -> int:
    """
    Extract memories from a conversation turn and store them in the memory DB.

    Steps:
      1. Run extract_memories() on the user input + assistant response.
      2. For each extracted memory, check if it already exists (by type + content).
      3. If it exists, update it (overwrite). If not, insert a new vector.
      4. Returns the number of memories stored/updated.

    This function is called AFTER every assistant response.
    """
    extracted = extract_memories(user_input, assistant_response, use_llm=use_llm_extraction)
    if not extracted:
        return 0

    stored_count = 0
    for mem in extracted:
        mtype = mem["memory_type"]
        content = mem["content"]
        importance = mem.get("importance", 0.5)

        # Check if a similar memory already exists
        existing = find_memory_by_content(user_id, mtype, content)

        if existing:
            # Update existing memory with new content and bumped importance
            # Use max importance so important facts don't get overwritten by less important ones
            old_imp = existing["metadata"].get("importance", 0.0)
            new_imp = max(old_imp, importance)
            update_memory(
                existing["id"],
                page_content=content,
                importance=new_imp,
                memory_type=mtype,
                user_id=user_id,
                session_id=session_id,
            )
            logger.info(f"Updated memory [{mtype}]: {content}")
        else:
            # Insert new memory
            add_memory(
                user_id=user_id,
                memory_type=mtype,
                content=content,
                importance=importance,
                session_id=session_id,
            )
        stored_count += 1

    return stored_count


def retrieve_user_context(
    user_id: str,
    query: str,
    top_k: int = 5,
) -> str:
    """
    Retrieve relevant memories for a user and format them as a prompt suffix.

    This is called BEFORE every assistant response to inject user context
    into the system prompt.
    """
    memories = retrieve_memories(user_id, query, top_k=top_k)
    return format_memories_for_prompt(memories)


def clear_user_data(user_id: str) -> int:
    """
    Delete all memories for a user. Used by the "clear my data" command.
    Returns the number of deleted vectors.
    """
    count = delete_user_memories(user_id)
    logger.info(f"Cleared {count} memories for user {user_id}")
    return count


def run_cleanup(days: int = 30) -> int:
    """
    Delete memories older than the specified number of days.
    Should be called periodically (e.g. on app startup).
    """
    count = delete_memories_older_than(days)
    if count > 0:
        logger.info(f"Cleanup: removed {count} memories older than {days} days")
    return count


def get_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Return memory statistics for display in the UI."""
    return {
        "total_memories": get_memory_count(user_id),
        "user_id": user_id or "all",
    }