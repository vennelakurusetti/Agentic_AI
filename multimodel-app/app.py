"""
Multi-Model Comparison Tool — Streamlit dashboard.

A clean, light-theme benchmarking UI for comparing LLM answers, latency and
cost side by side. Querying logic lives in main.py (ask / MODELS / PRICES).
"""

import altair as alt
import pandas as pd
import streamlit as st
from openai import APITimeoutError, APIStatusError

from main import ask, MODELS

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Multi-Model Comparison",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PRIMARY = "#6366F1"

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

      html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {
          font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      }
      .stApp { background: #F7F8FA; }

      /* Tighten top padding */
      .block-container { padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1180px; }

      /* Hero */
      .hero-title {
          font-size: 2.05rem; font-weight: 800; letter-spacing: -0.02em;
          color: #0F1117; margin: 0 0 .25rem 0;
      }
      .hero-sub { color: #5B6172; font-size: 1.02rem; margin: 0; }
      .hero-badge {
          display: inline-block; padding: .25rem .65rem; border-radius: 999px;
          background: #EEF0FF; color: #4F46E5; font-size: .76rem; font-weight: 600;
          letter-spacing: .02em; margin-bottom: .75rem;
      }

      /* Cards — bordered containers */
      [data-testid="stVerticalBlockBorderWrapper"] {
          background: #FFFFFF; border: 1px solid #ECEEF2 !important;
          border-radius: 16px; box-shadow: 0 1px 2px rgba(16,17,23,.04),
                                            0 8px 24px rgba(16,17,23,.04);
      }

      /* Metric tiles */
      [data-testid="stMetric"] {
          background: #FFFFFF; border: 1px solid #ECEEF2; border-radius: 14px;
          padding: 1rem 1.1rem; box-shadow: 0 1px 2px rgba(16,17,23,.04);
      }
      [data-testid="stMetricLabel"] { color: #6B7280; font-weight: 600; }
      [data-testid="stMetricValue"] { font-weight: 700; letter-spacing: -0.01em; }

      /* Buttons */
      .stButton > button {
          border-radius: 11px; font-weight: 600; padding: .55rem 1.1rem;
          border: 1px solid #E5E7EB; transition: all .15s ease;
      }
      .stButton > button[kind="primary"] {
          background: #6366F1; border-color: #6366F1;
          box-shadow: 0 1px 2px rgba(99,102,241,.35);
      }
      .stButton > button[kind="primary"]:hover {
          background: #4F46E5; border-color: #4F46E5;
      }

      /* Inputs */
      textarea, .stTextArea textarea {
          border-radius: 12px !important;
      }

      /* Expanders */
      [data-testid="stExpander"] {
          border: 1px solid #ECEEF2; border-radius: 14px; background: #FFFFFF;
          box-shadow: 0 1px 2px rgba(16,17,23,.03);
      }

      /* Dataframe rounding */
      [data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; }

      /* Section headings */
      .section-h {
          font-size: 1.18rem; font-weight: 700; color: #0F1117;
          margin: .25rem 0 .15rem 0; letter-spacing: -0.01em;
      }
      .section-sub { color: #6B7280; font-size: .9rem; margin: 0 0 .6rem 0; }

      /* Rank pill */
      .rank-pill {
          display:inline-block; padding:.15rem .55rem; border-radius:999px;
          font-size:.78rem; font-weight:700;
      }
      hr { margin: 1.4rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state ─────────────────────────────────────────────────────────────
st.session_state.setdefault("running", False)
st.session_state.setdefault("results", None)
st.session_state.setdefault("asked", "")


def short_name(model: str) -> str:
    """`google/gemma-4-31b-it:free` -> `gemma-4-31b-it`."""
    return model.split("/")[-1].replace(":free", "")


def query_all(question: str, models: list) -> list:
    """Call every model with per-model error isolation."""
    out = []
    for model in models:
        try:
            r = ask(question, model)
            out.append({
                "model": model, "ok": True, "answer": r["answer"],
                "latency": r["latency"], "cost_usd": r["cost_usd"],
                "in_tok": r["in_tok"], "out_tok": r["out_tok"],
            })
        except APITimeoutError:
            out.append({"model": model, "ok": False, "error": "Timed out after 30 s"})
        except APIStatusError as e:
            out.append({"model": model, "ok": False, "error": f"HTTP {e.status_code}: {e.message}"})
        except Exception as e:  # noqa: BLE001 — one model must not break the rest
            out.append({"model": model, "ok": False, "error": str(e)})
    return out


# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="hero-badge">BENCHMARKING</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Multi-Model Comparison</div>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-sub">Ask one question, compare answers, latency, and cost across models — side by side.</p>',
    unsafe_allow_html=True,
)
st.write("")

# ── Input card ────────────────────────────────────────────────────────────────
with st.container(border=True):
    question = st.text_area(
        "Your question",
        placeholder="e.g. Explain recursion in one short sentence.",
        height=110,
        key="question_input",
    )
    selected_models = st.multiselect(
        "Models to compare",
        options=MODELS,
        default=MODELS,
        help="Pick which models to run. All four free models are selected by default.",
    )
    c1, c2 = st.columns([1, 4])
    with c1:
        st.button(
            "Compare models",
            type="primary",
            use_container_width=True,
            disabled=not selected_models or st.session_state.running,
            on_click=lambda: st.session_state.update(running=True),
        )
    with c2:
        if st.session_state.running:
            st.caption(" ")

# ── Run (populates session_state.results, then falls through to render) ────────
if st.session_state.running:
    if not question.strip():
        st.session_state.running = False
        st.warning("Please type a question first.")
        st.stop()

    with st.spinner("Querying models…"):
        st.session_state.results = query_all(question, selected_models)
        st.session_state.asked = question
    st.session_state.running = False

# ── Results ───────────────────────────────────────────────────────────────────
results = st.session_state.results

if results:
    ok = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]

    # Rank successful results by speed (fastest first).
    ranked = sorted(ok, key=lambda r: r["latency"])
    rank_of = {r["model"]: i + 1 for i, r in enumerate(ranked)}

    st.markdown("---")
    st.markdown(f'<div class="section-h">Results</div>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="section-sub">Question: “{st.session_state.asked}”</p>',
        unsafe_allow_html=True,
    )

    # ── Summary metric tiles ──────────────────────────────────────────────────
    fastest = ranked[0] if ranked else None
    cheapest = min(ok, key=lambda r: r["cost_usd"]) if ok else None
    avg_latency = sum(r["latency"] for r in ok) / len(ok) if ok else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Models compared", len(results), f"{len(failed)} failed" if failed else "all ok")
    m2.metric("Fastest", short_name(fastest["model"]) if fastest else "—",
              f"{fastest['latency']:.2f}s" if fastest else None)
    m3.metric("Lowest cost", short_name(cheapest["model"]) if cheapest else "—",
              f"${cheapest['cost_usd']:.6f}" if cheapest else None)
    m4.metric("Avg latency", f"{avg_latency:.2f}s" if ok else "—")

    st.write("")

    # ── Controls: sort + filter ───────────────────────────────────────────────
    with st.container(border=True):
        f1, f2, f3 = st.columns([2, 2, 1.4])
        sort_by = f1.selectbox(
            "Sort by",
            ["Fastest first", "Cheapest first", "Most output tokens", "Model name"],
        )
        model_filter = f2.multiselect(
            "Show models",
            options=[r["model"] for r in results],
            default=[r["model"] for r in results],
            format_func=short_name,
        )
        only_ok = f3.toggle("Hide failures", value=False)

    view = [r for r in results if r["model"] in model_filter]
    if only_ok:
        view = [r for r in view if r["ok"]]

    def sort_key(r):
        if not r["ok"]:
            return (1, 0)  # push failures to the bottom regardless of sort
        if sort_by == "Fastest first":
            return (0, r["latency"])
        if sort_by == "Cheapest first":
            return (0, r["cost_usd"])
        if sort_by == "Most output tokens":
            return (0, -r["out_tok"])
        return (0, r["model"])

    view = sorted(view, key=sort_key)

    # ── Comparison table ──────────────────────────────────────────────────────
    st.markdown('<div class="section-h">Comparison table</div>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Click a column header to re-sort. Full responses are below.</p>',
                unsafe_allow_html=True)

    def badge(model, ok):
        if not ok:
            return "—"
        rank = rank_of.get(model)
        return {1: "🥇 #1", 2: "🥈 #2", 3: "🥉 #3"}.get(rank, f"#{rank}")

    rows = []
    for r in view:
        rows.append({
            "Rank": badge(r["model"], r["ok"]),
            "Model": short_name(r["model"]),
            "Status": "✅ OK" if r["ok"] else "⚠️ Failed",
            "Latency (s)": round(r["latency"], 2) if r["ok"] else None,
            "Out tokens": r["out_tok"] if r["ok"] else None,
            "Cost (USD)": r["cost_usd"] if r["ok"] else None,
            "Preview": (r["answer"][:90].replace("\n", " ") + "…") if r["ok"] else r["error"],
        })

    df = pd.DataFrame(rows)
    max_lat = max((r["latency"] for r in view if r["ok"]), default=1) or 1

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Rank": st.column_config.TextColumn("Rank", width="small"),
            "Model": st.column_config.TextColumn("Model", width="medium"),
            "Latency (s)": st.column_config.ProgressColumn(
                "Latency (s)", format="%.2f s", min_value=0, max_value=float(max_lat),
            ),
            "Out tokens": st.column_config.NumberColumn("Out tokens", format="%d"),
            "Cost (USD)": st.column_config.NumberColumn("Cost (USD)", format="$%.6f"),
            "Preview": st.column_config.TextColumn("Preview", width="large"),
        },
    )

    # ── Performance charts ────────────────────────────────────────────────────
    if ok:
        st.write("")
        cc1, cc2 = st.columns(2)

        chart_df = pd.DataFrame([{
            "Model": short_name(r["model"]),
            "Latency": r["latency"],
            "Out tokens": r["out_tok"],
        } for r in view if r["ok"]])

        with cc1:
            st.markdown('<div class="section-h">Latency</div>', unsafe_allow_html=True)
            lat_chart = (
                alt.Chart(chart_df)
                .mark_bar(cornerRadiusEnd=6, color=PRIMARY)
                .encode(
                    x=alt.X("Latency:Q", title="seconds"),
                    y=alt.Y("Model:N", sort="-x", title=None),
                    tooltip=["Model", alt.Tooltip("Latency:Q", format=".2f")],
                )
                .properties(height=max(140, 52 * len(chart_df)))
            )
            st.altair_chart(lat_chart, use_container_width=True)

        with cc2:
            st.markdown('<div class="section-h">Output tokens</div>', unsafe_allow_html=True)
            tok_chart = (
                alt.Chart(chart_df)
                .mark_bar(cornerRadiusEnd=6, color="#22C55E")
                .encode(
                    x=alt.X("Out tokens:Q", title="tokens"),
                    y=alt.Y("Model:N", sort="-x", title=None),
                    tooltip=["Model", "Out tokens"],
                )
                .properties(height=max(140, 52 * len(chart_df)))
            )
            st.altair_chart(tok_chart, use_container_width=True)

    # ── Expandable full responses ─────────────────────────────────────────────
    st.write("")
    st.markdown('<div class="section-h">Full responses</div>', unsafe_allow_html=True)
    for r in view:
        if r["ok"]:
            rank = rank_of.get(r["model"])
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, "•")
            with st.expander(f"{medal}  {short_name(r['model'])}  ·  {r['latency']:.2f}s  ·  ${r['cost_usd']:.6f}"):
                a, b, c = st.columns(3)
                a.metric("Latency", f"{r['latency']:.2f} s")
                b.metric("Output tokens", r["out_tok"])
                c.metric("Cost", f"${r['cost_usd']:.6f}")
                st.markdown(r["answer"])
                st.caption(r["model"])
        else:
            with st.expander(f"⚠️  {short_name(r['model'])}  ·  failed"):
                st.error(r["error"])
                st.caption(r["model"])

    st.markdown("---")
    st.caption(
        "Prices are illustrative, sourced from `PRICES` in main.py. Free models show $0.000000. "
        "Latency is measured client-side and varies with provider load."
    )
else:
    st.info("Enter a question above and click **Compare models** to run a benchmark.", icon="💡")
