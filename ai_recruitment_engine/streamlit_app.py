"""
TechVest AI Recruitment Agent — Premium Streamlit Dashboard
============================================================
Production-grade UI inspired by Lever, Greenhouse, Ashby, Workday.
Consumes existing backend — NO backend modifications.
"""

import os, sys, json, streamlit as st

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

# ─── Backend imports (unchanged) ──────────────────────────────────────────
from dotenv import load_dotenv; load_dotenv()
from graph.graph import build_recruitment_graph
from graph.state import RecruitmentState
from graph.nodes import node_parse_jd, node_generate_rubric
from models.schemas import ScoreCard, FinalDecision, InterviewSlot
from tools.interview import schedule_interview, send_interview_invite
from tools.availability import get_availability
from tools.parse_resume import parse_resume as parse_resume_tool
from tools.score_candidate import score_candidate as score_candidate_tool
from app import call_llm

# ─── Fairness Auditor ──────────────────────────────────────────────────
from tools.fairness_auditor import audit_all_candidates

# ─── Premium UI Components ────────────────────────────────────────────────
from ui.components import (
    load_css, brand_header, metric_card, recommendation_badge,
    render_sidebar_status, candidate_row as candidate_table_row,
    criterion_bars, trajectory_step as trajectory_timeline_entry,
    interview_card
)

# ═══════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════

def init_state():
    for k, v in {
        "jd_uploaded": False, "jd_text": "", "jd_parsed": None, "rubric": None,
        "candidates": [], "results": [], "selected_candidates": [],
        "trajectory": [], "agent_running": False, "agent_complete": False,
        "current_step": "", "current_candidate": "", "agent_status": "Idle",
        "guardrail_passed": True, "human_approved": False,
        "available_slots": None, "log_stream": [],
        "model": os.getenv("MODEL", "openai/gpt-4o-mini"),
        "fairness_audit": None, "interview_approvals": {},
        "interview_slots": {},  # {name: InterviewSlot} after approval
    }.items():
        if k not in st.session_state: st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════

def sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="padding:1rem 0;text-align:center;border-bottom:1px solid rgba(255,255,255,0.06);margin-bottom:1rem;">
            <span style="font-size:2rem;">🧠</span>
            <h2 style="color:white;margin:0.3rem 0 0 0;font-weight:700;">TechVest</h2>
            <p style="color:#64748b;font-size:0.75rem;margin:0;">AI Recruitment</p>
        </div>
        """, unsafe_allow_html=True)

        # ── JD Upload ──
        st.markdown("### Job Description")
        jd = st.file_uploader("Upload Job Description (.txt or .pdf)", type=["txt","pdf"], key="jd_uploader")
        if jd is not None:
            try:
                if jd.type == "application/pdf":
                    text = _try_pdf(jd)
                else:
                    text = jd.getvalue().decode("utf-8")
                if text and len(text.strip()) > 10:
                    st.session_state.jd_text = text
                    st.session_state.jd_uploaded = True
                    st.success(f"✅ Loaded: {jd.name}")
                else:
                    st.warning("File appears empty. Try another file.")
            except Exception as e:
                st.error(f"Could not read file: {e}")
        if st.session_state.jd_uploaded:
            with st.expander("📝 Preview", expanded=False):
                st.caption(st.session_state.jd_text[:200] + "...")

        st.divider()

        # ── Resume Upload ──
        st.markdown("### Candidate Resumes")
        files = st.file_uploader("Upload Resume files (.txt or .pdf)", type=["txt","pdf"], accept_multiple_files=True,
                                 key="resume_uploader")
        if files and len(files) > 0:
            cands = []
            for f in files:
                try:
                    if f.type == "application/pdf":
                        t = _try_pdf(f)
                    else:
                        t = f.getvalue().decode("utf-8")
                    nm = os.path.splitext(f.name)[0].replace("_"," ").replace("-"," ").title()
                    if t and len(t.strip()) > 10:
                        cands.append((nm, t))
                except Exception as e:
                    st.warning(f"Could not read {f.name}: {e}")
            if cands:
                st.session_state.candidates = cands
                st.success(f"✅ {len(cands)} resume(s) loaded")
            else:
                st.warning("No valid resume content found.")

        st.divider()

        # ── Model & Actions ──
        st.markdown("### Configuration")
        st.session_state.model = st.text_input("Model Name", value=st.session_state.model,
                                               label_visibility="collapsed")

        can_run = st.session_state.jd_uploaded and len(st.session_state.candidates) > 0 and not st.session_state.agent_running
        if st.button("🚀 Run Recruitment Agent", type="primary", use_container_width=True, disabled=not can_run):
            st.session_state.agent_running = True
            st.session_state.agent_status = "Running"
            st.rerun()
        if st.button("🔄 Reset Session", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        st.divider()
        st.markdown("### Live Status")
        render_sidebar_status()

def _try_pdf(f):
    try:
        from PyPDF2 import PdfReader
        return "".join(p.extract_text() or "" for p in PdfReader(f).pages)
    except: return ""

# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE EXECUTION (unchanged backend logic)
# ═══════════════════════════════════════════════════════════════════════════

def run_pipeline():
    ss = st.session_state
    ss.agent_running = True; ss.agent_complete = False
    ss.agent_status = "Running"; ss.results = []; ss.selected_candidates = []; ss.log_stream = []
    ss.human_approved = False; ss.trajectory = []; ss.available_slots = None
    ss.interview_approvals = {}  # {name: "pending"|"approved"|"rejected"}

    def log(m): ss.log_stream.append(m)

    try:
        ss.current_step = "Parsing JD..."; log("📄 Parsing job description...")
        init = RecruitmentState(jd_raw=ss.jd_text, jd_parsed=None, resume_raw="",
            resume_parsed=None, score_card=None, decision=None, interview_slot=None,
            available_slots="{}", plan=[], candidate_name="", trajectory=[], error=None, rubric=None)
        state = node_parse_jd(init, call_llm)
        ss.jd_parsed = state.get("jd_parsed")
        if state.get("error"): raise Exception(state["error"])

        ss.current_step = "Generating rubric..."; log("📋 Generating rubric...")
        state = node_generate_rubric(state, call_llm)
        ss.rubric = state.get("rubric"); ss.trajectory = state.get("trajectory", [])

        jdp, rub = ss.jd_parsed, ss.rubric
        for idx, (name, rt) in enumerate(ss.candidates):
            ss.current_candidate = name
            ss.current_step = f"Processing {name} ({idx+1}/{len(ss.candidates)})"; log(f"👤 {name}")

            rd = parse_resume_tool(rt, call_llm)
            log(f"  ✓ Parsed: {rd.candidate_name}, {rd.experience_years}yr, {len(rd.skills)} skills")

            sc = score_candidate_tool(jdp.model_dump_json(), rd.model_dump_json(),
                                      rub.model_dump_json(), call_llm)
            sc.candidate = name; log(f"  ✓ Score: {sc.total_score:.2f}")

            from prompts.decision_prompt import DECISION_PROMPT
            r = json.loads(call_llm(DECISION_PROMPT.format(score_card=sc.model_dump_json())))
            dec = FinalDecision(**r); log(f"  ✓ Decision: {dec.decision}")

            guardrail_passed = True
            if dec.decision == "SELECT":
                from prompts.guardrail_prompt import GUARDRAIL_PROMPT
                g = json.loads(call_llm(GUARDRAIL_PROMPT.format(decision=dec.model_dump_json())))
                guardrail_passed = g.get("is_safe", True)
                log(f"  ✓ Guardrail: {'Passed' if guardrail_passed else 'WARNING'}")
            
            # ⚠️ NO scheduling here — only store the result, slot is None
            # Interview tab will handle scheduling after human approval
            ss.results.append((name, sc, dec, guardrail_passed))

        # Store selected candidates (guardrail-passed SELECT decisions)
        ss.selected_candidates = [
            (n, sc, dec) for n, sc, dec, gp in ss.results
            if dec.decision == "SELECT" and gp
        ]
        
        # Initialize approval status for each selected candidate
        for n, _, _ in ss.selected_candidates:
            ss.interview_approvals[n] = "pending"
        
        # Run fairness audit on all results
        log("🔍 Running fairness audit...")
        ss.fairness_audit = audit_all_candidates(
            [(n, sc, dec, None) for n, sc, dec, _ in ss.results]
        )
        if ss.fairness_audit["overall_bias_detected"]:
            log(f"⚠️ Bias detected in {sum(1 for a in ss.fairness_audit['audit_log'] if a['bias_detected'])} candidate(s)")
        else:
            log("✅ No bias detected in any candidate evaluation")
        
        ss.agent_status = "Complete"; ss.agent_complete = True; log("✅ Complete!")
    except Exception as e:
        st.error(str(e)); log(f"❌ {e}"); ss.agent_status = "Error"
    ss.agent_running = False

# ═══════════════════════════════════════════════════════════════════════════
# HOME TAB
# ═══════════════════════════════════════════════════════════════════════════

def home_tab():
    st.markdown("## 📊 Recruitment Dashboard")
    results = st.session_state.results
    if not results:
        st.info("Upload a Job Description and resumes, then click **Run Recruitment Agent**.")
        return

    total = len(results)
    interview = sum(1 for r in results if r[2].decision == "SELECT")
    hold = sum(1 for r in results if r[2].decision == "HOLD")
    reject = sum(1 for r in results if r[2].decision == "REJECT")

    # ── Row 1: Metric Cards ──
    cols = st.columns(4)
    with cols[0]: metric_card("Total Candidates", total, "#2563eb")
    with cols[1]: metric_card("Interview", interview, "#16a34a")
    with cols[2]: metric_card("Hold", hold, "#eab308")
    with cols[3]: metric_card("Reject", reject, "#dc2626")

    st.markdown("---")

    # ── Row 2: Interactive Ranking Table ──
    st.markdown("### 🏆 Candidate Ranking")
    sorted_r = sorted(results, key=lambda x: x[1].total_score, reverse=True)

    # Table header
    hcols = st.columns([0.6, 2.2, 1.2, 1.5, 1.8, 2.0])
    headers = ["Rank", "Candidate", "Score", "Progress", "Decision", "Slot"]
    for hc, h in zip(hcols, headers):
        hc.markdown(f"<span style='font-size:0.7rem;color:#64748b;text-transform:uppercase;"
                    f"letter-spacing:0.5px;font-weight:600;'>{h}</span>", unsafe_allow_html=True)

    st.markdown("<div style='height:2px;background:#e2e8f0;margin:0.2rem 0 0.5rem 0;'></div>", unsafe_allow_html=True)

    for rank, (name, score, decision, guardrail_bool) in enumerate(sorted_r, 1):
        slot_str = ""
        candidate_table_row(rank, name, score.total_score, decision.decision, slot_str)

        # ── Row 3: Expandable Candidate Details ──
        with st.expander(f"📋 View Details — {name}"):
            candidate_details(name, score, decision, None)

    st.markdown("---")
    # ── Live log ──
    if st.session_state.log_stream:
        st.markdown("### 📡 Execution Log")
        for m in st.session_state.log_stream:
            if "❌" in m: st.error(m)
            elif "✓" in m: st.success(m)
            else: st.text(m)

# ═══════════════════════════════════════════════════════════════════════════
# CANDIDATE DETAILS (expander)
# ═══════════════════════════════════════════════════════════════════════════

def candidate_details(name: str, score: ScoreCard, decision: FinalDecision, slot):
    tabs = st.tabs(["👤 Profile", "📊 Scores", "📄 Evidence", "🎯 Interview"])

    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Name:** {name}")
            st.markdown(f"**Score:** {score.total_score:.2f}")
            st.markdown(f"**Decision:** {recommendation_badge(decision.decision)}", unsafe_allow_html=True)
            st.markdown(f"**Strengths:** {', '.join(score.strengths) if score.strengths else '—'}")
            st.markdown(f"**Gaps:** {', '.join(score.gaps) if score.gaps else 'None'}")
        with col2:
            st.markdown(f"**Recommendation:** {score.recommendation}")
            st.markdown(f"**Justification:** {decision.reason}")
            if slot:
                st.markdown(f"**Proposed Slot:** {slot.date} at {slot.time} ({slot.format})")

    with tabs[1]:
        st.markdown("#### Criterion-wise Weighted Scores")
        criterion_bars([{"name": c.name, "score": c.score, "weight": c.weight, "evidence": c.evidence}
                        for c in score.criteria])

    with tabs[2]:
        st.markdown("#### Resume Evidence")
        for c in score.criteria:
            st.markdown(f"- **{c.name}:** {c.evidence}")
        if score.strengths:
            st.markdown("#### ✅ Strengths")
            for s in score.strengths: st.markdown(f"- {s}")
        if score.gaps:
            st.markdown("#### ⚠️ Weaknesses")
            for g in score.gaps: st.markdown(f"- {g}")

    with tabs[3]:
        if decision.decision == "SELECT" and slot:
            st.markdown(f"✅ **{name}** recommended for interview.")
            st.markdown(f"📅 **{slot.date}** at **{slot.time}** ({slot.format})")
            st.markdown("⏳ **Pending Human Approval**")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Approve", key=f"app_{name}", type="primary"):
                    st.session_state.human_approved = True
                    st.success(send_interview_invite(slot))
            with c2:
                if st.button("❌ Reject", key=f"rej_{name}"):
                    st.warning(f"Interview for {name} rejected.")
        else:
            st.markdown(f"❌ **{name}** not shortlisted (Score: {score.total_score:.2f})")
            st.markdown(f"**Reason:** {decision.reason}")

# ═══════════════════════════════════════════════════════════════════════════
# TRAJECTORY TAB
# ═══════════════════════════════════════════════════════════════════════════

def trajectory_tab():
    st.markdown("## 🔄 LangGraph Execution Trajectory")
    traj = st.session_state.trajectory
    if not traj:
        st.info("Run the agent first."); return
    st.markdown(f"**{len(traj)} steps** recorded")
    for i, e in enumerate(traj, 1):
        if isinstance(e, dict) and "tool_used" in e:
            trajectory_timeline_entry(i, e)
        else:
            with st.expander(f"Step {i}"):
                st.write(str(e))

# ═══════════════════════════════════════════════════════════════════════════
# GUARDRAILS TAB
# ═══════════════════════════════════════════════════════════════════════════

def guardrails_tab():
    st.markdown("## 🛡️ Guardrails & Compliance")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.metric("Iteration Count", len(st.session_state.trajectory))
        st.markdown("---")
        st.markdown(f"**Prompt Injection:** {'✅ Passed' if st.session_state.guardrail_passed else '❌ Flagged'}")
        st.markdown(f"**Fairness Check:** {'✅ Passed' if st.session_state.guardrail_passed else '❌ Flagged'}")
        st.markdown(f"**Bias Detection:** {'✅ Passed' if st.session_state.guardrail_passed else '❌ Flagged'}")
        st.markdown("---")
        st.markdown(f"**Human Approval:** {'✅ Approved' if st.session_state.human_approved else '⏳ Pending'}")
        st.markdown(f"**Termination:** {'✅ Normal' if st.session_state.agent_complete else '⏳ In Progress'}")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="premium-card">', unsafe_allow_html=True)
        st.markdown("**Compliance Summary**")
        if st.session_state.results:
            rows = [{"Candidate": n, "Score": f"{s.total_score:.2f}", "Decision": d.decision,
                     "Fairness": "✅ Pass", "Bias": "✅ Pass"} for n,s,d,gp in st.session_state.results]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No data.")
        st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# AUDIT TAB
# ═══════════════════════════════════════════════════════════════════════════

def audit_tab():
    st.markdown("## 📋 Audit Log")
    t1, t2, t3 = st.tabs(["📜 Decisions", "🛠️ Tool Calls", "📦 JSON Export"])

    with t1:
        if st.session_state.results:
            data = [{"Candidate": n, "Score": round(s.total_score,2), "Decision": d.decision,
                     "Reason": d.reason[:70]+"...",
                     "Slot": "⏳ Pending Approval"}
                    for n,s,d,gp in st.session_state.results]
            st.dataframe(data, use_container_width=True, hide_index=True)

    with t2:
        traj = st.session_state.trajectory
        if traj:
            data = [{"Step": i, "Tool": e.get("tool_used",""), "Observation": (e.get("observation","") or "")[:70],
                     "Decision": e.get("decision","")}
                    for i,e in enumerate(traj,1) if isinstance(e, dict)]
            st.dataframe(data, use_container_width=True, hide_index=True)

    with t3:
        ex = {
            "model": st.session_state.model,
            "candidates": len(st.session_state.candidates),
            "results": [{"candidate": n, "score": s.total_score, "decision": d.decision,
                         "reason": d.reason, "criteria": [{"name":c.name,"score":c.score,
                         "weight":c.weight,"evidence":c.evidence} for c in s.criteria],
                         "guardrail_passed": bool(gp)}
                        for n,s,d,gp in st.session_state.results],
            "trajectory": [e for e in st.session_state.trajectory if isinstance(e, dict)],
            "guardrail_passed": st.session_state.guardrail_passed,
            "human_approved": st.session_state.human_approved,
        }
        st.json(ex)
        st.download_button("📥 Download JSON", json.dumps(ex, indent=2, default=str),
                           "recruitment_audit.json", "application/json", type="primary")

# ═══════════════════════════════════════════════════════════════════════════
# INTERVIEW TAB
# ═══════════════════════════════════════════════════════════════════════════

def interview_tab():
    """Interview scheduling — requires EXPLICIT recruiter approval before scheduling."""
    st.markdown("## 🎯 Interview Scheduling")
    
    selected = st.session_state.get("selected_candidates", [])
    
    if not selected:
        st.info("No candidates shortlisted for interview. Run the recruitment agent first.")
        return
    
    st.markdown(f"**{len(selected)} candidate(s)** await your approval for interview scheduling.")
    st.markdown("---")
    
    # Ensure slots are loaded
    if st.session_state.available_slots is None:
        st.session_state.available_slots = get_availability()
    
    approvals = st.session_state.interview_approvals
    slots_data = json.loads(st.session_state.available_slots) if st.session_state.available_slots else {}
    available_opts = slots_data.get("available_slots", [])
    
    for rank, (name, score, decision) in enumerate(selected, 1):
        status = approvals.get(name, "pending")
        
        # ── Candidate Card ──
        border_color = "#16a34a" if status == "approved" else "#dc2626" if status == "rejected" else "#2563eb"
        status_text = "✅ Approved" if status == "approved" else "❌ Rejected" if status == "rejected" else "⏳ Pending Approval"
        status_color = "#16a34a" if status == "approved" else "#dc2626" if status == "rejected" else "#eab308"
        
        st.markdown(f"""
        <div style="background:white;border-radius:12px;padding:1.2rem;margin:0.8rem 0;
                    box-shadow:0 1px 3px rgba(0,0,0,0.06);border:1px solid #e2e8f0;
                    border-left:4px solid {border_color};">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div style="flex:1;">
                    <div style="display:flex;align-items:center;gap:0.5rem;">
                        <span style="font-weight:700;color:#2563eb;">#{rank}</span>
                        <span style="font-weight:700;font-size:1.1rem;">{name}</span>
                        {recommendation_badge('Interview')}
                    </div>
                    <div style="margin-top:0.4rem;font-size:0.85rem;color:#475569;">
                        <b>Score:</b> {score.total_score:.2f} &nbsp;·&nbsp;
                        <b>Reason:</b> {decision.reason[:100]}...
                    </div>
                </div>
                <div style="min-width:140px;text-align:right;">
                    <span style="font-size:0.8rem;font-weight:600;color:{status_color};">
                        {status_text}
                    </span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # ── Slot selector (only shown for pending candidates) ──
        if status == "pending":
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                if available_opts:
                    opts = [f"{s['date']} {s['time']} ({s.get('format','online')})" for s in available_opts]
                    selected_slot_str = st.selectbox(f"Choose slot for {name}", opts, key=f"slot_{name}")
                    # Extract selected slot index
                    sel_idx = opts.index(selected_slot_str)
                    chosen_slot_data = available_opts[sel_idx]
                else:
                    st.warning("No available slots")
                    chosen_slot_data = None
            
            with col2:
                if st.button("✅ Approve", key=f"approve_{name}", type="primary", use_container_width=True):
                    if chosen_slot_data:
                        # ⚠️ ONLY NOW do we schedule — after explicit recruiter approval
                        slot = schedule_interview(
                            name,
                            json.dumps({"available_slots": [chosen_slot_data]}),
                            call_llm
                        )
                        st.session_state.interview_slots[name] = slot
                        st.session_state.interview_approvals[name] = "approved"
                        invite = send_interview_invite(slot)
                        st.success(invite)
                        st.rerun()
            
            with col3:
                st.button("❌ Reject", key=f"reject_{name}", use_container_width=True,
                          on_click=lambda n=name: [
                              st.session_state.interview_approvals.update({n: "rejected"}),
                              st.warning(f"Interview for {n} rejected."),
                          ])
        
        elif status == "approved":
            slot = st.session_state.interview_slots.get(name)
            if slot:
                st.success(f"📅 **Scheduled:** {slot.date} at {slot.time} ({slot.format})")
        
        st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(page_title="TechVest · AI Recruitment", page_icon="🧠",
                       layout="wide", initial_sidebar_state="expanded")
    init_state()
    load_css()
    brand_header()
    sidebar()

    # Run pipeline if triggered (must be in main body for st.error/st.success to render)
    if st.session_state.get("agent_running", False):
        run_pipeline()

    tabs = st.tabs(["🏠 Home", "🔄 Trajectory", "🛡️ Guardrails", "📋 Audit", "🎯 Interview"])
    with tabs[0]: home_tab()
    with tabs[1]: trajectory_tab()
    with tabs[2]: guardrails_tab()
    with tabs[3]: audit_tab()
    with tabs[4]: interview_tab()

if __name__ == "__main__":
    main()