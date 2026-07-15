"""
LangGraph node functions for the recruitment pipeline.

Each node:
  - Accepts a RecruitmentState dict
  - Returns a partial state dict with updated fields
  - Appends a structured trajectory entry
"""

import json
from typing import Any, Callable

from graph.state import RecruitmentState
from models.schemas import (
    JobDescription,
    FinalDecision,
    HiringRubric,
    RubricCriterion,
)
from tools.parse_resume import parse_resume as parse_resume_tool
from tools.score_candidate import score_candidate
from tools.availability import get_availability
from tools.interview import schedule_interview as schedule_interview_tool
from prompts.jd_prompt import JD_ANALYSIS_PROMPT
from prompts.planner_prompt import PLANNER_PROMPT
from prompts.decision_prompt import DECISION_PROMPT
from prompts.guardrail_prompt import GUARDRAIL_PROMPT
from prompts.rubric_prompt import RUBRIC_PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _make_traj_entry(
    thought: str,
    tool_used: str,
    arguments: dict,
    observation: str,
    state_changes: dict,
    decision: str = "",
) -> dict:
    """Create a structured trajectory entry."""
    return {
        "thought": thought,
        "tool_used": tool_used,
        "arguments": arguments,
        "observation": observation,
        "state_changes": state_changes,
        "decision": decision,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Nodes
# ─────────────────────────────────────────────────────────────────────────────

def node_parse_jd(state: RecruitmentState, llm_call: Callable) -> dict:
    """Parse the job description into structured JobDescription data."""
    trajectory = list(state.get("trajectory", []))

    if state.get("jd_parsed") is not None:
        trajectory.append(_make_traj_entry(
            thought="JD already parsed — skipping.",
            tool_used="parse_jd",
            arguments={},
            observation="Skipped — JD already parsed",
            state_changes={},
            decision="SKIP",
        ))
        return {**state, "trajectory": trajectory}

    prompt = JD_ANALYSIS_PROMPT.format(jd=state["jd_raw"])
    response = llm_call(prompt)

    try:
        data = json.loads(response)
        jd_parsed = JobDescription(**data)
        trajectory.append(_make_traj_entry(
            thought="Analyse JD to extract structured hiring requirements.",
            tool_used="parse_jd",
            arguments={"jd_raw_length": len(state["jd_raw"])},
            observation=f"Parsed JD: {jd_parsed.job_title}",
            state_changes={"jd_parsed": {"from": None, "to": jd_parsed.job_title}},
            decision="PARSED",
        ))
        return {**state, "jd_parsed": jd_parsed, "trajectory": trajectory, "error": None}
    except Exception as e:
        trajectory.append(_make_traj_entry(
            thought="JD parsing failed.",
            tool_used="parse_jd",
            arguments={},
            observation=f"Failed to parse JD: {e}",
            state_changes={},
            decision="ERROR",
        ))
        return {**state, "trajectory": trajectory, "error": f"JD parse error: {e}"}


def node_generate_rubric(state: RecruitmentState, llm_call: Callable) -> dict:
    """Generate an objective scoring rubric from the parsed JD."""
    trajectory = list(state.get("trajectory", []))

    jd_parsed_json = (
        state["jd_parsed"].model_dump_json() if state.get("jd_parsed") else "{}"
    )
    prompt = RUBRIC_PROMPT.format(jd_parsed=jd_parsed_json, jd_raw=state["jd_raw"])
    response = llm_call(prompt)

    try:
        data = json.loads(response)
        criteria_list = [RubricCriterion(**c) for c in data.get("criteria", [])]
        total_w = sum(c.weight for c in criteria_list)
        rubric = HiringRubric(criteria=criteria_list, total_weight=total_w)
        trajectory.append(_make_traj_entry(
            thought="Generate objective scoring criteria from JD requirements.",
            tool_used="generate_rubric",
            arguments={"jd_title": state["jd_parsed"].job_title if state.get("jd_parsed") else ""},
            observation=f"Generated rubric: {len(criteria_list)} criteria (total weight: {total_w})",
            state_changes={"rubric": {"from": None, "to": f"{len(criteria_list)} criteria, weight={total_w}"}},
            decision="RUBRIC_READY",
        ))
        return {**state, "rubric": rubric, "trajectory": trajectory}
    except Exception as e:
        trajectory.append(_make_traj_entry(
            thought="Rubric generation failed.",
            tool_used="generate_rubric",
            arguments={},
            observation=f"Rubric error: {e}",
            state_changes={},
            decision="ERROR",
        ))
        return {**state, "trajectory": trajectory, "error": f"Rubric error: {e}"}


def node_create_plan(state: RecruitmentState, llm_call: Callable) -> dict:
    """Create a step-by-step evaluation plan for the candidate."""
    trajectory = list(state.get("trajectory", []))

    jd_json = (
        state["jd_parsed"].model_dump_json() if state.get("jd_parsed") else state["jd_raw"]
    )
    prompt = PLANNER_PROMPT.format(jd=jd_json, resume=state["resume_raw"])
    response = llm_call(prompt)

    try:
        data = json.loads(response)
        plan = data.get("plan", [])
        trajectory.append(_make_traj_entry(
            thought="Create step-by-step evaluation plan for this candidate.",
            tool_used="create_plan",
            arguments={"jd": "parsed", "resume": "loaded"},
            observation=f"Created plan with {len(plan)} steps",
            state_changes={"plan": {"from": "[]", "to": f"{len(plan)} steps"}},
            decision="PLANNED",
        ))
        return {**state, "plan": plan, "trajectory": trajectory}
    except Exception as e:
        trajectory.append(_make_traj_entry(
            thought="Plan creation failed.",
            tool_used="create_plan",
            arguments={},
            observation=f"Plan error: {e}",
            state_changes={},
            decision="ERROR",
        ))
        return {**state, "plan": [], "trajectory": trajectory}


def node_parse_resume(state: RecruitmentState, llm_call: Callable) -> dict:
    """Parse the candidate resume into structured ResumeData."""
    trajectory = list(state.get("trajectory", []))

    resume_data = parse_resume_tool(state["resume_raw"], llm_call)
    trajectory.append(_make_traj_entry(
        thought="Extract structured information from resume text.",
        tool_used="parse_resume",
        arguments={"resume_length": len(state["resume_raw"])},
        observation=f"Parsed resume for: {resume_data.candidate_name}",
        state_changes={
            "resume_parsed": {"from": None, "to": resume_data.candidate_name},
            "candidate_name": {"from": "", "to": resume_data.candidate_name},
        },
        decision="PARSED",
    ))
    return {
        **state,
        "resume_parsed": resume_data,
        "candidate_name": resume_data.candidate_name,
        "trajectory": trajectory,
    }


def node_score_candidate(state: RecruitmentState, llm_call: Callable) -> dict:
    """Score the candidate against the JD rubric."""
    trajectory = list(state.get("trajectory", []))

    jd_json = state["jd_parsed"].model_dump_json() if state.get("jd_parsed") else state["jd_raw"]
    resume_json = (
        state["resume_parsed"].model_dump_json() if state.get("resume_parsed") else state["resume_raw"]
    )
    rubric_json = state["rubric"].model_dump_json() if state.get("rubric") else "{}"

    sc = score_candidate(jd_json, resume_json, rubric_json, llm_call)
    trajectory.append(_make_traj_entry(
        thought="Evaluate candidate against JD requirements and rubric.",
        tool_used="score_candidate",
        arguments={
            "jd": "parsed",
            "resume": "parsed",
            "rubric_criteria": len(state["rubric"].criteria) if state.get("rubric") else 0,
        },
        observation=f"Scored {sc.candidate}: {sc.total_score:.4f}",
        state_changes={"score_card": {"from": None, "to": f"score={sc.total_score:.4f}"}},
        decision=f"SCORE={sc.total_score:.4f}",
    ))
    return {**state, "score_card": sc, "trajectory": trajectory}


def node_make_decision(state: RecruitmentState, llm_call: Callable) -> dict:
    """Make the final SELECT / HOLD / REJECT decision."""
    trajectory = list(state.get("trajectory", []))

    score_json = state["score_card"].model_dump_json() if state.get("score_card") else "{}"
    prompt = DECISION_PROMPT.format(score_card=score_json)
    response = llm_call(prompt)

    try:
        data = json.loads(response)
        decision = FinalDecision(**data)

        # ── Threshold enforcement as safety net ──────────────────────────
        total = state["score_card"].total_score if state.get("score_card") else 0.0
        if total < 0.40 and decision.decision != "REJECT":
            decision.decision = "REJECT"
            decision.reason = (
                f"Score {total:.2f} is below 40% threshold — overridden to REJECT. "
                + decision.reason
            )
        elif 0.40 <= total < 0.60 and decision.decision not in ("HOLD", "REJECT"):
            decision.decision = "HOLD"
            decision.reason = (
                f"Score {total:.2f} is in the 40–60% borderline range — overridden to HOLD. "
                + decision.reason
            )

        trajectory.append(_make_traj_entry(
            thought="Evaluate scorecard to determine candidate disposition.",
            tool_used="make_decision",
            arguments={"scorecard_score": f"{total:.4f}"},
            observation=f"Decision for {decision.candidate_name}: {decision.decision}",
            state_changes={"decision": {"from": None, "to": f"{decision.decision}: {decision.reason[:60]}"}},
            decision=decision.decision,
        ))
        return {**state, "decision": decision, "trajectory": trajectory}
    except Exception as e:
        trajectory.append(_make_traj_entry(
            thought="Decision step failed.",
            tool_used="make_decision",
            arguments={},
            observation=f"Decision error: {e}",
            state_changes={},
            decision="ERROR",
        ))
        return {**state, "trajectory": trajectory, "error": f"Decision error: {e}"}


def node_check_availability(state: RecruitmentState, llm_call: Callable) -> dict:
    """Check available interview slots."""
    trajectory = list(state.get("trajectory", []))

    slots_json = get_availability()
    slots_data = json.loads(slots_json)
    slot_count = len(slots_data.get("available_slots", []))

    trajectory.append(_make_traj_entry(
        thought="Selected candidate needs an interview slot. Checking interviewer availability.",
        tool_used="check_availability",
        arguments={},
        observation=f"Found {slot_count} available slot(s)",
        state_changes={"available_slots": {"from": "not_checked", "to": f"{slot_count} slots"}},
        decision="AVAILABLE",
    ))
    return {**state, "available_slots": slots_json, "trajectory": trajectory}


def node_schedule_interview(state: RecruitmentState, llm_call: Callable) -> dict:
    """Prepare an interview proposal (requires human approval in the UI)."""
    trajectory = list(state.get("trajectory", []))

    slot = schedule_interview_tool(
        state["candidate_name"],
        state.get("available_slots", "{}"),
        llm_call,
    )
    trajectory.append(_make_traj_entry(
        thought="Availability confirmed. Propose an interview slot for the selected candidate.",
        tool_used="propose_interview",
        arguments={"candidate": state["candidate_name"], "slot": f"{slot.date} {slot.time}"},
        observation=f"Interview proposal for {slot.candidate_name}: {slot.date} {slot.time} — PENDING HUMAN APPROVAL",
        state_changes={"interview_slot": {"from": None, "to": f"{slot.date} {slot.time}"}},
        decision="PROPOSED_PENDING_APPROVAL",
    ))
    return {**state, "interview_slot": slot, "trajectory": trajectory}


def node_guardrail_check(state: RecruitmentState, llm_call: Callable) -> dict:
    """Run safety, fairness, and bias guardrail check on the decision."""
    trajectory = list(state.get("trajectory", []))

    decision_json = state["decision"].model_dump_json() if state.get("decision") else "{}"
    prompt = GUARDRAIL_PROMPT.format(decision=decision_json)
    response = llm_call(prompt)

    try:
        data = json.loads(response)
        is_safe: bool = bool(data.get("is_safe", True))
        reason: str = data.get("reason", "OK")
        issues: list = data.get("issues", [])

        trajectory.append(_make_traj_entry(
            thought="Verify decision is safe, fair, and compliant with hiring regulations.",
            tool_used="guardrail_check",
            arguments={
                "decision": state["decision"].decision if state.get("decision") else "unknown",
            },
            observation=f"Guardrail {'PASSED' if is_safe else 'FLAGGED'}: {reason}",
            state_changes={},
            decision="PASSED" if is_safe else "FLAGGED",
        ))
        # Store guardrail result in state for downstream use
        return {
            **state,
            "trajectory": trajectory,
            "guardrail_passed": is_safe,
            "guardrail_reason": reason,
            "guardrail_issues": issues,
        }
    except Exception as e:
        trajectory.append(_make_traj_entry(
            thought="Guardrail check failed.",
            tool_used="guardrail_check",
            arguments={},
            observation=f"Guardrail check error: {e}",
            state_changes={},
            decision="ERROR",
        ))
        return {**state, "trajectory": trajectory, "guardrail_passed": True, "guardrail_reason": "", "guardrail_issues": []}


# ─────────────────────────────────────────────────────────────────────────────
# Conditional edge
# ─────────────────────────────────────────────────────────────────────────────

def should_schedule(state: RecruitmentState) -> str:
    """Route to interview scheduling only for SELECT decisions that passed guardrails."""
    decision = state.get("decision")
    guardrail_ok = state.get("guardrail_passed", True)
    if decision and decision.decision == "SELECT" and guardrail_ok:
        return "schedule"
    return "skip"
