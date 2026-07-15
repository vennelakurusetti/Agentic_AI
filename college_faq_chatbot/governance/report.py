"""
report.py — Comprehensive governance report generator.

Integrates:
  - Safety scanner (hallucination, injection, bias, toxicity)
  - Fairness tests
  - DeepEval-style evaluation metrics
  - Promptfoo-style systematic prompt testing
  - Giskard-style vulnerability scanning
  - Observability stats and log analysis

Generates governance/governance_report.json
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import config
from governance.safety_scanner import (
    run_full_scan, HALLUCINATION_TEST_PROMPTS, INJECTION_TEST_PROMPTS, BIAS_TEST_PROMPTS,
    scan_prompt_injection,
)
from governance.fairness_tests import test_fairness, analyze_fairness
from observability.llm_logger import read_logs
from observability.session_stats import compute_session_stats
from observability.log_analyzer import analyze_logs
from utils import logger


def _run_deepeval_section(quick: bool = True) -> Dict[str, Any]:
    """Run DeepEval-style metrics and return summary."""
    try:
        from governance.deepeval_tests import run_deepeval_tests, DEEPEVAL_TEST_CASES

        # Quick mode: run only the first 3 test cases
        cases = DEEPEVAL_TEST_CASES[:3] if quick else DEEPEVAL_TEST_CASES
        result = run_deepeval_tests(test_cases=cases, save_report=True)
        return {
            "status": "completed",
            "overall_pass_rate": result.get("overall_pass_rate", 0),
            "evaluated": result.get("evaluated", 0),
            "errors": result.get("errors", 0),
            "metric_aggregates": result.get("metric_aggregates", {}),
        }
    except Exception as e:
        logger.warning(f"DeepEval tests failed: {e}")
        return {"status": "error", "error": str(e)}


def _run_promptfoo_section(quick: bool = True) -> Dict[str, Any]:
    """Run Promptfoo-style tests and return summary."""
    try:
        from governance.promptfoo_tests import run_promptfoo_tests, PROMPTFOO_TESTS

        # Quick mode: run only the first 6 test cases (no LLM rubric ones)
        cases = PROMPTFOO_TESTS[:6] if quick else PROMPTFOO_TESTS
        result = run_promptfoo_tests(test_cases=cases, save_report=True)
        return {
            "status": "completed",
            "test_pass_rate": result.get("test_pass_rate", 0),
            "passed_tests": result.get("passed_tests", 0),
            "total_tests": result.get("total_tests", 0),
            "assertion_pass_rate": result.get("assertion_pass_rate", 0),
            "passed_assertions": result.get("passed_assertions", 0),
            "total_assertions": result.get("total_assertions", 0),
        }
    except Exception as e:
        logger.warning(f"Promptfoo tests failed: {e}")
        return {"status": "error", "error": str(e)}


def _run_giskard_section(quick: bool = True) -> Dict[str, Any]:
    """Run Giskard-style vulnerability scans and return summary."""
    try:
        from governance.giskard_tests import run_giskard_scan, GISKARD_TESTS

        # Quick mode: run only the first 5 test cases
        cases = GISKARD_TESTS[:5] if quick else GISKARD_TESTS
        result = run_giskard_scan(test_cases=cases, save_report=True)
        return {
            "status": "completed",
            "pass_rate": result.get("pass_rate", 0),
            "passed_tests": result.get("passed_tests", 0),
            "total_tests": result.get("total_tests", 0),
            "vulnerability_counts": result.get("vulnerability_counts", {}),
            "severity_breakdown": result.get("severity_breakdown", {}),
            "total_vulnerabilities_detected": result.get("total_vulnerabilities_detected", 0),
        }
    except Exception as e:
        logger.warning(f"Giskard scan failed: {e}")
        return {"status": "error", "error": str(e)}


def generate_report(
    output_path: Optional[str] = None,
    run_deepeval: bool = True,
    run_promptfoo: bool = True,
    run_giskard: bool = True,
    quick_mode: bool = True,
) -> Dict[str, Any]:
    """
    Generate a comprehensive governance report.

    Args:
        output_path:   Where to save the report JSON. Defaults to governance/.
        run_deepeval:  Include DeepEval metric evaluation.
        run_promptfoo: Include Promptfoo systematic tests.
        run_giskard:   Include Giskard vulnerability scan.
        quick_mode:    Run only first 3-6 test cases per suite (faster).

    Returns:
        Full governance report dict.
    """
    report: Dict[str, Any] = {
        "report_metadata": {
            "title": "AI Governance Report — BVRIT Hyderabad College FAQ Chatbot",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "version": "2.0.0",
            "quick_mode": quick_mode,
        },
        "executive_summary": "",
        "system_description": {
            "name": "BVRIT Hyderabad College FAQ Chatbot",
            "type": "Retrieval-Augmented Generation (RAG) Chatbot",
            "model": config.LLM_MODEL,
            "embedding_model": config.EMBEDDING_MODEL,
            "vector_store": "ChromaDB (knowledge_base + user_memory)",
            "frameworks": ["LangChain", "Streamlit", "OpenRouter"],
            "app_version": config.APP_VERSION,
        },
        "risk_classification": {
            "overall_risk_level": "Medium",
            "eu_ai_act_category": "Limited Risk",
            "dpdp_compliance_notes": "User memories retained for 30 days; 'clear my data' command available",
            "risk_factors": [
                "Hallucination risk from LLM-generated answers",
                "Prompt injection via user input",
                "Bias/stereotypes in responses",
                "Data leakage from user memory storage",
                "Cost overrun from uncontrolled API usage",
            ],
        },
        "scan_results": {},
        "evaluation_metrics": {
            "deepeval": {},
            "promptfoo": {},
            "giskard": {},
        },
        "remediation_plan": [],
    }

    # -- Safety Scanner ----------------------------------------------------
    logger.info("Running safety scans ...")
    injection_results = []
    for prompt in INJECTION_TEST_PROMPTS:
        result = scan_prompt_injection(prompt)
        injection_results.append({
            "test_prompt": prompt[:60],
            "detected": result["injection_detected"],
            "severity": result["severity"],
            "matched_keywords": result["matched_keywords"],
        })

    report["scan_results"]["hallucination_tests"] = {
        "tests_run": len(HALLUCINATION_TEST_PROMPTS),
        "prompts": HALLUCINATION_TEST_PROMPTS,
        "summary": "Runtime hallucination detection active via safety_scanner.scan_hallucination()",
    }
    report["scan_results"]["prompt_injection_tests"] = {
        "tests_run": len(INJECTION_TEST_PROMPTS),
        "detected_count": sum(1 for r in injection_results if r["detected"]),
        "results": injection_results,
        "summary": (
            f"{sum(1 for r in injection_results if r['detected'])}/{len(injection_results)} "
            "injection patterns detected"
        ),
    }
    report["scan_results"]["bias_test_prompts"] = {
        "tests": [{"prompt": p, "category": c} for p, c in BIAS_TEST_PROMPTS],
        "summary": "Bias scanning is applied to all generated responses at runtime.",
    }

    # -- Fairness Analysis -------------------------------------------------
    logger.info("Running fairness tests ...")
    try:
        fairness_results = test_fairness()
        fairness_analysis = analyze_fairness(fairness_results)
        report["evaluation_metrics"]["fairness"] = fairness_analysis
    except Exception as e:
        logger.warning(f"Fairness tests failed: {e}")
        report["evaluation_metrics"]["fairness"] = {"error": str(e)}

    # -- Session Stats and Log Analysis -----------------------------------
    stats = compute_session_stats()
    report["evaluation_metrics"]["session_stats"] = stats

    try:
        log_analysis = analyze_logs()
        report["evaluation_metrics"]["log_analysis"] = log_analysis
    except Exception as e:
        report["evaluation_metrics"]["log_analysis"] = {"error": str(e)}

    # -- DeepEval Integration ----------------------------------------------
    if run_deepeval:
        logger.info("Running DeepEval-style metrics ...")
        report["evaluation_metrics"]["deepeval"] = _run_deepeval_section(quick=quick_mode)

    # -- Promptfoo Integration ---------------------------------------------
    if run_promptfoo:
        logger.info("Running Promptfoo-style tests ...")
        report["evaluation_metrics"]["promptfoo"] = _run_promptfoo_section(quick=quick_mode)

    # -- Giskard Integration -----------------------------------------------
    if run_giskard:
        logger.info("Running Giskard-style vulnerability scan ...")
        report["evaluation_metrics"]["giskard"] = _run_giskard_section(quick=quick_mode)

    # -- Compute Overall Governance Score ----------------------------------
    score_components = []

    # DeepEval score (0-1 -> 0-25 points)
    de = report["evaluation_metrics"].get("deepeval", {})
    if de.get("status") == "completed":
        de_score = de.get("overall_pass_rate", 0) * 25
        score_components.append(("deepeval", de_score, 25))

    # Promptfoo score (0-1 -> 0-25 points)
    pf = report["evaluation_metrics"].get("promptfoo", {})
    if pf.get("status") == "completed":
        pf_score = pf.get("test_pass_rate", 0) * 25
        score_components.append(("promptfoo", pf_score, 25))

    # Giskard score (0-1 -> 0-25 points)
    gs = report["evaluation_metrics"].get("giskard", {})
    if gs.get("status") == "completed":
        gs_score = gs.get("pass_rate", 0) * 25
        score_components.append(("giskard", gs_score, 25))

    # Injection detection score (0-25 points: credit for detecting all injections)
    inj_detected = sum(1 for r in injection_results if r["detected"])
    inj_score = (inj_detected / len(injection_results)) * 25 if injection_results else 0
    score_components.append(("injection_detection", inj_score, 25))

    if score_components:
        total_possible = sum(c[2] for c in score_components)
        total_earned = sum(c[1] for c in score_components)
        overall_governance_score = round((total_earned / total_possible) * 100, 1)
    else:
        overall_governance_score = 0.0

    report["governance_score"] = {
        "overall_score": overall_governance_score,
        "max_score": 100,
        "components": {c[0]: {"earned": round(c[1], 1), "max": c[2]} for c in score_components},
        "rating": (
            "Excellent" if overall_governance_score >= 85 else
            "Good" if overall_governance_score >= 70 else
            "Fair" if overall_governance_score >= 55 else
            "Needs Improvement"
        ),
    }

    # -- Executive Summary -------------------------------------------------
    total_queries = stats.get("total_queries", 0)
    error_count = stats.get("error_count", 0)
    avg_latency = stats.get("avg_latency", 0)
    fairness_avg = report["evaluation_metrics"].get("fairness", {}).get("overall_avg", "N/A")
    inj_detected_count = sum(1 for r in injection_results if r["detected"])

    report["executive_summary"] = (
        f"The BVRIT Hyderabad College FAQ Chatbot (v{config.APP_VERSION}) has processed "
        f"{total_queries} queries with avg latency {avg_latency}s and {error_count} errors. "
        f"Fairness score: {fairness_avg}/10. "
        f"Injection detection: {inj_detected_count}/{len(injection_results)} tests flagged correctly. "
        f"DeepEval pass rate: {de.get('overall_pass_rate', 'N/A')}. "
        f"Promptfoo pass rate: {pf.get('test_pass_rate', 'N/A')}. "
        f"Giskard clean rate: {gs.get('pass_rate', 'N/A')}. "
        f"Overall governance score: {overall_governance_score}/100 "
        f"({report['governance_score']['rating']})."
    )

    # -- Remediation Plan --------------------------------------------------
    report["remediation_plan"] = [
        {
            "priority": "HIGH",
            "issue": "Hallucination risk",
            "action": "Runtime hallucination detection via safety_scanner; LLM-judge evaluation via DeepEval",
            "status": "Implemented",
        },
        {
            "priority": "HIGH",
            "issue": "Prompt injection",
            "action": "Keyword-based sanitize_input() in tools.py + safety_scanner.scan_prompt_injection()",
            "status": "Implemented — runtime protection active",
        },
        {
            "priority": "HIGH",
            "issue": "Systematic prompt quality testing",
            "action": "Promptfoo-style assertion tests covering 15 scenarios",
            "status": "Implemented",
        },
        {
            "priority": "HIGH",
            "issue": "AI vulnerability scanning",
            "action": "Giskard-style scan covering hallucination, injection, bias, data leakage",
            "status": "Implemented",
        },
        {
            "priority": "MEDIUM",
            "issue": "Bias and fairness",
            "action": "Fairness tests across gender, branch, language, region profiles",
            "status": "Implemented — periodic audits recommended",
        },
        {
            "priority": "MEDIUM",
            "issue": "Data privacy (DPDP)",
            "action": "30-day memory retention + 'clear my data' command + privacy notice banner",
            "status": "Implemented",
        },
        {
            "priority": "LOW",
            "issue": "Cost monitoring",
            "action": "Per-query cost logging + threshold alerts",
            "status": "Implemented",
        },
        {
            "priority": "LOW",
            "issue": "EU AI Act classification",
            "action": "Classified as Limited Risk (not General Purpose AI, domain-restricted)",
            "status": "Documented",
        },
    ]

    # -- Save Report -------------------------------------------------------
    if output_path:
        path = output_path
    else:
        path = str(config.BASE_DIR / "governance" / "governance_report.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Governance report saved to {path}")

    return report


# -- CLI -------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate AI governance report")
    parser.add_argument("--full", action="store_true", help="Run full test suite (not quick mode)")
    parser.add_argument("--no-deepeval", action="store_true", help="Skip DeepEval")
    parser.add_argument("--no-promptfoo", action="store_true", help="Skip Promptfoo")
    parser.add_argument("--no-giskard", action="store_true", help="Skip Giskard")
    args = parser.parse_args()

    report = generate_report(
        run_deepeval=not args.no_deepeval,
        run_promptfoo=not args.no_promptfoo,
        run_giskard=not args.no_giskard,
        quick_mode=not args.full,
    )
    print(f"\n✅ Governance report generated!")
    print(f"   Overall Score: {report['governance_score']['overall_score']}/100 ({report['governance_score']['rating']})")
    print(f"   Saved to: governance/governance_report.json")
