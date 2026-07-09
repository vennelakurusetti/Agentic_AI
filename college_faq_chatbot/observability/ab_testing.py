"""
ab_testing.py — A/B testing for two grounding prompts (current vs. stricter).
Randomly assigns versions, logs prompt version, citations, refusals.
"""

import random
from typing import Dict, Any, Optional, Tuple

import config
from observability.llm_logger import log_llm_call
from utils import logger

# ── Prompt Versions ──
PROMPT_VERSIONS = {
    "A": "current",
    "B": "stricter",
}

# Grounding prompt A (current) — flexible
PROMPT_A = (
    "You are a helpful assistant for BVRIT Hyderabad College of Engineering for Women. "
    "Answer based on the provided context. If the context doesn't contain enough "
    "information, say so clearly."
)

# Grounding prompt B (stricter) — refuses ungrounded answers
PROMPT_B = (
    "You are a strict assistant for BVRIT Hyderabad College of Engineering for Women. "
    "You MUST ONLY answer using information explicitly present in the provided context. "
    "If the context does not contain the answer, respond with: "
    "'This information is not available in the uploaded knowledge base.' "
    "Do NOT infer, guess, or use external knowledge."
)


def get_prompt_version() -> Tuple[str, str]:
    """Randomly assign a prompt version (A or B). Returns (version_id, prompt_text)."""
    version = random.choice(["A", "B"])
    prompt = PROMPT_A if version == "A" else PROMPT_B
    logger.info(f"A/B test: assigned prompt version {version} ({PROMPT_VERSIONS[version]})")
    return version, prompt


def log_ab_result(
    version: str,
    citations: list,
    refused: bool,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Log A/B test result to the JSONL log file."""
    log_llm_call(
        model="N/A",
        input_tokens=0,
        output_tokens=0,
        latency=0,
        success=True,
        prompt_version=version,
        metadata={
            "ab_version": version,
            "ab_label": PROMPT_VERSIONS.get(version, "unknown"),
            "citations_count": len(citations),
            "citations": citations,
            "refused": refused,
            **(metadata or {}),
        },
    )