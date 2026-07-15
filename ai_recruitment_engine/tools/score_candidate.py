"""
Candidate scorer tool.
Calls the LLM with injection-protected prompt, then normalises total_score
to guarantee a 0.0–1.0 float regardless of what the LLM returns.
"""

import json
from typing import Callable

from tools.sanitizer import SafePromptWrapper
from prompts.scorer_prompt import SCORER_PROMPT
from models.schemas import ScoreCard, CriterionScore


def _normalise_total_score(raw: float, criteria: list[CriterionScore]) -> float:
    """
    Normalise total_score to 0.0–1.0.

    Priority order:
    1. If raw is already in 0–1 range → use as-is.
    2. If raw is in 1–100 range (LLM returned a percentage) → divide by 100.
    3. Recompute from criteria as fallback:
         sum(score_i * weight_i) / (5 * 100)
    """
    if 0.0 <= raw <= 1.0:
        return round(raw, 4)

    if 1.0 < raw <= 100.0:
        return round(raw / 100.0, 4)

    # Fallback: recompute from criteria
    if criteria:
        total = sum(c.score * c.weight for c in criteria)
        denom = 5.0 * 100.0  # max score per criterion * weight denominator
        return round(min(total / denom, 1.0), 4)

    return 0.0


def score_candidate(
    jd_json: str,
    resume_data_json: str,
    rubric_json: str,
    llm_call: Callable,
) -> ScoreCard:
    """
    Score a candidate against JD requirements using the rubric.

    SECURITY: Resume-derived data is UNTRUSTED. The scoring prompt is wrapped
    with injection protection to prevent resume text from influencing scores,
    changing weights, or overriding the rubric.

    Returns a ScoreCard with total_score guaranteed to be in [0.0, 1.0].
    """
    raw_prompt = SCORER_PROMPT.format(
        jd=jd_json,
        resume_data=resume_data_json,
        rubric=rubric_json,
    )
    safe_prompt = SafePromptWrapper.wrap_scoring(raw_prompt)
    response = llm_call(safe_prompt)

    try:
        data = json.loads(response)

        # Build CriterionScore objects
        criteria_list: list[CriterionScore] = []
        for c in data.get("criteria", []):
            criteria_list.append(CriterionScore(**c))
        data["criteria"] = criteria_list

        scorecard = ScoreCard(**data)

        # ── Guarantee normalised total_score ──────────────────────────────
        scorecard.total_score = _normalise_total_score(
            float(scorecard.total_score), scorecard.criteria
        )
        return scorecard

    except (json.JSONDecodeError, Exception):
        return ScoreCard(candidate="Unknown", recommendation="Hold")
