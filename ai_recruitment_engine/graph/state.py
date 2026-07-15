"""
LangGraph state definition for the recruitment pipeline.
"""

from typing import Any, List, Optional, TypedDict

from models.schemas import (
    FinalDecision,
    HiringRubric,
    InterviewSlot,
    JobDescription,
    ResumeData,
    ScoreCard,
)


class TrajectoryEntry(TypedDict):
    """One step in the execution trajectory."""
    thought: str
    tool_used: str
    arguments: dict
    observation: str
    state_changes: dict
    decision: str


class RecruitmentState(TypedDict, total=False):
    """Full state passed through every node in the recruitment graph."""

    # ── Input ────────────────────────────────────────────────────────────
    jd_raw: str                          # Raw job description text
    resume_raw: str                      # Raw resume text

    # ── Parsed data ──────────────────────────────────────────────────────
    jd_parsed: Optional[JobDescription]  # Structured JD
    resume_parsed: Optional[ResumeData]  # Structured resume
    rubric: Optional[HiringRubric]       # Generated scoring rubric
    plan: List[str]                      # Agent evaluation plan

    # ── Per-candidate outputs ─────────────────────────────────────────────
    candidate_name: str
    score_card: Optional[ScoreCard]
    decision: Optional[FinalDecision]

    # ── Guardrail results ────────────────────────────────────────────────
    guardrail_passed: bool               # True = safe, False = flagged
    guardrail_reason: str                # Human-readable summary
    guardrail_issues: List[str]          # Specific violation strings

    # ── Interview ────────────────────────────────────────────────────────
    available_slots: str                 # JSON string of available slots
    interview_slot: Optional[InterviewSlot]

    # ── Execution metadata ───────────────────────────────────────────────
    trajectory: List[Any]                # List of TrajectoryEntry dicts
    error: Optional[str]                 # Last error message
