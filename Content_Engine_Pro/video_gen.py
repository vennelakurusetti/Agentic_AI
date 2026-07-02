"""
video_gen.py — Video Concept Generation Module

Generates a detailed video production concept / storyboard using the
LLM model. Output is a structured video brief that can be handed off
to a production team or video AI tool.
"""

import logging

from config import TEXT_MODEL
from text_gen import _call_openrouter

logger = logging.getLogger(__name__)


# ── Video Concept Generation ──────────────────────────────────────────────


def _build_video_system_prompt() -> str:
    """Build the system prompt for video concept generation.

    Returns:
        System prompt string for video concept LLM call.
    """
    return (
        "You are an expert Creative Director for video production.\n\n"
        "Generate a detailed promotional video concept document.\n"
        "Include:\n"
        "1. **Video Title** — Catchy working title\n"
        "2. **Duration** — 5-8 seconds\n"
        "3. **Visual Storyboard** — 3-5 key scenes with descriptions\n"
        "4. **Camera Movement** — Push-in, parallax, drift, etc.\n"
        "5. **Lighting** — Lighting style matching the brand tone\n"
        "6. **Audio Direction** — Background music style and pacing\n"
        "7. **Call to Action** — Final frame text or voiceover\n\n"
        "Format as a clean, professional document.\n"
        "No markdown code fences.\n"
        "No JSON.\n"
    )


def generate_video_concept(
    product: str, tone: str, image_url: str, tagline: str
) -> str:
    """Generate a video production concept document.

    Args:
        product: Product name.
        tone: Brand tone.
        image_url: URL of the hero image to base the video on.
        tagline: Campaign tagline to include.

    Returns:
        Video concept document text.
    """
    system_prompt = _build_video_system_prompt()
    user_prompt = (
        f"Product: {product}\n"
        f"Brand Tone: {tone}\n"
        f"Campaign Tagline: \"{tagline}\"\n"
        f"Hero Image Reference: {image_url}\n\n"
        "Generate a promotional video concept based on this campaign:"
    )

    try:
        concept = _call_openrouter(
            system_prompt, user_prompt,
            max_retries=2, model=TEXT_MODEL,
        )
        logger.info("Video concept generated (%d chars)", len(concept))
        return concept
    except Exception as e:
        logger.error("Video concept generation failed: %s", e)
        return (
            "Video concept generation is currently unavailable. "
            "No video generation models are available on OpenRouter at this time. "
            "Please check back later or use a dedicated video generation service."
        )


# ── Backward-Compatible Wrapper ───────────────────────────────────────────


def generate_video(image_url: str, tone: str,
                   product: str = "campaign product",
                   tagline: str = "campaign tagline") -> str:
    """Generate video content (concept document since no video AI exists).

    Args:
        image_url: URL of the source image (used as reference).
        tone: Brand tone.
        product: Product name.
        tagline: Campaign tagline to weave into the concept.

    Returns:
        Video concept document text.
    """
    logger.info("Generating video concept (no video AI model available)")
    return generate_video_concept(
        product=product, tone=tone,
        image_url=image_url, tagline=tagline,
    )