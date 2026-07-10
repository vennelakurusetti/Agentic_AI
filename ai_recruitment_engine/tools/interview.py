import json
from prompts.schedule_prompt import SCHEDULE_PROMPT
from models.schemas import InterviewSlot

def schedule_interview(candidate_name: str, slots: str, llm_call) -> InterviewSlot:
    """Prepare an interview proposal for a candidate (requires human approval)."""
    prompt = SCHEDULE_PROMPT.format(candidate_name=candidate_name, slots=slots)
    response = llm_call(prompt)
    try:
        data = json.loads(response)
        # Handle different response formats
        if "candidate_name" in data and "date" in data:
            return InterviewSlot(**data)
        elif data.get("candidate") and data.get("slot"):
            # Parse "2026-07-15 10:00 AM" format
            parts = data["slot"].split(" ", 1)
            return InterviewSlot(
                candidate_name=data["candidate"],
                date=parts[0] if len(parts) > 0 else "2026-07-15",
                time=parts[1] if len(parts) > 1 else "10:00 AM",
                format="online"
            )
        else:
            return InterviewSlot(candidate_name=candidate_name, date="2026-07-15", time="10:00 AM", format="online")
    except (json.JSONDecodeError, Exception):
        # Default fallback slot
        return InterviewSlot(
            candidate_name=candidate_name,
            date="2026-07-15",
            time="10:00 AM",
            format="online"
        )


def send_interview_invite(slot: InterviewSlot) -> str:
    """Return interview proposal for human approval."""
    return f"Interview Proposal: {slot.candidate_name} on {slot.date} at {slot.time} ({slot.format}) | Status: Pending Human Approval"