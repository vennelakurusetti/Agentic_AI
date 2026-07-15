"""
llm_judge.py — LLM-as-judge evaluation for the College FAQ RAG Chatbot.

Uses GPT-4o-mini as a judge to score generated answers on 5 criteria:
  1. Accuracy       — Is the answer factually correct based on the context?
  2. Completeness   — Does the answer fully address the question?
  3. Grounding      — Is every claim in the answer supported by the retrieved context?
  4. Clarity        — Is the answer well-structured and easy to understand?
  5. Citation       — Are the cited sources appropriate and relevant?

Each criterion is scored 0-10. The overall score is the average.
Results saved to evaluation/llm_judge_report.json
"""

import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv()

import config

# ---------------------------------------------------------------------------
# Judge Prompts
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = """You are an expert QA evaluator for a college FAQ chatbot.
Your job is to evaluate the quality of a generated answer based on a retrieved context.
You must score the answer on 5 criteria, each from 0 to 10.
Be strict and objective. Base your evaluation solely on the provided context and answer.
Return ONLY valid JSON. No markdown, no explanation outside the JSON."""

JUDGE_USER_TEMPLATE = """Evaluate the following QA pair:

QUESTION: {question}

RETRIEVED CONTEXT (what the system had access to):
{context}

GENERATED ANSWER:
{answer}

CITATIONS USED:
{citations}

Score on each criterion from 0 to 10:
1. accuracy: Is the answer factually correct based on the context? (0=completely wrong, 10=perfectly accurate)
2. completeness: Does the answer fully address the question? (0=misses everything, 10=fully addresses)
3. grounding: Is every claim in the answer supported by the context? (0=hallucinations everywhere, 10=fully grounded)
4. clarity: Is the answer well-structured, readable, and clear? (0=confusing, 10=excellent clarity)
5. citation_quality: Are the citations relevant and useful? (0=wrong citations, 10=perfect citations)

Return this exact JSON structure:
{{
  "scores": {{
    "accuracy": <0-10>,
    "completeness": <0-10>,
    "grounding": <0-10>,
    "clarity": <0-10>,
    "citation_quality": <0-10>
  }},
  "reasoning": {{
    "accuracy": "<brief reason>",
    "completeness": "<brief reason>",
    "grounding": "<brief reason>",
    "clarity": "<brief reason>",
    "citation_quality": "<brief reason>"
  }},
  "overall": <average of all 5 scores, float>,
  "summary": "<one sentence overall assessment>"
}}"""

# ---------------------------------------------------------------------------
# Default test questions for the judge
# ---------------------------------------------------------------------------

DEFAULT_JUDGE_QUESTIONS = [
    "What is the admission process for B.Tech at BVRIT Hyderabad?",
    "What departments are available?",
    "Tell me about placements at BVRIT Hyderabad.",
    "What are the campus facilities?",
    "What is the fee structure for CSE?",
    "Tell me about the hostel facilities.",
    "What research opportunities are available?",
    "What student clubs are there?",
    "How is the library at BVRIT Hyderabad?",
    "What is the vision and mission of the college?",
]


# ---------------------------------------------------------------------------
# LLM Helper
# ---------------------------------------------------------------------------

def _get_judge_llm():
    """Get a non-streaming LLM for judging."""
    from langchain_openai import ChatOpenAI
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")
    return ChatOpenAI(
        model=config.LLM_MODEL,
        temperature=0.0,
        max_tokens=1024,
        openai_api_key=api_key,
        openai_api_base=config.OPENROUTER_BASE_URL,
        streaming=False,
    )


# ---------------------------------------------------------------------------
# Core judge function
# ---------------------------------------------------------------------------

def judge_answer(
    question: str,
    answer: str,
    context: str,
    citations: Optional[List[str]] = None,
    sample_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Use LLM to judge the quality of a single answer.

    Args:
        question:   The user's question.
        answer:     The generated answer.
        context:    The retrieved context that was available.
        citations:  List of cited section names.
        sample_id:  Optional identifier.

    Returns:
        Dict with scores, reasoning, overall score, and summary.
    """
    citations_str = ", ".join(citations or []) or "None"
    context_truncated = context[:2500] if len(context) > 2500 else context

    prompt = JUDGE_USER_TEMPLATE.format(
        question=question,
        context=context_truncated,
        answer=answer[:1500],
        citations=citations_str,
    )

    result = {
        "sample_id": sample_id or question[:40],
        "question": question,
        "answer_preview": answer[:300],
        "num_citations": len(citations or []),
        "timestamp": datetime.now().isoformat(),
    }

    try:
        llm = _get_judge_llm()
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        response = llm.invoke(messages)
        raw = response.content.strip()

        # Strip markdown fences
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        result.update({
            "scores": data.get("scores", {}),
            "reasoning": data.get("reasoning", {}),
            "overall": float(data.get("overall", 0.0)),
            "summary": data.get("summary", ""),
            "judge_error": None,
        })

    except Exception as exc:
        result.update({
            "scores": {k: 0 for k in ["accuracy", "completeness", "grounding", "clarity", "citation_quality"]},
            "reasoning": {},
            "overall": 0.0,
            "summary": "",
            "judge_error": str(exc),
        })

    return result


def judge_batch(
    qa_pairs: List[Dict[str, Any]],
    delay: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Judge a batch of QA pairs.

    Each dict in qa_pairs must have: question, answer, context.
    Optional: citations, sample_id.
    """
    results = []
    for i, pair in enumerate(qa_pairs):
        print(f"  [LLM Judge] {i + 1}/{len(qa_pairs)}: {pair['question'][:60]}")
        result = judge_answer(
            question=pair["question"],
            answer=pair["answer"],
            context=pair.get("context", ""),
            citations=pair.get("citations", []),
            sample_id=pair.get("sample_id", f"sample_{i + 1}"),
        )
        results.append(result)
        if delay > 0:
            time.sleep(delay)
    return results


# ---------------------------------------------------------------------------
# Full pipeline: RAG + Judge
# ---------------------------------------------------------------------------

def run_llm_judge_evaluation(
    questions: Optional[List[str]] = None,
    save_report: bool = True,
    delay: float = 0.5,
) -> Dict[str, Any]:
    """
    Run the full LLM judge evaluation:
      1. For each question, run the RAG pipeline.
      2. Extract answer and context.
      3. Run the LLM judge on each QA pair.
      4. Aggregate scores.

    Args:
        questions:    List of questions to evaluate. Uses DEFAULT_JUDGE_QUESTIONS if None.
        save_report:  Whether to save the report.
        delay:        Seconds between LLM calls (rate limiting).

    Returns:
        Full evaluation report dict.
    """
    try:
        from rag import answer_question
    except ImportError as e:
        return {"error": f"Cannot import rag module: {e}"}

    if questions is None:
        questions = DEFAULT_JUDGE_QUESTIONS

    print(f"\n[LLM Judge] Evaluating {len(questions)} questions ...")

    # Step 1: Generate answers via RAG
    qa_pairs = []
    rag_errors = []

    for i, question in enumerate(questions):
        print(f"  [RAG] {i + 1}/{len(questions)}: {question[:60]}")
        try:
            result = answer_question(question)
            answer = result.get("answer", "")
            chunks = result.get("chunks", [])
            context = "\n\n".join(
                c.page_content for c in chunks if hasattr(c, "page_content")
            )[:3000]
            citations = result.get("citations", [])

            qa_pairs.append({
                "question": question,
                "answer": answer,
                "context": context,
                "citations": citations,
                "sample_id": f"judge_{i + 1}",
            })
            time.sleep(delay)
        except Exception as exc:
            rag_errors.append({"question": question, "error": str(exc)})
            print(f"    [!] RAG Error: {exc}")

    # Step 2: Judge all QA pairs
    print(f"\n[LLM Judge] Judging {len(qa_pairs)} answers ...")
    judged = judge_batch(qa_pairs, delay=delay)

    # Step 3: Aggregate scores
    criteria = ["accuracy", "completeness", "grounding", "clarity", "citation_quality"]
    agg_scores: Dict[str, float] = {}
    for criterion in criteria:
        valid = [
            r["scores"].get(criterion, 0)
            for r in judged
            if r.get("scores") and not r.get("judge_error")
        ]
        agg_scores[criterion] = round(sum(valid) / len(valid), 2) if valid else 0.0

    overall_scores = [r["overall"] for r in judged if not r.get("judge_error")]
    agg_scores["overall"] = round(sum(overall_scores) / len(overall_scores), 2) if overall_scores else 0.0

    report = {
        "evaluation_type": "LLM-as-Judge",
        "timestamp": datetime.now().isoformat(),
        "judge_model": config.LLM_MODEL,
        "num_questions": len(questions),
        "num_judged": len(judged),
        "num_rag_errors": len(rag_errors),
        "aggregate_scores": agg_scores,
        "samples": judged,
        "rag_errors": rag_errors,
    }

    if save_report:
        config.EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
        path = config.EVALUATION_DIR / "llm_judge_report.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n[LLM Judge] Report saved -> {path}")

    print(f"\n-- LLM Judge Aggregate Scores ---------------------------")
    for criterion, score in agg_scores.items():
        bar = "#" * int(score) + "." * (10 - int(score))
        print(f"  {criterion:<20} {bar} {score:.2f}/10")
    print(f"----------------------------------------------------------\n")

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run LLM-as-Judge evaluation")
    parser.add_argument("--questions", type=int, default=10, help="Number of questions")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between API calls")
    args = parser.parse_args()
    run_llm_judge_evaluation(
        questions=DEFAULT_JUDGE_QUESTIONS[:args.questions],
        delay=args.delay,
    )
