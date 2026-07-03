"""
utils.py - Logging and utility functions for the College FAQ Chatbot.
"""

import logging
import time
from typing import Dict, Any, Optional


def setup_logger(name: str = "college_faq_chatbot") -> logging.Logger:
    """Set up and return a logger with consistent formatting."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = setup_logger()


class Timer:
    """Context manager for measuring execution time."""

    def __init__(self, label: str = ""):
        self.label = label
        self.elapsed = 0.0

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed = time.perf_counter() - self.start
        if self.label:
            logger.info(f"{self.label}: {self.elapsed:.3f}s")


def format_metadata(metadata: Dict[str, Any]) -> str:
    """Format chunk metadata into a readable citation string."""
    parts = []
    if "section" in metadata and metadata["section"]:
        parts.append(str(metadata["section"]))
    if "page" in metadata and metadata["page"]:
        parts.append(f"Page {metadata['page']}")
    if "filename" in metadata and metadata["filename"]:
        parts.append(str(metadata["filename"]))
    return " | ".join(parts) if parts else "Unknown source"


def count_tokens(text: str) -> int:
    """Approximate token count for OpenAI models (~4 chars per token)."""
    return len(text) // 4