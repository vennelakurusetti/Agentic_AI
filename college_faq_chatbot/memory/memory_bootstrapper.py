"""
memory_bootstrapper.py — One-time memory bootstrapping from past chat history.

When a user enters their username at startup, this module:
1. Scans the existing chat history (JSONL) for that user.
2. Runs the existing memory extractor over every user+assistant turn.
3. Deduplicates via memory_store.find_memory_by_content().
4. Updates conflicts via memory_store.update_memory().
5. Adds new memories via memory_store.add_memory().
6. Marks the user as "bootstrapped" so it runs only once.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

import config
from memory.memory_store import add_memory, update_memory, find_memory_by_content, get_memory_count
from memory.memory_extractor import extract_memories, extract_pattern_based
from utils import logger

# ── Chat history file location ──
# We store chat history per user as JSONL files
CHAT_HISTORY_DIR = config.BASE_DIR / "chat_history"


def _ensure_chat_history_dir() -> None:
    """Create the chat history directory if it doesn't exist."""
    CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def get_chat_history_path(user_id: str) -> Path:
    """Return the path to the chat history JSONL file for a user."""
    _ensure_chat_history_dir()
    return CHAT_HISTORY_DIR / f"{user_id}_history.jsonl"


def append_to_chat_history(
    user_id: str,
    user_message: str,
    assistant_message: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a conversation turn to the user's chat history file."""
    path = get_chat_history_path(user_id)
    entry = {
        "user": user_message,
        "assistant": assistant_message,
        "metadata": metadata or {},
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def load_chat_history(user_id: str) -> List[Dict[str, str]]:
    """Load all past conversation turns for a user from their JSONL file."""
    path = get_chat_history_path(user_id)
    if not path.exists():
        return []
    turns = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    turns.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return turns


def bootstrap_memories_from_history(
    user_id: str,
    use_llm: bool = False,
) -> Dict[str, Any]:
    """
    Scan all past chat history for a user, extract long-term memories,
    and store them in the memory ChromaDB.

    Skips duplicate memories (same user_id + memory_type + similar content).
    Updates conflicting memories (same user_id + memory_type, different content).

    Args:
        user_id: The username/ID to bootstrap for.
        use_llm: Whether to use LLM-based extraction (slower, more accurate).

    Returns:
        Dict with keys: new_count, updated_count, skipped_count, total_turns.
    """
    turns = load_chat_history(user_id)
    if not turns:
        logger.info(f"No chat history found for user {user_id}")
        return {"new_count": 0, "updated_count": 0, "skipped_count": 0, "total_turns": 0}

    new_count = 0
    updated_count = 0
    skipped_count = 0

    logger.info(f"Bootstrapping memories for user {user_id} from {len(turns)} conversation turns")

    for turn in turns:
        user_input = turn.get("user", "")
        assistant_response = turn.get("assistant", "")

        if not user_input.strip():
            continue

        # Extract memories using the existing extractor
        memories = extract_memories(user_input, assistant_response, use_llm=use_llm)

        for mem in memories:
            memory_type = mem.get("memory_type", "")
            content = mem.get("content", "")
            importance = mem.get("importance", 0.5)

            if not memory_type or not content:
                continue

            # Check if a similar memory already exists
            existing = find_memory_by_content(user_id, memory_type, content[:30])

            if existing:
                # Check if content is different -- update
                existing_content = existing.get("page_content", "")
                if existing_content.lower() != content.lower():
                    update_memory(
                        existing["id"],
                        page_content=content,
                        importance=importance,
                    )
                    updated_count += 1
                    logger.info(f"  Updated memory: [{memory_type}] '{existing_content}' -> '{content}'")
                else:
                    skipped_count += 1
            else:
                # New memory — add it
                add_memory(
                    user_id=user_id,
                    memory_type=memory_type,
                    content=content,
                    importance=importance,
                )
                new_count += 1

    total_count = get_memory_count(user_id)
    logger.info(
        f"Bootstrapping complete for {user_id}: "
        f"{new_count} new, {updated_count} updated, {skipped_count} skipped, "
        f"{total_count} total memories"
    )

    return {
        "new_count": new_count,
        "updated_count": updated_count,
        "skipped_count": skipped_count,
        "total_turns": len(turns),
    }