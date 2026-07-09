"""
memory_extractor.py — Extract meaningful user facts from conversation turns.

Uses the LLM to detect statements like:
  "My name is Priya" → {memory_type: "name", content: "Priya"}
  "I am interested in CSE" → {memory_type: "interest", content: "CSE"}
  "I like English" → {memory_type: "language_preference", content: "English"}

Only long-term useful facts are stored. Temporary chat messages are ignored.
"""

import json
import os
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

import config
from utils import logger

load_dotenv()

# System prompt for the extraction LLM
EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction assistant. Your job is to extract **long-term useful facts** about a user from their conversation.

Look for statements like:
- "My name is ..." → memory_type: "name", content: the name
- "I am interested in ..." → memory_type: "interest", content: the interest
- "I prefer ..." → memory_type: "preference", content: the preference
- "I speak ..." / "I like ..." → memory_type: "language_preference", content: the language
- "I don't like ..." → memory_type: "dislike", content: the disliked thing
- "I am in first/second/third/fourth year" → memory_type: "year", content: the year
- "My favorite branch is ..." → memory_type: "branch_interest", content: the branch
- "I already know ..." → memory_type: "known_skill", content: the skill
- "I am from ..." → memory_type: "location", content: the place

Rules:
1. Extract ONLY statements that are factual and would be useful in future conversations.
2. Ignore greetings, thanks, goodbyes, and temporary chat messages.
3. Set importance (0.0 to 1.0) based on how useful the fact is for personalisation.
4. Return a JSON array of objects. Each object has: memory_type, content, importance.
5. If nothing meaningful is found, return an empty array [].
6. Do NOT include explanations or extra text — only valid JSON."""


def get_llm() -> ChatOpenAI:
    """Get a non-streaming ChatOpenAI for extraction."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in environment variables")
    model = os.getenv("LLM_MODEL", config.LLM_MODEL)
    return ChatOpenAI(
        model=model,
        temperature=0.0,
        max_tokens=512,
        openai_api_key=api_key,
        openai_api_base=config.OPENROUTER_BASE_URL,
        streaming=False,
    )


# ── Pattern-based extraction (fast path, no LLM call) ──────────

SIMPLE_PATTERNS = [
    # (memory_type, regex pattern, content_group_index, importance)
    ("name", r"my name is (\w+(?:\s+\w+)?)", 1, 0.95),
    ("interest", r"i am interested in (\w+(?:\s+\w+)?)", 1, 0.85),
    ("preference", r"i prefer (\w+(?:\s+\w+)?)", 1, 0.80),
    ("language_preference", r"i (?:speak|like) (\w+(?:\s+\w+)?)", 1, 0.75),
    ("dislike", r"i don't like (\w+(?:\s+\w+)?)", 1, 0.70),
    ("year", r"i am in (first|second|third|fourth|1st|2nd|3rd|4th)\s*(?:year)?", 1, 0.85),
    ("branch_interest", r"my favorite branch is (\w+(?:\s+\w+)?)", 1, 0.85),
    ("branch_interest", r"i (?:want|am going) to (?:join|take|study|pursue) (\w+(?:\s+\w+)?)", 1, 0.80),
    ("known_skill", r"i (?:already )?know (\w+(?:\s+\w+)?)", 1, 0.80),
    ("location", r"i am from (\w+(?:\s+\w+)?)", 1, 0.75),
    ("goal", r"i want to become (?:a |an )?(\w+(?:\s+\w+)?)", 1, 0.80),
]


def extract_pattern_based(user_input: str) -> List[Dict[str, Any]]:
    """
    Fast pattern-based extraction for common memory patterns.
    Returns a list of {memory_type, content, importance} dicts.
    """
    results = []
    lower = user_input.lower()
    for memory_type, pattern, group_idx, importance in SIMPLE_PATTERNS:
        import re
        match = re.search(pattern, lower)
        if match:
            content = match.group(group_idx).strip().title()
            results.append({
                "memory_type": memory_type,
                "content": content,
                "importance": importance,
            })
    return results


def extract_llm_based(user_input: str, assistant_response: str) -> List[Dict[str, Any]]:
    """
    LLM-based extraction for more complex or implicit facts.
    The assistant response is included for context.
    """
    llm = get_llm()
    user_content = f"User: {user_input}\nAssistant: {assistant_response}"
    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        response = llm.invoke(messages)
        raw = response.content.strip()
        # Remove markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        extracted = json.loads(raw)
        if isinstance(extracted, list):
            return extracted
        return []
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"LLM extraction failed: {e}")
        return []


def extract_memories(
    user_input: str,
    assistant_response: str,
    use_llm: bool = True,
) -> List[Dict[str, Any]]:
    """
    Extract memories from a conversation turn.

    1. Try pattern-based extraction first (fast, no API cost).
    2. If use_llm is True, also run LLM-based extraction.
    3. Merge results, deduplicate by memory_type.
    """
    memories = extract_pattern_based(user_input)

    if use_llm:
        llm_memories = extract_llm_based(user_input, assistant_response)
        # Merge: LLM results override or supplement pattern results
        existing_types = {m["memory_type"] for m in memories}
        for mem in llm_memories:
            if mem["memory_type"] not in existing_types:
                memories.append(mem)
                existing_types.add(mem["memory_type"])

    logger.info(f"Extracted {len(memories)} memories from turn")
    for m in memories:
        logger.info(f"  → [{m['memory_type']}] {m['content']} (importance={m['importance']})")
    return memories