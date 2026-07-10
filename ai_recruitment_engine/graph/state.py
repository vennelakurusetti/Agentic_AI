from typing import TypedDict, List, Optional, Any
from models.schemas import JobDescription, ResumeData, ScoreCard, InterviewSlot, FinalDecision, HiringRubric

class TrajectoryEntry(TypedDict):
    """Structured trajectory entry with full step details."""
    thought: str
    tool_used: str
    arguments: dict
    observation: str
    state_changes: dict
    decision: str

class RecruitmentState(TypedDict):
    """State for the recruitment agent graph."""
    jd_raw: str                      # Raw job description text
    jd_parsed: Optional[JobDescription]  # Parsed JD
    resume_raw: str                  # Raw resume text
    resume_parsed: Optional[ResumeData]  # Parsed resume
    score_card: Optional[ScoreCard]  # Candidate score
    decision: Optional[FinalDecision]  # Final decision
    interview_slot: Optional[InterviewSlot]  # Scheduled interview
    available_slots: str             # Available interview slots
    plan: List[str]                  # Execution plan
    candidate_name: str              # Candidate name
    trajectory: List[Any]            # Execution log (TrajectoryEntry dicts)
    error: Optional[str]             # Error message if any
    rubric: Optional[HiringRubric]   # Generated hiring rubric
