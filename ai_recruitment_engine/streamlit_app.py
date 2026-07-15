"""
TechVest AI Recruitment Agent  —  Streamlit Dashboard
"""

import json
import os
import sys

import streamlit as st

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(SCRIPT_DIR, ".env"))

# ── backend ──────────────────────────────────────────────────────────────────
from app import call_llm
from graph.nodes import node_generate_rubric, node_parse_jd
from graph.state import RecruitmentState
from models.schemas import FinalDecision, ScoreCard
from prompts.decision_prompt import DECISION_PROMPT
from prompts.guardrail_prompt import GUARDRAIL_PROMPT
from tools.availability import get_availability
from tools.fairness_auditor import audit_all_candidates
from tools.interview import schedule_interview, send_interview_invite
from tools.parse_resume import parse_resume as parse_resume_tool
from tools.score_candidate import score_candidate as score_candidate_tool

# ── UI ────────────────────────────────────────────────────────────────────────
from ui.components import (
    brand_header,
    candidate_row,
    criterion_bars,
    guardrail_badge,
    interview_card,
    load_css,
    metric_card,
    recommendation_badge,
    render_sidebar_status,
    score_ring,
    trajectory_step,
)


# =============================================================================
# SESSION STATE
# =============================================================================

def init_state():
    defaults = {
        "jd_uploaded":         False,
        "jd_text":             "",
        "jd_parsed":           None,
        "rubric":              None,
        "candidates":          [],
        "results":             [],          # (name, ScoreCard, FinalDecision, gp, gr, gi)
        "selected_candidates": [],          # (name, ScoreCard, FinalDecision) — SELECT+passed only
        "trajectory":          [],
        "agent_running":       False,
        "agent_complete":      False,
        "current_step":        "",
        "current_candidate":   "",
        "agent_status":        "Idle",
        "human_approved":      False,
        "available_slots":     None,
        "log_stream":          [],
        "model":               os.getenv("MODEL", "openai/gpt-4o-mini"),
        "fairness_audit":      None,
        "interview_approvals": {},          # name → "pending"|"approved"|"rejected"
        "interview_slots":     {},          # name → InterviewSlot
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# =============================================================================
# HELPERS
# =============================================================================

def _read_pdf(f) -> str:
    try:
        from PyPDF2 import PdfReader
        return "".join(p.extract_text() or "" for p in PdfReader(f).pages)
    except Exception:
        return ""


def _section(title: str):
    """Render a clean section heading."""
    st.markdown(
        f"<h3 style='font-size:1rem;font-weight:700;color:#1e293b;"
        f"margin:1.2rem 0 0.6rem 0;padding-bottom:0.3rem;"
        f"border-bottom:2px solid #e2e8f0;'>{title}</h3>",
        unsafe_allow_html=True,
    )


def _empty_state(icon: str, title: str, body: str):
    st.markdown(
        f"<div style='text-align:center;padding:2.5rem 1rem;background:#f8fafc;"
        f"border-radius:12px;border:1px dashed #cbd5e1;margin:0.5rem 0;'>"
        f"<div style='font-size:2.2rem;margin-bottom:0.4rem;'>{icon}</div>"
        f"<p style='font-weight:700;font-size:1rem;color:#0f172a;margin:0;'>{title}</p>"
        f"<p style='color:#64748b;font-size:0.85rem;margin:0.3rem 0 0 0;'>{body}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )


# =============================================================================
# SIDEBAR
# =============================================================================

def sidebar():
    with st.sidebar:
        # Logo / brand
        st.markdown(
            "<div style='text-align:center;padding:1rem 0 0.8rem 0;"
            "border-bottom:1px solid rgba(255,255,255,0.07);margin-bottom:0.8rem;'>"
            "<span style='font-size:2rem;'>🧠</span>"
            "<h2 style='color:#f1f5f9;margin:0.2rem 0 0 0;font-size:1.1rem;"
            "font-weight:800;letter-spacing:-0.01em;'>TechVest</h2>"
            "<p style='color:#475569;font-size:0.7rem;margin:0;'>AI Recruitment Engine</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        # JD upload
        st.markdown("### Job Description")
        jd_file = st.file_uploader("JD file (.txt / .pdf)", type=["txt","pdf"], key="jd_uploader")
        if jd_file is not None:
            try:
                raw = (_read_pdf(jd_file) if jd_file.type == "application/pdf"
                       else jd_file.getvalue().decode("utf-8"))
                if raw and raw.strip():
                    st.session_state.jd_text     = raw
                    st.session_state.jd_uploaded = True
                    st.success(f"✅ {jd_file.name}")
                else:
                    st.warning("File appears empty.")
            except Exception as e:
                st.error(f"Read error: {e}")

        if st.session_state.jd_uploaded:
            with st.expander("Preview", expanded=False):
                st.caption(st.session_state.jd_text[:400] + ("…" if len(st.session_state.jd_text) > 400 else ""))

        st.divider()

        # Resume upload
        st.markdown("### Resumes")
        res_files = st.file_uploader(
            "Resume files (.txt / .pdf)",
            type=["txt","pdf"],
            accept_multiple_files=True,
            key="resume_uploader",
        )
        if res_files:
            cands = []
            for f in res_files:
                try:
                    raw = (_read_pdf(f) if f.type == "application/pdf"
                           else f.getvalue().decode("utf-8"))
                    if raw and raw.strip():
                        nm = os.path.splitext(f.name)[0].replace("_"," ").replace("-"," ").title()
                        cands.append((nm, raw))
                except Exception as e:
                    st.warning(f"{f.name}: {e}")
            if cands:
                st.session_state.candidates = cands
                st.success(f"✅ {len(cands)} resume(s)")

        st.divider()

        # Config & run
        st.markdown("### Configuration")
        st.session_state.model = st.text_input(
            "Model", value=st.session_state.model, label_visibility="collapsed"
        )

        ready = (
            st.session_state.jd_uploaded
            and len(st.session_state.candidates) > 0
            and not st.session_state.agent_running
        )
        if st.button("🚀  Run Recruitment Agent", type="primary",
                     use_container_width=True, disabled=not ready):
            st.session_state.agent_running = True
            st.session_state.agent_status  = "Running"
            st.rerun()

        if st.button("🔄  Reset", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        st.divider()
        st.markdown("### Status")
        render_sidebar_status()


# =============================================================================
# PIPELINE EXECUTION
# =============================================================================

def run_pipeline():
    ss = st.session_state
    ss.agent_running       = True
    ss.agent_complete      = False
    ss.agent_status        = "Running"
    ss.results             = []
    ss.selected_candidates = []
    ss.log_stream          = []
    ss.human_approved      = False
    ss.trajectory          = []
    ss.available_slots     = None
    ss.interview_approvals = {}

    def log(msg: str):
        ss.log_stream.append(msg)

    try:
        # ── 1. Parse JD ──────────────────────────────────────────────────────
        ss.current_step = "Parsing JD…"
        log("📄 Parsing job description…")
        seed = RecruitmentState(
            jd_raw=ss.jd_text, jd_parsed=None, resume_raw="",
            resume_parsed=None, score_card=None, decision=None,
            interview_slot=None, available_slots="{}", plan=[],
            candidate_name="", trajectory=[], error=None, rubric=None,
            guardrail_passed=True, guardrail_reason="", guardrail_issues=[],
        )
        state = node_parse_jd(seed, call_llm)
        ss.jd_parsed = state.get("jd_parsed")
        if state.get("error"):
            raise RuntimeError(state["error"])
        log(f"  ✓ JD: {ss.jd_parsed.job_title if ss.jd_parsed else 'parsed'}")

        # ── 2. Generate rubric ───────────────────────────────────────────────
        ss.current_step = "Generating rubric…"
        log("📐 Generating scoring rubric…")
        state = node_generate_rubric(state, call_llm)
        ss.rubric     = state.get("rubric")
        ss.trajectory = list(state.get("trajectory", []))
        if state.get("error"):
            raise RuntimeError(state["error"])
        log(f"  ✓ Rubric: {len(ss.rubric.criteria)} criteria" if ss.rubric else "  ✓ Rubric generated")

        jdp = ss.jd_parsed
        rub = ss.rubric

        # ── 3. Per-candidate loop ────────────────────────────────────────────
        for idx, (name, resume_text) in enumerate(ss.candidates):
            ss.current_candidate = name
            ss.current_step      = f"Processing {name} ({idx+1}/{len(ss.candidates)})"
            log(f"👤 {name}")

            # Parse resume
            rd = parse_resume_tool(resume_text, call_llm)
            log(f"  ✓ Parsed: {rd.experience_years}yr exp, {len(rd.skills)} skills")

            # Score
            sc = score_candidate_tool(
                jdp.model_dump_json(), rd.model_dump_json(), rub.model_dump_json(), call_llm
            )
            sc.candidate = name
            log(f"  ✓ Score: {sc.total_score:.4f}")

            ss.trajectory.append({
                "thought":       f"Score {name} against rubric.",
                "tool_used":     "score_candidate",
                "arguments":     {"candidate": name, "criteria": len(rub.criteria)},
                "observation":   f"Score={sc.total_score:.4f}  strengths={len(sc.strengths)}  gaps={len(sc.gaps)}",
                "state_changes": {"score_card": {"from": None, "to": f"{sc.total_score:.4f}"}},
                "decision":      f"SCORE={sc.total_score:.4f}",
            })

            # Decision
            dec_raw  = call_llm(DECISION_PROMPT.format(score_card=sc.model_dump_json()))
            dec_data = json.loads(dec_raw)
            dec      = FinalDecision(**dec_data)

            # Safety-net threshold enforcement
            if sc.total_score < 0.40 and dec.decision != "REJECT":
                dec.decision = "REJECT"
                dec.reason   = f"[Auto] Score {sc.total_score:.2f} < 0.40 threshold. " + dec.reason
            elif 0.40 <= sc.total_score < 0.60 and dec.decision not in ("HOLD","REJECT"):
                dec.decision = "HOLD"
                dec.reason   = f"[Auto] Score {sc.total_score:.2f} in 0.40–0.60 range. " + dec.reason

            log(f"  ✓ Decision: {dec.decision}")
            ss.trajectory.append({
                "thought":       f"Make hiring decision for {name}.",
                "tool_used":     "make_decision",
                "arguments":     {"candidate": name, "score": f"{sc.total_score:.4f}"},
                "observation":   f"{dec.decision} — {dec.reason[:90]}",
                "state_changes": {"decision": {"from": None, "to": dec.decision}},
                "decision":      dec.decision,
            })

            # Guardrail
            gr_raw    = call_llm(GUARDRAIL_PROMPT.format(decision=dec.model_dump_json()))
            gr_data   = json.loads(gr_raw)
            gp        = bool(gr_data.get("is_safe", True))
            gr_reason = gr_data.get("reason", "")
            gr_issues = gr_data.get("issues", [])

            if not gp:
                sc.total_score = 0.0
                dec.decision   = "REJECT"
                dec.reason     = f"Guardrail violation: {gr_reason or 'failed safety check'}"
                dec.candidate_name = name
                log(f"  ⚠️  Guardrail FAILED — {gr_reason}")
            else:
                log("  ✓ Guardrail: passed")

            ss.trajectory.append({
                "thought":       f"Safety/fairness check for {name}.",
                "tool_used":     "guardrail_check",
                "arguments":     {"candidate": name, "decision": dec.decision},
                "observation":   f"{'PASSED' if gp else 'FLAGGED'}: {gr_reason}",
                "state_changes": {},
                "decision":      "PASSED" if gp else "FLAGGED",
            })

            ss.results.append((name, sc, dec, gp, gr_reason, gr_issues))

        # ── 4. Shortlist ─────────────────────────────────────────────────────
        ss.selected_candidates = [
            (n, sc, dec)
            for n, sc, dec, gp, _gr, _gi in ss.results
            if dec.decision == "SELECT" and gp
        ]
        for n, _sc, _dec in ss.selected_candidates:
            ss.interview_approvals[n] = "pending"

        # ── 5. Stopping condition entry ──────────────────────────────────────
        n_sel  = len(ss.selected_candidates)
        n_hold = sum(1 for r in ss.results if r[2].decision == "HOLD")
        n_rej  = sum(1 for r in ss.results if r[2].decision == "REJECT")
        ss.trajectory.append({
            "thought":       "All candidates processed — pipeline complete.",
            "tool_used":     "agent_stop",
            "arguments":     {"total": len(ss.candidates), "selected": n_sel, "hold": n_hold, "rejected": n_rej},
            "observation":   (f"Pipeline complete: {len(ss.candidates)} processed, "
                              f"{n_sel} selected, {n_hold} hold, {n_rej} rejected."),
            "state_changes": {},
            "decision":      "PIPELINE_COMPLETE",
        })

        # ── 6. Fairness audit ────────────────────────────────────────────────
        log("🔍 Running fairness audit…")
        ss.fairness_audit = audit_all_candidates(
            [(n, sc, dec, None) for n, sc, dec, *_ in ss.results]
        )
        bias_n = sum(1 for a in ss.fairness_audit["audit_log"] if a["bias_detected"])
        if ss.fairness_audit["overall_bias_detected"]:
            log(f"  ⚠️  Bias indicators in {bias_n} candidate(s)")
        else:
            log("  ✓ No bias detected")

        ss.agent_status   = "Complete"
        ss.agent_complete = True
        log("✅ Pipeline complete!")

    except Exception as exc:
        st.error(f"Pipeline error: {exc}")
        log(f"❌ {exc}")
        ss.agent_status = "Error"

    ss.agent_running = False



# =============================================================================
# HOME TAB
# =============================================================================

def _candidate_details(name: str, score: ScoreCard, decision: FinalDecision, slot):
    t_profile, t_scores, t_evidence = st.tabs(["👤 Profile", "📊 Scores", "📄 Evidence"])

    with t_profile:
        ca, cb = st.columns(2)
        with ca:
            st.markdown(f"**Candidate:** {name}")
            st.markdown(f"**Score:** {score.total_score:.4f}")
            st.markdown(
                f"**Decision:** {recommendation_badge(decision.decision)}",
                unsafe_allow_html=True,
            )
        with cb:
            st.markdown(f"**Recommendation:** {score.recommendation}")
            st.markdown(f"**Reason:** {decision.reason}")
            if slot:
                st.markdown(f"**Interview:** {slot.date} at {slot.time} ({slot.format})")
        if score.strengths:
            st.markdown("**✅ Strengths:**")
            for s in score.strengths:
                st.markdown(f"- {s}")
        if score.gaps:
            st.markdown("**⚠️ Gaps:**")
            for g in score.gaps:
                st.markdown(f"- {g}")

    with t_scores:
        _section("Criterion-wise Weighted Scores")
        criterion_bars([
            {"name": c.name, "score": c.score, "weight": c.weight, "evidence": c.evidence}
            for c in score.criteria
        ])

    with t_evidence:
        _section("Resume Evidence per Criterion")
        for c in score.criteria:
            with st.expander(f"**{c.name}**  ·  {c.score}/5  (weight {c.weight}%)", expanded=False):
                st.markdown(c.evidence or "_No evidence recorded_")


def home_tab():
    results = st.session_state.results
    if not results:
        _empty_state(
            "🚀", "Ready to start",
            "Upload a Job Description and at least one resume in the sidebar, "
            "then click <b>Run Recruitment Agent</b>.",
        )
        return

    total    = len(results)
    selected = sum(1 for r in results if r[2].decision == "SELECT")
    hold     = sum(1 for r in results if r[2].decision == "HOLD")
    reject   = sum(1 for r in results if r[2].decision == "REJECT")

    # ── Metric row ────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Total",     total,    "#2563eb")
    with c2: metric_card("Interview", selected, "#16a34a")
    with c3: metric_card("Hold",      hold,     "#d97706")
    with c4: metric_card("Reject",    reject,   "#dc2626")

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

    # ── Ranking table ─────────────────────────────────────────────────────────
    _section("🏆 Candidate Ranking")

    # header — must exactly match candidate_row column ratios [0.35, 2.2, 0.9, 1.6, 1.4, 1.8]
    hc = st.columns([0.35, 2.2, 0.9, 1.6, 1.4, 1.8])
    for col, lbl in zip(hc, ["#", "Name", "Score", "Progress", "Decision", "Slot"]):
        col.markdown(
            f"<span style='font-size:0.65rem;text-transform:uppercase;"
            f"letter-spacing:0.8px;font-weight:700;color:#94a3b8;'>{lbl}</span>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height:1px;background:#f1f5f9;margin:0.15rem 0 0.3rem 0;'></div>",
                unsafe_allow_html=True)

    sorted_r = sorted(results, key=lambda x: x[1].total_score, reverse=True)
    for rank, (name, score, decision, *_) in enumerate(sorted_r, 1):
        candidate_row(rank, name, score.total_score, decision.decision)
        with st.expander(
            f"📋  {name}  ·  {score.total_score:.2f}  ·  {decision.decision}",
            expanded=False,
        ):
            _candidate_details(name, score, decision, None)
        # thin divider between rows
        st.markdown("<div style='height:1px;background:#f8fafc;'></div>", unsafe_allow_html=True)

    # ── Execution log ─────────────────────────────────────────────────────────
    if st.session_state.log_stream:
        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        _section("📡 Execution Log")
        log_box = st.container()
        with log_box:
            for msg in st.session_state.log_stream:
                if "❌" in msg:
                    st.error(msg)
                elif "✓" in msg or "✅" in msg:
                    st.success(msg)
                elif "⚠️" in msg:
                    st.warning(msg)
                else:
                    st.markdown(
                        f"<p style='margin:0.1rem 0;font-size:0.82rem;"
                        f"color:#475569;font-family:monospace;'>{msg}</p>",
                        unsafe_allow_html=True,
                    )


# =============================================================================
# TRAJECTORY TAB
# =============================================================================

def trajectory_tab():
    traj = st.session_state.trajectory
    if not traj:
        _empty_state("🔄", "No trajectory yet", "Run the agent to see the step-by-step execution trace.")
        return

    # Stopping condition banner
    stops = [e for e in traj if isinstance(e, dict) and e.get("decision") == "PIPELINE_COMPLETE"]
    if stops:
        obs = stops[0].get("observation", "")
        st.success(f"🏁  {obs}")

    _section(f"Pipeline Steps  ·  {len(traj)} recorded")

    for i, entry in enumerate(traj, 1):
        if isinstance(entry, dict) and "tool_used" in entry:
            trajectory_step(i, entry)
        else:
            with st.expander(f"Step {i}"):
                st.write(str(entry))


# =============================================================================
# GUARDRAILS TAB
# =============================================================================

def guardrails_tab():
    results  = st.session_state.results
    fairness = st.session_state.get("fairness_audit")
    traj     = st.session_state.trajectory

    # ── Per-candidate guardrail cards ─────────────────────────────────────────
    _section("🔒 Per-Candidate Guardrail Results")
    if not results:
        _empty_state("🛡️", "No results yet", "Run the agent to see guardrail results.")
    else:
        for name, sc, dec, gp, gr, gi in results:
            border = "#16a34a" if gp else "#dc2626"
            issues_html = ""
            if gi:
                items = "".join(f"<li style='font-size:0.78rem;color:#b91c1c;margin:0.15rem 0;'>{i}</li>" for i in gi)
                issues_html = f"<ul style='margin:0.3rem 0 0 1rem;padding:0;'>{items}</ul>"
            st.markdown(
                f"<div style='background:white;border-radius:10px;padding:0.85rem 1.1rem;"
                f"margin:0.3rem 0;border:1px solid #e2e8f0;border-left:4px solid {border};"
                f"box-shadow:0 1px 3px rgba(0,0,0,0.04);'>"
                f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                f"<span style='font-weight:700;font-size:0.92rem;color:#0f172a;'>{name}</span>"
                f"<span>{guardrail_badge(gp)}</span>"
                f"</div>"
                f"<div style='font-size:0.8rem;color:#64748b;margin-top:0.25rem;'>"
                f"{gr or ('All checks passed.' if gp else 'Violation detected.')}"
                f"</div>"
                f"{issues_html}"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    # ── Stopping conditions ───────────────────────────────────────────────────
    _section("🏁 Stopping Conditions")
    stop_entries = [e for e in traj if isinstance(e, dict) and e.get("decision") == "PIPELINE_COMPLETE"]
    if stop_entries:
        args = stop_entries[0].get("arguments", {})
        obs  = stop_entries[0].get("observation", "")
        m1, m2, m3, m4 = st.columns(4)
        with m1: metric_card("Processed", args.get("total", "—"),    "#2563eb")
        with m2: metric_card("Selected",  args.get("selected", "—"), "#16a34a")
        with m3: metric_card("Hold",      args.get("hold", "—"),     "#d97706")
        with m4: metric_card("Rejected",  args.get("rejected", "—"), "#dc2626")
        st.info(f"🏁 {obs}")
    else:
        st.info("Run the agent to see stopping condition data.")

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    # ── Fairness audit ────────────────────────────────────────────────────────
    _section("⚖️ Fairness Audit")
    if not fairness:
        st.info("Run the agent to see the fairness audit.")
    else:
        overall_ok = not fairness.get("overall_bias_detected", False)
        if overall_ok:
            st.success("✅  No demographic bias detected across all candidates.")
        else:
            st.error("⚠️  Bias indicators detected — see detail below.")

        audit_rows = []
        for e in fairness.get("audit_log", []):
            audit_rows.append({
                "Candidate":       e["candidate"],
                "Original Score":  round(e["original_score"], 4),
                "Corrected Score": round(e.get("corrected_total_score", e["original_score"]), 4),
                "Bias":            "⚠️ Yes" if e["bias_detected"] else "✅ No",
                "Detail":          (e.get("reason", "") or "—")[:90],
            })
        if audit_rows:
            st.dataframe(audit_rows, hide_index=True, use_container_width=True)

        for e in fairness.get("audit_log", []):
            if e["bias_detected"]:
                with st.expander(f"⚠️  {e['candidate']} — bias detail"):
                    for cs in e.get("corrected_scores", []):
                        if cs["corrected_score"] != cs["original_score"]:
                            st.markdown(
                                f"- **{cs['name']}**: {cs['original_score']} → {cs['corrected_score']}  ({cs['reason']})"
                            )

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    # ── Compliance summary ────────────────────────────────────────────────────
    _section("📋 Compliance Summary")
    col_a, col_b = st.columns(2)
    with col_a:
        all_passed = all(r[3] for r in results) if results else True
        overall_ok_safe = overall_ok if fairness else True
        items = [
            ("Prompt injection defence", "✅ Active"    if results else "—"),
            ("All guardrails passed",    "✅ Yes"       if all_passed else "❌ No"),
            ("Fairness audit",           "✅ Passed"    if overall_ok_safe else "⚠️ Issues"),
            ("Human approval gate",      "✅ Enforced"  if results else "—"),
            ("Normal termination",       "✅ Complete"  if st.session_state.agent_complete else "⏳ Pending"),
            ("Trajectory steps",         str(len(traj))),
        ]
        for lbl, val in items:
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;padding:0.3rem 0;"
                f"border-bottom:1px solid #f1f5f9;font-size:0.83rem;'>"
                f"<span style='color:#475569;'>{lbl}</span>"
                f"<span style='font-weight:600;color:#0f172a;'>{val}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    with col_b:
        if results:
            table = [
                {
                    "Candidate":  n,
                    "Score":      f"{s.total_score:.4f}",
                    "Decision":   d.decision,
                    "Guardrail":  "✅" if gp else "❌",
                    "Bias":       "✅" if not any(
                        a["bias_detected"] for a in (fairness or {}).get("audit_log", []) if a["candidate"] == n
                    ) else "⚠️",
                }
                for n, s, d, gp, _, __ in results
            ]
            st.dataframe(table, hide_index=True, use_container_width=True)
        else:
            st.info("No data yet.")


# =============================================================================
# AUDIT TAB
# =============================================================================

def audit_tab():
    t_dec, t_tools, t_json = st.tabs(["📜 Decisions", "🛠️ Tool Calls", "📦 JSON Export"])

    with t_dec:
        if st.session_state.results:
            rows = [
                {
                    "Candidate":  n,
                    "Score":      round(s.total_score, 4),
                    "Decision":   d.decision,
                    "Guardrail":  "✅" if gp else "❌",
                    "Reason":     (d.reason or "")[:90] + ("…" if len(d.reason or "") > 90 else ""),
                }
                for n, s, d, gp, _gr, _gi in st.session_state.results
            ]
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            _empty_state("📜", "No decisions yet", "Run the agent first.")

    with t_tools:
        traj = st.session_state.trajectory
        if traj:
            rows = [
                {
                    "Step":        i,
                    "Tool":        e.get("tool_used", ""),
                    "Observation": (e.get("observation", "") or "")[:90],
                    "Decision":    e.get("decision", ""),
                }
                for i, e in enumerate(traj, 1) if isinstance(e, dict)
            ]
            st.dataframe(rows, hide_index=True, use_container_width=True)
        else:
            _empty_state("🛠️", "No tool calls yet", "Run the agent first.")

    with t_json:
        export = {
            "model":           st.session_state.model,
            "candidate_count": len(st.session_state.candidates),
            "results": [
                {
                    "candidate":        n,
                    "score":            s.total_score,
                    "decision":         d.decision,
                    "reason":           d.reason,
                    "guardrail_passed": gp,
                    "guardrail_reason": gr,
                    "guardrail_issues": gi,
                    "criteria": [
                        {"name": c.name, "score": c.score, "weight": c.weight, "evidence": c.evidence}
                        for c in s.criteria
                    ],
                }
                for n, s, d, gp, gr, gi in st.session_state.results
            ],
            "trajectory":     [e for e in st.session_state.trajectory if isinstance(e, dict)],
            "human_approved":  st.session_state.human_approved,
            "fairness_audit":  st.session_state.get("fairness_audit"),
        }
        st.json(export)
        st.download_button(
            "📥  Download audit.json",
            data=json.dumps(export, indent=2, default=str),
            file_name="recruitment_audit.json",
            mime="application/json",
            type="primary",
        )


# =============================================================================
# INTERVIEW TAB
# =============================================================================

def interview_tab():
    results  = st.session_state.get("results", [])
    selected = st.session_state.get("selected_candidates", [])

    if not results:
        _empty_state("🎯", "No results yet", "Run the agent first.")
        return

    # HOLD notice
    holds = [(n, s, d) for n, s, d, *_ in results if d.decision == "HOLD"]
    if holds:
        _section("⏸️ On Hold — Borderline Candidates")
        for name, score, dec in holds:
            st.markdown(
                f"<div style='background:#fffbeb;border-radius:9px;padding:0.8rem 1rem;"
                f"margin:0.3rem 0;border:1px solid #fde68a;border-left:4px solid #d97706;'>"
                f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
                f"<b style='color:#0f172a;'>{name}</b>"
                f"<span class='tv-badge tv-hold'>◉ HOLD</span>"
                f"</div>"
                f"<div style='font-size:0.8rem;color:#92400e;margin-top:0.25rem;'>"
                f"Score: {score.total_score:.4f} &nbsp;·&nbsp; {dec.reason[:130]}"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)

    # SELECT candidates
    if not selected:
        _empty_state("📋", "No candidates shortlisted", "No SELECT decisions — check scores in Home tab.")
        return

    _section(f"✅ {len(selected)} Candidate(s) Shortlisted")
    st.markdown(
        "<p style='font-size:0.85rem;color:#64748b;margin:-0.3rem 0 0.8rem 0;'>"
        "Choose an interview slot and click Approve to confirm scheduling.</p>",
        unsafe_allow_html=True,
    )

    if st.session_state.available_slots is None:
        st.session_state.available_slots = get_availability()

    approvals  = st.session_state.interview_approvals
    slots_data = json.loads(st.session_state.available_slots or "{}")
    avail_opts = slots_data.get("available_slots", [])
    slot_strs  = [f"{s['date']}  {s['time']}  ({s.get('format','online')})" for s in avail_opts]

    for rank, (name, score, decision) in enumerate(selected, 1):
        status  = approvals.get(name, "pending")
        border  = "#16a34a" if status == "approved" else "#dc2626" if status == "rejected" else "#2563eb"
        s_col   = "#16a34a" if status == "approved" else "#dc2626" if status == "rejected" else "#d97706"
        s_label = "✅ Approved" if status == "approved" else "❌ Rejected" if status == "rejected" else "⏳ Pending"

        # Candidate header card
        st.markdown(
            f"<div style='background:white;border-radius:10px;padding:0.9rem 1.1rem;"
            f"margin:0.5rem 0 0.3rem 0;border:1px solid #e2e8f0;border-left:4px solid {border};"
            f"box-shadow:0 1px 3px rgba(0,0,0,0.04);'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
            f"<div>"
            f"<span style='font-size:0.78rem;font-weight:700;color:#2563eb;'>#{rank}</span>"
            f"&nbsp;&nbsp;"
            f"<span style='font-weight:700;font-size:0.95rem;color:#0f172a;'>{name}</span>"
            f"&nbsp;&nbsp;"
            f"{recommendation_badge('SELECT')}"
            f"</div>"
            f"<span style='font-size:0.78rem;font-weight:700;color:{s_col};'>{s_label}</span>"
            f"</div>"
            f"<div style='font-size:0.8rem;color:#64748b;margin-top:0.3rem;'>"
            f"Score: <b>{score.total_score:.4f}</b>"
            f"&nbsp;·&nbsp;{decision.reason[:110]}{'…' if len(decision.reason) > 110 else ''}"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

        if status == "pending":
            col_slot, col_ok, col_no = st.columns([3, 1, 1])
            with col_slot:
                if slot_strs:
                    chosen_str  = st.selectbox("Slot", slot_strs, key=f"slot_{name}", label_visibility="collapsed")
                    chosen_slot = avail_opts[slot_strs.index(chosen_str)]
                else:
                    st.warning("No slots available.")
                    chosen_slot = None
            with col_ok:
                if st.button("✅ Approve", key=f"app_{name}", type="primary", use_container_width=True):
                    if chosen_slot:
                        slot = schedule_interview(
                            name, json.dumps({"available_slots": [chosen_slot]}), call_llm
                        )
                        st.session_state.interview_slots[name]     = slot
                        st.session_state.interview_approvals[name] = "approved"
                        st.session_state.human_approved             = True
                        st.success(send_interview_invite(slot))
                        st.rerun()
            with col_no:
                if st.button("❌ Reject", key=f"rej_{name}", use_container_width=True):
                    st.session_state.interview_approvals[name] = "rejected"
                    st.rerun()

        elif status == "approved":
            slot = st.session_state.interview_slots.get(name)
            if slot:
                interview_card(name, score.total_score, slot, approved=True)

        elif status == "rejected":
            st.markdown(
                f"<p style='font-size:0.82rem;color:#dc2626;margin:0.2rem 0 0.5rem 0;'>"
                f"❌ Interview rejected for {name}.</p>",
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:3px;background:#f8fafc;border-radius:2px;margin:0.3rem 0;'></div>",
                    unsafe_allow_html=True)


# =============================================================================
# MAIN
# =============================================================================

def main():
    st.set_page_config(
        page_title="TechVest · AI Recruitment",
        page_icon="🧠",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_state()
    load_css()
    brand_header()
    sidebar()

    if st.session_state.get("agent_running"):
        with st.spinner("⏳  Running pipeline…"):
            run_pipeline()
        st.rerun()

    tabs = st.tabs(["🏠 Home", "🔄 Trajectory", "🛡️ Guardrails", "📋 Audit", "🎯 Interview"])
    with tabs[0]: home_tab()
    with tabs[1]: trajectory_tab()
    with tabs[2]: guardrails_tab()
    with tabs[3]: audit_tab()
    with tabs[4]: interview_tab()


if __name__ == "__main__":
    main()
