"""
session_stats.py — Streamlit "Session Stats" sidebar with live updates.
Tracks total queries, avg latency, P95 latency, total cost, total tokens, error count.
"""

import math
import statistics
from typing import Dict, Any, List

from observability.llm_logger import read_logs


def compute_session_stats() -> Dict[str, Any]:
    """Compute session statistics from the JSONL log file."""
    logs = read_logs(limit=5000)
    if not logs:
        return {
            "total_queries": 0,
            "avg_latency": 0.0,
            "p95_latency": 0.0,
            "total_cost": 0.0,
            "total_tokens": 0,
            "error_count": 0,
            "error_rate": 0.0,
        }

    latencies = [e["latency"] for e in logs if e.get("latency") is not None]
    errors = [e for e in logs if not e.get("success", True)]
    total_cost = sum(e.get("cost", 0) for e in logs)
    total_tokens = sum(e.get("input_tokens", 0) + e.get("output_tokens", 0) for e in logs)

    avg_latency = statistics.mean(latencies) if latencies else 0.0
    sorted_lat = sorted(latencies)
    p95 = sorted_lat[math.ceil(len(sorted_lat) * 0.95) - 1] if sorted_lat else 0.0

    return {
        "total_queries": len(logs),
        "avg_latency": round(avg_latency, 2),
        "p95_latency": round(p95, 2),
        "total_cost": round(total_cost, 6),
        "total_tokens": total_tokens,
        "error_count": len(errors),
        "error_rate": round(len(errors) / len(logs) * 100, 2) if logs else 0.0,
    }


def render_stats_html(stats: Dict[str, Any]) -> str:
    """Render session stats as HTML for the Streamlit sidebar."""
    return f"""
    <div style="background:rgba(255,255,255,0.08);border-radius:8px;padding:0.6rem;margin-bottom:0.5rem;font-size:0.8rem;">
        <div style="display:flex;justify-content:space-between;">
            <span>Queries</span><span><strong>{stats['total_queries']}</strong></span>
        </div>
        <div style="display:flex;justify-content:space-between;">
            <span>Avg Latency</span><span><strong>{stats['avg_latency']}s</strong></span>
        </div>
        <div style="display:flex;justify-content:space-between;">
            <span>P95 Latency</span><span><strong>{stats['p95_latency']}s</strong></span>
        </div>
        <div style="display:flex;justify-content:space-between;">
            <span>Total Cost</span><span><strong>${stats['total_cost']:.6f}</strong></span>
        </div>
        <div style="display:flex;justify-content:space-between;">
            <span>Total Tokens</span><span><strong>{stats['total_tokens']}</strong></span>
        </div>
        <div style="display:flex;justify-content:space-between;">
            <span>Errors</span><span><strong>{stats['error_count']} ({stats['error_rate']}%)</strong></span>
        </div>
    </div>
    """