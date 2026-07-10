import json
from tools.sanitizer import SafePromptWrapper
from prompts.scorer_prompt import SCORER_PROMPT
from models.schemas import ScoreCard, CriterionScore

def score_candidate(jd_json: str, resume_data_json: str, rubric_json: str, llm_call) -> ScoreCard:
    """Score a candidate against JD requirements using rubric.
    
    SECURITY: Resume-derived data is UNTRUSTED. The scoring prompt is wrapped
    with injection protection to prevent resume text from influencing scores,
    changing weights, or overriding the rubric.
    """
    raw_prompt = SCORER_PROMPT.format(jd=jd_json, resume_data=resume_data_json, rubric=rubric_json)
    safe_prompt = SafePromptWrapper.wrap_scoring(raw_prompt)
    response = llm_call(safe_prompt)
    try:
        data = json.loads(response)
        # Parse criteria into CriterionScore objects
        criteria_list = []
        for c in data.get("criteria", []):
            criteria_list.append(CriterionScore(**c))
        data["criteria"] = criteria_list
        return ScoreCard(**data)
    except (json.JSONDecodeError, Exception) as e:
        return ScoreCard(candidate="Unknown", recommendation="Hold")
