"""
pages/1_📊_Logs.py — Observability & Logs dashboard page.
Shows LLM call logs, latency charts, cost tracking, and anomaly detection.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
import config
from observability.llm_logger import read_logs
from observability.session_stats import compute_session_stats, render_stats_html
from observability.log_analyzer import analyze_logs
from observability.threshold_alerts import check_all_alerts

st.set_page_config(
    page_title="Logs & Observability — BVRIT FAQ",
    page_icon="📊",
    layout="wide",
)

# ── Shared CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%) !important; }
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        text-align: center;
        border-left: 4px solid #3949ab;
    }
    .metric-value { font-size: 1.8rem; font-weight: 700; color: #1a237e; }
    .metric-label { font-size: 0.85rem; color: #666; margin-top: 0.2rem; }
    .alert-card {
        padding: 0.8rem 1rem;
        border-radius: 8px;
        margin-bottom: 0.6rem;
    }
    .alert-warning { background: #fff3cd; border-left: 4px solid #ffc107; }
    .alert-ok { background: #d4edda; border-left: 4px solid #28a745; }
    .alert-error { background: #f8d7da; border-left: 4px solid #dc3545; }
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown("## 📊 Observability & Logs Dashboard")
    st.caption("Real-time monitoring of all LLM calls, latency, cost, and anomalies.")

    # ── Stats row ──────────────────────────────────────────────────────────
    stats = compute_session_stats()
    cols = st.columns(6)
    metrics = [
        ("Total Queries", stats["total_queries"], "📊"),
        ("Avg Latency", f"{stats['avg_latency']}s", "⏱️"),
        ("P95 Latency", f"{stats['p95_latency']}s", "📈"),
        ("Total Cost", f"${stats['total_cost']:.6f}", "💰"),
        ("Total Tokens", f"{stats['total_tokens']:,}", "🔤"),
        ("Error Rate", f"{stats['error_rate']}%", "❌"),
    ]
    for col, (label, value, icon) in zip(cols, metrics):
        with col:
            st.markdown(
                f'<div class="metric-card">'
                f'<div class="metric-value">{icon} {value}</div>'
                f'<div class="metric-label">{label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Anomaly detection ──────────────────────────────────────────────────
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### 🔍 Log Analysis & Anomaly Detection")
        if st.button("🔄 Refresh Analysis", use_container_width=False):
            st.cache_data.clear()

        analysis = analyze_logs()
        if analysis["anomaly_detected"]:
            st.error(f"⚠️ {len(analysis['anomalies'])} anomalies detected in recent logs")
            for anomaly in analysis["anomalies"]:
                st.markdown(
                    f'<div class="alert-card alert-warning">⚠️ {anomaly}</div>',
                    unsafe_allow_html=True,
                )
            if analysis["root_causes"]:
                st.markdown("**Root Cause Suggestions:**")
                for cause in analysis["root_causes"]:
                    st.info(f"💡 {cause}")
        else:
            st.markdown(
                f'<div class="alert-card alert-ok">✅ No anomalies detected in last {analysis["total_logs_analyzed"]} log entries</div>',
                unsafe_allow_html=True,
            )

    with col2:
        st.markdown("### 📋 Quick Stats")
        st.markdown(render_stats_html(stats), unsafe_allow_html=True)

    st.markdown("---")

    # ── Log table ──────────────────────────────────────────────────────────
    st.markdown("### 📋 Recent LLM Calls (last 100)")
    logs = read_logs(limit=100)

    if not logs:
        st.info("No logs yet. Start chatting to generate logs!")
    else:
        # Build dataframe
        rows = []
        for log in reversed(logs):
            ts = log.get("timestamp", "")
            try:
                ts = datetime.fromisoformat(ts).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
            rows.append({
                "Timestamp": ts,
                "Model": log.get("model", ""),
                "Input Tokens": log.get("input_tokens", 0),
                "Output Tokens": log.get("output_tokens", 0),
                "Latency (s)": log.get("latency", 0),
                "Cost ($)": f"{log.get('cost', 0):.6f}",
                "Success": "✅" if log.get("success") else "❌",
                "Prompt Ver.": log.get("prompt_version", ""),
                "Error": log.get("error", "")[:40] if log.get("error") else "",
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, height=400)

        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label="⬇️ Download Logs as CSV",
            data=csv,
            file_name=f"llm_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

    st.markdown("---")

    # ── Latency histogram ──────────────────────────────────────────────────
    if logs:
        latencies = [log.get("latency", 0) for log in logs if log.get("latency")]
        if latencies:
            st.markdown("### ⏱️ Latency Distribution")
            lat_df = pd.DataFrame({"Latency (s)": latencies})
            st.bar_chart(lat_df["Latency (s)"].value_counts().sort_index())

    # ── A/B Test summary ───────────────────────────────────────────────────
    st.markdown("### 🧪 A/B Prompt Test Summary")
    ab_logs = [log for log in logs if log.get("metadata", {}).get("ab_version")]
    if ab_logs:
        ab_data = {}
        for log in ab_logs:
            ver = log["metadata"]["ab_version"]
            ab_data.setdefault(ver, {"count": 0, "refused": 0, "citations_total": 0})
            ab_data[ver]["count"] += 1
            if log["metadata"].get("refused"):
                ab_data[ver]["refused"] += 1
            ab_data[ver]["citations_total"] += log["metadata"].get("citations_count", 0)

        ab_rows = []
        for ver, data in ab_data.items():
            ab_rows.append({
                "Version": ver,
                "Queries": data["count"],
                "Refusals": data["refused"],
                "Refusal Rate": f"{data['refused'] / data['count']:.1%}" if data["count"] > 0 else "0%",
                "Avg Citations": f"{data['citations_total'] / data['count']:.1f}" if data["count"] > 0 else "0",
            })
        if ab_rows:
            st.dataframe(pd.DataFrame(ab_rows), use_container_width=True)
    else:
        st.info("No A/B test data yet. A/B testing begins on first query.")


if __name__ == "__main__":
    main()
