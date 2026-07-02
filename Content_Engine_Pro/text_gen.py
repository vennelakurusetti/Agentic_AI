"""
text_gen.py — Text generation module for taglines, blog intros, social posts.

Supports critic feedback injection for self-critique regeneration
and voiceover script generation for TTS.
"""

import json
import logging
import time
from typing import Any

import requests

from config import (
    FEW_SHOT_EXAMPLES,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    RETRY_BACKOFF,
    TEXT_MODEL,
    TEXT_RETRIES,
)

logger = logging.getLogger(__name__)


# ── OpenRouter Helper ────────────────────────────────────────────────────


def _call_openrouter(
    system_prompt: str,
    user_prompt: str,
    max_retries: int = TEXT_RETRIES,
    model: str = TEXT_MODEL,
) -> str:
    """Call OpenRouter chat completion with retry + exponential backoff.

    Args:
        system_prompt: System-level instruction for the LLM.
        user_prompt: User message containing the task.
        max_retries: Maximum number of retry attempts.
        model: Model identifier string.

    Returns:
        Generated text response.

    Raises:
        RuntimeError: If all retries fail.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    last_exception: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "OpenRouter call attempt %d/%d - model=%s",
                attempt, max_retries, model,
            )
            resp = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers, json=payload, timeout=60,
            )
            resp.raise_for_status()
            content: str = resp.json()["choices"][0]["message"]["content"].strip()
            logger.info("OpenRouter success on attempt %d", attempt)
            return content
        except Exception as exc:
            last_exception = exc
            logger.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < max_retries:
                backoff = RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)]
                time.sleep(backoff)

    raise RuntimeError(f"OpenRouter call failed after {max_retries} retries.") from last_exception


# ── Tagline Generation ───────────────────────────────────────────────────


def generate_tagline(
    product: str,
    tone: str,
    critic_feedback: str | None = None,
) -> str:
    """Generate campaign tagline using dynamic few-shot prompting.

    Args:
        product: Product name.
        tone: Brand tone (e.g. 'premium', 'playful').
        critic_feedback: Optional critic feedback for regeneration.

    Returns:
        Generated tagline string.
    """
    examples = FEW_SHOT_EXAMPLES.get(tone.lower(), FEW_SHOT_EXAMPLES["premium"])
    few_shot_block = "\n\n".join(f"Product: {ex[0]}\nTagline: {ex[1]}" for ex in examples)

    feedback_section = ""
    if critic_feedback:
        feedback_section = (
            f"\n\nCritic Feedback (address these issues):\n{critic_feedback}\n"
        )

    system_prompt = (
        "You are a Creative Director.\n\nGenerate ONE memorable campaign tagline.\n\n"
        "Requirements:\n"
        "- Maximum 10 words\n- No hashtags\n- No quotation marks\n"
        "- Emotionally engaging\n- Easy to remember\n"
        "- Match the requested brand tone perfectly.\n\n"
        f"Examples:\n{few_shot_block}"
        f"{feedback_section}"
    )
    return _call_openrouter(system_prompt, f"Product: {product}\nTone: {tone}\n\nTagline:")


# ── Social Posts Generation ─────────────────────────────────────────────


def _validate_social_json(raw: str) -> dict[str, str] | None:
    """Parse and validate social media JSON response.

    Args:
        raw: Raw response string from the LLM.

    Returns:
        Parsed dict with twitter/instagram/linkedin keys, or None on failure.
    """
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data: dict[str, Any] = json.loads(cleaned)
        for key in ("twitter", "instagram", "linkedin"):
            if key not in data or not isinstance(data[key], str):
                return None
        return data
    except (json.JSONDecodeError, TypeError):
        return None


def generate_social_posts(
    product: str,
    audience: str,
    tone: str,
    critic_feedback: str | None = None,
) -> dict[str, str]:
    """Generate platform-specific social posts with structured output.

    Args:
        product: Product name.
        audience: Target audience description.
        tone: Brand tone.
        critic_feedback: Optional critic feedback for regeneration.

    Returns:
        Dict with keys 'twitter', 'instagram', 'linkedin'.
    """
    feedback_section = ""
    if critic_feedback:
        feedback_section = (
            f"\n\nCritic Feedback (address these issues):\n{critic_feedback}\n"
        )

    system_prompt = (
        "Generate platform-specific social media posts.\n\n"
        "Return ONLY valid JSON.\nNo markdown.\nNo explanations.\nNo code fences.\n\n"
        'Schema:\n{\n    "twitter": "",\n    "instagram": "",\n    "linkedin": ""\n}\n\n'
        "Rules:\n"
        "- Twitter: max 280 characters\n"
        "- Instagram: max 2200 characters\n"
        "- LinkedIn: max 700 characters"
        f"{feedback_section}"
    )
    user_prompt = f"Product: {product}\nTone: {tone}\nAudience: {audience}\n\nSocial Media Posts (JSON):"

    raw = _call_openrouter(system_prompt, user_prompt)
    parsed = _validate_social_json(raw)
    if parsed is not None:
        return parsed

    logger.warning("Social JSON parse failed. Retrying once...")
    raw = _call_openrouter(system_prompt, user_prompt)
    parsed = _validate_social_json(raw)
    if parsed is not None:
        return parsed

    logger.error("Social JSON parse failed after retry.")
    return {"twitter": "", "instagram": "", "linkedin": ""}


# ── Blog Introduction Generation ────────────────────────────────────────


def generate_blog_intro(
    product: str,
    audience: str,
    tagline: str,
    tone: str,
    critic_feedback: str | None = None,
) -> str:
    """Write a ~200 word blog introduction using role prompting.

    Args:
        product: Product name.
        audience: Target audience.
        tagline: Campaign tagline to weave in.
        tone: Brand tone.
        critic_feedback: Optional critic feedback for regeneration.

    Returns:
        Blog introduction text.
    """
    feedback_section = ""
    if critic_feedback:
        feedback_section = (
            f"\n\nCritic Feedback (address these issues):\n{critic_feedback}\n"
        )

    system_prompt = (
        "You are an experienced Content Strategist.\n\n"
        "Write an engaging blog introduction.\n\nRequirements:\n"
        "- Exactly 200 words.\n"
        "- Naturally weave the campaign tagline into the narrative.\n"
        "- No headings.\n- No markdown.\n- No bullet points."
        f"{feedback_section}"
    )
    user_prompt = (
        f"Audience: {audience}\nProduct: {product}\n"
        f"Campaign Tagline: {tagline}\nTone: {tone}\n\nBlog Introduction:"
    )
    return _call_openrouter(system_prompt, user_prompt)


# ── Voiceover Script Generation ─────────────────────────────────────────


def generate_voiceover_script(blog_intro: str) -> str:
    """Rewrite blog introduction into a professional narration script.

    Args:
        blog_intro: The blog introduction text to convert.

    Returns:
        Voiceover narration script text.
    """
    system_prompt = (
        "Rewrite this blog introduction into a professional narration script.\n\n"
        "Rules:\n"
        "- Short sentences.\n"
        "- Maximum 15 words each.\n"
        "- Add commas for breathing pauses.\n"
        "- Add ellipses for dramatic pauses.\n"
        "- Remove references to images or visuals.\n"
        "- Output only narration text.\n"
        "- No markdown.\n- No labels."
    )
    user_prompt = f"Blog Introduction:\n\n{blog_intro}\n\nNarration Script:"
    return _call_openrouter(system_prompt, user_prompt)