# -*- coding: utf-8 -*-
"""
verify_fixes.py - Run verification tests for all implemented fixes.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

all_passed = True

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def check(label, condition, detail=""):
    global all_passed
    status = "PASS" if condition else "FAIL"
    if not condition:
        all_passed = False
    suffix = f" | {detail}" if detail else ""
    print(f"  {status} | {label}{suffix}")

# =====================================================================
# TEST 1: Memory Extraction
# =====================================================================
section("TEST 1: Memory Extraction")
from memory.memory_extractor import extract_pattern_based

cases = [
    ("I like AIML",          "branch_interest",    True),
    ("I am interested in AIML", "branch_interest", True),
    ("I prefer CSE",         "branch_interest",    True),
    ("I like English",       "language_preference",True),
    ("I speak Telugu",       "language_preference",True),
    ("My name is Priya",     "name",               True),
    ("Answer me in Hindi",   "response_style",     True),
    ("I like the placements","branch_interest",    False),  # must NOT be branch
    ("I like the college",   "branch_interest",    False),  # must NOT be branch
]
for text, mtype, should_have in cases:
    mems = extract_pattern_based(text)
    types = [m["memory_type"] for m in mems]
    has = mtype in types
    ok = has if should_have else not has
    check(repr(text)[:45], ok, f"types={types}")

# =====================================================================
# TEST 2: Personal Query Detection
# =====================================================================
section("TEST 2: Personal Query Detection (Memory Retrieval)")
from prompts import is_personal_query

pq_cases = [
    ("Which branch do I like?",    True),
    ("What is my name?",           True),
    ("What language do I prefer?", True),
    ("Do you remember me?",        True),
    ("Tell me about myself",       True),
    ("What is the admission process?", False),
    ("Tell me about CSE fees",     False),
    ("What are the placements?",   False),
]
for text, expected in pq_cases:
    result = is_personal_query(text)
    check(repr(text)[:48], result == expected, f"expected={expected} got={result}")

# =====================================================================
# TEST 3: Function Calling Validation
# =====================================================================
section("TEST 3: Function Calling Validation")
from tools import fee_calculator, percentage_calculator, date_checker

r = percentage_calculator(marks=-10, total=100)
check("Negative marks rejected", bool(r.get("error")), r.get("error","")[:50])

r = percentage_calculator(marks=0, total=0)
check("Zero total rejected",     bool(r.get("error")), r.get("error","")[:50])

r = percentage_calculator(marks=150, total=100)
check("Marks > total rejected",  bool(r.get("error")), r.get("error","")[:50])

r = percentage_calculator(marks=450, total=600)
check("Valid calc 75%",          r.get("percentage") == 75.0, f"pct={r.get('percentage')}")

r = fee_calculator(branch="cse civil", category="general")
check("Contradictory branch rejected", bool(r.get("error")), r.get("error","")[:50])

# =====================================================================
# TEST 4: Date Tool Auto-Invoke + Days Remaining
# =====================================================================
section("TEST 4: Date Tool Auto-Invoke + Days Remaining")
from tool_rag import ToolRouter
router = ToolRouter()

date_trigger_queries = [
    "How many days remain until admission deadline?",
    "Has the admission deadline passed?",
    "Days left for counseling?",
    "Is admission still open?",
    "How much time is left for the deadline?",
]
for q in date_trigger_queries:
    route = router.route(q)
    check(q[:52], route == "date_checker", f"route={route}")

# Date checker computes days
r = date_checker(event_name="admission", compute_days=True)
ans = r.get("answer", "")
has_days = ("Days Remaining" in ans or "has passed" in ans or "TODAY" in ans)
check("date_checker computes remaining days", has_days, f"days_until={r.get('days_until_deadline')}")

# =====================================================================
# TEST 5: Coreference Resolution Patterns
# =====================================================================
section("TEST 5: Coreference Resolution (pattern detection)")
import re
ref_pattern = re.compile(
    r"\b(it|its|that|this|those|these|"
    r"the (?:first|second|third|last|previous|above|mentioned|said|same)|"
    r"tell me more|compare (?:it|them|both)|which one|"
    r"the one you mentioned|previous one|first one|second one|"
    r"what about it|more about it|what about that)\b",
    re.I,
)
coref_cases = [
    ("tell me more about it",        True),
    ("what is its fee",              True),
    ("the first one",                True),
    ("compare it with the previous one", True),
    ("What is the CSE fee?",         False),
    ("Tell me about admissions",     False),
]
for text, should_trigger in coref_cases:
    triggered = bool(ref_pattern.search(text))
    check(repr(text)[:48], triggered == should_trigger, f"triggered={triggered}")

# =====================================================================
# TEST 6: Evaluation Page Structure
# =====================================================================
section("TEST 6: Evaluation Page (structure + encoding)")
import ast

with open("pages/2_Evaluation.py", "r", encoding="utf-8") as f:
    src = f.read()

ast.parse(src)
check("Evaluation page parses without syntax errors", True)

required_fns = [
    "_run_ragas", "_dim_functional", "_dim_quality", "_dim_safety",
    "_dim_security", "_dim_robustness", "_dim_performance", "_dim_context",
    "_dim_ragas_summary", "run_complete_evaluation", "_render_combined_report",
    "main",
]
for fn in required_fns:
    check(f"  Function {fn} exists", f"def {fn}" in src)

# No non-ASCII in non-comment lines
lines = src.splitlines()
bad_runtime_lines = []
for i, line in enumerate(lines, 1):
    if line.strip().startswith("#"):
        continue
    for c in line:
        try:
            c.encode("cp1252")
        except UnicodeEncodeError:
            bad_runtime_lines.append(i)
            break
check("No non-ASCII in runtime code (charmap safe)", len(bad_runtime_lines) == 0,
      f"bad lines: {bad_runtime_lines}" if bad_runtime_lines else "")

# =====================================================================
# SUMMARY
# =====================================================================
print(f"\n{'='*60}")
if all_passed:
    print("  ALL TESTS PASSED")
else:
    print("  SOME TESTS FAILED - see above")
print('='*60)
sys.exit(0 if all_passed else 1)
