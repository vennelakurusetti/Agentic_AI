"""
AI Recruitment Engine — Real OpenRouter API (no mock fallback)
"""

import os
import json
import sys
import requests
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

load_dotenv(os.path.join(SCRIPT_DIR, ".env"))


def call_llm(prompt: str) -> str:
    """
    Send a prompt to the OpenRouter API and return the model's response text.
    Raises an exception on failure — no mock fallback.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("MODEL", "openai/gpt-4o-mini")

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set in .env. "
            "Please add your OpenRouter API key to ai_recruitment_engine/.env"
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
    }

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2000,
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"].strip()

    # Strip markdown code fences that LLMs often wrap JSON in
    if content.startswith("```"):
        lines = content.splitlines()
        # Remove opening ```json or ``` etc.
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove trailing ``` if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    return content


def run_agent():
    """Run the recruitment agent end-to-end (placeholder)."""
    from graph.graph import build_recruitment_graph
    builder = build_recruitment_graph(call_llm)