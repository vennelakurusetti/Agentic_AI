"""
Autonomous Recruitment Agent Controller.
Uses a ReAct-style loop to decide the next best action.
"""

import json
import os
from prompts.agent_prompt import AGENT_PROMPT
from tools.parse_resume import parse_resume as parse_resume_tool
from tools.score_candidate import score_candidate as score_candidate_tool
from tools.availability import get_availability
from tools.interview import schedule_interview, send_interview_invite
from models.schemas import ResumeData, ScoreCard, InterviewSlot, HiringRubric, JobDescription
from typing import Callable, Optional


class AgentContext:
    """Holds the state for the autonomous recruitment agent."""
    
    def __init__(self, jd_parsed: JobDescription, rubric: HiringRubric, candidates: list):
        self.jd_parsed = jd_parsed
        self.rubric = rubric
        self.remaining_candidates = list(candidates)  # list of (name, resume_text)
        self.processed_candidates = []  # list of (name, ResumeData, ScoreCard)
        self.shortlist = []  # list of (name, ScoreCard, InterviewSlot)
        self.parsed_resumes = {}  # name -> ResumeData
        self.scored_candidates = {}  # name -> ScoreCard
        self.available_slots = None
        self.pending_selected = []  # names of selected candidates awaiting interview
        self.done = False
    
    def get_remaining_names(self) -> str:
        if not self.remaining_candidates:
            return "None - all candidates processed"
        return ", ".join(name for name, _ in self.remaining_candidates)
    
    def get_processed_summary(self) -> str:
        if not self.processed_candidates:
            return "None"
        lines = []
        for name, rd, sc in self.processed_candidates:
            lines.append(f"  - {name}: score={sc.total_score:.2f}, decision={'SELECT' if sc.total_score >= 0.6 else 'REJECT'}")
        return "\n".join(lines)
    
    def get_shortlist_summary(self) -> str:
        if not self.shortlist:
            return "None"
        lines = []
        for name, sc, slot in self.shortlist:
            lines.append(f"  - {name}: score={sc.total_score:.2f}, interview={slot.date} {slot.time} ({slot.format})")
        return "\n".join(lines)


def run_autonomous_agent(
    jd_parsed: JobDescription,
    rubric: HiringRubric,
    candidates: list,
    llm_call: Callable,
    call_llm_raw: Callable,
) -> list:
    """
    Run the autonomous recruitment agent loop.
    
    Args:
        jd_parsed: Parsed job description
        rubric: Generated hiring rubric
        candidates: List of (candidate_name, resume_text) tuples
        llm_call: Function to call LLM with prompt
        call_llm_raw: Raw LLM call function (for tool calls)
    
    Returns:
        Final shortlist of (name, ScoreCard, InterviewSlot)
    """
    ctx = AgentContext(jd_parsed, rubric, candidates)
    
    print("\n" + "=" * 60)
    print("  AUTONOMOUS RECRUITMENT AGENT")
    print("  ReAct Loop - Deciding next best action")
    print("=" * 60)
    
    iteration = 0
    while not ctx.done and iteration < 15:
        iteration += 1
        
        # Build the agent prompt with current state
        jd_json = jd_parsed.model_dump_json(indent=2)
        rubric_json = rubric.model_dump_json(indent=2)
        
        # Count selected candidates (score >= 0.6)
        selected_count = sum(1 for sc in ctx.scored_candidates.values() if sc.total_score >= 0.6)
        availability_checked = "Yes" if ctx.available_slots is not None else "No"
        
        prompt = AGENT_PROMPT.format(
            step=iteration,
            parsed_count=len(ctx.parsed_resumes),
            scored_count=len(ctx.scored_candidates),
            selected_count=selected_count,
            interview_scheduled=len(ctx.shortlist),
            availability_checked=availability_checked,
            jd_parsed=jd_json,
            rubric=rubric_json,
            remaining_candidates=ctx.get_remaining_names(),
            processed_candidates=ctx.get_processed_summary(),
            shortlist=ctx.get_shortlist_summary(),
        )
        
        # Get agent decision
        response = llm_call(prompt)
        try:
            decision = json.loads(response)
        except json.JSONDecodeError:
            print(f"  [WARN] Agent returned invalid JSON, stopping.")
            break
        
        thought = decision.get("thought", "")
        next_tool = decision.get("tool", decision.get("next_tool", "done"))
        reason = decision.get("reason", "")
        arguments = decision.get("arguments", {})
        expected = decision.get("expected_observation", "")
        
        print(f"\n  Iteration {iteration}:")
        print(f"    Thought: {thought}")
        print(f"    Tool: {next_tool}")
        print(f"    Args: {json.dumps(arguments)[:100]}")
        print(f"    Expected: {expected[:80]}...")
        print(f"    Reason: {reason}")
        
        # Execute the chosen tool
        if next_tool == "parse_resume":
            if not ctx.remaining_candidates:
                print("    No remaining candidates to parse.")
                continue
            name, resume_text = ctx.remaining_candidates[0]
            print(f"    -> Parsing resume for: {name}")
            resume_data = parse_resume_tool(resume_text, call_llm_raw)
            ctx.parsed_resumes[name] = resume_data
            print(f"       Extracted: {resume_data.candidate_name}, {resume_data.experience_years}yr, {len(resume_data.skills)} skills")
        
        elif next_tool == "score_candidate":
            # Find a parsed but unscored candidate
            unscored = [n for n in ctx.parsed_resumes if n not in ctx.scored_candidates]
            if not unscored:
                print("    No parsed candidates to score.")
                continue
            name = unscored[0]
            resume_data = ctx.parsed_resumes[name]
            print(f"    -> Scoring candidate: {name}")
            score = score_candidate_tool(
                jd_parsed.model_dump_json(),
                resume_data.model_dump_json(),
                rubric.model_dump_json(),
                call_llm_raw,
            )
            ctx.scored_candidates[name] = score
            ctx.processed_candidates.append((name, resume_data, score))
            # Remove from remaining
            ctx.remaining_candidates = [(n, t) for n, t in ctx.remaining_candidates if n != name]
            print(f"       Score: {score.total_score:.2f}")
            
            # If selected, add to pending
            if score.total_score >= 0.6:
                ctx.pending_selected.append(name)
                print(f"       Decision: SELECT (threshold >= 0.6)")
            else:
                print(f"       Decision: REJECT (below threshold)")
        
        elif next_tool == "check_availability":
            if ctx.available_slots is not None:
                print("    Availability already checked.")
                continue
            print("    -> Checking interviewer availability")
            ctx.available_slots = get_availability()
            slots_data = json.loads(ctx.available_slots)
            print(f"       Found {len(slots_data.get('available_slots', []))} slots")
        
        elif next_tool == "propose_interview":
            if not ctx.pending_selected:
                print("    No selected candidates awaiting interview scheduling.")
                continue
            if ctx.available_slots is None:
                print("    Need to check availability first.")
                continue
            
            name = ctx.pending_selected[0]
            print(f"    -> Scheduling interview for: {name}")
            slot = schedule_interview(name, ctx.available_slots, call_llm_raw)
            invite_msg = send_interview_invite(slot)
            ctx.shortlist.append((name, ctx.scored_candidates[name], slot))
            ctx.pending_selected.pop(0)
            print(f"       {invite_msg}")
        
        elif next_tool == "done":
            print("    Agent signaled completion.")
            ctx.done = True
        
        else:
            print(f"    Unknown tool: {next_tool}, stopping.")
            ctx.done = True
    
    # Print final summary
    print("\n" + "=" * 60)
    print("  AGENT FINAL SHORTLIST")
    print("=" * 60)
    
    # Sort shortlist by score descending
    ctx.shortlist.sort(key=lambda x: x[1].total_score, reverse=True)
    
    if ctx.shortlist:
        print(f"\n  {'Rank':5s} {'Candidate':20s} {'Score':8s} {'Interview'}")
        print("  " + "-" * 55)
        for rank, (name, sc, slot) in enumerate(ctx.shortlist, 1):
            print(f"  {rank:<5d} {name:20s} {sc.total_score:.2f}    {slot.date} {slot.time}")
    else:
        print("\n  No candidates were selected.")
    
    print(f"\n  Processed: {len(ctx.processed_candidates)} candidates")
    print(f"  Shortlisted: {len(ctx.shortlist)} candidates")
    print("=" * 60)
    
    return ctx.shortlist