"""
voiceover_gen.py — Voiceover Generation Module

Generates a voiceover script from the blog introduction using LLM,
then converts it to speech using TTS API (OpenAI TTS via OpenRouter).
Saves as voiceover.mp3 and provides download in Streamlit.
"""

import io
import logging
import time
from pathlib import Path
from typing import Any

import requests

from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, TEXT_MODEL, TEXT_RETRIES, RETRY_BACKOFF

logger = logging.getLogger(__name__)

# ── TTS Configuration ───────────────────────────────────────────────────

# Using OpenAI TTS via OpenRouter
TTS_MODEL: str = "openai/tts-1"
TTS_VOICE: str = "alloy"  # Options: alloy, echo, fable, onyx, nova, shimmer

# Output file path
VOICEOVER_OUTPUT: str = "voiceover.mp3"


# ── Voiceover Script Generation ─────────────────────────────────────────


def generate_voiceover_script(blog_intro: str) -> str:
    """Rewrite blog introduction into a professional narration script.

    Args:
        blog_intro: The blog introduction text to convert.

    Returns:
        Voiceover narration script text.
    """
    from text_gen import _call_openrouter

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


# ── Text-to-Speech via OpenRouter ───────────────────────────────────────


def _call_tts_api(text: str) -> bytes | None:
    """Call OpenRouter TTS API to generate speech audio.

    Uses the OpenAI TTS model (openai/tts-1) via OpenRouter.
    Tries the dedicated /audio/speech endpoint first, then falls back
    to chat completions if needed.

    Args:
        text: The narration text to convert to speech.

    Returns:
        Raw audio bytes (MP3), or None on failure.
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Try dedicated TTS endpoint first
    payload: dict[str, Any] = {
        "model": TTS_MODEL,
        "input": text,
        "voice": TTS_VOICE,
    }

    try:
        logger.info(
            "Calling TTS API model=%s voice=%s text_len=%d",
            TTS_MODEL, TTS_VOICE, len(text),
        )
        resp = requests.post(
            f"{OPENROUTER_BASE_URL}/audio/speech",
            headers=headers,
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()

        # Response is raw audio bytes
        audio_bytes = resp.content
        logger.info("TTS API success: %d bytes received", len(audio_bytes))
        return audio_bytes

    except requests.exceptions.RequestException as e:
        logger.warning("Dedicated TTS endpoint failed: %s. Trying chat completions...", e)

    # Fallback: Try via chat completions with response format
    try:
        chat_payload: dict[str, Any] = {
            "model": TTS_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": f"Generate speech audio for this text: {text}",
                }
            ],
        }
        logger.info("TTS fallback via chat completions")
        resp = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=chat_payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # Check if response contains audio data
        if isinstance(content, str):
            import re
            # Look for data URI
            data_match = re.search(r"data:audio/[^\s\"']+", content)
            if data_match:
                logger.info("Found audio data URI in response")
                return content.encode("utf-8")

            # Look for any URL
            url_match = re.search(r"https?://[^\s\"'<>)]+\.(?:mp3|wav|ogg|m4a)", content)
            if url_match:
                audio_resp = requests.get(url_match.group(0), timeout=60)
                if audio_resp.status_code == 200:
                    logger.info("Downloaded audio from URL: %d bytes", len(audio_resp.content))
                    return audio_resp.content

        logger.warning("Chat completions fallback did not return audio")
    except Exception as e2:
        logger.error("TTS fallback also failed: %s", e2)

    return None


def generate_voiceover(blog_intro: str) -> tuple[str | None, bytes | None]:
    """Generate voiceover script and speech audio.

    Args:
        blog_intro: Blog introduction text to convert.

    Returns:
        Tuple of (script_text, audio_bytes). Either may be None on failure.
    """
    # Step 1: Generate narration script
    try:
        script = generate_voiceover_script(blog_intro)
        logger.info("Voiceover script generated (%d chars)", len(script))
    except Exception as e:
        logger.error("Voiceover script generation failed: %s", e)
        return None, None

    if not script.strip():
        logger.warning("Voiceover script is empty")
        return None, None

    # Step 2: Generate speech from script
    audio_bytes = _call_tts_api(script)

    # Step 3: Save to file if successful
    if audio_bytes:
        try:
            output_path = Path(VOICEOVER_OUTPUT)
            output_path.write_bytes(audio_bytes)
            logger.info("Voiceover saved to %s", output_path)
        except Exception as e:
            logger.error("Failed to save voiceover file: %s", e)

    return script, audio_bytes