"""
adapter.py — Multi-Channel Adaptation Module

Rewrites campaign assets (tagline, blog, social posts) for different
channels: B2B LinkedIn, Gen-Z TikTok, Parents Facebook.
Keeps hero image and promotional video UNCHANGED.
"""

import json
import logging
from typing import Any

from config import (
    ADAPTATION_MODEL,
    ADAPTATION_RETRIES,
    CHANNEL_OPTIONS,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    RETRY_BACKOFF,
)
from text_gen import _call_openrouter

logger = logging.getLogger(__name__)


# ── Adaptation System Prompt ────────────────────────────────────────────

ADAPTATION_SYSTEM_PROMPT: str = (
    "Rewrite the following campaign assets for a specific channel.\n\n"
    "Adapt:\n"
    "- tone\n"
    "- vocabulary\n"
    "- emoji usage\n"
    "- marketing language\n\n"
    "Return ONLY valid JSON.\n"
    "No markdown.\nNo explanations.\nNo code fences.\n\n"
    'Schema:\n{\n    "tagline":"",\n    "blog":"",\n    "social":""\n}\n\n'
    "The 'social' field should be a single string containing all three "
    "platform posts (Twitter, Instagram, LinkedIn) adapted for the channel.\n"
    "Keep each social post under 200 characters total.\n"
    "Keep blog under 150 words.\n"
    "Keep tagline under 10 words.\n"
    "IMPORTANT: Close ALL JSON strings with a double quote. "
    "Do not leave any string unclosed. "
    "The JSON must be complete and valid."
)


# ── Data Structures ──────────────────────────────────────────────────────


class AdaptationResult:
    """Stores the adapted assets for a specific channel."""

    def __init__(
        self,
        channel: str,
        tagline: str,
        blog: str,
        social: str,
    ) -> None:
        """Initialise an adaptation result.

        Args:
            channel: The target channel name.
            tagline: Adapted tagline.
            blog: Adapted blog introduction.
            social: Adapted social posts (single string).
        """
        self.channel: str = channel
        self.tagline: str = tagline
        self.blog: str = blog
        self.social: str = social

    def to_dict(self) -> dict[str, str]:
        """Convert to dict for serialisation.

        Returns:
            Dict with tagline, blog, social keys.
        """
        return {
            "tagline": self.tagline,
            "blog": self.blog,
            "social": self.social,
        }


# ── JSON Parsing ────────────────────────────────────────────────────────


def _parse_adaptation_json(raw: str) -> dict[str, str] | None:
    """Parse the JSON response from the adaptation LLM.

    Handles truncated JSON by attempting to recover partial content.

    Args:
        raw: Raw response string.

    Returns:
        Parsed dict with tagline/blog/social keys, or None on failure.
    """
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data: dict[str, Any] = json.loads(cleaned)
        for key in ("tagline", "blog", "social"):
            if key not in data or not isinstance(data[key], str):
                return None
        return data
    except (json.JSONDecodeError, TypeError):
        pass

    # Attempt recovery for truncated JSON
    try:
        # Find the last complete key-value pair before truncation
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        result: dict[str, str] = {}
        for key in ("tagline", "blog", "social"):
            # Find the key and extract its value
            search_key = f'"{key}": "'
            start = cleaned.find(search_key)
            if start == -1:
                return None
            start += len(search_key)
            # Find the closing quote (not escaped)
            end = start
            while end < len(cleaned):
                if cleaned[end] == '"' and (end == 0 or cleaned[end - 1] != "\\"):
                    break
                end += 1
            if end >= len(cleaned):
                # Truncated - take what we have
                result[key] = cleaned[start:end]
            else:
                result[key] = cleaned[start:end]

        if all(k in result for k in ("tagline", "blog", "social")):
            return result
    except Exception:
        pass

    return None


# ── Channel Adaptation ──────────────────────────────────────────────────


def adapt_for_channel(
    channel: str,
    tagline: str,
    blog: str,
    social: dict[str, str],
) -> AdaptationResult | None:
    """Rewrite campaign assets for a specific channel.

    Args:
        channel: Target channel (e.g. 'B2B LinkedIn', 'Gen-Z TikTok').
        tagline: Original campaign tagline.
        blog: Original blog introduction.
        social: Original social posts dict.

    Returns:
        AdaptationResult with adapted assets, or None on failure.
    """
    social_text = json.dumps(social, indent=2)

    user_prompt = (
        f"Channel: {channel}\n\n"
        f"Assets\n\n"
        f"Tagline:\n{tagline}\n\n"
        f"Blog:\n{blog}\n\n"
        f"Social:\n{social_text}\n\n"
        "Return adapted assets as JSON:"
    )

    try:
        raw = _call_openrouter(
            ADAPTATION_SYSTEM_PROMPT,
            user_prompt,
            max_retries=ADAPTATION_RETRIES,
            model=ADAPTATION_MODEL,
        )
        parsed = _parse_adaptation_json(raw)
        if parsed:
            logger.info(
                "Adaptation for '%s' successful: tagline=%d chars, blog=%d chars",
                channel, len(parsed["tagline"]), len(parsed["blog"]),
            )
            return AdaptationResult(
                channel=channel,
                tagline=parsed["tagline"],
                blog=parsed["blog"],
                social=parsed["social"],
            )

        logger.warning(
            "Adaptation JSON parse failed for '%s'. Raw: %s",
            channel, raw[:200],
        )
    except Exception as e:
        logger.error("Adaptation for '%s' failed: %s", channel, e)

    return None


def adapt_for_all_channels(
    tagline: str,
    blog: str,
    social: dict[str, str],
) -> dict[str, AdaptationResult]:
    """Adapt campaign assets for all available channels.

    Args:
        tagline: Original campaign tagline.
        blog: Original blog introduction.
        social: Original social posts dict.

    Returns:
        Dict mapping channel names to AdaptationResult instances.
    """
    results: dict[str, AdaptationResult] = {}

    for channel in CHANNEL_OPTIONS:
        logger.info("Adapting campaign for channel: %s", channel)
        result = adapt_for_channel(channel, tagline, blog, social)
        if result:
            results[channel] = result
        else:
            logger.warning("Adaptation failed for channel: %s", channel)

    return results