"""
memory_extractor.py -- Extract meaningful user facts from conversation turns.

Correctly classifies:
  - "I like AIML" / "I am interested in AIML"  -> branch_interest
  - "I like English" / "I speak Telugu"          -> language_preference
  - "My name is Priya"                           -> name
  - "Answer me in Telugu"                        -> response_style

Classification rules (strictly enforced):
  Branch keywords (CSE, ECE, EEE, IT, AIML, DS, etc.)  -> branch_interest
  Language keywords (English, Telugu, Hindi, etc.)       -> language_preference
  Otherwise                                              -> preference (generic)
"""

import json
import os
import re
from typing import Dict, Any, List

from dotenv import load_dotenv

import config
from utils import logger

load_dotenv()

# ---------------------------------------------------------------------------
# Known keyword sets
# ---------------------------------------------------------------------------

# Canonical branch keywords — all lowercase
BRANCH_KEYWORDS = {
    "cse", "ece", "eee", "it", "aiml", "ai", "ml", "ds",
    "computer science", "electronics", "electrical", "mechanical",
    "civil", "data science", "artificial intelligence", "machine learning",
    "information technology", "ai and ml", "ai&ml", "ai ml",
    "computer science engineering", "electronics and communication",
    "electrical and electronics",
}

# Canonical language keywords — all lowercase
LANGUAGE_KEYWORDS = {
    "english", "telugu", "hindi", "tamil", "kannada", "malayalam",
    "marathi", "bengali", "urdu", "odia",
}


def _is_branch(text: str) -> bool:
    """Return True if `text` refers to an engineering branch/department."""
    t = text.lower().strip()
    # Exact match
    if t in BRANCH_KEYWORDS:
        return True
    # Substring match (handles "AIML department", "CSE branch", etc.)
    for b in BRANCH_KEYWORDS:
        if b in t:
            return True
    return False


def _is_language(text: str) -> bool:
    """Return True if `text` refers to a spoken/written language."""
    t = text.lower().strip()
    if t in LANGUAGE_KEYWORDS:
        return True
    for lang in LANGUAGE_KEYWORDS:
        if lang in t:
            return True
    return False


def _normalize_branch(text: str) -> str:
    """Return standardized branch name."""
    t = text.strip()
    upper = t.upper()
    if upper in {"CSE", "ECE", "EEE", "IT", "AIML", "AI", "ML", "DS", "AI&ML"}:
        return upper
    # Strip trailing qualifiers ("branch", "department", etc.)
    for suffix in [" branch", " department", " stream", " engineering", " course"]:
        if t.lower().endswith(suffix):
            t = t[: -len(suffix)].strip()
    return t.title()


# ---------------------------------------------------------------------------
# Named pattern table
# (memory_type, compiled_regex, capture_group, importance)
# More specific patterns listed first so they match before the ambiguous ones.
# ---------------------------------------------------------------------------

_PATTERNS = [
    # Name
    ("name", re.compile(r"my name is ([A-Za-z]+(?:\s+[A-Za-z]+)?)", re.I), 1, 0.95),
    ("name", re.compile(r"call me ([A-Za-z]+)", re.I), 1, 0.90),
    ("name", re.compile(r"i am ([A-Za-z]+),? a student", re.I), 1, 0.85),

    # Branch interest -- explicit qualifiers (run before the ambiguous patterns)
    (
        "branch_interest",
        re.compile(
            r"(?:my (?:favourite|favorite|preferred) branch is"
            r"|i (?:want to|plan to|wish to|would like to) (?:join|study|take|pursue))"
            r" ([A-Za-z0-9&\s]+)",
            re.I,
        ),
        1, 0.92,
    ),
    (
        "branch_interest",
        re.compile(
            r"i (?:am )?interested in ([A-Za-z0-9&\s]+?)"
            r" (?:branch|department|stream|engineering|course)",
            re.I,
        ),
        1, 0.90,
    ),

    # Year / semester
    ("year", re.compile(r"i am (?:in |a )?(\w+)[\s-]?year", re.I), 1, 0.85),
    ("year", re.compile(r"i am (?:a )?(\w+)[\s-]?year student", re.I), 1, 0.85),

    # Goal
    ("goal", re.compile(r"i want to become (?:a |an )?([A-Za-z\s]+)", re.I), 1, 0.80),
    (
        "goal",
        re.compile(r"my (?:goal|aim|dream) is (?:to become )?(?:a |an )?([A-Za-z\s]+)", re.I),
        1, 0.80,
    ),

    # Location
    ("location", re.compile(r"i am from ([A-Za-z\s]+)", re.I), 1, 0.75),
    ("location", re.compile(r"i (?:live|stay|reside) in ([A-Za-z\s]+)", re.I), 1, 0.72),

    # Known skill
    ("known_skill", re.compile(r"i (?:already )?know ([A-Za-z0-9\+\#\s]+)", re.I), 1, 0.78),
    (
        "known_skill",
        re.compile(r"i (?:have|had) (?:experience|expertise) (?:in|with) ([A-Za-z0-9\s]+)", re.I),
        1, 0.78,
    ),
]

# ---------------------------------------------------------------------------
# Ambiguous "I like / I prefer / I am interested in" patterns
# These require disambiguation: branch vs language vs generic preference.
# ---------------------------------------------------------------------------

_AMBIGUOUS_PATTERNS = [
    re.compile(r"i (?:like|love|enjoy|prefer) ([A-Za-z0-9&\s]+)", re.I),
    re.compile(r"i am interested in ([A-Za-z0-9&\s]+)", re.I),
    re.compile(
        r"my (?:favourite|favorite|preferred) (?:language|subject|topic|field|area|stream) is"
        r" ([A-Za-z0-9&\s]+)",
        re.I,
    ),
    re.compile(r"i (?:chose|choose|selected|opted for|opting for) ([A-Za-z0-9&\s]+)", re.I),
]

# Explicit language patterns: "I speak / communicate in ..."
_LANG_EXPLICIT = re.compile(
    r"i (?:speak|communicate in|prefer to (?:speak|talk|write) in) ([A-Za-z]+)", re.I
)

# Response style: "Answer me in Telugu"
_RESPONSE_STYLE = re.compile(
    r"(?:please |kindly )?(?:answer|respond|reply|explain|write)"
    r" (?:me )?(?:in|using) ([A-Za-z]+)(?: language)?",
    re.I,
)

# Trailing filler words to strip from captured groups
_FILLER = re.compile(
    r"\s*(very much|a lot|really|quite|so much|too|as well|also|further|more|most)$", re.I
)

# Words that are clearly NOT a branch or language preference (prevent false captures)
_IGNORE_WORDS = {
    "college", "bvrit", "campus", "placement", "job", "company",
    "course", "fee", "seat", "hostel", "library", "food",
}


def _classify_like_statement(captured: str) -> Dict[str, Any]:
    """
    Disambiguate an "I like/prefer/am-interested-in X" statement.

    Returns a memory dict:
      - Branch keyword  -> {"memory_type": "branch_interest",    ...}
      - Language keyword -> {"memory_type": "language_preference", ...}
      - Otherwise        -> {"memory_type": "preference",          ...}

    Examples:
      "I like AIML"              -> branch_interest: AIML
      "I am interested in CSE"   -> branch_interest: CSE
      "I like English"           -> language_preference: English
      "I prefer Telugu"          -> language_preference: Telugu
    """
    text = captured.strip()
    text_lower = text.lower()

    # Skip clearly irrelevant captures
    if text_lower in _IGNORE_WORDS or len(text_lower) < 2:
        return {}

    if _is_branch(text_lower):
        return {
            "memory_type": "branch_interest",
            "content": _normalize_branch(text),
            "importance": 0.90,
        }
    if _is_language(text_lower):
        return {
            "memory_type": "language_preference",
            "content": text.title(),
            "importance": 0.82,
        }
    # Generic preference — store only if the text seems meaningful (> 3 chars, not a stop-word)
    if len(text_lower) > 3:
        return {
            "memory_type": "preference",
            "content": text.title(),
            "importance": 0.70,
        }
    return {}


# ---------------------------------------------------------------------------
# Public: pattern-based extraction (fast, no LLM cost)
# ---------------------------------------------------------------------------

def extract_pattern_based(user_input: str) -> List[Dict[str, Any]]:
    """
    Fast, rule-based memory extraction. No LLM cost.
    Returns list of {memory_type, content, importance}.

    Guarantees:
    - "I like AIML"                     -> branch_interest: AIML
    - "I am interested in CSE"          -> branch_interest: CSE
    - "I am interested in CSE branch"   -> branch_interest: CSE
    - "I like English"                  -> language_preference: English
    - "I speak Telugu"                  -> language_preference: Telugu
    - "Answer me in Hindi"              -> response_style: Respond in Hindi
    - "My name is Priya"                -> name: Priya
    """
    results: List[Dict[str, Any]] = []
    seen_types: set = set()

    def _add(mem_type: str, content: str, importance: float) -> None:
        content = content.strip()
        if not content or len(content) < 2:
            return
        if mem_type not in seen_types:
            results.append({"memory_type": mem_type, "content": content, "importance": importance})
            seen_types.add(mem_type)

    # --- Pass 1: Named patterns (specific — run first) ---
    for mem_type, pattern, grp, importance in _PATTERNS:
        m = pattern.search(user_input)
        if m:
            captured = _FILLER.sub("", m.group(grp).strip())
            if not captured or len(captured) < 2:
                continue
            if mem_type == "branch_interest":
                # Accept only if the captured text is actually a branch keyword
                if _is_branch(captured.lower()):
                    _add(mem_type, _normalize_branch(captured), importance)
                # else: captured text is not a branch — skip, don't pollute
                continue
            _add(mem_type, captured.strip().title(), importance)

    # --- Pass 2: Explicit language ("I speak Telugu") ---
    m = _LANG_EXPLICIT.search(user_input)
    if m:
        lang = m.group(1).strip().title()
        if _is_language(lang.lower()):
            _add("language_preference", lang, 0.85)

    # --- Pass 3: Response style ("Answer me in Telugu") ---
    m = _RESPONSE_STYLE.search(user_input)
    if m:
        lang = m.group(1).strip().title()
        if _is_language(lang.lower()):
            _add("response_style", f"Respond in {lang}", 0.78)

    # --- Pass 4: Ambiguous "I like / I prefer / I am interested in" ---
    for pattern in _AMBIGUOUS_PATTERNS:
        m = pattern.search(user_input)
        if m:
            captured = _FILLER.sub("", m.group(1).strip())
            if len(captured) < 2:
                continue
            mem = _classify_like_statement(captured)
            if mem and mem.get("memory_type"):
                _add(mem["memory_type"], mem["content"], mem["importance"])

    return results


# ---------------------------------------------------------------------------
# Optional: LLM-based extraction (richer, costs one API call)
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """You are a memory extraction assistant for a college FAQ chatbot.
Extract ONLY long-term, reusable facts about the user from their message.

Classification rules (IMPORTANT):
- "I like/prefer/am interested in CSE/ECE/AIML/IT/etc." -> memory_type: "branch_interest"
- "I like/speak/prefer English/Telugu/Hindi/etc."        -> memory_type: "language_preference"
- "My name is X"                                          -> memory_type: "name"
- "I am in first/second year"                            -> memory_type: "year"
- "I want to become a X"                                 -> memory_type: "goal"
- "I am from X"                                          -> memory_type: "location"
- "I already know Python/Java/etc."                      -> memory_type: "known_skill"
- "Answer me in X language"                              -> memory_type: "response_style"

Known engineering branches: CSE, ECE, EEE, IT, AIML, DS, Mechanical, Civil, Data Science, AI&ML.
Known languages: English, Telugu, Hindi, Tamil, Kannada, Malayalam, etc.

Rules:
1. Extract ONLY factual, persistent user attributes -- NOT questions or opinions about the college.
2. Do NOT extract "I like the placements" or "I like the college" -- those are opinions, not user attributes.
3. Return a JSON array of {memory_type, content, importance (0.0-1.0)}.
4. Return [] if nothing useful is found.
5. Return ONLY valid JSON, no extra text."""


def extract_llm_based(user_input: str, assistant_response: str) -> List[Dict[str, Any]]:
    """LLM-based extraction. Falls back gracefully if API fails."""
    try:
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return []
        llm = ChatOpenAI(
            model=config.LLM_MODEL,
            temperature=0.0,
            max_tokens=512,
            openai_api_key=api_key,
            openai_api_base=config.OPENROUTER_BASE_URL,
            streaming=False,
        )
        messages = [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"User said: {user_input}"},
        ]
        response = llm.invoke(messages)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        extracted = json.loads(raw)
        if isinstance(extracted, list):
            return extracted
        return []
    except Exception as e:
        logger.debug(f"LLM extraction skipped: {e}")
        return []


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_memories(
    user_input: str,
    assistant_response: str,
    use_llm: bool = False,
) -> List[Dict[str, Any]]:
    """
    Extract memories from a conversation turn.
    Pattern extraction always runs. LLM extraction is optional.
    """
    memories = extract_pattern_based(user_input)

    if use_llm:
        llm_mems = extract_llm_based(user_input, assistant_response)
        existing_types = {m["memory_type"] for m in memories}
        for mem in llm_mems:
            if mem.get("memory_type") and mem["memory_type"] not in existing_types:
                memories.append(mem)
                existing_types.add(mem["memory_type"])

    if memories:
        logger.info(f"Extracted {len(memories)} memories:")
        for m in memories:
            logger.info(f"  [{m['memory_type']}] {m['content']} (imp={m['importance']})")
    return memories
