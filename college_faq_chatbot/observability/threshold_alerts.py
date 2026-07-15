"""
threshold_alerts.py — Monitor latency, cost, and error rate thresholds.
Rejects inputs over 2000 characters with logging.
"""

import time
from typing import Dict, Any, Optional, List

import config
from observability.llm_logger import read_logs, log_llm_call
from utils import logger

# ── Thresholds ──
MAX_LATENCY = 10.0        # seconds
MAX_COST_PER_QUERY = 0.10  # USD
MAX_ERROR_RATE = 5.0       # percent
MAX_INPUT_LENGTH = 2000    # characters


def check_latency_alert(latency: float) -> Optional[str]:
    """Alert if latency exceeds threshold."""
    if latency > MAX_LATENCY:
        msg = f"[WARN] Latency alert: {latency:.2f}s exceeds {MAX_LATENCY}s threshold"
        logger.warning(msg)
        return msg
    return None


def check_cost_alert(cost: float) -> Optional[str]:
    """Alert if cost per query exceeds threshold."""
    if cost > MAX_COST_PER_QUERY:
        msg = f"[WARN] Cost alert: ${cost:.6f} exceeds ${MAX_COST_PER_QUERY} threshold"
        logger.warning(msg)
        return msg
    return None


def check_error_rate_alert() -> Optional[str]:
    """Alert if error rate over last 100 queries exceeds threshold."""
    logs = read_logs(limit=100)
    if not logs:
        return None
    error_count = sum(1 for e in logs if not e.get("success", True))
    error_rate = (error_count / len(logs)) * 100
    if error_rate > MAX_ERROR_RATE:
        msg = f"[WARN] Error rate alert: {error_rate:.1f}% exceeds {MAX_ERROR_RATE}% threshold"
        logger.warning(msg)
        return msg
    return None


def validate_input_length(user_input: str) -> Optional[str]:
    """Reject inputs over max length. Returns error message or None."""
    if len(user_input) > MAX_INPUT_LENGTH:
        msg = f"Input too long ({len(user_input)} chars). Maximum is {MAX_INPUT_LENGTH} characters."
        logger.warning(f"Input rejected: {len(user_input)} chars (max {MAX_INPUT_LENGTH})")
        log_llm_call(
            model="N/A",
            input_tokens=len(user_input),
            output_tokens=0,
            latency=0,
            success=False,
            error=f"Input too long: {len(user_input)} chars",
            metadata={"rejection_reason": "input_too_long", "input_length": len(user_input)},
        )
        return msg
    return None


def check_all_alerts(latency: float, cost: float) -> List[str]:
    """Run all threshold checks and return list of alert messages."""
    alerts = []
    for check in [check_latency_alert(latency), check_cost_alert(cost), check_error_rate_alert()]:
        if check:
            alerts.append(check)
    return alerts