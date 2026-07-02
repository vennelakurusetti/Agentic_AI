"""
image_gen.py — AI Image Generation Module

Constructs a hero image prompt based on the product and brand tone,
then generates the image via OpenRouter's image API
(black-forest-labs/flux.2-pro).
"""

import logging
import time
from typing import Any

import requests

from config import (
    IMAGE_MODEL,
    IMAGE_RETRIES,
    OPENROUTER_BASE_URL,
    OPENROUTER_IMAGE_KEY,
    RETRY_BACKOFF,
    STYLE_MAP,
)

logger = logging.getLogger(__name__)


# ── Prompt Construction ───────────────────────────────────────────────────


def build_image_prompt(product: str, tone: str) -> str:
    """Build a detailed hero image prompt using the style map.

    Formula: Subject + Style + Composition + Lighting + Camera Angle +
             Color Palette + Negative Constraints.

    Args:
        product: Product name.
        tone: Brand tone (e.g. 'premium', 'playful').

    Returns:
        Full image prompt string.
    """
    style = STYLE_MAP.get(tone.lower(), STYLE_MAP["premium"])

    prompt = (
        f"{style} of {product}.\n\n"
        "Centered composition.\n"
        "Soft studio lighting.\n"
        "Luxury atmosphere.\n"
        "16:9 aspect ratio.\n"
        "Shallow depth of field.\n"
        "Minimal background.\n"
        "No text.\n"
        "No logos.\n"
        "No watermark.\n"
        "Ultra high resolution."
    )
    return prompt


# ── Image Generation ──────────────────────────────────────────────────────


def _call_image_api(prompt: str) -> str:
    """Call OpenRouter image generation endpoint via chat completions.

    Uses openai/gpt-5-image-mini which returns image URLs in the response.

    Args:
        prompt: The image prompt text.

    Returns:
        URL string of the generated image.

    Raises:
        RuntimeError: On API failure.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_IMAGE_KEY}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "model": IMAGE_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    try:
        resp = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract content from response
        message = data["choices"][0]["message"]
        content = message.get("content", "")

        # Log the raw response (first 500 chars)
        logger.info("Image API response: %s...", str(content)[:500])

        if isinstance(content, str):
            import re
            # Try markdown image syntax first: ![alt](url)
            md_match = re.search(r"!\[.*?\]\((https?://[^\s)]+)\)", content)
            if md_match:
                url = md_match.group(1).strip()
                logger.info("Extracted image URL via markdown: %s", url)
                return url

            # Try direct image URL patterns
            url_match = re.search(
                r"https?://[^\s\"'<>)]+\.(?:png|jpg|jpeg|gif|webp)(?:\?[^\s\"'<>)]*)?",
                content,
            )
            if url_match:
                url = url_match.group(0).strip()
                logger.info("Extracted image URL via extension: %s", url)
                return url

            # Try data URI
            if "data:image" in content:
                logger.info("Response contains data URI image")
                return content.strip()

            # Fallback: any URL
            url_match = re.search(r"https?://[^\s\"'<>)]+", content)
            if url_match:
                url = url_match.group(0).strip()
                logger.info("Extracted image URL via fallback: %s", url)
                return url

        raise RuntimeError(
            f"Could not extract image URL from response. "
            f"Content preview: {str(content)[:300]}"
        )

    except requests.RequestException as e:
        raise RuntimeError(f"Image API request failed: {e}") from e


def generate_image(prompt: str) -> str:
    """Generate a hero image with retry logic.

    Args:
        prompt: The image generation prompt.

    Returns:
        URL string of the generated image, or empty string on failure.
    """
    last_exception: Exception | None = None
    for attempt in range(1, IMAGE_RETRIES + 1):
        try:
            logger.info("Image generation attempt %d/%d", attempt, IMAGE_RETRIES)
            url = _call_image_api(prompt)
            if url:
                logger.info("Image generated successfully: %s", url)
                return url
        except Exception as exc:
            last_exception = exc
            logger.warning("Image attempt %d failed: %s", attempt, exc)
            if attempt < IMAGE_RETRIES:
                backoff = RETRY_BACKOFF[min(attempt - 1, len(RETRY_BACKOFF) - 1)]
                time.sleep(backoff)

    logger.error("Image generation failed after %d retries.", IMAGE_RETRIES)
    return ""
