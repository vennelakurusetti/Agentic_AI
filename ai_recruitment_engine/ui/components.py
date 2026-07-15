"""
TechVest UI Components
======================
Minimal, reliable UI primitives.
Rule: use st.metric / st.columns / st.progress natively wherever possible.
HTML only for badges, coloured pills, and card borders that Streamlit cannot produce.
"""

import json
import os

import streamlit as st


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────────────────────

def load_css():
    st.markdown("""
    <style>

    /* ── Page background ─────────────────────────────────────────── */
    .main .block-container {
        padding-top: 1.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }

    /* ── Sidebar ──────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background-color: #0f172a !important;
    }
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stTextInput input {
        color: #cbd5e1 !important;
    }
    [data-testid="stSidebar"] h3 {
        color: #475569 !important;
        font-size: 0.65rem !important;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        font-weight: 700 !important;
        margin: 0.8rem 0 0.3rem 0 !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.08) !important;
        margin: 0.8rem 0 !important;
    }
    /* Run button */
    [data-testid="stSidebar"] [data-testid="baseButton-primary"] {
        background: #2563eb !important;
        color: #fff !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
        background: rgba(255,255,255,0.07) !important;
        color: #94a3b8 !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 8px !important;
    }
    /* File uploader area */
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
        background: #1e293b !important;
        border: 1px dashed #334155 !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] *:not(button) {
        color: #64748b !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
        background: #2563eb !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        font-size: 0.8rem !important;
    }

    /* ── Tabs ─────────────────────────────────────────────────────── */
    [data-testid="stTabs"] [data-baseweb="tab"] {
        font-weight: 600;
        font-size: 0.85rem;
        padding: 0.5rem 1rem;
    }
    [data-testid="stTabs"] [aria-selected="true"] {
        color: #2563eb !important;
        border-bottom: 2px solid #2563eb !important;
    }

    /* ── Progress bar ─────────────────────────────────────────────── */
    [data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, #2563eb, #7c3aed) !important;
    }

    /* ── Badges ───────────────────────────────────────────────────── */
    .tv-badge {
        display: inline-block;
        padding: 0.18rem 0.6rem;
        border-radius: 999px;
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        line-height: 1.5;
        vertical-align: middle;
    }
    .tv-select  { background: #dcfce7; color: #15803d; }
    .tv-hold    { background: #fef9c3; color: #854d0e; }
    .tv-reject  { background: #fee2e2; color: #b91c1c; }
    .tv-pass    { background: #dcfce7; color: #15803d; }
    .tv-flag    { background: #fee2e2; color: #b91c1c; }
    .tv-purple  { background: #ede9fe; color: #6d28d9; }
    .tv-blue    { background: #dbeafe; color: #1d4ed8; }

    /* ── Score pill ───────────────────────────────────────────────── */
    .tv-score {
        display: inline-block;
        padding: 0.25rem 0.55rem;
        border-radius: 7px;
        font-size: 0.88rem;
        font-weight: 800;
        color: white;
        min-width: 52px;
        text-align: center;
    }

    /* ── Left-border cards ───────────────────────────────────────── */
    .tv-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
        margin: 0.3rem 0 0.5rem 0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    /* ── Metric card ──────────────────────────────────────────────── */
    .tv-metric {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        border-top: 3px solid #2563eb;
        padding: 0.9rem 1rem;
        text-align: center;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .tv-metric .tv-m-label {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.7px;
        font-weight: 700;
        color: #64748b;
        margin: 0 0 0.25rem 0;
    }
    .tv-metric .tv-m-value {
        font-size: 2.1rem;
        font-weight: 900;
        margin: 0;
        line-height: 1;
    }

    /* ── Criterion bars ───────────────────────────────────────────── */
    .tv-crit { margin: 0.5rem 0; }
    .tv-crit-track {
        background: #f1f5f9;
        border-radius: 4px;
        height: 7px;
        overflow: hidden;
        margin: 0.12rem 0 0.08rem 0;
    }
    .tv-crit-fill { height: 7px; border-radius: 4px; }

    /* ── Sidebar status panel ─────────────────────────────────────── */
    .tv-status {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.09);
        border-radius: 10px;
        padding: 0.7rem 0.9rem;
    }
    .tv-status-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.22rem 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .tv-status-row:last-child { border-bottom: none; }
    .tv-sl { font-size: 0.63rem; text-transform: uppercase;
             letter-spacing: 0.9px; color: #475569 !important; font-weight: 600; }
    .tv-sv { font-size: 0.78rem; font-weight: 600; color: #e2e8f0 !important; }

    /* ── Trajectory expander ──────────────────────────────────────── */
    [data-testid="stExpander"] summary {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: #1e293b !important;
    }

    /* ── DataFrames ───────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border-radius: 8px !important;
    }

    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# BRAND HEADER
# ─────────────────────────────────────────────────────────────────────────────

def brand_header():
    model = st.session_state.get("model") or os.getenv("MODEL", "openai/gpt-4o-mini")
    c_title, c_badge = st.columns([9, 1])
    with c_title:
        st.markdown(
            "<h2 style='margin:0 0 0.1rem 0;color:#0f172a;font-weight:900;line-height:1.2;'>"
            "🧠 TechVest <span style='color:#2563eb;'>AI Recruitment</span></h2>"
            f"<p style='margin:0;color:#64748b;font-size:0.82rem;'>"
            f"Powered by LangGraph &nbsp;·&nbsp; Model: <code>{model}</code></p>",
            unsafe_allow_html=True,
        )
    with c_badge:
        st.markdown(
            "<div style='padding-top:0.6rem;text-align:right;'>"
            "<span class='tv-badge tv-purple'>⚡ LangGraph</span>"
            "</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "<div style='height:1px;background:#e2e8f0;margin:0.7rem 0 1rem 0;'></div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# METRIC CARD
# ─────────────────────────────────────────────────────────────────────────────

def metric_card(label: str, value, color: str = "#2563eb"):
    st.markdown(
        f"<div class='tv-metric' style='border-top-color:{color};'>"
        f"<p class='tv-m-label'>{label}</p>"
        f"<p class='tv-m-value' style='color:{color};'>{value}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# BADGES
# ─────────────────────────────────────────────────────────────────────────────

def recommendation_badge(decision: str) -> str:
    _cls   = {"SELECT":"tv-select","HOLD":"tv-hold","REJECT":"tv-reject",
               "Interview":"tv-select","Hold":"tv-hold","Reject":"tv-reject"
              }.get(decision, "tv-hold")
    _label = {"SELECT":"✓ SELECT","HOLD":"◉ HOLD","REJECT":"✕ REJECT",
               "Interview":"✓ SELECT","Hold":"◉ HOLD","Reject":"✕ REJECT"
              }.get(decision, decision)
    return f'<span class="tv-badge {_cls}">{_label}</span>'


def guardrail_badge(passed: bool) -> str:
    return (
        '<span class="tv-badge tv-pass">✓ Passed</span>'
        if passed else
        '<span class="tv-badge tv-flag">✕ Flagged</span>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# SCORE PILL
# ─────────────────────────────────────────────────────────────────────────────

def score_pill(score: float) -> str:
    bg = "#16a34a" if score >= 0.60 else "#d97706" if score >= 0.40 else "#dc2626"
    return f"<span class='tv-score' style='background:{bg};'>{score:.2f}</span>"


# backward-compat alias used by streamlit_app.py
def score_ring(score: float) -> str:
    return score_pill(score)


# ─────────────────────────────────────────────────────────────────────────────
# CANDIDATE RANKING ROW
# ─────────────────────────────────────────────────────────────────────────────

def candidate_row(rank: int, name: str, score: float, decision: str, slot_str: str = ""):
    """
    Renders one row in the ranking table.
    Columns: rank | name | score-pill | progress | badge | slot
    """
    c_rank, c_name, c_score, c_prog, c_dec, c_slot = st.columns([0.35, 2.2, 0.9, 1.6, 1.4, 1.8])

    with c_rank:
        st.markdown(
            f"<div style='padding-top:0.4rem;font-weight:800;"
            f"color:#2563eb;font-size:0.95rem;'>#{rank}</div>",
            unsafe_allow_html=True,
        )
    with c_name:
        st.markdown(
            f"<div style='padding-top:0.45rem;font-weight:600;"
            f"font-size:0.92rem;color:#0f172a;'>{name}</div>",
            unsafe_allow_html=True,
        )
    with c_score:
        st.markdown(
            f"<div style='padding-top:0.3rem;'>{score_pill(score)}</div>",
            unsafe_allow_html=True,
        )
    with c_prog:
        st.markdown("<div style='padding-top:0.55rem;'>", unsafe_allow_html=True)
        st.progress(min(float(score), 1.0))
        st.markdown("</div>", unsafe_allow_html=True)
    with c_dec:
        st.markdown(
            f"<div style='padding-top:0.4rem;'>{recommendation_badge(decision)}</div>",
            unsafe_allow_html=True,
        )
    with c_slot:
        txt = f"📅 {slot_str}" if slot_str else "—"
        colour = "#475569" if slot_str else "#cbd5e1"
        st.markdown(
            f"<div style='padding-top:0.45rem;font-size:0.8rem;color:{colour};'>{txt}</div>",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# CRITERION BARS
# ─────────────────────────────────────────────────────────────────────────────

def criterion_bars(criteria: list):
    for c in criteria:
        name     = c.get("name", "")
        raw      = c.get("score", 0)
        score    = int(raw) if isinstance(raw, (int, float)) else 0
        weight   = c.get("weight", 0)
        evidence = (c.get("evidence", "") or "")[:120]
        pct      = (score / 5.0) * 100
        fill_col = "#16a34a" if score >= 4 else "#d97706" if score >= 2 else "#dc2626"

        st.markdown(
            f"<div class='tv-crit'>"
            # label row
            f"<div style='display:flex;justify-content:space-between;"
            f"font-size:0.82rem;margin-bottom:0.08rem;'>"
            f"<span style='font-weight:600;color:#1e293b;'>{name}</span>"
            f"<span style='color:#475569;'>{score}<span style='color:#94a3b8;'>/5</span>"
            f"&nbsp;<span style='font-size:0.72rem;color:#94a3b8;'>({weight}%)</span></span>"
            f"</div>"
            # bar
            f"<div class='tv-crit-track'>"
            f"<div class='tv-crit-fill' style='background:{fill_col};width:{pct:.1f}%;'></div>"
            f"</div>"
            # evidence
            f"<div style='font-size:0.71rem;color:#64748b;font-style:italic;'>{evidence}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# TRAJECTORY STEP
# ─────────────────────────────────────────────────────────────────────────────

_TOOL_ICONS = {
    "parse_jd":          "📄",
    "generate_rubric":   "📐",
    "create_plan":       "🗒️",
    "parse_resume":      "👤",
    "score_candidate":   "📊",
    "make_decision":     "⚖️",
    "guardrail_check":   "🛡️",
    "propose_interview": "📅",
    "check_availability":"🗓️",
    "agent_stop":        "🏁",
}


def trajectory_step(step_num: int, entry: dict):
    tool        = entry.get("tool_used", "—")
    thought     = (entry.get("thought", "") or "")[:160]
    observation = (entry.get("observation", "") or "")[:140]
    decision    = (entry.get("decision", "") or "")
    args        = entry.get("arguments", {})
    changes     = entry.get("state_changes", {})
    icon        = _TOOL_ICONS.get(tool, "🔧")

    # Decision colour
    if "ERROR" in decision.upper():
        d_col = "#dc2626"; d_bg = "#fef2f2"
    elif decision == "FLAGGED":
        d_col = "#d97706"; d_bg = "#fffbeb"
    elif decision == "PIPELINE_COMPLETE":
        d_col = "#7c3aed"; d_bg = "#f5f3ff"
    else:
        d_col = "#16a34a"; d_bg = "#f0fdf4"

    label = f"{icon} Step {step_num}  ·  {tool}"
    with st.expander(label, expanded=False):
        col_main, col_dec = st.columns([4, 1])
        with col_main:
            st.markdown(
                f"<p style='margin:0 0 0.3rem 0;font-size:0.82rem;color:#475569;'>"
                f"<b style='color:#0f172a;'>Thought:</b> {thought}</p>"
                f"<p style='margin:0;font-size:0.82rem;color:#475569;'>"
                f"<b style='color:#0f172a;'>Observation:</b> {observation}</p>",
                unsafe_allow_html=True,
            )
        with col_dec:
            if decision:
                st.markdown(
                    f"<div style='text-align:right;padding-top:0.1rem;'>"
                    f"<span style='font-size:0.68rem;font-weight:700;color:{d_col};"
                    f"background:{d_bg};padding:0.2rem 0.5rem;border-radius:6px;"
                    f"border:1px solid {d_col}33;display:inline-block;'>{decision}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

        if args:
            st.markdown(
                f"<p style='font-size:0.76rem;color:#64748b;margin:0.25rem 0 0 0;'>"
                f"<b>Args:</b> <code style='background:#f8fafc;padding:0.1rem 0.3rem;"
                f"border-radius:4px;'>{json.dumps(args)[:220]}</code></p>",
                unsafe_allow_html=True,
            )
        if changes:
            parts = []
            for k, v in changes.items():
                frm = str(v.get("from", "∅"))[:45]
                to  = str(v.get("to",   "✓"))[:45]
                parts.append(
                    f"<span style='color:#94a3b8;'>{frm}</span>"
                    f" → <b style='color:#0f172a;'>{to}</b>"
                )
            changes_html = " &nbsp;|&nbsp; ".join(
                f"<code>{k}</code>: {p}" for (k, _), p in zip(changes.items(), parts)
            )
            st.markdown(
                f"<p style='font-size:0.75rem;color:#475569;margin:0.2rem 0 0 0;'>"
                f"<b>State:</b> {changes_html}</p>",
                unsafe_allow_html=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# INTERVIEW CARD
# ─────────────────────────────────────────────────────────────────────────────

def interview_card(name: str, score: float, slot, approved: bool):
    border  = "#16a34a" if approved else "#2563eb"
    s_color = "#16a34a" if approved else "#d97706"
    s_text  = "✅ Confirmed" if approved else "⏳ Pending"
    st.markdown(
        f"<div class='tv-card' style='border-left:4px solid {border};'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
        f"<span style='font-weight:700;color:#0f172a;font-size:0.95rem;'>{name}</span>"
        f"<span style='font-size:0.78rem;font-weight:700;color:{s_color};'>{s_text}</span>"
        f"</div>"
        f"<div style='margin-top:0.4rem;font-size:0.82rem;color:#475569;'>"
        f"📅 <b>{slot.date}</b> &nbsp;at&nbsp; <b>{slot.time}</b>"
        f" &nbsp;·&nbsp; {slot.format}"
        f" &nbsp;·&nbsp; Score: {score_pill(score)}"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR STATUS PANEL
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar_status():
    status = st.session_state.get("agent_status", "Idle")
    dot_color = {"Idle":"#475569","Running":"#3b82f6","Complete":"#22c55e","Error":"#ef4444"}.get(status,"#475569")
    n_proc = len(st.session_state.get("results", []))
    n_sel  = len(st.session_state.get("selected_candidates", []))
    step   = (st.session_state.get("current_step") or "—")[:30]
    cand   = (st.session_state.get("current_candidate") or "—")[:20]
    appr   = "✅ Yes" if st.session_state.get("human_approved") else "⏳ No"

    dot = (f"<span style='display:inline-block;width:7px;height:7px;border-radius:50%;"
           f"background:{dot_color};margin-right:5px;vertical-align:middle;'></span>")

    rows = [
        ("Status",      f"{dot}{status}"),
        ("Step",        step),
        ("Candidate",   cand),
        ("Processed",   f"{n_proc} cand."),
        ("Shortlisted", f"{n_sel} selected"),
        ("Approved",    appr),
    ]

    html = "<div class='tv-status'>" + "".join(
        f"<div class='tv-status-row'>"
        f"<span class='tv-sl'>{lbl}</span>"
        f"<span class='tv-sv'>{val}</span>"
        f"</div>"
        for lbl, val in rows
    ) + "</div>"
    st.markdown(html, unsafe_allow_html=True)
