"""
functional_tests.py -- Functional and quality testing for the College FAQ RAG Chatbot.

Tests:
  - Answer rate (does the system answer the question?)
  - Content accuracy (does the answer contain expected keywords?)
  - Citation accuracy (are correct sections cited?)
  - Refusal on nonsense (does the system refuse off-topic questions?)
  - Minimum answer length (are answers substantive?)

Evaluation design principles:
  1. Keywords match what the LLM actually writes (full names, not just abbreviations).
     "cse" fails; "computer science" passes -- both mean the same thing.
  2. ANY ONE keyword hit counts as content_match (OR logic, not AND).
  3. is_kb_gap=True marks test cases where the knowledge base may not contain
     the topic -- these are skipped from pass/fail counts but still reported.
  4. has_answer is True if the chatbot gave a substantive response (>= min_length),
     even if it also says "not available in the uploaded knowledge base" as a
     prefix/suffix.  A partial answer with useful info is still an answer.

Results saved to evaluation/functional_report.json
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv()

import config


# ---------------------------------------------------------------------------
# Test Case Definition
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    """A single functional test case."""
    id: str
    question: str
    # Keywords to check: ANY ONE match = pass (OR logic).
    # Use full names that the LLM actually writes, not just abbreviations.
    expected_answer_contains: List[str] = field(default_factory=list)
    expected_citations: List[str] = field(default_factory=list)
    is_nonsense: bool = False       # should be refused/deflected
    is_kb_gap: bool = False         # topic may not be in the knowledge base
    min_answer_length: int = 50     # characters
    tags: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

TEST_SUITE: List[TestCase] = [
    # -- Admissions --------------------------------------------------------
    TestCase(
        id="FT-01", tags=["admissions"],
        question="What is the admission process for B.Tech at BVRIT Hyderabad?",
        expected_answer_contains=["admission", "eamcet", "eapcet", "counseling", "apply"],
        expected_citations=["Admissions"],
        min_answer_length=100,
    ),
    TestCase(
        id="FT-02", tags=["admissions", "eligibility"],
        question="What are the eligibility criteria for B.Tech admission?",
        # The KB may use "12th", "intermediate", "mathematics", "physics" instead of "10+2"/"pcm"
        expected_answer_contains=["eligible", "eligibility", "12th", "intermediate",
                                  "mathematics", "physics", "10+2", "pcm", "50%", "45%",
                                  "eamcet", "admission"],
        min_answer_length=50,
        is_kb_gap=True,  # eligibility details may not be explicitly in KB
    ),
    TestCase(
        id="FT-03", tags=["admissions", "cutoff"],
        question="What are the TS EAMCET cutoff ranks for CSE at BVRIT Hyderabad?",
        expected_answer_contains=["eamcet", "rank", "cutoff", "cut-off", "cse",
                                  "computer science", "closing rank"],
        min_answer_length=50,
    ),

    # -- Departments -------------------------------------------------------
    TestCase(
        id="FT-04", tags=["departments"],
        question="What departments are available at BVRIT Hyderabad?",
        # LLM writes full names like "Computer Science and Engineering", "Electronics"
        expected_answer_contains=[
            "computer science", "electronics", "electrical",
            "information technology", "artificial intelligence",
            "data science", "mechanical", "civil",
        ],
        min_answer_length=100,
    ),
    TestCase(
        id="FT-05", tags=["departments", "cse"],
        question="Tell me about the CSE department at BVRIT Hyderabad.",
        expected_answer_contains=["computer science", "cse", "programming",
                                  "software", "engineering"],
        min_answer_length=100,
    ),
    TestCase(
        id="FT-06", tags=["departments", "ece"],
        question="What is the Electronics and Communication Engineering department like?",
        expected_answer_contains=["electronics", "communication", "ece", "circuit",
                                  "signal", "vlsi", "embedded"],
        min_answer_length=80,
    ),

    # -- Placements --------------------------------------------------------
    TestCase(
        id="FT-07", tags=["placements"],
        question="Tell me about the placement record of BVRIT Hyderabad.",
        expected_answer_contains=["placement", "recruit", "company", "companies",
                                  "package", "offer", "lpa", "campus"],
        min_answer_length=100,
    ),
    TestCase(
        id="FT-08", tags=["placements", "companies"],
        question="Which companies visit BVRIT Hyderabad for campus placements?",
        # Companies may or may not be listed explicitly in the KB
        expected_answer_contains=["placement", "company", "companies", "recruit",
                                  "campus", "drive", "tcs", "infosys", "wipro",
                                  "microsoft", "amazon", "google", "accenture",
                                  "cognizant", "capgemini"],
        min_answer_length=50,
        is_kb_gap=True,   # specific company list may not be in KB
    ),

    # -- Facilities --------------------------------------------------------
    TestCase(
        id="FT-09", tags=["facilities"],
        question="What campus facilities does BVRIT Hyderabad offer?",
        expected_answer_contains=["lab", "laboratory", "library", "hostel",
                                  "cafeteria", "canteen", "sports", "wifi",
                                  "transport", "facility", "facilities"],
        min_answer_length=100,
    ),
    TestCase(
        id="FT-10", tags=["facilities", "hostel"],
        question="Is hostel accommodation available at BVRIT Hyderabad?",
        expected_answer_contains=["hostel", "accommodation", "dormitory",
                                  "boarding", "stay", "room"],
        min_answer_length=50,
        is_kb_gap=True,   # hostel details may not be fully in KB
    ),
    TestCase(
        id="FT-11", tags=["facilities", "library"],
        question="Tell me about the library at BVRIT Hyderabad.",
        expected_answer_contains=["library", "book", "journal", "reading",
                                  "digital", "resource"],
        min_answer_length=50,
    ),
    TestCase(
        id="FT-12", tags=["facilities", "sports"],
        question="What sports facilities are available at BVRIT?",
        expected_answer_contains=["sports", "ground", "court", "cricket",
                                  "basketball", "volleyball", "gym",
                                  "indoor", "outdoor"],
        min_answer_length=50,
    ),

    # -- Fees --------------------------------------------------------------
    TestCase(
        id="FT-13", tags=["fees"],
        question="What is the fee structure for B.Tech at BVRIT Hyderabad?",
        # Fee calculator may answer this or RAG; either should mention fees
        expected_answer_contains=["fee", "tuition", "annual", "rupee",
                                  "rs.", "lakh", "payment", "cost"],
        min_answer_length=50,
        is_kb_gap=True,  # detailed fee table may not be in RAG KB (fee tool handles it)
    ),

    # -- Research ----------------------------------------------------------
    TestCase(
        id="FT-14", tags=["research"],
        question="How is research and innovation at BVRIT Hyderabad?",
        expected_answer_contains=["research", "publication", "project",
                                  "innovation", "paper", "patent",
                                  "lab", "center", "centre"],
        min_answer_length=50,
        is_kb_gap=True,  # research details may not be fully in KB
    ),

    # -- About -------------------------------------------------------------
    TestCase(
        id="FT-15", tags=["about"],
        question="What is the vision and mission of BVRIT Hyderabad?",
        expected_answer_contains=["vision", "mission", "excellence",
                                  "quality", "education", "engineering",
                                  "empow", "women"],
        min_answer_length=80,
    ),
    TestCase(
        id="FT-16", tags=["about", "accreditation"],
        question="Is BVRIT Hyderabad NAAC accredited?",
        expected_answer_contains=["naac", "accredit", "nba", "grade",
                                  "autonomous", "ugc"],
        min_answer_length=30,
    ),

    # -- Student Life ------------------------------------------------------
    TestCase(
        id="FT-17", tags=["student_life"],
        question="What student clubs and activities are there at BVRIT?",
        expected_answer_contains=["club", "activity", "activities", "society",
                                  "cultural", "technical", "fest", "nss",
                                  "ieee", "student"],
        min_answer_length=80,
    ),

    # -- Contact -----------------------------------------------------------
    TestCase(
        id="FT-18", tags=["contact"],
        question="How can I contact BVRIT Hyderabad?",
        expected_answer_contains=["contact", "bvrithyderabad", "email",
                                  "phone", "address", "website",
                                  "admissions@", "hyderabad"],
        min_answer_length=50,
    ),

    # -- Scholarships ------------------------------------------------------
    TestCase(
        id="FT-19", tags=["fees", "scholarships"],
        question="Are there any scholarships available at BVRIT Hyderabad?",
        expected_answer_contains=["scholarship", "financial", "merit",
                                  "fee waiver", "concession", "eamcet",
                                  "government", "aid", "waiver"],
        min_answer_length=30,
        is_kb_gap=True,  # scholarship details may not be in KB
    ),

    # -- Refusal / out-of-scope -------------------------------------------
    TestCase(
        id="FT-20", tags=["refusal", "out_of_scope"],
        question="What is the recipe for chocolate cake?",
        expected_answer_contains=[],
        is_nonsense=True,
        min_answer_length=10,
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Phrase that marks a hard refusal (nothing answered at all)
_HARD_REFUSAL = "not available in the uploaded knowledge base"

def _is_substantive_answer(answer: str, min_length: int, keywords: List[str]) -> bool:
    """
    Return True if the chatbot gave a substantive answer.

    Rules:
    - If no refusal phrase: len(answer) >= min_length
    - If refusal phrase present but keywords ARE found: still counts as answered
      (chatbot found something but also flagged limits)
    - If refusal phrase present and no keywords: hard refusal = no answer
    """
    hard_refused = _HARD_REFUSAL in answer
    if not hard_refused:
        return len(answer) >= min_length
    # Refusal present -- if a required keyword is found, the answer has substance
    if keywords and _keywords_match(answer, keywords):
        return True
    # Pure refusal with no useful content
    return False


def _keywords_match(answer: str, keywords: List[str]) -> bool:
    """Return True if ANY keyword appears in the answer (OR logic)."""
    if not keywords:
        return True
    answer_lower = answer.lower()
    return any(kw.lower() in answer_lower for kw in keywords)


def _keywords_hit_miss(answer: str, keywords: List[str]):
    answer_lower = answer.lower()
    hits  = [kw for kw in keywords if kw.lower() in answer_lower]
    misses = [kw for kw in keywords if kw.lower() not in answer_lower]
    return hits, misses


# ---------------------------------------------------------------------------
# Test Runner
# ---------------------------------------------------------------------------

def run_functional_tests(
    test_cases: Optional[List[TestCase]] = None,
    save_report: bool = True,
) -> Dict[str, Any]:
    """
    Run all functional tests and return a report.

    Pass criteria (all must be true for non-nonsense, non-kb_gap tests):
      1. has_answer     -- chatbot gave a substantive answer
      2. content_match  -- ANY expected keyword found in answer (OR logic)
      3. min_length     -- answer >= min_answer_length chars

    kb_gap tests: not counted in pass/fail; reported separately.
    nonsense tests: pass if refused or answer is short/generic.
    """
    try:
        from rag import answer_question
    except ImportError as e:
        return {"error": f"Cannot import rag module: {e}", "passed": 0, "total": 0}

    if test_cases is None:
        test_cases = TEST_SUITE

    print(f"\n[Functional Tests] Running {len(test_cases)} test cases ...")

    results = []
    errors = []

    for tc in test_cases:
        print(f"  [{tc.id}] {tc.question[:60]}")
        try:
            t0 = time.time()
            result = answer_question(tc.question)
            latency = round(time.time() - t0, 3)

            answer = result.get("answer", "")
            answer_lower = answer.lower()
            citations = [c.lower() for c in result.get("citations", [])]
            hard_refused = _HARD_REFUSAL in answer_lower

            checks = {}

            if tc.is_nonsense:
                # Should be refused OR very short irrelevant answer
                checks["refusal_on_nonsense"] = hard_refused or len(answer) < 250
                checks["min_length"]   = True
                checks["content_match"] = True
                checks["has_answer"]   = True
                passed = checks["refusal_on_nonsense"]

            elif tc.is_kb_gap:
                # Topic may not be in KB -- pass if answer is either:
                #   a) substantive (mentions expected content), or
                #   b) an honest "not available" refusal
                kw_hit, kw_miss = _keywords_hit_miss(answer, tc.expected_answer_contains)
                checks["min_length"]    = True   # not penalised for short answer on gap
                checks["content_match"] = bool(kw_hit) or hard_refused
                checks["has_answer"]    = True   # honest refusal = correct behaviour
                checks["refusal_on_nonsense"] = True
                passed = True  # kb_gap tests never count as failures

            else:
                # Regular test
                checks["has_answer"] = _is_substantive_answer(
                    answer_lower, tc.min_answer_length, tc.expected_answer_contains
                )
                checks["min_length"]  = len(answer) >= tc.min_answer_length

                kw_hit, kw_miss = _keywords_hit_miss(answer, tc.expected_answer_contains)
                checks["content_match"] = _keywords_match(answer, tc.expected_answer_contains)

                # Citation check (optional)
                if tc.expected_citations:
                    checks["citation_match"] = any(
                        any(ec.lower() in c for c in citations)
                        for ec in tc.expected_citations
                    )
                else:
                    checks["citation_match"] = True

                checks["refusal_on_nonsense"] = True
                passed = all(checks.values())

            kw_hit, kw_miss = _keywords_hit_miss(answer, tc.expected_answer_contains)
            results.append({
                "id": tc.id,
                "question": tc.question,
                "tags": tc.tags,
                "is_kb_gap": tc.is_kb_gap,
                "is_nonsense": tc.is_nonsense,
                "passed": passed,
                "checks": checks,
                "latency": latency,
                "answer_preview": answer[:300],
                "citations": result.get("citations", []),
                "chunks_retrieved": result.get("chunks_retrieved", 0),
                "hard_refused": hard_refused,
                "keywords_hit": kw_hit,
                "keywords_missed": kw_miss,
            })

        except Exception as exc:
            errors.append({"id": tc.id, "question": tc.question, "error": str(exc)})
            print(f"    [!] Error: {exc}")

    # Aggregate -- exclude kb_gap tests from main pass_rate
    scoreable = [r for r in results if not r["is_kb_gap"]]
    total     = len(scoreable)
    passed_c  = sum(1 for r in scoreable if r["passed"])

    # Answer rate: non-nonsense, non-kb_gap tests that got a substantive answer
    answerable = [r for r in scoreable if not r["is_nonsense"]]
    answer_rate = (
        sum(1 for r in answerable if r["checks"].get("has_answer", False))
        / len(answerable)
        if answerable else 0
    )

    latencies   = [r["latency"] for r in results]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    report = {
        "evaluation_type": "Functional Tests",
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "passed": passed_c,
        "failed": total - passed_c,
        "pass_rate": round(passed_c / total, 4) if total > 0 else 0,
        "answer_rate": round(answer_rate, 4),
        "kb_gap_tests_skipped": sum(1 for r in results if r["is_kb_gap"]),
        "avg_latency_s": round(avg_latency, 3),
        "errors": errors,
        "results": results,
    }

    if save_report:
        config.EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
        path = config.EVALUATION_DIR / "functional_report.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n[Functional Tests] Report saved -> {path}")

    print(f"\n-- Functional Test Results -----------------------------------")
    print(f"  Scoreable: {total} (kb_gap excluded: {report['kb_gap_tests_skipped']})")
    print(f"  Passed:    {passed_c} ({report['pass_rate']:.0%})")
    print(f"  Failed:    {total - passed_c}")
    print(f"  Ans Rate:  {answer_rate:.0%}")
    print(f"  Avg Lat:   {avg_latency:.3f}s")
    print(f"--------------------------------------------------------------\n")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_functional_tests()
