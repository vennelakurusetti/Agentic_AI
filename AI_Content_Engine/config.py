"""
Configuration module for AI Content Engine.

Centralizes all constants, model names, retry settings,
style maps, few-shot examples, and environment variables.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────────────────────
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_IMAGE_KEY: str = os.getenv("OPENROUTER_IMAGE_KEY", "")

# ── Models ────────────────────────────────────────────────────────────────
TEXT_MODEL: str = os.getenv("OPENROUTER_TEXT_MODEL", "openai/gpt-4o-mini")
IMAGE_MODEL: str = os.getenv("OPENROUTER_IMAGE_MODEL", "google/gemini-3.1-flash-image")
VIDEO_MODEL: str = os.getenv("OPENROUTER_VIDEO_MODEL", "openai/gpt-4o-mini")

# ── OpenRouter Base URL ───────────────────────────────────────────────────
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

# ── Retry Settings ────────────────────────────────────────────────────────
TEXT_RETRIES: int = 3
IMAGE_RETRIES: int = 2
VIDEO_RETRIES: int = 2
RETRY_BACKOFF: list[int] = [1, 2, 4]  # seconds

# ── Brand Tones ───────────────────────────────────────────────────────────
SUPPORTED_TONES: list[str] = [
    "premium",
    "playful",
    "eco",
    "professional",
    "luxury",
    "minimal",
    "friendly",
]

# ── Style Map for Image Prompts ───────────────────────────────────────────
STYLE_MAP: dict[str, str] = {
    "premium": "photorealistic studio product photography with luxury lighting",
    "playful": "bright colorful flat illustration",
    "eco": "watercolor illustration using earthy natural colors",
    "professional": "minimal modern commercial photography",
    "luxury": "cinematic premium product advertisement",
    "minimal": "clean Scandinavian aesthetic",
    "friendly": "warm lifestyle photography",
}

# ── Few-Shot Examples for Tagline Generation ──────────────────────────────
FEW_SHOT_EXAMPLES: dict[str, list[tuple[str, str]]] = {
    "premium": [
        ("Luxury Watch", "Time Refined."),
        ("Designer Perfume", "Essence of Elegance."),
    ],
    "playful": [
        ("Kids Shoes", "Jump Bigger."),
        ("Colorful Toy Set", "Play Without Limits."),
    ],
    "eco": [
        ("Reusable Bottle", "Refill Today. Restore Tomorrow."),
        ("Bamboo Toothbrush", "Brush Kindly."),
    ],
    "professional": [
        ("Business Software", "Work Smarter. Lead Faster."),
        ("Corporate Training", "Build Tomorrow's Leaders."),
    ],
    "luxury": [
        ("Diamond Necklace", "Forever Adorned."),
        ("Sports Car", "Velocity Meets Art."),
    ],
    "minimal": [
        ("Desk Lamp", "Less Light. More Focus."),
        ("Notebook", "Blank Pages. Big Ideas."),
    ],
    "friendly": [
        ("Pet Food", "Love in Every Bite."),
        ("Baby Lotion", "Gentle Care. Happy Skin."),
    ],
}