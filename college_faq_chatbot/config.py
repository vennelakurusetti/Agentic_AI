"""
config.py - Central configuration for the College FAQ Chatbot.
"""

import os
from pathlib import Path

# Project paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = BASE_DIR / "chroma_db"
TEST_CASES_DIR = BASE_DIR / "test_cases"
EVALUATION_DIR = BASE_DIR / "evaluation"
DOCX_PATH = DATA_DIR / "knowledge_base.docx"
CHAT_HISTORY_DIR = BASE_DIR / "chat_history"

# Auto-create directories on import
for _d in [DATA_DIR, TEST_CASES_DIR, EVALUATION_DIR, CHAT_HISTORY_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# Chunking settings
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Retrieval settings
TOP_K = 8

# Embedding model
EMBEDDING_MODEL = "text-embedding-3-small"

# LLM settings
LLM_MODEL = "openai/gpt-4o-mini"
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 1024

# OpenRouter base URL
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# RAGAS evaluation
RAGAS_METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]

# ChromaDB collection name (knowledge base)
CHROMA_COLLECTION_NAME = "college_faq"

# ── Memory ChromaDB (separate database) ──────────────────────
MEMORY_DIR = BASE_DIR / "memory_db"
MEMORY_COLLECTION_NAME = "user_memory"
MEMORY_TOP_K = 5          # Number of memories to retrieve per query
MEMORY_CLEANUP_DAYS = 30  # Auto-delete memories older than this
MEMORY_DEFAULT_USER_ID = "default_user"

# ── Observability ─────────────────────────────────────────────
LOG_FILE = BASE_DIR / "observability" / "llm_calls.jsonl"

# ── Thresholds ────────────────────────────────────────────────
MAX_INPUT_LENGTH = 2000   # Characters
MAX_LATENCY = 10.0        # Seconds
MAX_COST_PER_QUERY = 0.10 # USD
MAX_ERROR_RATE = 5.0      # Percent

# Debug mode default
DEBUG_MODE = False

# App version
APP_VERSION = "2.0.0"


def get_env_or_raise(key: str) -> str:
    """Get an environment variable or raise an error."""
    value = os.getenv(key)
    if not value:
        raise ValueError(
            f"Missing required environment variable: {key}. "
            f"Please add it to your .env file."
        )
    return value
