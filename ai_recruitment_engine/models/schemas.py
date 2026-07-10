from pydantic import BaseModel, Field
from typing import List, Optional

class JobDescription(BaseModel):
    job_title: str = ""
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    minimum_education: str = ""
    minimum_experience: str = ""
    responsibilities: List[str] = Field(default_factory=list)
    communication_required: bool = False
    weight_suggestions: List[str] = Field(default_factory=list)

class ResumeData(BaseModel):
    candidate_name: str = ""
    skills: List[str] = Field(default_factory=list)
    education: List[str] = Field(default_factory=list)
    experience_years: int = 0
    experience_details: List[str] = Field(default_factory=list)
    projects: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    communication_evidence: str = ""
    resume_lines: List[str] = Field(default_factory=list)

class CriterionScore(BaseModel):
    name: str = ""
    score: int = 0
    weight: int = 0
    evidence: str = ""

class ScoreCard(BaseModel):
    candidate: str = ""
    criteria: list[CriterionScore] = []
    total_score: float = 0.0
    strengths: list[str] = []
    gaps: list[str] = []
    recommendation: str = "Hold"

class InterviewSlot(BaseModel):
    candidate_name: str = ""
    date: str = ""
    time: str = ""
    format: str = ""  # "online" or "offline"

class FinalDecision(BaseModel):
    candidate_name: str = ""
    decision: str = ""  # "SELECT" or "REJECT"
    reason: str = ""

class PlannerOutput(BaseModel):
    plan: List[str] = Field(default_factory=list)

class GuardrailCheck(BaseModel):
    is_safe: bool = True
    reason: str = ""

class RubricCriterion(BaseModel):
    name: str = ""
    weight: int = 0
    description: str = ""
    evidence: str = ""
    levels: dict = {}

class HiringRubric(BaseModel):
    criteria: list[RubricCriterion] = []
    total_weight: int = 0
