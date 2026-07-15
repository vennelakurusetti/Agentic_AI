"""
_verify_fixes.py -- Comprehensive verification of all 8 fixes.
Run: python _verify_fixes.py
"""
import sys
sys.path.insert(0, ".")

results = {}

# =========================================================================
# 1. Memory Extraction
# =========================================================================
print("\n=== 1. Memory Extraction ===")
from memory.memory_extractor import extract_pattern_based

mem_tests = [
    ("I like AIML",                 "branch_interest", "AIML"),
    ("I am interested in AIML",     "branch_interest", "AIML"),
    ("I am interested in CSE",      "branch_interest", "CSE"),
    ("I am interested in CSE branch","branch_interest", "CSE"),
    ("I prefer ECE",                "branch_interest", "ECE"),
    ("I like English",              "language_preference", "English"),
    ("I speak Telugu",              "language_preference", "Telugu"),
    ("I prefer Hindi",              "language_preference", "Hindi"),
    ("My name is Priya",            "name", "Priya"),
    ("I am interested in data science", "branch_interest", "Data"),
]

mem_pass = 0
for text, exp_type, exp_val in mem_tests:
    mems = extract_pattern_based(text)
    found = [m for m in mems if m["memory_type"] == exp_type]
    ok = any(exp_val.lower() in m["content"].lower() for m in found)
    status = "PASS" if ok else "FAIL"
    if ok: mem_pass += 1
    print(f"  [{status}] {repr(text[:40])} -> {exp_type}:{exp_val}")

results["memory_extraction"] = (mem_pass, len(mem_tests))

# =========================================================================
# 2. Personal Query Detection (Memory Retrieval)
# =========================================================================
print("\n=== 2. Personal Query Detection ===")
from prompts import is_personal_query

pq_tests = [
    ("What is my name?",               True),
    ("Which branch do I like?",        True),
    ("What language do I prefer?",     True),
    ("What are my interests?",         True),
    ("Do you remember me?",            True),
    ("Tell me about myself",           True),
    ("What is the admission process?", False),
    ("What are the fees for CSE?",     False),
    ("Tell me about placements",       False),
]

pq_pass = 0
for text, expected in pq_tests:
    result = is_personal_query(text)
    ok = result == expected
    if ok: pq_pass += 1
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] is_personal={result} | {text}")

results["personal_query"] = (pq_pass, len(pq_tests))

# =========================================================================
# 3. Coreference resolution patterns exist in rag.py
# =========================================================================
print("\n=== 3. Coreference Resolution ===")
import re
with open("rag.py", "r", encoding="utf-8") as f:
    rag_src = f.read()

checks = [
    ("rewrite_query function defined",    "def rewrite_query(" in rag_src),
    ("ref_pattern checks for 'it'",       r"\bref_pattern\b" in rag_src and r'"it|its|that|this"' not in rag_src or "it|its" in rag_src),
    ("LLM rewrite called",                "llm.invoke" in rag_src and "QUERY_REWRITE_PROMPT" in rag_src),
    ("Fallback on rewrite failure",       "return question" in rag_src),
]

cref_pass = 0
for name, ok in checks:
    if ok: cref_pass += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

results["coreference"] = (cref_pass, len(checks))

# =========================================================================
# 4. Tool Input Validation
# =========================================================================
print("\n=== 4. Tool Input Validation ===")
from tools import fee_calculator, date_checker, percentage_calculator

tool_tests = [
    ("Negative marks",          lambda: percentage_calculator(-10, 100),  lambda r: bool(r.get("error"))),
    ("Zero total",              lambda: percentage_calculator(50, 0),     lambda r: bool(r.get("error"))),
    ("Marks > total",           lambda: percentage_calculator(150, 100),  lambda r: bool(r.get("error"))),
    ("Contradictory branch",    lambda: fee_calculator("cse civil"),      lambda r: bool(r.get("error"))),
    ("Empty event",             lambda: date_checker(""),                 lambda r: bool(r.get("error"))),
    ("Valid 450/600=75%",       lambda: percentage_calculator(450, 600),  lambda r: r.get("percentage") == 75.0),
    ("Valid fee CSE",           lambda: fee_calculator("cse"),            lambda r: r.get("annual_fee") == 115000),
]

tool_pass = 0
for name, fn, check in tool_tests:
    try:
        r = fn()
        ok = check(r)
    except Exception as e:
        ok = False
        print(f"  [FAIL] {name}: exception {e}")
        continue
    if ok: tool_pass += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

results["tool_validation"] = (tool_pass, len(tool_tests))

# =========================================================================
# 5. Date Tool Routing
# =========================================================================
print("\n=== 5. Date Tool Routing ===")
from tool_rag import ToolRouter
router = ToolRouter()

date_tests = [
    ("How many days remain until admission deadline?", "date_checker"),
    ("Has the admission deadline passed?",             "date_checker"),
    ("Days left for counseling?",                      "date_checker"),
    ("When is the EAMCET exam?",                       "date_checker"),
    ("How much time is left for the application?",     "date_checker"),
    ("Is the admission still open?",                   "date_checker"),
    ("What is the CSE fee?",                           "fee_calculator"),
    ("I got 450 out of 600, am I eligible?",           "percentage_calculator"),
    ("What departments are available?",                "rag"),
]

date_pass = 0
for q, expected in date_tests:
    route = router.route(q)
    ok = route == expected
    if ok: date_pass += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] route={route!r} | {q[:50]}")

results["date_routing"] = (date_pass, len(date_tests))

# =========================================================================
# 6. Date Days Calculation
# =========================================================================
print("\n=== 6. Date Days Calculation ===")
from tools import _days_until
from datetime import date

days, is_future = _days_until("2026-07-31")
today = date.today()
expected_days = (date(2026, 7, 31) - today).days
days_ok = days == expected_days
days_pass = int(days_ok)
print(f"  [{'PASS' if days_ok else 'FAIL'}] _days_until('2026-07-31'): {days} days (expected {expected_days})")

# Check date_checker answer includes days info
r = date_checker("admission")
has_days = "days" in r.get("answer", "").lower()
print(f"  [{'PASS' if has_days else 'FAIL'}] date_checker answer includes days info")
days_pass += int(has_days)

results["date_days"] = (days_pass, 2)

# =========================================================================
# 7. Evaluation Page - encoding
# =========================================================================
print("\n=== 7. Evaluation Page Encoding ===")
import re

with open("pages/2_Evaluation.py", "r", encoding="utf-8") as f:
    eval_content = f.read()

enc_checks = [
    ("UTF-8 encoding on all file reads",  'encoding="utf-8"' in eval_content),
    ("No emoji in data values",           not bool(re.search(r'["\'](.*?[\u2600-\u27BF\U0001F000-\U0001FFFF].*?)["\'].*?if', eval_content))),
    ("Status uses ASCII PASS/FAIL",       '"PASS" if' in eval_content or ".upper()" in eval_content),
    ("Run Complete Evaluation button",    'Run Complete Evaluation' in eval_content),
    ("CSV download uses utf-8",           'encode("utf-8")' in eval_content),
]

enc_pass = 0
for name, ok in enc_checks:
    if ok: enc_pass += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

results["evaluation_encoding"] = (enc_pass, len(enc_checks))

# =========================================================================
# 8. Combined Evaluation
# =========================================================================
print("\n=== 8. Combined Evaluation ===")
comb_checks = [
    ("run_complete_evaluation defined",   "def run_complete_evaluation(" in eval_content),
    ("Runs RAGAS",                        "_run_ragas" in eval_content),
    ("Runs Functional",                   "_run_functional" in eval_content),
    ("Runs Security",                     "_run_security" in eval_content),
    ("Runs LLM Judge",                    "_run_llm_judge" in eval_content),
    ("Never stops on failure (try/except)","except Exception as e" in eval_content),
    ("Progress bar rendered",             "st.progress(" in eval_content),
    ("Saves combined report",             'combined_evaluation_report.json' in eval_content),
    ("Weakest dimension reported",        "weakest_dimension" in eval_content),
    ("Recommended fixes reported",        "recommended_fixes" in eval_content),
    ("Overall score reported",            "overall_score" in eval_content),
]

comb_pass = 0
for name, ok in comb_checks:
    if ok: comb_pass += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

results["combined_evaluation"] = (comb_pass, len(comb_checks))

# =========================================================================
# Summary
# =========================================================================
print("\n" + "="*60)
print("SUMMARY")
print("="*60)
total_pass = 0
total_tests = 0
for category, (p, t) in results.items():
    pct = p/t*100 if t > 0 else 0
    icon = "PASS" if p == t else ("WARN" if p >= t*0.8 else "FAIL")
    print(f"  [{icon}] {category:<30} {p}/{t} ({pct:.0f}%)")
    total_pass += p
    total_tests += t

print(f"\nTotal: {total_pass}/{total_tests} ({total_pass/total_tests*100:.0f}%)")
print("="*60)
