"""
Runner module for Prompt Doctor.

Executes the user's prompt on a given sample input by calling the OpenRouter API.
Returns the model's raw text output.
"""

import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"


def run_prompt(user_prompt: str, sample_input: str) -> str:
    """
    Execute the user's prompt on the given sample input using OpenRouter.

    The user's prompt is treated as the system message, and the sample input
    is sent as the user message. This simulates how the prompt would behave
    in a real interaction.

    Args:
        user_prompt: The prompt written by the student.
        sample_input: The sample input to test the prompt against.

    Returns:
        The model's response text, or an error message string if something fails.
    """
    if not user_prompt.strip():
        return "[Error: Prompt is empty.]"

    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
        return (
            "[Error: OpenRouter API key is not configured. "
            "Add your key to the .env file.]"
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": user_prompt,
            },
            {
                "role": "user",
                "content": sample_input,
            },
        ],
        "temperature": 0.3,
    }

    try:
        response = requests.post(
            OPENROUTER_BASE,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices", [])
        if not choices:
            return "[Error: No choices returned from the API.]"

        message = choices[0].get("message", {})
        content = message.get("content", "")

        if not content:
            return "[Error: Empty response from the model.]"

        return content.strip()

    except requests.exceptions.Timeout:
        return "[Error: Request timed out after 60 seconds. Try a simpler prompt.]"
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "unknown"
        return f"[Error: API returned HTTP {status}. Check your API key and model name.]"
    except requests.exceptions.ConnectionError:
        return "[Error: Could not connect to OpenRouter. Check your internet connection.]"
    except requests.exceptions.RequestException as e:
        return f"[Error: Request failed: {str(e)}]"
    except json.JSONDecodeError:
        return "[Error: Received non-JSON response from API.]"
    except Exception as e:
        return f"[Error: Unexpected error: {str(e)}]"