"""
evaluator.py - Simple evaluation for the College FAQ Chatbot.
Generates test cases, runs the RAG pipeline, and saves results.
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv

import config
from rag import answer_question
from utils import logger, Timer

load_dotenv()


def get_test_questions() -> List[str]:
    """Return a set of test questions covering all knowledge base sections."""
    return [
        "What is the admission process for B.Tech?",
        "What departments are available at BVRIT Hyderabad?",
        "Tell me about the placement record of the college.",
        "What campus facilities does the college offer?",
        "How can I contact the college?",
        "What is the fee structure for B.Tech programs?",
        "Tell me about the CSE department faculty.",
        "What research facilities are available?",
        "What student clubs and activities are there?",
        "Is hostel accommodation available?",
        "What is the vision of the college?",
        "Tell me about the library facilities.",
        "What sports facilities are available?",
        "How does the training and placement cell work?",
        "What are the admission requirements for international students?",
    ]


def generate_test_cases(
    num_questions: int = 10,
    save: bool = True,
) -> List[Dict[str, Any]]:
    """Generate test cases for evaluation."""
    questions = get_test_questions()[:num_questions]

    test_cases = []
    for i, question in enumerate(questions):
        logger.info(f"Generating test case {i + 1}/{len(questions)}: '{question[:50]}...'")

        # Get RAG response
        result = answer_question(question, debug=False)
        answer = result.get("answer", "")
        chunks = result.get("chunks", [])
        contexts = [chunk.page_content for chunk in chunks]
        citations = result.get("citations", [])

        test_case = {
            "question": question,
            "answer": answer,
            "contexts": contexts,
            "citations": citations,
            "chunks_retrieved": result.get("chunks_retrieved", 0),
            "has_answer": "not available in the uploaded knowledge base" not in answer.lower(),
        }
        test_cases.append(test_case)

        # Save individual test case
        if save:
            case_path = config.TEST_CASES_DIR / f"test_case_{i + 1}.json"
            with open(case_path, "w", encoding="utf-8") as f:
                json.dump(test_case, f, indent=2, ensure_ascii=False)

    # Save all test cases
    if save:
        all_path = config.TEST_CASES_DIR / "all_test_cases.json"
        with open(all_path, "w", encoding="utf-8") as f:
            json.dump({"test_cases": test_cases}, f, indent=2, ensure_ascii=False)

    logger.info(f"Generated {len(test_cases)} test cases")
    return test_cases


def run_evaluation(test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run evaluation on the test cases."""
    logger.info(f"Running evaluation on {len(test_cases)} test cases...")

    # Calculate metrics
    total = len(test_cases)
    answered = sum(1 for tc in test_cases if tc.get("has_answer", False))
    unanswered = total - answered
    avg_chunks = sum(tc.get("chunks_retrieved", 0) for tc in test_cases) / total if total > 0 else 0
    avg_answer_length = sum(len(tc.get("answer", "")) for tc in test_cases) / total if total > 0 else 0

    # Per-question breakdown
    per_question = []
    for tc in test_cases:
        per_question.append({
            "question": tc["question"],
            "has_answer": tc.get("has_answer", False),
            "chunks_retrieved": tc.get("chunks_retrieved", 0),
            "answer_length": len(tc.get("answer", "")),
            "citations": tc.get("citations", []),
            "answer_preview": tc.get("answer", "")[:100],
        })

    evaluation_report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_test_cases": total,
        "answered": answered,
        "unanswered": unanswered,
        "answer_rate": round(answered / total, 4) if total > 0 else 0,
        "avg_chunks_retrieved": round(avg_chunks, 2),
        "avg_answer_length": round(avg_answer_length, 0),
        "per_question": per_question,
        "recommendations": generate_recommendations(answered, total),
    }

    logger.info(f"Evaluation complete. Answer rate: {answered}/{total}")
    return evaluation_report


def generate_recommendations(answered: int, total: int) -> List[str]:
    """Generate recommendations based on evaluation results."""
    recommendations = []
    rate = answered / total if total > 0 else 0

    if rate < 0.5:
        recommendations.append(
            "Low answer rate. Consider updating the knowledge base document "
            "with more comprehensive information."
        )
    if rate < 0.8:
        recommendations.append(
            "Some questions were not answered. Review the knowledge base "
            "for missing sections."
        )
    if rate >= 0.8:
        recommendations.append(
            "Good answer rate. The knowledge base covers most topics well."
        )

    return recommendations


def save_evaluation_report(report: Dict[str, Any]) -> Path:
    """Save the evaluation report to a JSON file."""
    report_path = config.EVALUATION_DIR / "report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"Evaluation report saved to {report_path}")
    return report_path


def load_evaluation_report() -> Optional[Dict[str, Any]]:
    """Load the saved evaluation report."""
    report_path = config.EVALUATION_DIR / "report.json"
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def run_full_evaluation(num_questions: int = 10) -> Dict[str, Any]:
    """Run the full evaluation pipeline."""
    print("=" * 60)
    print("Evaluation Pipeline")
    print("=" * 60)

    # Step 1: Generate test cases
    print(f"\n[Step 1/2] Generating {num_questions} test cases...")
    test_cases = generate_test_cases(num_questions=num_questions)

    # Step 2: Run evaluation
    print(f"\n[Step 2/2] Running evaluation...")
    report = run_evaluation(test_cases)

    # Save report
    save_evaluation_report(report)

    print(f"\n{'=' * 60}")
    print(f"✅ Evaluation Complete!")
    print(f"   Answer Rate: {report['answer_rate']:.0%}")
    print(f"   Answered: {report['answered']}/{report['total_test_cases']}")
    print(f"   Avg Chunks: {report['avg_chunks_retrieved']}")
    print(f"   Report: evaluation/report.json")
    print(f"{'=' * 60}")

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run evaluation")
    parser.add_argument(
        "--questions", type=int, default=10,
        help="Number of test questions"
    )
    args = parser.parse_args()

    run_full_evaluation(num_questions=args.questions)