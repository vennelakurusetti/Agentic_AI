"""
log_analyzer.py — Production log analyzer to detect anomalies and suggest root causes.
"""

from typing import Dict, Any, List, Optional
from collections import Counter

from observability.llm_logger import read_logs
from utils import logger


def analyze_logs(limit: int = 500) -> Dict[str, Any]:
    """
    Analyze recent LLM logs and return:
      - anomaly_detected: bool
      - anomalies: list of anomaly descriptions
      - root_causes: list of suggested root causes
    """
    logs = read_logs(limit=limit)
    if not logs:
        return {"anomaly_detected": False, "anomalies": [], "root_causes": []}

    anomalies = []
    root_causes = []

    # 1. Check for high error rate
    errors = [e for e in logs if not e.get("success", True)]
    if errors:
        error_rate = (len(errors) / len(logs)) * 100
        if error_rate > 5:
            anomalies.append(f"High error rate: {error_rate:.1f}% ({len(errors)}/{len(logs)})")
            # Root cause: check error messages
            error_msgs = Counter(e.get("error", "") for e in errors)
            top_errors = error_msgs.most_common(3)
            for err, count in top_errors:
                root_causes.append(f"Frequent error ({count}x): {err[:100]}")

    # 2. Check for latency spikes
    latencies = [e["latency"] for e in logs if e.get("latency") is not None and e.get("success")]
    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        spikes = [l for l in latencies if l > avg_lat * 2]
        if spikes:
            anomalies.append(f"Latency spikes: {len(spikes)}/{len(latencies)} calls > 2x avg ({avg_lat:.2f}s)")
            root_causes.append("Possible causes: large context windows, API throttling, or model overload")

    # 3. Check for cost outliers
    costs = [e.get("cost", 0) for e in logs if e.get("cost") is not None]
    if costs:
        avg_cost = sum(costs) / len(costs)
        high_cost = [c for c in costs if c > avg_cost * 3 and c > 0.01]
        if high_cost:
            anomalies.append(f"Cost outliers: {len(high_cost)} queries with cost > 3x avg (${avg_cost:.6f})")
            root_causes.append("Possible causes: very long responses, model upgrades, or verbose prompts")

    # 4. Check for model consistency
    models = [e.get("model", "") for e in logs if e.get("model")]
    if models:
        model_counts = Counter(models)
        if len(model_counts) > 1:
            anomalies.append(f"Multiple models in use: {dict(model_counts)}")
            root_causes.append("Verify model configuration is consistent across all calls")

    # 5. Check for input length anomalies
    input_tokens = [e.get("input_tokens", 0) for e in logs if e.get("input_tokens")]
    if input_tokens:
        avg_input = sum(input_tokens) / len(input_tokens)
        long_inputs = [t for t in input_tokens if t > avg_input * 2]
        if long_inputs:
            anomalies.append(f"Large inputs: {len(long_inputs)} queries with > 2x avg input tokens ({avg_input:.0f})")
            root_causes.append("Possible causes: memory context injection, long conversation history, or verbose queries")

    return {
        "anomaly_detected": len(anomalies) > 0,
        "anomalies": anomalies,
        "root_causes": root_causes,
        "total_logs_analyzed": len(logs),
        "error_count": len(errors),
    }