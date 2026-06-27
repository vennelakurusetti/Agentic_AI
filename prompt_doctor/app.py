"""
Prompt Doctor — Streamlit Application

A prompt engineering learning tool where users write prompts that are
executed and then graded by an AI examiner.

Layout: Two-panel design.
  Left panel  — domain selector, level picker, level task, prompt input.
  Right panel — live AI output and examiner verdict.
"""

import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title="Prompt Doctor",
    page_icon="\U0001fa89",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from levels import (
    DOMAINS,
    LEVELS,
    get_level,
    get_principles_for_level,
    get_max_level,
    get_domains,
)
from runner import run_prompt
from examiner import evaluate

# ---------------------------------------------------------------------------
# Light mode theme via custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
    .stApp { background-color: #f8f9fa; }
    h1, h2, h3, h4, h5, h6 { color: #1a1a2e !important; }
    .stMarkdown, p, li { color: #333333; }
    hr { border-color: #e0e0e0; }

    .stButton button {
        background-color: #4361ee;
        color: white;
        border-radius: 8px;
        font-weight: 600;
        border: none;
    }
    .stButton button:hover {
        background-color: #3a56d4;
        color: white;
    }

    .stTextArea textarea {
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        background-color: #ffffff;
        color: #1a1a2e !important;
        font-size: 14px;
        caret-color: #1a1a2e;
    }
    .stTextArea textarea:focus {
        border-color: #4361ee;
        box-shadow: 0 0 0 1px #4361ee;
        color: #1a1a2e !important;
    }
    .stTextArea textarea::placeholder {
        color: #999999 !important;
    }
    div[data-baseweb="textarea"] textarea {
        color: #1a1a2e !important;
    }
    div[data-baseweb="textarea"] textarea:focus {
        color: #1a1a2e !important;
    }

    .stAlert { border-radius: 8px; }
    .stSuccess { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
    .stError { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    .stWarning { background-color: #fff3cd; color: #856404; border: 1px solid #ffeeba; }
    .stInfo { background-color: #d1ecf1; color: #0c5460; border: 1px solid #bee5eb; }

    .stStatus { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; }
    div[data-testid="stExpander"] { background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; }

    /* Level step cards */
    .level-card {
        background-color: #ffffff;
        border: 2px solid #e0e0e0;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .level-card:hover { border-color: #4361ee; box-shadow: 0 2px 8px rgba(67,97,238,0.1); }
    .level-card.active { border-color: #4361ee; background-color: #f0f2ff; }
    .level-card.passed { border-color: #28a745; background-color: #f0fff4; }
    .level-card.locked { opacity: 0.5; cursor: not-allowed; }
    .level-card .lvl-num { font-size: 20px; font-weight: 700; color: #4361ee; margin-right: 10px; }
    .level-card .lvl-title { font-size: 15px; font-weight: 600; color: #1a1a2e; }
    .level-card .lvl-domain { font-size: 12px; color: #888; margin-top: 2px; }
    .level-card .lvl-principles { font-size: 12px; color: #666; margin-top: 4px; }

    /* Verdict banner */
    .verdict-pass {
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        border: 2px solid #28a745; border-radius: 12px; padding: 20px; text-align: center;
    }
    .verdict-revise {
        background: linear-gradient(135deg, #fff3cd, #ffeeba);
        border: 2px solid #ffc107; border-radius: 12px; padding: 20px; text-align: center;
    }
    .verdict-error {
        background: linear-gradient(135deg, #f8d7da, #f5c6cb);
        border: 2px solid #dc3545; border-radius: 12px; padding: 20px; text-align: center;
    }
    .verdict-title { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
    .verdict-sub  { font-size: 14px; color: #555; }

    /* Principle row */
    .principle-row {
        background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px;
        padding: 14px 16px; margin-bottom: 8px;
    }
    .principle-row.pass { border-left: 4px solid #28a745; }
    .principle-row.fail { border-left: 4px solid #dc3545; }
    .principle-name { font-weight: 600; font-size: 15px; color: #1a1a2e; }
    .principle-weakness { color: #dc3545; font-size: 13px; margin-top: 4px; }
    .principle-question { color: #4361ee; font-size: 13px; margin-top: 4px; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "current_level" not in st.session_state:
    st.session_state.current_level = 1
if "unlocked_levels" not in st.session_state:
    st.session_state.unlocked_levels = {1}
if "selected_domain" not in st.session_state:
    st.session_state.selected_domain = None
if "history" not in st.session_state:
    st.session_state.history = {}
if "submitted_prompt" not in st.session_state:
    st.session_state.submitted_prompt = ""
if "custom_input" not in st.session_state:
    st.session_state.custom_input = ""
if "submitted" not in st.session_state:
    st.session_state.submitted = False

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
left_col, right_col = st.columns([1, 1], gap="large")

# ============================= LEFT PANEL =============================
with left_col:
    st.markdown(
        "<h1 style='margin-bottom:0;'>\U0001fa89 Prompt Doctor</h1>"
        "<p style='color:#666; margin-top:0;'>"
        "Learn prompt engineering across 5 levels. Each level teaches a new principle. "
        "Write a prompt, see what the AI produces, and get graded by an AI examiner.</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # --- Domain dropdown (cosmetic filter) ---
    domain_options = ["All Domains"] + get_domains()
    selected_domain_filter = st.selectbox(
        "\U0001f3f7\ufe0f Filter by domain",
        options=domain_options,
        index=0,
        key="domain_filter",
    )
    st.markdown("---")

    # --- Level selection ---
    st.subheader("\U0001f3af Levels")

    completed_count = sum(
        1 for lvl in range(1, get_max_level() + 1)
        if lvl in st.session_state.history
        and st.session_state.history[lvl].get("result", {}).get("verdict") == "pass"
    )
    st.caption(f"{completed_count}/{get_max_level()} levels completed")

    for level_num in range(1, get_max_level() + 1):
        lvl_data = get_level(level_num)
        unlocked = level_num in st.session_state.unlocked_levels
        is_current = level_num == st.session_state.current_level
        passed = (
            level_num in st.session_state.history
            and st.session_state.history[level_num].get("result", {}).get("verdict") == "pass"
        )

        # Filter by domain if not "All"
        domain_filter = st.session_state.get("domain_filter", "All Domains")
        if domain_filter != "All Domains" and lvl_data["domain"] != domain_filter:
            continue

        principle_labels = " \u2022 ".join(
            [p.replace("_", " ").title() for p in lvl_data["principles"]]
        )
        domain_icon = DOMAINS[lvl_data["domain"]]["icon"]

        if not unlocked:
            st.markdown(
                f"<div class='level-card locked'>"
                f"<div style='display:flex; align-items:center; gap:10px;'>"
                f"<span style='font-size:20px;'>\U0001f512</span>"
                f"<div><div class='lvl-title'>Level {level_num}: {lvl_data['title']}</div>"
                f"<div class='lvl-domain'>{domain_icon} {lvl_data['domain']}</div></div></div></div>",
                unsafe_allow_html=True,
            )
        else:
            cls = "level-card"
            if is_current:
                cls += " active"
            if passed:
                cls += " passed"

            check = "\U00002705 " if passed else ""
            arrow = "\U000025b6 " if is_current else ""

            st.markdown(
                f"<div class='{cls}' onclick=''>"
                f"<div style='display:flex; align-items:center; gap:10px;'>"
                f"<span class='lvl-num'>{check}{arrow}L{level_num}</span>"
                f"<div><div class='lvl-title'>{lvl_data['title']}</div>"
                f"<div class='lvl-domain'>{domain_icon} {lvl_data['domain']} \u2022 {principle_labels}</div></div></div></div>",
                unsafe_allow_html=True,
            )
            if st.button(
                f"Go to Level {level_num}: {lvl_data['title']}",
                key=f"lvl_btn_{level_num}",
                use_container_width=True,
            ):
                st.session_state.current_level = level_num
                st.session_state.submitted = False
                st.session_state.submitted_prompt = ""
                st.rerun()

    st.markdown("---")

    # --- Current level detail + prompt input ---
    level_num = st.session_state.current_level
    level_data = get_level(level_num)
    principles = get_principles_for_level(level_num)
    domain_icon = DOMAINS[level_data["domain"]]["icon"]

    st.subheader(f"\U0001f4dd Current: Level {level_num} \u2014 {level_data['title']}")
    st.markdown(f"**Domain:** {domain_icon} {level_data['domain']}")

    principle_names = [p.replace("_", " ").title() for p in principles]
    st.markdown("**Principles:** " + " \u2022 ".join([f"`{p}`" for p in principle_names]))

    st.info(f"\U0001f3af **Task:** {level_data['task']}")

    with st.expander("\U0001f4a1 Hint"):
        st.markdown(level_data["hint"])

    st.markdown(f"**Default input:** `{level_data['sample_input']}`")

    custom_input = st.text_area(
        "Or type your own input (optional):",
        height=80,
        placeholder="Leave blank to use the default sample input above...",
        key="custom_input_area",
    )

    st.markdown("---")

    user_prompt = st.text_area(
        "Write your prompt:",
        height=180,
        placeholder="Write your prompt here...",
        key="prompt_input_area",
    )

    col_a, col_b = st.columns([1, 3])
    with col_a:
        submitted_click = st.button("\U0001f680 Submit", type="primary", use_container_width=True)
    with col_b:
        st.markdown(
            "<small style='color:#999;'>Your prompt is run against your custom input "
            "(or the default sample) and then graded by the AI examiner.</small>",
            unsafe_allow_html=True,
        )

    if submitted_click:
        if not user_prompt.strip():
            st.warning("Please write a prompt before submitting.")
        else:
            st.session_state.submitted = True
            st.session_state.submitted_prompt = user_prompt
            st.session_state.custom_input = custom_input.strip()
            st.rerun()

# ============================= RIGHT PANEL =============================
with right_col:
    st.subheader("\U0001f4ca Results")

    if not st.session_state.submitted or not st.session_state.submitted_prompt.strip():
        st.markdown(
            "<div style='background:#ffffff; border:2px dashed #e0e0e0; border-radius:12px; "
            "padding:60px 20px; text-align:center; margin-top:20px;'>"
            "<div style='font-size:48px; margin-bottom:16px;'>\U0001fa89</div>"
            "<h3 style='color:#999;'>Waiting for your prompt...</h3>"
            "<p style='color:#aaa;'>Write a prompt on the left panel and hit Submit.<br>"
            "The AI output and examiner grading will appear here.</p></div>",
            unsafe_allow_html=True,
        )
    else:
        user_prompt = st.session_state.submitted_prompt
        level_num = st.session_state.current_level
        level_data = get_level(level_num)
        principles = get_principles_for_level(level_num)
        sample_input = st.session_state.custom_input or level_data["sample_input"]

        # --- Run prompt ---
        with st.status("\U0001f916 Running your prompt...", expanded=True) as run_status:
            st.write(f"**Input:** {sample_input}")
            output = run_prompt(user_prompt, sample_input)
            run_status.update(label="\U00002705 Prompt executed", state="complete")

        st.markdown("### \U0001f916 AI Output")
        if output.startswith("[Error:"):
            st.error(output)
        else:
            st.markdown(
                f"<div style='background:#ffffff; border:1px solid #e0e0e0; border-radius:8px; "
                f"padding:16px; margin-bottom:16px;'>{output}</div>",
                unsafe_allow_html=True,
            )
        st.markdown("---")

        # --- Evaluate ---
        with st.status("\U0001f50d Examiner is grading your prompt...", expanded=True) as exam_status:
            result = evaluate(user_prompt, level_num, principles)
            exam_status.update(label="\U00002705 Grading complete", state="complete")

        # --- Verdict banner ---
        verdict = result.get("verdict", "revise")
        ran_ok = result.get("ran_ok", False)

        if not ran_ok:
            st.markdown(
                "<div class='verdict-error'>"
                "<div class='verdict-title'>\U000026a0 Examiner Error</div>"
                "<div class='verdict-sub'>The examiner could not grade your prompt. See details below.</div></div>",
                unsafe_allow_html=True,
            )
        elif verdict == "pass":
            st.markdown(
                "<div class='verdict-pass'>"
                "<div class='verdict-title'>\U0001f389 Pass</div>"
                "<div class='verdict-sub'>All principles demonstrated successfully!</div></div>",
                unsafe_allow_html=True,
            )
            st.balloons()
            next_level = level_num + 1
            if next_level <= get_max_level():
                st.session_state.unlocked_levels.add(next_level)
                st.success(
                    f"\U0001f514 **Level {next_level}: {get_level(next_level)['title']}** unlocked!"
                )
        # Auto-switch to the next level
                st.session_state.current_level = next_level
                st.session_state.submitted = False
                st.session_state.submitted_prompt = ""
                st.session_state.custom_input = ""
                st.rerun()
        else:
            st.markdown(
                "<div class='verdict-revise'>"
                "<div class='verdict-title'>\U0001f4dd Revise</div>"
                "<div class='verdict-sub'>Some principles need improvement. Review the feedback below.</div></div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # --- Principle breakdown ---
        st.markdown("### \U0001f4cb Principle Breakdown")
        for principle in result.get("principles", []):
            passed = principle.get("pass", False)
            name = principle["name"].replace("_", " ").title()
            weakness = principle.get("weakness", "")
            question = principle.get("question", "")

            cls = "principle-row pass" if passed else "principle-row fail"
            icon = "\U00002705" if passed else "\U0000274c"
            st.markdown(
                f"<div class='{cls}'>"
                f"<div class='principle-name'>{icon} {name}</div>"
                + (f"<div class='principle-weakness'>\U000026a0 {weakness}</div>" if not passed and weakness else "")
                + (f"<div class='principle-question'>\U0001f4a1 {question}</div>" if not passed and question else "")
                + "</div>",
                unsafe_allow_html=True,
            )

        # Save history
        st.session_state.history[level_num] = {
            "prompt": user_prompt,
            "output": output,
            "result": result,
        }

        # Previous attempts
        if level_num in st.session_state.history:
            with st.expander("\U0001f4dc Submission history for this level"):
                st.markdown(f"**Prompt:** `{st.session_state.history[level_num]['prompt'][:80]}...`")
                st.markdown(f"**Verdict:** **{st.session_state.history[level_num]['result'].get('verdict', 'N/A').upper()}**")