"""Quick test of the full pipeline - run from ai_recruitment_engine directory."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))

from graph.nodes import node_parse_jd, node_generate_rubric, node_create_plan
from graph.state import RecruitmentState
from app import call_llm
from tools.parse_resume import parse_resume as parse_resume_tool
from tools.score_candidate import score_candidate as score_candidate_tool
from tools.availability import get_availability
from tools.interview import schedule_interview, send_interview_invite
from models.schemas import FinalDecision

# Load test data
data_dir = os.path.join(os.path.dirname(__file__), "data")
jd_raw = open(os.path.join(data_dir, "jd.txt")).read()
priya = open(os.path.join(data_dir, "priya.txt")).read()
rahul = open(os.path.join(data_dir, "rahul.txt")).read()
meera = open(os.path.join(data_dir, "meera.txt")).read()

# Step 1: Parse JD
s = RecruitmentState(jd_raw=jd_raw, jd_parsed=None, resume_raw="", resume_parsed=None,
    score_card=None, decision=None, interview_slot=None, available_slots="{}",
    plan=[], candidate_name="", trajectory=[], error=None, rubric=None)
s = node_parse_jd(s, call_llm)
assert s.get("jd_parsed"), "JD parsing failed"
print(f"✓ JD parsed: {s['jd_parsed'].job_title}")

# Step 2: Generate rubric
s = node_generate_rubric(s, call_llm)
assert s.get("rubric"), "Rubric generation failed"
print(f"✓ Rubric: {len(s['rubric'].criteria)} criteria")

# Step 3: Create plan
s = node_create_plan(s, call_llm)
print(f"✓ Plan: {len(s.get('plan',[]))} steps")

# Step 4: Process each candidate
for name, rt in [("Priya Sharma", priya), ("Rahul Verma", rahul), ("Meera Patel", meera)]:
    rd = parse_resume_tool(rt, call_llm)
    assert rd.candidate_name, f"Failed to parse {name}"
    print(f"✓ Parsed: {rd.candidate_name}")
    
    sc = score_candidate_tool(
        s["jd_parsed"].model_dump_json(),
        rd.model_dump_json(),
        s["rubric"].model_dump_json(),
        call_llm
    )
    sc.candidate = name
    print(f"  Score: {sc.total_score:.2f}")
    
    from prompts.decision_prompt import DECISION_PROMPT
    r = json.loads(call_llm(DECISION_PROMPT.format(score_card=sc.model_dump_json())))
    dec = FinalDecision(**r)
    print(f"  Decision: {dec.decision}")
    
    if dec.decision == "SELECT":
        from prompts.guardrail_prompt import GUARDRAIL_PROMPT
        g = json.loads(call_llm(GUARDRAIL_PROMPT.format(decision=dec.model_dump_json())))
        print(f"  Guardrail: {'Passed' if g.get('is_safe') else 'WARNING'}")
        
        av = get_availability()
        sl = schedule_interview(name, av, call_llm)
        print(f"  Slot: {sl.date} {sl.time}")
        invite = send_interview_invite(sl)
        print(f"  Invite: {invite}")

print("\n✅ FULL PIPELINE TEST PASSED")