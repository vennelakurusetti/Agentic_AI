import json
from graph.state import RecruitmentState
from models.schemas import JobDescription, FinalDecision, HiringRubric, RubricCriterion
from tools.parse_resume import parse_resume as parse_resume_tool
from tools.score_candidate import score_candidate
from tools.availability import get_availability
from tools.interview import schedule_interview as schedule_interview_tool
from prompts.jd_prompt import JD_ANALYSIS_PROMPT
from prompts.planner_prompt import PLANNER_PROMPT
from prompts.decision_prompt import DECISION_PROMPT
from prompts.guardrail_prompt import GUARDRAIL_PROMPT
from prompts.rubric_prompt import RUBRIC_PROMPT
from typing import Any, Callable


def _make_traj_entry(thought: str, tool_used: str, arguments: dict, observation: str, state_changes: dict, decision: str = "") -> dict:
    """Helper to create a structured trajectory entry."""
    return {
        "thought": thought,
        "tool_used": tool_used,
        "arguments": arguments,
        "observation": observation,
        "state_changes": state_changes,
        "decision": decision,
    }


def node_parse_jd(state: RecruitmentState, llm_call: Callable) -> RecruitmentState:
    """Parse the job description into structured data."""
    trajectory = list(state.get("trajectory", []))
    
    if state.get("jd_parsed") is not None:
        trajectory.append(_make_traj_entry(
            thought="JD already parsed.",
            tool_used="parse_jd",
            arguments={},
            observation="Skipped - JD already parsed",
            state_changes={},
            decision="SKIP"
        ))
        return {**state, "trajectory": trajectory}
    
    prompt = JD_ANALYSIS_PROMPT.format(jd=state["jd_raw"])
    response = llm_call(prompt)
    
    try:
        data = json.loads(response)
        jd_parsed = JobDescription(**data)
        trajectory.append(_make_traj_entry(
            thought=f"Analyze JD to extract structured requirements",
            tool_used="parse_jd",
            arguments={"jd_raw_length": len(state["jd_raw"])},
            observation=f"Parsed JD: {jd_parsed.job_title}",
            state_changes={"jd_parsed": {"from": None, "to": jd_parsed.job_title}},
            decision="PARSED"
        ))
        return {**state, "jd_parsed": jd_parsed, "trajectory": trajectory, "error": None}
    except (json.JSONDecodeError, Exception) as e:
        trajectory.append(_make_traj_entry(
            thought="JD parsing failed",
            tool_used="parse_jd",
            arguments={},
            observation=f"Failed to parse JD: {str(e)}",
            state_changes={},
            decision="ERROR"
        ))
        return {**state, "trajectory": trajectory, "error": f"JD parse error: {str(e)}"}


def node_create_plan(state: RecruitmentState, llm_call: Callable) -> RecruitmentState:
    """Create an evaluation plan."""
    trajectory = list(state.get("trajectory", []))
    
    jd_json = state["jd_parsed"].model_dump_json() if state.get("jd_parsed") else state["jd_raw"]
    prompt = PLANNER_PROMPT.format(jd=jd_json, resume=state["resume_raw"])
    response = llm_call(prompt)
    
    try:
        data = json.loads(response)
        plan = data.get("plan", [])
        trajectory.append(_make_traj_entry(
            thought="Create step-by-step evaluation plan",
            tool_used="create_plan",
            arguments={"jd": "parsed", "resume": "loaded"},
            observation=f"Created plan: {len(plan)} steps",
            state_changes={"plan": {"from": "[]", "to": f"{len(plan)} steps"}},
            decision="PLANNED"
        ))
        return {**state, "plan": plan, "trajectory": trajectory}
    except (json.JSONDecodeError, Exception) as e:
        trajectory.append(_make_traj_entry(
            thought="Plan creation needed",
            tool_used="create_plan",
            arguments={},
            observation=f"Plan creation failed: {str(e)}",
            state_changes={},
            decision="ERROR"
        ))
        return {**state, "plan": [], "trajectory": trajectory}


def node_parse_resume(state: RecruitmentState, llm_call: Callable) -> RecruitmentState:
    """Parse the resume into structured data."""
    trajectory = list(state.get("trajectory", []))
    
    resume_data = parse_resume_tool(state["resume_raw"], llm_call)
    trajectory.append(_make_traj_entry(
        thought="Extract structured information from resume",
        tool_used="parse_resume",
        arguments={"resume_length": len(state["resume_raw"])},
        observation=f"Parsed resume for: {resume_data.candidate_name}",
        state_changes={
            "resume_parsed": {"from": None, "to": f"{resume_data.candidate_name}"},
            "candidate_name": {"from": "", "to": resume_data.candidate_name}
        },
        decision="PARSED"
    ))
    
    return {
        **state,
        "resume_parsed": resume_data,
        "candidate_name": resume_data.candidate_name,
        "trajectory": trajectory,
    }


def node_score_candidate(state: RecruitmentState, llm_call: Callable) -> RecruitmentState:
    """Score the candidate against JD."""
    trajectory = list(state.get("trajectory", []))
    
    jd_json = state["jd_parsed"].model_dump_json() if state.get("jd_parsed") else state["jd_raw"]
    resume_json = state["resume_parsed"].model_dump_json() if state.get("resume_parsed") else state["resume_raw"]
    rubric_json = state["rubric"].model_dump_json() if state.get("rubric") else "{}"
    
    score = score_candidate(jd_json, resume_json, rubric_json, llm_call)
    trajectory.append(_make_traj_entry(
        thought=f"Evaluate candidate against JD requirements and rubric",
        tool_used="score_candidate",
        arguments={"jd": "parsed", "resume": "parsed", "rubric": f"{len(state.get('rubric',{}).criteria or [])} criteria"},
        observation=f"Scored {score.candidate}: {score.total_score:.2f}",
        state_changes={
            "score_card": {"from": None, "to": f"score={score.total_score:.2f}"}
        },
        decision=f"SCORE={score.total_score:.2f}"
    ))
    
    return {**state, "score_card": score, "trajectory": trajectory}


def node_make_decision(state: RecruitmentState, llm_call: Callable) -> RecruitmentState:
    """Make final decision on candidate."""
    trajectory = list(state.get("trajectory", []))
    
    score_json = state["score_card"].model_dump_json() if state.get("score_card") else "{}"
    prompt = DECISION_PROMPT.format(score_card=score_json)
    response = llm_call(prompt)
    
    try:
        data = json.loads(response)
        decision = FinalDecision(**data)
        trajectory.append(_make_traj_entry(
            thought=f"Evaluate scorecard to determine candidate disposition",
            tool_used="make_decision",
            arguments={"scorecard": f"score={state['score_card'].total_score:.2f}"},
            observation=f"Decision for {decision.candidate_name}: {decision.decision}",
            state_changes={
                "decision": {"from": None, "to": f"{decision.decision}: {decision.reason[:50]}..."}
            },
            decision=decision.decision
        ))
        return {**state, "decision": decision, "trajectory": trajectory}
    except (json.JSONDecodeError, Exception) as e:
        trajectory.append(_make_traj_entry(
            thought="Decision needed",
            tool_used="make_decision",
            arguments={},
            observation=f"Decision failed: {str(e)}",
            state_changes={},
            decision="ERROR"
        ))
        return {**state, "trajectory": trajectory, "error": f"Decision error: {str(e)}"}


def node_check_availability(state: RecruitmentState, llm_call: Callable) -> RecruitmentState:
    """Check interviewer availability."""
    trajectory = list(state.get("trajectory", []))
    
    slots = get_availability()
    trajectory.append(_make_traj_entry(
        thought="Selected candidate needs interview slot. Check interviewer availability.",
        tool_used="check_availability",
        arguments={},
        observation="Checked interviewer availability",
        state_changes={
            "available_slots": {"from": "not_checked", "to": "available"}
        },
        decision="AVAILABLE"
    ))
    
    return {**state, "available_slots": slots, "trajectory": trajectory}


def node_schedule_interview(state: RecruitmentState, llm_call: Callable) -> RecruitmentState:
    """Prepare interview proposal for selected candidates (requires human approval)."""
    trajectory = list(state.get("trajectory", []))
    
    slot = schedule_interview_tool(
        state["candidate_name"],
        state.get("available_slots", "{}"),
        llm_call
    )
    trajectory.append(_make_traj_entry(
        thought=f"Availability known. Prepare interview proposal for selected candidate.",
        tool_used="propose_interview",
        arguments={"candidate": state["candidate_name"], "slot": f"{slot.date} {slot.time}"},
        observation=f"Interview proposal for {slot.candidate_name}: {slot.date} {slot.time} (Pending Human Approval)",
        state_changes={
            "interview_slot": {"from": None, "to": f"{slot.date} {slot.time}"}
        },
        decision="PROPOSED_PENDING_APPROVAL"
    ))
    
    return {**state, "interview_slot": slot, "trajectory": trajectory}


def node_guardrail_check(state: RecruitmentState, llm_call: Callable) -> RecruitmentState:
    """Perform guardrail check on the decision."""
    trajectory = list(state.get("trajectory", []))
    
    decision_json = state["decision"].model_dump_json() if state.get("decision") else "{}"
    prompt = GUARDRAIL_PROMPT.format(decision=decision_json)
    response = llm_call(prompt)
    
    try:
        data = json.loads(response)
        is_safe = data.get("is_safe", True)
        reason = data.get("reason", "OK")
        trajectory.append(_make_traj_entry(
            thought="Verify decision is safe, fair, and compliant",
            tool_used="guardrail_check",
            arguments={"decision": state["decision"].decision if state.get("decision") else "unknown"},
            observation=f"Guardrail {'passed' if is_safe else 'WARNING'}: {reason}",
            state_changes={},
            decision="PASSED" if is_safe else "FLAGGED"
        ))
        return {**state, "trajectory": trajectory}
    except (json.JSONDecodeError, Exception) as e:
        trajectory.append(_make_traj_entry(
            thought="Guardrail check needed",
            tool_used="guardrail_check",
            arguments={},
            observation=f"Guardrail check failed: {str(e)}",
            state_changes={},
            decision="ERROR"
        ))
        return {**state, "trajectory": trajectory}


def node_generate_rubric(state: RecruitmentState, llm_call: Callable) -> RecruitmentState:
    """Generate an objective hiring rubric from the JD."""
    trajectory = list(state.get("trajectory", []))
    
    jd_parsed_json = state["jd_parsed"].model_dump_json() if state.get("jd_parsed") else "{}"
    prompt = RUBRIC_PROMPT.format(jd_parsed=jd_parsed_json, jd_raw=state["jd_raw"])
    response = llm_call(prompt)
    
    try:
        data = json.loads(response)
        criteria_list = []
        total_w = 0
        for c in data.get("criteria", []):
            criterion = RubricCriterion(**c)
            criteria_list.append(criterion)
            total_w += criterion.weight
        rubric = HiringRubric(criteria=criteria_list, total_weight=total_w)
        trajectory.append(_make_traj_entry(
            thought="Generate objective scoring criteria from JD requirements",
            tool_used="generate_rubric",
            arguments={"jd": state["jd_parsed"].job_title},
            observation=f"Generated rubric: {len(criteria_list)} criteria (total weight: {total_w})",
            state_changes={
                "rubric": {"from": None, "to": f"{len(criteria_list)} criteria, weight={total_w}"}
            },
            decision="RUBRIC_READY"
        ))
        return {**state, "rubric": rubric, "trajectory": trajectory}
    except (json.JSONDecodeError, Exception) as e:
        trajectory.append(_make_traj_entry(
            thought="Rubric generation needed for objective scoring",
            tool_used="generate_rubric",
            arguments={},
            observation=f"Rubric generation failed: {str(e)}",
            state_changes={},
            decision="ERROR"
        ))
        return {**state, "trajectory": trajectory, "error": f"Rubric error: {str(e)}"}


def should_schedule(state: RecruitmentState) -> str:
    """Conditional edge: schedule only if selected."""
    if state.get("decision") and state["decision"].decision == "SELECT":
        return "schedule"
    return "skip"
