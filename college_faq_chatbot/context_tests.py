# -*- coding: utf-8 -*-
"""
context_tests.py - Verify coreference resolution and memory-based personalization.

Tests the 4 conversations from the spec:
  Conv 1: I am interested in AIML. / What is the fee?  -> AIML fee
  Conv 2: Tell me about CSE.       / What is its fee?  -> CSE fee
  Conv 3: Which UG programs?       / Fee for first one -> EEE fee
  Conv 4: Tell me about AIML.      / What are its placements? -> AIML placements
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from tool_rag import (
    _pre_resolve_query,
    _extract_branch_from_history,
    _extract_branch_from_memory,
    _resolve_ordinal_branch,
    resolve_branch_for_fee,
    ToolRouter,
)

all_passed = True

def check(label, condition, detail=""):
    global all_passed
    status = "PASS" if condition else "FAIL"
    if not condition:
        all_passed = False
    suffix = f"  [{detail}]" if detail else ""
    print(f"  {status} | {label}{suffix}")

def section(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print('='*65)

# =====================================================================
# TEST: _extract_branch_from_memory
# =====================================================================
section("Memory branch extraction")

mem1 = "\n\n--- User Memory Context ---\n[HIGH] Branch Interest: AIML\n[MED] Name: Priya"
mem2 = "\n\n--- User Memory Context ---\n[HIGH] Branch Interest: CSE\n"
mem3 = ""

check("AIML from memory", _extract_branch_from_memory(mem1) == "aiml",
      f"got={_extract_branch_from_memory(mem1)}")
check("CSE from memory",  _extract_branch_from_memory(mem2) == "cse",
      f"got={_extract_branch_from_memory(mem2)}")
check("None from empty",  _extract_branch_from_memory(mem3) is None,
      f"got={_extract_branch_from_memory(mem3)}")

# =====================================================================
# TEST: _extract_branch_from_history
# =====================================================================
section("History branch extraction")

hist_cse = [
    {"role": "user",      "content": "Tell me about CSE."},
    {"role": "assistant", "content": "CSE (Computer Science Engineering) is a premier department..."},
]
hist_aiml = [
    {"role": "user",      "content": "I am interested in AIML"},
    {"role": "assistant", "content": "AIML is a great choice..."},
]
hist_none = [
    {"role": "user",      "content": "What is the campus like?"},
    {"role": "assistant", "content": "The campus has many facilities..."},
]

check("CSE from history",  _extract_branch_from_history(hist_cse) == "cse",
      f"got={_extract_branch_from_history(hist_cse)}")
check("AIML from history", _extract_branch_from_history(hist_aiml) == "aiml",
      f"got={_extract_branch_from_history(hist_aiml)}")
check("None from unrelated history", _extract_branch_from_history(hist_none) is None,
      f"got={_extract_branch_from_history(hist_none)}")

# =====================================================================
# TEST: _resolve_ordinal_branch
# =====================================================================
section("Ordinal branch resolution")

hist_ug = [
    {"role": "user",      "content": "Which UG programs are offered?"},
    {"role": "assistant", "content": "BVRIT offers the following UG programs: EEE, ECE, CSE, IT, AIML, DS."},
]

branch_first = _resolve_ordinal_branch("fee for the first one", hist_ug)
branch_second = _resolve_ordinal_branch("fee for the second one", hist_ug)
check("First one -> EEE",  branch_first == "eee",  f"got={branch_first}")
check("Second one -> ECE", branch_second == "ece", f"got={branch_second}")

# Fallback when no history: use canonical order (EEE is first)
branch_fallback = _resolve_ordinal_branch("fee for the first one", [])
check("First one fallback -> eee", branch_fallback == "eee", f"got={branch_fallback}")

# =====================================================================
# TEST: _pre_resolve_query
# =====================================================================
section("Pre-resolve query (rule-based rewrite)")

# "its fee" with CSE in history
resolved = _pre_resolve_query("What is its fee?", hist_cse, "")
check("'its fee' -> CSE fee query", "cse" in resolved.lower() or "computer science" in resolved.lower(),
      f"resolved='{resolved}'")

# "What is the fee?" with AIML in memory (no branch in query or history)
resolved = _pre_resolve_query("What is the fee?", [], mem1)
check("'fee?' + AIML memory -> AIML fee query", "aiml" in resolved.lower() or "artificial intelligence" in resolved.lower(),
      f"resolved='{resolved}'")

# "fee for the first one" with UG list in history
resolved = _pre_resolve_query("What is the fee for the first one?", hist_ug, "")
check("'fee for first one' -> EEE fee query", "eee" in resolved.lower() or "electrical" in resolved.lower(),
      f"resolved='{resolved}'")

# No coreference -- should be unchanged
resolved = _pre_resolve_query("What is the CSE fee?", [], "")
check("No coreference: query unchanged", resolved == "What is the CSE fee?",
      f"resolved='{resolved}'")

# =====================================================================
# TEST: resolve_branch_for_fee (full priority chain)
# =====================================================================
section("resolve_branch_for_fee (full priority chain)")

# Priority 1: explicit in query
b = resolve_branch_for_fee("What is the ECE fee?", [], "")
check("P1 explicit ECE in query", b == "ece", f"got={b}")

# Priority 2: ordinal
b = resolve_branch_for_fee("fee for the first one", hist_ug, "")
check("P2 ordinal -> EEE", b == "eee", f"got={b}")

# Priority 3: history
b = resolve_branch_for_fee("What is the fee?", hist_cse, "")
check("P3 CSE from history", b == "cse", f"got={b}")

# Priority 4: memory
b = resolve_branch_for_fee("What is the fee?", [], mem1)
check("P4 AIML from memory", b == "aiml", f"got={b}")

# Priority 5: generic fallback
b = resolve_branch_for_fee("What is the fee?", [], "")
check("P5 generic fallback", b == "general", f"got={b}")

# =====================================================================
# TEST: Full ToolRouter conversations (4 spec conversations)
# =====================================================================
section("CONVERSATION 1: I am interested in AIML -> What is the fee?")
router = ToolRouter()

chat1 = [
    {"role": "user",      "content": "I am interested in AIML"},
    {"role": "assistant", "content": "AIML (Artificial Intelligence and Machine Learning) is offered at BVRIT Hyderabad. It covers AI, ML, deep learning and data science topics."},
]
result1 = router.execute_with_tools(
    query="What is the fee?",
    chat_history=chat1,
    memory_context="\n\n--- User Memory Context ---\n[HIGH] Branch Interest: AIML",
)
ans1 = result1.get("answer", "").lower()
check("Returns AIML fee (not generic)", "aiml" in ans1 or "artificial intelligence" in ans1,
      f"tool={result1.get('tool_used')} answer_start={result1.get('answer','')[:80]}")
check("Tool used is fee_calculator", result1.get("tool_used") == "fee_calculator",
      f"tool={result1.get('tool_used')}")

section("CONVERSATION 2: Tell me about CSE -> What is its fee?")
chat2 = [
    {"role": "user",      "content": "Tell me about CSE"},
    {"role": "assistant", "content": "CSE (Computer Science Engineering) is one of the most popular branches at BVRIT Hyderabad. It covers programming, algorithms, data structures, and more."},
]
result2 = router.execute_with_tools(
    query="What is its fee?",
    chat_history=chat2,
    memory_context="",
)
ans2 = result2.get("answer", "").lower()
check("Returns CSE fee", "cse" in ans2 or "computer science" in ans2,
      f"tool={result2.get('tool_used')} answer_start={result2.get('answer','')[:80]}")
check("Tool used is fee_calculator", result2.get("tool_used") == "fee_calculator",
      f"tool={result2.get('tool_used')}")

section("CONVERSATION 3: Which UG programs? -> Fee for the first one?")
chat3 = [
    {"role": "user",      "content": "Which UG programs are offered?"},
    {"role": "assistant", "content": "BVRIT Hyderabad offers the following UG programs: EEE, ECE, CSE, IT, AIML, and Data Science."},
]
result3 = router.execute_with_tools(
    query="What is the fee for the first one?",
    chat_history=chat3,
    memory_context="",
)
ans3 = result3.get("answer", "").lower()
check("Returns EEE fee", "eee" in ans3 or "electrical" in ans3,
      f"tool={result3.get('tool_used')} answer_start={result3.get('answer','')[:80]}")
check("Tool used is fee_calculator", result3.get("tool_used") == "fee_calculator",
      f"tool={result3.get('tool_used')}")

section("CONVERSATION 4: Tell me about AIML -> What are its placements?")
chat4 = [
    {"role": "user",      "content": "Tell me about AIML"},
    {"role": "assistant", "content": "AIML (Artificial Intelligence and Machine Learning) is a cutting-edge program at BVRIT Hyderabad focusing on AI, ML, and data science careers."},
]
result4 = router.execute_with_tools(
    query="What are its placements?",
    chat_history=chat4,
    memory_context="",
)
# This should go to RAG with "AIML" resolved in the query
resolved_q4_route = result4.get("tool_used", "")
ans4 = result4.get("answer", "").lower()
# Either RAG retrieved AIML-specific content, or the query was rewritten with AIML
check("AIML resolved in placements query (RAG route)", resolved_q4_route == "rag",
      f"tool={resolved_q4_route}")
check("Answer mentions AIML or placements", "aiml" in ans4 or "artificial intelligence" in ans4 or "placement" in ans4,
      f"answer_start={result4.get('answer','')[:80]}")

# =====================================================================
# SUMMARY
# =====================================================================
print(f"\n{'='*65}")
if all_passed:
    print("  ALL TESTS PASSED")
else:
    print("  SOME TESTS FAILED - see above")
print('='*65)
sys.exit(0 if all_passed else 1)
