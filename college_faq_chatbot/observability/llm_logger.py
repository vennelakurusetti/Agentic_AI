"""
llm_logger.py — Wraps every LLM call with logging (timestamp, model, latency, tokens, cost, success/failure).
Persists logs in JSONL format.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Callable
from functools import wraps

import config
from utils import logger

LOG_FILE = config.BASE_DIR / "observability" / "llm_calls.jsonl"

# ── Cost per 1K tokens (OpenRouter approximate) ──
MODEL_COST_PER_1K = {
    "openai/gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
    "openai/gpt-4o": {"input": 0.0025, "output": 0.0100},
    "DEFAULT": {"input": 0.0005, "output": 0.0015},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = MODEL_COST_PER_1K.get(model, MODEL_COST_PER_1K["DEFAULT"])
    return (input_tokens / 1000) * rates["input"] + (output_tokens / 1000) * rates["output"]


def log_llm_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency: float,
    success: bool,
    prompt_version: str = "",
    error: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record a single LLM call to the JSONL log file."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency": round(latency, 3),
        "cost": round(estimate_cost(model, input_tokens, output_tokens), 6),
        "success": success,
        "prompt_version": prompt_version,
        "error": error,
        "metadata": metadata or {},
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def wrap_llm_call(llm_func: Callable, prompt_version: str = "") -> Callable:
    """Decorator that wraps an LLM call function with logging."""
    @wraps(llm_func)
    def wrapper(*args, **kwargs):
        start = time.time()
        success = False
        error = ""
        input_tokens = kwargs.get("input_tokens", 0) or 0
        output_tokens = 0
        model = kwargs.get("model", "") or ""
        try:
            result = llm_func(*args, **kwargs)
            if hasattr(result, "usage_metadata"):
                meta = result.usage_metadata
                input_tokens = meta.get("input_tokens", 0) or 0
                output_tokens = meta.get("output_tokens", 0) or 0
            success = True
            latency = time.time() - start
            log_llm_call(model, input_tokens, output_tokens, latency, True, prompt_version)
            return result
        except Exception as e:
            latency = time.time() - start
            error = str(e)
            log_llm_call(model, input_tokens, output_tokens, latency, False, prompt_version, error=error)
            raise
    return wrapper


def read_logs(limit: int = 1000) -> list[Dict[str, Any]]:
    """Read recent LLM call logs from the JSONL file."""
    if not LOG_FILE.exists():
        return []
    logs = []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                logs.append(json.loads(line))
    return logs[-limit:]