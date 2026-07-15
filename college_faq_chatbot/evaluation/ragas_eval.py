"""
ragas_eval.py — RAGAS-style evaluation for the College FAQ RAG Chatbot.

Implements four core metrics without any external eval packages:
  - Faithfulness       : Does the answer contain only info from the contexts?
  - Answer Relevancy   : Does the answer address the question?
  - Context Precision  : Are the retrieved chunks relevant to the question?
  - Context Recall     : Do the retrieved chunks cover the answer?

All scoring is done via LLM-as-judge using GPT-4o-mini through OpenRouter.
Results are saved to evaluation/ragas_report.json.
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Allow imports from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config

load_dotenv()


# ---------------------------------------------------------------------------
# LLM helper
# ---------------------------------------------------------------------------

def _get_llm():
    """Instantiate a ChatOpenAI client pointed at OpenRouter."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set in environment / .env")

    return ChatOpenAI(
        model=config.LLM_MODEL,
        temperature=0.0,
        max_tokens=512,
        openai_api_key=api_key,
        openai_api_base=config.OPENROUTER_BASE_URL,
    )


def _call_llm(prompt: str, fallback_score: float = 0.5) -> Dict[str, Any]:
    """
    Call the LLM with a prompt and parse the JSON response.

    Returns a dict with at least {"score": float, "reason": str}.
    Falls back to fallback_score if parsing fails.
    """
    try:
        llm = _get_llm()
        response = llm.invoke(prompt)
        raw = response.content.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        score = float(data.get("score", fallback_score))
        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))
        return {"score": score, "reason": data.get("reason", "")}

    except Exception as exc:  # noqa: BLE001
        return {"score": fallback_score, "reason": f"Scoring error: {exc}"}


# ---------------------------------------------------------------------------
# Individual metric scorers
# ---------------------------------------------------------------------------

def score_faithfulness(question: str, answer: str, contexts: List[str]) -> Dict[str, Any]:
    """
    Score faithfulness: does the answer contain only information supported by contexts?

    Args:
        question: The user's question.
        answer:   The generated answer.
        contexts: List of retrieved context chunks.

    Returns:
        Dict with keys "score" (0-1) and "reason".
    """
    combined = "\n\n---\n\n".join(contexts)[:3000]
    prompt = f"""Rate the faithfulness of this answer on a scale of 0 to 1.
Faithfulness means: the answer only contains information supported by the given contexts.
A score of 1.0 means every claim in the answer can be found in the contexts.
A score of 0.0 means the answer contains facts not supported by or contradicted by the contexts.

Question: {question}
Answer: {answer}
Contexts: {combined}

Return JSON: {{"score": 0.0-1.0, "reason": "brief explanation"}}
Respond with ONLY valid JSON. No markdown, no extra text."""
    return _call_llm(prompt, fallback_score=0.5)


def score_answer_relevancy(question: str, answer: str) -> Dict[str, Any]:
    """
    Score answer relevancy: does the answer actually address the question?

    Args:
        question: The user's question.
        answer:   The generated answer.

    Returns:
        Dict with keys "score" (0-1) and "reason".
    """
    prompt = f"""Rate how relevant this answer is to the question on a scale of 0 to 1.
A score of 1.0 means the answer directly and completely addresses the question.
A score of 0.0 means the answer is off-topic or completely misses the question.

Question: {question}
Answer: {answer}

Return JSON: {{"score": 0.0-1.0, "reason": "brief explanation"}}
Respond with ONLY valid JSON. No markdown, no extra text."""
    return _call_llm(prompt, fallback_score=0.5)


def score_context_precision(question: str, contexts: List[str]) -> Dict[str, Any]:
    """
    Score context precision: what fraction of retrieved chunks are relevant to the question?

    Args:
        question: The user's question.
        contexts: List of retrieved context chunks.

    Returns:
        Dict with keys "score" (0-1) and "reason".
    """
    numbered = "\n\n".join(
        f"[Chunk {i + 1}]: {ctx[:500]}" for i, ctx in enumerate(contexts)
    )[:3000]
    prompt = f"""You are evaluating a RAG retrieval system.
Given the user's question and a list of retrieved chunks, rate the precision of the retrieval.
Precision = (number of chunks relevant to the question) / (total number of chunks).
A score of 1.0 means all chunks are relevant. A score of 0.0 means none are relevant.

Question: {question}

Retrieved Chunks:
{numbered}

Return JSON: {{"score": 0.0-1.0, "reason": "brief explanation of how many chunks were relevant"}}
Respond with ONLY valid JSON. No markdown, no extra text."""
    return _call_llm(prompt, fallback_score=0.5)


def score_context_recall(question: str, answer: str, contexts: List[str]) -> Dict[str, Any]:
    """
    Score context recall: do the retrieved chunks contain the information needed for the answer?

    Args:
        question: The user's question.
        answer:   The reference/generated answer.
        contexts: List of retrieved context chunks.

    Returns:
        Dict with keys "score" (0-1) and "reason".
    """
    combined = "\n\n---\n\n".join(contexts)[:3000]
    prompt = f"""You are evaluating a RAG retrieval system.
Given the user's question, a reference answer, and retrieved chunks, rate the recall.
Recall = fraction of information in the answer that can be attributed to the retrieved chunks.
A score of 1.0 means all answer content is present in the contexts.
A score of 0.0 means none of the answer content appears in the contexts.

Question: {question}
Answer (reference): {answer}
Retrieved Contexts: {combined}

Return JSON: {{"score": 0.0-1.0, "reason": "brief explanation"}}
Respond with ONLY valid JSON. No markdown, no extra text."""
    return _call_llm(prompt, fallback_score=0.5)


# ---------------------------------------------------------------------------
# Single sample evaluator
# ---------------------------------------------------------------------------

def evaluate_sample(
    question: str,
    answer: str,
    contexts: List[str],
    sample_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run all four RAGAS-style metrics on a single QA sample.

    Args:
        question:  The user question.
        answer:    The generated answer.
        contexts:  List of retrieved context chunks (plain strings).
        sample_id: Optional identifier for the sample.

    Returns:
        Dict with individual metric results and an aggregate score.
    """
    result: Dict[str, Any] = {
        "sample_id": sample_id or question[:40],
        "question": question,
        "answer_preview": answer[:200],
        "num_contexts": len(contexts),
        "timestamp": datetime.now().isoformat(),
    }

    metrics = [
        ("faithfulness", score_faithfulness, (question, answer, contexts)),
        ("answer_relevancy", score_answer_relevancy, (question, answer)),
        ("context_precision", score_context_precision, (question, contexts)),
        ("context_recall", score_context_recall, (question, answer, contexts)),
    ]

    scores = {}
    for metric_name, fn, args in metrics:
        metric_result = fn(*args)
        scores[metric_name] = metric_result["score"]
        result[metric_name] = metric_result
        # Small sleep to avoid rate limiting
        time.sleep(0.3)

    # Aggregate: simple mean of all four metrics
    result["aggregate_score"] = round(sum(scores.values()) / len(scores), 4)
    result["scores"] = scores
    return result


# ---------------------------------------------------------------------------
# Batch evaluator
# ---------------------------------------------------------------------------

DEFAULT_TEST_CASES: List[Dict[str, str]] = [
    {"question": "What is the admission process at BVRIT Hyderabad?"},
    {"question": "What departments are available?"},
    {"question": "Tell me about placements at BVRIT Hyderabad."},
    {"question": "What are the campus facilities?"},
    {"question": "What is the fee structure for CSE?"},
    {"question": "What are the TS EAMCET cutoff ranks?"},
    {"question": "Tell me about the CSE department."},
    {"question": "What student clubs are available?"},
    {"question": "How is the research at the college?"},
    {"question": "What are the hostel facilities?"},
]


def run_ragas_evaluation(
    test_cases: Optional[List[Dict[str, str]]] = None,
    save_report: bool = True,
) -> Dict[str, Any]:
    """
    Run the full RAGAS-style evaluation pipeline.

    For each test case the RAG pipeline is called to get an answer and contexts,
    then all four metrics are scored via LLM.

    Args:
        test_cases:   List of dicts with at least {"question": str}. Uses
                      DEFAULT_TEST_CASES if None.
        save_report:  Whether to save the report JSON to evaluation/.

    Returns:
        Full evaluation report dict.
    """
    from rag import answer_question  # noqa: PLC0415

    if test_cases is None:
        test_cases = DEFAULT_TEST_CASES

    print(f"\n[RAGAS Eval] Starting evaluation on {len(test_cases)} test cases …")

    sample_results = []
    errors = []

    for i, tc in enumerate(test_cases, 1):
        question = tc["question"]
        print(f"  [{i}/{len(test_cases)}] Evaluating: {question[:60]}")

        try:
            # Run RAG pipeline
            rag_result = answer_question(question)
            answer = rag_result.get("answer", "")
            chunks = rag_result.get("chunks", [])
            contexts = [c.page_content for c in chunks if hasattr(c, "page_content")]

            if not contexts:
                contexts = ["No context retrieved."]

            sample = evaluate_sample(
                question=question,
                answer=answer,
                contexts=contexts,
                sample_id=f"sample_{i}",
            )
            sample_results.append(sample)

        except Exception as exc:  # noqa: BLE001
            error_entry = {"question": question, "error": str(exc)}
            errors.append(error_entry)
            print(f"    [!] Error: {exc}")

    # Aggregate across all samples
    metric_names = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    aggregate: Dict[str, float] = {}
    for metric in metric_names:
        valid_scores = [
            s["scores"][metric]
            for s in sample_results
            if "scores" in s and metric in s["scores"]
        ]
        aggregate[metric] = round(sum(valid_scores) / len(valid_scores), 4) if valid_scores else 0.0

    aggregate["overall"] = round(sum(aggregate.values()) / len(aggregate), 4) if aggregate else 0.0

    report: Dict[str, Any] = {
        "evaluation_type": "RAGAS-style",
        "timestamp": datetime.now().isoformat(),
        "num_test_cases": len(test_cases),
        "num_evaluated": len(sample_results),
        "num_errors": len(errors),
        "aggregate_scores": aggregate,
        "samples": sample_results,
        "errors": errors,
    }

    if save_report:
        report_path = config.EVALUATION_DIR / "ragas_report.json"
        config.EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n[RAGAS Eval] Report saved -> {report_path}")

    # Print summary
    print("\n-- RAGAS Aggregate Scores --------------------------")
    for metric, score in aggregate.items():
        bar = "#" * int(score * 20) + "." * (20 - int(score * 20))
        print(f"  {metric:<22} {bar} {score:.4f}")
    print("----------------------------------------------------\n")

    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_ragas_evaluation()
