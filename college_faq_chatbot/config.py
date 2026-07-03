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

# ChromaDB collection name
CHROMA_COLLECTION_NAME = "college_faq"

# Debug mode default
DEBUG_MODE = False

def get_env_or_raise(key: str) -> str:
    """Get an environment variable or raise an error."""
    value = os.getenv(key)
    if not value:
        raise ValueError(
        f"Missing required environment variable: {key}. "
        f"Please add it to your .env file."
    )
    return value