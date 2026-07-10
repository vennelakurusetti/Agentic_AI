"""
UI Components for TechVest Recruitment Dashboard.
"""

import streamlit as st
import json


def load_css():
    """Inject minimal CSS for proper contrast. Blue upload cards on sidebar."""
    st.markdown("""
    <style>
    .main > div { padding: 0 1rem !important; max-width: 100% !important; }
    .block-container { padding: 1rem 2rem !important; max-width: 100% !important; }
    
    /* ─── Brand Header ─── */
    .brand-bar {
        background: linear-gradient(135deg, #0a2540 0%, #1a3a6b 100%);
        padding: 1rem 2rem;
        border-radius: 0;
        margin: -1rem -2rem 1.5rem -2rem;
        box-shadow: 0 4px 20px rgba(10,37,64,0.15);
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
        box-sizing: border-box;
    }
    .brand-left {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
    }
    .brand-bar h1 {
        color: white !important;
        font-size: 1.4rem;
        font-weight: 700;
        margin: 0;
        line-height: 1.3;
        padding-left: 0;
    }
    .brand-bar p {
        color: rgba(255,255,255,0.7) !important;
        font-size: 0.85rem;
        margin: 0.15rem 0 0 0;
        line-height: 1.4;
        padding-left: 0;
    }
    .brand-bar .badge-model {
        background: rgba(255,255,255,0.12);
        color: rgba(255,255,255,0.85) !important;
        padding: 0.25rem 0.8rem;
        border-radius: 20px;
        font-size: 0.7rem;
        font-weight: 500;
        white-space: nowrap;
        margin-right: 0;
    }
    
    /* ─── Metric Cards ─── */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        border: 1px solid #e2e8f0;
        border-top: 3px solid #1a73e8;
        text-align: center;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100px;
    }
    .metric-card .label {
        color: #64748b !important;
        font-size: 0.8rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0 0 0.2rem 0;
    }
    .metric-card .value {
        font-size: 2rem;
        font-weight: 800;
        margin: 0;
        line-height: 1.2;
    }
    
    .premium-card {
        background: white;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        border: 1px solid #e2e8f0;
    }
    
    .badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 100px; font-size: 0.75rem; font-weight: 600; }
    .badge-interview { background: #dcfce7; color: #166534 !important; }
    .badge-hold { background: #fef3c7; color: #92400e !important; }
    .badge-reject { background: #fce4ec; color: #b71c1c !important; }
    .badge-select { background: #dcfce7; color: #166534 !important; }
    
    /* ─── Sidebar ─── */
    section[data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid rgba(255,255,255,0.06);
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div {
        color: #e2e8f0 !important;
    }
    section[data-testid="stSidebar"] h3 {
        color: #94a3b8 !important;
        font-size: 0.7rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600 !important;
        margin-bottom: 0.3rem;
    }
    section[data-testid="stSidebar"] .stButton button {
        width: 100%; border-radius: 8px; font-weight: 600; font-size: 0.85rem;
        padding: 0.6rem 1rem; border: none;
    }
    section[data-testid="stSidebar"] .stButton button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb, #1d4ed8); color: white !important;
        box-shadow: 0 2px 8px rgba(37,99,235,0.3);
    }
    section[data-testid="stSidebar"] .stButton button[kind="secondary"] { background: rgba(255,255,255,0.08); color: #e2e8f0 !important; }
    
    /* ─── Blue Upload Cards ─── */
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
        background: linear-gradient(135deg, #1a3a6b 0%, #0f2b54 100%);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] section { padding: 0; }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] small { color: #94a3b8 !important; }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] button {
        background: #2563eb; color: white !important; border: none;
        border-radius: 6px; font-weight: 500; font-size: 0.8rem;
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] button:hover { background: #1d4ed8; }
    
    .sidebar-status {
        background: rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .sidebar-status p { color: #cbd5e1 !important; font-size: 0.8rem; margin: 0.4rem 0; }
    .sidebar-status .label { color: #64748b !important; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px; }
    .sidebar-status b { color: #f1f5f9 !important; }
    
    .stProgress > div > div > div > div { background: linear-gradient(90deg, #2563eb, #1d4ed8) !important; }
    .streamlit-expanderHeader { font-weight: 600; font-size: 0.85rem; color: #0f172a; border-radius: 8px; }
    hr { margin: 1.5rem 0; border-color: #e2e8f0 !important; }
    
    [data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0; }
    .stInfo { border-radius: 8px; border: none; background: #eef2ff; }
    .stInfo p { color: #1e3a8a !important; }
    
    div.stButton > button:not([kind]) { border-radius: 8px; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)


def brand_header():
    """Render brand header bar with proper alignment."""
    st.markdown("""
    <div class="brand-bar">
        <div class="brand-left">
            <h1>🧠 TechVest · AI Recruitment Agent</h1>
            <p>Intelligent candidate evaluation powered by LangGraph + GPT-4o Mini</p>
        </div>
        <div>
            <span class="badge-model">⚡ LangGraph Pipeline</span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def metric_card(label: str, value, color: str = "#2563eb"):
    """Render a metric card."""
    st.markdown(f"""
    <div class="metric-card" style="border-top-color:{color};">
        <p class="label">{label}</p>
        <p class="value" style="color:{color};">{value}</p>
    </div>
    """, unsafe_allow_html=True)


def recommendation_badge(decision: str) -> str:
    """Return badge HTML."""
    cls_map = {"SELECT": "badge badge-select", "Interview": "badge badge-interview",
               "REJECT": "badge badge-reject", "Reject": "badge badge-reject",
               "HOLD": "badge badge-hold", "Hold": "badge badge-hold"}
    cls = cls_map.get(decision, "badge badge-hold")
    return f'<span class="{cls}">{decision}</span>'


def render_sidebar_status():
    """Render live status panel in sidebar."""
    status = st.session_state.get("agent_status", "Idle")
    colors = {"Idle": "#94a3b8", "Running": "#2563eb", "Complete": "#16a34a", "Error": "#dc2626"}
    dot_color = colors.get(status, "#94a3b8")
    
    st.markdown(f"""
    <div class="sidebar-status">
        <p><span class="label">Status</span><br>
        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{dot_color};margin-right:6px;"></span>
        <b>{status}</b></p>
        <p><span class="label">Current Step</span><br>{st.session_state.get("current_step","—") or "—"}</p>
        <p><span class="label">Current Candidate</span><br>{st.session_state.get("current_candidate","—") or "—"}</p>
        <p><span class="label">Guardrail</span><br>{"✅ Passed" if st.session_state.get("guardrail_passed",True) else "❌ Flagged"}</p>
        <p><span class="label">Human Approval</span><br>{"✅ Approved" if st.session_state.get("human_approved",False) else "⏳ Pending"}</p>
    </div>
    """, unsafe_allow_html=True)


def candidate_row(rank: int, name: str, score: float, decision: str, slot_str: str = ""):
    """Render a candidate table row."""
    cols = st.columns([0.6, 2.2, 1.2, 1.5, 1.8, 2.0])
    with cols[0]:
        st.markdown(f"<p style='font-weight:700;color:#2563eb;margin:0;'>#{rank}</p>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"<p style='margin:0;'><b>{name}</b></p>", unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"<p style='font-weight:700;margin:0;'>{score:.2f}</p>", unsafe_allow_html=True)
    with cols[3]:
        st.progress(min(score, 1.0))
    with cols[4]:
        st.markdown(recommendation_badge(decision), unsafe_allow_html=True)
    with cols[5]:
        if slot_str:
            st.markdown(f"<p style='color:#64748b;font-size:0.85rem;margin:0;'>📅 {slot_str}</p>", unsafe_allow_html=True)
        else:
            st.markdown("<p style='color:#94a3b8;margin:0;'>—</p>", unsafe_allow_html=True)


def criterion_bars(criteria: list):
    """Render weighted score bars."""
    for c in criteria:
        name = c.get("name", "")
        score = c.get("score", 0)
        weight = c.get("weight", 0)
        evidence = (c.get("evidence", "") or "")[:90]
        pct = score / 5.0
        bar_color = "#16a34a" if score >= 4 else "#eab308" if score >= 2 else "#dc2626"
        
        st.markdown(f"""
        <div style="margin:0.7rem 0;">
            <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-bottom:0.15rem;">
                <span style="color:#0f172a;"><b>{name}</b></span>
                <span style="color:#0f172a;">{score}/5 · <span style="color:#64748b;">{weight}%</span></span>
            </div>
            <div style="background:#e2e8f0;border-radius:6px;height:6px;overflow:hidden;">
                <div style="background:{bar_color};width:{pct*100}%;height:6px;border-radius:6px;"></div>
            </div>
            <div style="font-size:0.75rem;color:#64748b;margin-top:0.15rem;">{evidence}</div>
        </div>
        """, unsafe_allow_html=True)


def trajectory_step(step_num: int, entry: dict):
    """Render a trajectory step."""
    tool = entry.get("tool_used", "—")
    thought = entry.get("thought", "")[:120]
    observation = entry.get("observation", "")[:100]
    decision = entry.get("decision", "")
    args = entry.get("arguments", {})
    changes = entry.get("state_changes", {})
    
    label = f"Step {step_num}: {tool} — {observation[:55]}..."
    with st.expander(label, expanded=False):
        st.markdown(f"**🧠 Thought:** {thought}")
        st.markdown(f"**🔧 Tool:** `{tool}`")
        if args:
            st.markdown(f"**📋 Args:** `{json.dumps(args)[:150]}`")
        st.markdown(f"**👁️ Observation:** {observation}")
        if decision:
            st.markdown(f"**✅ Decision:** `{decision}`")
        if changes:
            st.markdown("**📊 State Changes:**")
            for k, v in changes.items():
                st.markdown(f"- `{k}`: {str(v.get('from','∅'))[:40]} → {str(v.get('to','✓'))[:40]}")


def interview_card(name: str, score: float, slot, approved: bool):
    """Render an interview card."""
    st.markdown(f"""
    <div style="background:white;border-radius:12px;padding:1.2rem;margin:0.8rem 0;
                box-shadow:0 1px 3px rgba(0,0,0,0.06);border:1px solid #e2e8f0;
                border-left:4px solid {'#16a34a' if approved else '#2563eb'};">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <span style="font-weight:700;font-size:1rem;color:#0f172a;">{name}</span>
                {recommendation_badge('Interview')}
            </div>
            <div style="text-align:right;">
                <span style="font-size:0.8rem;color:#64748b;">Score: {score:.2f}</span>
            </div>
        </div>
        <div style="margin-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:0.85rem;color:#0f172a;">
                📅 {slot.date} at {slot.time} · <span style="color:#64748b;">{slot.format}</span>
            </span>
            <span style="font-size:0.8rem;font-weight:600;color:{'#16a34a' if approved else '#eab308'};">
                {'✅ Approved' if approved else '⏳ Pending Approval'}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)