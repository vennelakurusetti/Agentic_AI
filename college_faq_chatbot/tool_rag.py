"""
tool_rag.py -- Tool-augmented RAG router.

Routes user queries to:
  1. fee_calculator       -- fee/cost questions
  2. date_checker         -- deadline/date/days-remaining questions
  3. percentage_calculator -- marks/eligibility questions
  4. multi_tool           -- queries needing two or more tools
  5. rag                  -- all other college queries (pure RAG pipeline)

Context-aware branch resolution (priority order):
  1. Explicit branch in current query
  2. Branch from coreference-resolved query (e.g., "its fee" -> "CSE fee")
  3. Branch from recent conversation history
  4. Branch from stored user memory
  5. Fall back to generic if none found

Entry point:
    from tool_rag import ToolRouter
    router = ToolRouter()
    result = router.execute_with_tools(query, chat_history, top_k, memory_context)
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from tools import (
    fee_calculator,
    date_checker,
    percentage_calculator,
    sanitize_input,
    normalize_branch,
    normalize_event,
    TOOL_DESCRIPTIONS,
    BRANCH_ALIASES,
)
from utils import logger

load_dotenv()

# ---------------------------------------------------------------------------
# ROUTING PATTERNS
# ---------------------------------------------------------------------------

_FEE_PATTERNS = re.compile(
    r"\b(fee|fees|fee\s*structure|tuition|annual\s*fees?"
    r"|total\s*fees?|semester\s*fees?|hostel\s*fees?|college\s*fees?"
    r"|how\s*much\s*(?:is\s+the|are\s+the|does\s+it|do\s+i|will\s+i\s+pay)\b"
    r"|cost\s+of\s+(?:studying|joining|admission|btech|engineering))\b",
    re.IGNORECASE,
)

_DATE_PATTERNS = re.compile(
    r"\b("
    r"deadline|last\s*date|due\s*date|when\s*is|when\s*does|date\s*of"
    r"|admission\s*open|application\s*date|exam\s*date|schedule|calendar"
    r"|important\s*dates?|when\s*to\s*apply|closing\s*date"
    r"|days?\s*(?:left|remaining|until|till|before|to go)"
    r"|how\s*many\s*days"
    r"|time\s*(?:left|remaining|until|till|to go)"
    r"|how\s*much\s*time\s*(?:is\s*left|remains?|remaining|until|till)"
    r"|has\s+(?:the\s+)?(?:admission|application|deadline|counseling|counselling|eamcet|exam)\s+(?:deadline\s+)?(?:passed|closed|expired|ended|over)"
    r"|is\s+(?:the\s+)?(?:admission|application|counseling|counselling)\s+(?:still\s+)?(?:open|available|active)"
    r"|(?:admission|application|deadline|counseling|counselling)\s+(?:status|update)"
    r")\b",
    re.IGNORECASE,
)

_PERCENT_PATTERNS = re.compile(
    r"\b(percentage|percent|per\s*cent|marks\s*out\s*of|score\s*of"
    r"|calculate\s*(my\s*)?percentage|what\s*is\s*my\s*percentage"
    r"|am\s*i\s*eligible|eligib|(\d+)\s*out\s*of\s*(\d+))\b",
    re.IGNORECASE,
)

_MARKS_EXTRACT = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:out\s*of|/)\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

# Matches any known branch keyword in a string
_BRANCH_EXTRACT = re.compile(
    r"\b(cse|ece|eee|it\b|aiml|ai\s*(?:and|&|\+)?\s*ml?|"
    r"computer\s*science|electronics(?:\s+and\s+communication)?|"
    r"electrical(?:\s+and\s+electronics)?|information\s*technology|"
    r"mechanical(?:\s+engineering)?|civil(?:\s+engineering)?|"
    r"data\s*science|artificial\s*intelligence|machine\s*learning)\b",
    re.IGNORECASE,
)

_CATEGORY_EXTRACT = re.compile(
    r"\b(management|management\s*quota|general|open|nri|sc|st|obc|lateral)\b",
    re.IGNORECASE,
)

# "my branch" / "my department" pattern -- signals memory lookup
_MY_BRANCH_PATTERN = re.compile(
    r"\b(my\s+(?:branch|department|stream|course|program|interest)|"
    r"for\s+me|for\s+my\s+(?:branch|course)|about\s+my\s+branch)\b",
    re.I,
)

# Ordinal references: "the first one", "second one", etc.
_ORDINAL_PATTERN = re.compile(
    r"\b(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+"
    r"(?:one|branch|department|program|course)?\b",
    re.I,
)

# Known UG program order at BVRIT (as typically listed)
_UG_PROGRAM_ORDER = ["eee", "ece", "cse", "it", "aiml", "ds", "mech", "civil"]


# ---------------------------------------------------------------------------
# CONTEXT-AWARE BRANCH RESOLUTION
# ---------------------------------------------------------------------------

def _extract_branch_from_text(text: str) -> Optional[str]:
    """Extract a branch key from any text string. Returns normalised key or None."""
    m = _BRANCH_EXTRACT.search(text)
    if m:
        return normalize_branch(m.group(1))
    return None


def _extract_branch_from_memory(memory_context: str) -> Optional[str]:
    """
    Pull branch preference from the memory context string.
    Looks for lines like "[HIGH] Branch Interest: AIML" or "Branch Interest: CSE".
    """
    if not memory_context:
        return None
    # Pattern: "Branch Interest: <value>" (case-insensitive key)
    m = re.search(r"branch\s+interest\s*:\s*([A-Za-z0-9&\s]+)", memory_context, re.I)
    if m:
        branch_text = m.group(1).strip()
        key = normalize_branch(branch_text)
        if key != "default":
            return key
    return None


def _extract_branch_from_history(chat_history: List[Dict[str, str]]) -> Optional[str]:
    """
    Scan the most recent conversation turns for a branch mention.
    Looks at the last 6 messages (3 turns), most recent first.
    """
    if not chat_history:
        return None
    for msg in reversed(chat_history[-6:]):
        content = msg.get("content", "")
        if not content:
            continue
        branch = _extract_branch_from_text(content)
        if branch and branch != "default":
            return branch
    return None


def _resolve_ordinal_branch(question: str, chat_history: List[Dict[str, str]]) -> Optional[str]:
    """
    Resolve "first one", "second one" etc. against the last assistant answer
    that listed multiple programs/branches.

    Strategy: look for ordinal in question, then find the ordered list
    in recent assistant messages and pick the Nth item.
    """
    m = _ORDINAL_PATTERN.search(question)
    if not m:
        return None

    ordinal_word = m.group(1).lower()
    ordinal_map = {
        "first": 0, "1st": 0,
        "second": 1, "2nd": 1,
        "third": 2, "3rd": 2,
        "fourth": 3, "4th": 3,
        "fifth": 4, "5th": 4,
    }
    idx = ordinal_map.get(ordinal_word, 0)

    # Search recent assistant messages for branch mentions in order
    for msg in reversed(chat_history[-6:]):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        # Find all branch matches in order of appearance
        matches = _BRANCH_EXTRACT.findall(content)
        if len(matches) > idx:
            return normalize_branch(matches[idx])

    # Fallback: use canonical UG program order
    if idx < len(_UG_PROGRAM_ORDER):
        return _UG_PROGRAM_ORDER[idx]

    return None


def resolve_branch_for_fee(
    query: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    memory_context: str = "",
) -> str:
    """
    Resolve the branch to use for fee_calculator using priority order:
      1. Explicit branch in current query
      2. Ordinal reference ("the first one") resolved against history
      3. Branch from recent conversation history
      4. Branch from stored user memory
      5. Return "general" if none found

    This ensures "What is the fee?" after "Tell me about CSE" returns CSE fee.
    """
    history = chat_history or []

    # Priority 1: explicit branch in current query
    branch = _extract_branch_from_text(query)
    if branch and branch != "default":
        logger.info(f"Branch resolved from query: {branch}")
        return branch

    # Priority 2: ordinal reference
    branch = _resolve_ordinal_branch(query, history)
    if branch and branch != "default":
        logger.info(f"Branch resolved from ordinal: {branch}")
        return branch

    # Priority 3: branch from conversation history
    branch = _extract_branch_from_history(history)
    if branch and branch != "default":
        logger.info(f"Branch resolved from history: {branch}")
        return branch

    # Priority 4: branch from stored memory
    branch = _extract_branch_from_memory(memory_context)
    if branch and branch != "default":
        logger.info(f"Branch resolved from memory: {branch}")
        return branch

    logger.info("Branch not resolved, using general")
    return "general"


# ---------------------------------------------------------------------------
# TOOL ROUTER CLASS
# ---------------------------------------------------------------------------

class ToolRouter:
    """
    Routes user queries to the appropriate tool or RAG pipeline.

    Result dict always has:
        answer          -- The final response string
        citations       -- List of section/source names
        tool_used       -- Tool name or "rag" or "multi_tool"
        chunks_retrieved -- Number of RAG chunks (0 for pure tool calls)
    """

    def route(self, query: str) -> str:
        has_fee = bool(_FEE_PATTERNS.search(query))
        has_date = bool(_DATE_PATTERNS.search(query))
        has_percent = bool(_PERCENT_PATTERNS.search(query))

        tool_count = sum([has_fee, has_date, has_percent])

        if tool_count >= 2:
            return "multi_tool"
        if has_percent:
            return "percentage_calculator"
        if has_fee:
            return "fee_calculator"
        if has_date:
            return "date_checker"
        return "rag"

    # -- Parameter extraction -------------------------------------------

    def _extract_fee_params(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        memory_context: str = "",
    ) -> Tuple[str, str]:
        """
        Extract branch and category for fee_calculator.
        Uses full context-aware resolution for branch (not just current query).
        """
        branch = resolve_branch_for_fee(query, chat_history, memory_context)

        category = "general"
        cat_match = _CATEGORY_EXTRACT.search(query)
        if cat_match:
            category = cat_match.group(1)

        return branch, category

    def _extract_date_params(self, query: str) -> str:
        lower = query.lower()
        if "eamcet" in lower or "eapcet" in lower:
            return "eamcet"
        if "hostel" in lower or "accommodation" in lower:
            return "hostel"
        if "internship" in lower:
            return "internship"
        if "placement" in lower:
            return "placement"
        if "academic" in lower or "semester" in lower or "exam" in lower or "exams" in lower:
            return "academic calendar"
        if "fee" in lower and ("payment" in lower or "pay" in lower):
            return "fees"
        if "counseling" in lower or "counselling" in lower:
            return "counseling"
        return "admission"

    def _extract_percent_params(self, query: str) -> Tuple[Optional[float], Optional[float], str]:
        marks = None
        total = None
        category = "general"

        marks_match = _MARKS_EXTRACT.search(query)
        if marks_match:
            marks = float(marks_match.group(1))
            total = float(marks_match.group(2))

        cat_match = _CATEGORY_EXTRACT.search(query)
        if cat_match:
            category = cat_match.group(1)

        return marks, total, category

    # -- Tool executors -------------------------------------------------

    def _run_fee_calculator(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        memory_context: str = "",
    ) -> Dict[str, Any]:
        branch, category = self._extract_fee_params(query, chat_history, memory_context)
        logger.info(f"ToolRouter: fee_calculator(branch={branch!r}, category={category!r})")
        return fee_calculator(branch=branch, category=category)

    def _run_date_checker(self, query: str) -> Dict[str, Any]:
        event = self._extract_date_params(query)
        logger.info(f"ToolRouter: date_checker(event={event!r})")
        return date_checker(event_name=event, compute_days=True)

    def _run_percentage_calculator(self, query: str) -> Dict[str, Any]:
        marks, total, category = self._extract_percent_params(query)
        if marks is None or total is None:
            return {
                "tool_name": "percentage_calculator",
                "answer": (
                    "To calculate your percentage, please provide your marks in the format: "
                    "**'X out of Y'** (e.g., '450 out of 600')."
                ),
                "citations": [],
            }
        logger.info(f"ToolRouter: percentage_calculator(marks={marks}, total={total})")
        return percentage_calculator(marks=marks, total=total, category=category)

    def _run_multi_tool(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        memory_context: str = "",
    ) -> Dict[str, Any]:
        answers = []
        all_citations = []

        if _FEE_PATTERNS.search(query):
            fee_result = self._run_fee_calculator(query, chat_history, memory_context)
            if not fee_result.get("error"):
                answers.append(fee_result["answer"])
                all_citations.extend(fee_result.get("citations", []))

        if _DATE_PATTERNS.search(query):
            date_result = self._run_date_checker(query)
            if not date_result.get("error"):
                answers.append(date_result["answer"])
                all_citations.extend(date_result.get("citations", []))

        if _PERCENT_PATTERNS.search(query):
            pct_result = self._run_percentage_calculator(query)
            if not pct_result.get("error"):
                answers.append(pct_result["answer"])
                all_citations.extend(pct_result.get("citations", []))

        combined = "\n\n---\n\n".join(answers) if answers else (
            "I could not find the requested information. "
            "Please try asking more specific questions."
        )

        return {
            "tool_name": "multi_tool",
            "answer": combined,
            "citations": list(dict.fromkeys(all_citations)),
        }

    # -- RAG fallback --------------------------------------------------

    def _run_rag(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 8,
        memory_context: str = "",
    ) -> Dict[str, Any]:
        from rag import answer_question
        result = answer_question(
            question=query,
            chat_history=chat_history or [],
            top_k=top_k,
            memory_context=memory_context,
        )
        result["tool_used"] = "rag"
        return result

    # -- Main entry point ----------------------------------------------

    def execute_with_tools(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        top_k: int = 8,
        memory_context: str = "",
        force_rag: bool = False,
    ) -> Dict[str, Any]:
        """
        Main entry point: route query, execute tool or RAG, return unified result.

        Pre-routing: resolve coreferences in the query using conversation history
        so that "its fee", "the first one", etc. are expanded before routing and
        parameter extraction.

        Always returns a dict with:
          - answer:            str
          - citations:         list[str]
          - tool_used:         str
          - chunks_retrieved:  int
        """
        if force_rag:
            return self._run_rag(query, chat_history, top_k, memory_context)

        # Sanitize before routing
        try:
            safe_query = sanitize_input(query, "query")
        except ValueError:
            return {
                "answer": (
                    "I'm sorry, but I cannot process that input. "
                    "Please ask a regular question about BVRIT Hyderabad."
                ),
                "citations": [],
                "tool_used": "blocked",
                "chunks_retrieved": 0,
            }

        # --- Pre-routing: coreference resolution ---
        # Rewrite the query BEFORE routing so that "What is its fee?"
        # becomes "What is the fee for CSE?" and gets correctly routed
        # and branch-extracted.
        resolved_query = _pre_resolve_query(safe_query, chat_history or [], memory_context)
        logger.info(
            f"ToolRouter: '{safe_query[:50]}' -> resolved: '{resolved_query[:50]}'"
            if resolved_query != safe_query else
            f"ToolRouter: query unchanged: '{safe_query[:50]}'"
        )

        route = self.route(resolved_query)
        logger.info(f"ToolRouter: routing '{resolved_query[:60]}' -> {route}")

        if route == "fee_calculator":
            result = self._run_fee_calculator(resolved_query, chat_history, memory_context)
        elif route == "date_checker":
            result = self._run_date_checker(resolved_query)
        elif route == "percentage_calculator":
            result = self._run_percentage_calculator(resolved_query)
        elif route == "multi_tool":
            result = self._run_multi_tool(resolved_query, chat_history, memory_context)
        else:
            # For RAG, pass the original query so the RAG pipeline can also rewrite it
            return self._run_rag(query, chat_history, top_k, memory_context)

        # If tool errored or returned nothing meaningful, fall back to RAG
        if result.get("error") or not result.get("answer"):
            logger.warning(f"Tool {route} failed or returned empty. Falling back to RAG.")
            return self._run_rag(query, chat_history, top_k, memory_context)

        result.setdefault("tool_used", route)
        result.setdefault("chunks_retrieved", 0)
        result.setdefault("citations", [])
        result.setdefault("chunks", [])
        return result


# ---------------------------------------------------------------------------
# PRE-ROUTING QUERY RESOLVER (rule-based, no LLM, instant)
# ---------------------------------------------------------------------------

# Pronouns / ordinals that indicate a coreference needing resolution
_NEEDS_RESOLVE = re.compile(
    r"\b(it|its|that|this|those|these|"
    r"the\s+(?:first|second|third|fourth|fifth|last|previous|above)|"
    r"(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s+one|"
    r"my\s+branch|for\s+me|about\s+my\s+(?:branch|course|department))\b",
    re.I,
)


def _pre_resolve_query(
    query: str,
    chat_history: List[Dict[str, str]],
    memory_context: str,
) -> str:
    """
    Rule-based pre-resolution of coreferences BEFORE routing.
    Handles the most common patterns without an LLM call.

    Cases handled:
      "What is its fee?"            -> "What is the fee for CSE?" (from history)
      "What is the fee for it?"     -> "What is the fee for CSE?"
      "What is the fee?"            -> "What is the fee for AIML?" (from memory)
      "What is the fee for the first one?" -> "What is the fee for EEE?" (ordinal)
      "What are its placements?"    -> "What are the placements for CSE?"
      "Tell me about my branch"     -> "Tell me about AIML" (from memory)
    """
    lower = query.lower()

    # --- Always resolve ordinal references first (no pronoun needed) ---
    ordinal_match = re.search(
        r"\b(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s*(?:one)?\b",
        lower,
    )
    if ordinal_match:
        branch = _resolve_ordinal_branch(query, chat_history)
        if branch and branch != "default":
            from tools import FEE_STRUCTURE
            branch_name = FEE_STRUCTURE.get(branch, {}).get("full_name", branch.upper())
            resolved = re.sub(
                r"\b(the\s+)?(first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\s*(?:one)?\b",
                branch_name,
                query,
                flags=re.I,
            )
            logger.info(f"Pre-resolve ordinal: '{query}' -> '{resolved}'")
            return resolved

    # --- Resolve "its", "it", "that" -> branch from history ---
    pronoun_match = re.search(r"\b(its|it|that|this)\b", lower)
    if pronoun_match:
        branch = _extract_branch_from_history(chat_history)
        if branch and branch != "default":
            from tools import FEE_STRUCTURE
            branch_name = FEE_STRUCTURE.get(branch, {}).get("full_name", branch.upper())
            resolved = re.sub(
                r"\b(its|it|that|this)\b",
                branch_name,
                query,
                count=1,
                flags=re.I,
            )
            logger.info(f"Pre-resolve pronoun: '{query}' -> '{resolved}'")
            return resolved

    # --- Resolve "my branch" / "for me" -> branch from memory ---
    if _MY_BRANCH_PATTERN.search(query):
        branch = _extract_branch_from_memory(memory_context)
        if branch and branch != "default":
            from tools import FEE_STRUCTURE
            branch_name = FEE_STRUCTURE.get(branch, {}).get("full_name", branch.upper())
            resolved = re.sub(
                r"\bmy\s+(?:branch|department|stream|course|program|interest)\b",
                branch_name,
                query,
                flags=re.I,
            )
            logger.info(f"Pre-resolve my-branch: '{query}' -> '{resolved}'")
            return resolved

    # --- Generic fee/placements query with NO explicit branch ---
    # Applies even without a pronoun: "What is the fee?" after "Tell me about CSE"
    # or "What is the fee?" when memory has AIML preference.
    has_fee_or_placement = bool(_FEE_PATTERNS.search(query)) or bool(
        re.search(r"\b(placement|placements|placed|package|salary|recruit)\b", query, re.I)
    )
    if has_fee_or_placement and not _BRANCH_EXTRACT.search(query):
        branch = (
            _extract_branch_from_history(chat_history)
            or _extract_branch_from_memory(memory_context)
        )
        if branch and branch != "default":
            from tools import FEE_STRUCTURE
            branch_name = FEE_STRUCTURE.get(branch, {}).get("full_name", branch.upper())
            resolved = query.rstrip("?. ") + f" for {branch_name}?"
            logger.info(f"Pre-resolve fee/placement+context: '{query}' -> '{resolved}'")
            return resolved

    return query
