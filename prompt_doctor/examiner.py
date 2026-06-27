"""
Examiner module for Prompt Doctor.

Evaluates a student's prompt based on the principles required for the current level.
Calls the OpenRouter API with a meta-prompt that instructs the LLM to act as a
fair prompt engineering examiner, returning structured JSON feedback.
"""

import os
import re
import json
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"

# ---------------------------------------------------------------------------
# Principle descriptions used in the examiner system prompt
# ---------------------------------------------------------------------------
PRINCIPLE_DEFINITIONS = {
    "role": (
        "A clear role assignment that defines who or what the AI is pretending to be "
        "(e.g., 'You are a software engineer', 'Act as a tutor'). A prompt that merely "
        "states an instruction without a role identity should fail this check."
    ),
    "clear_instruction": (
        "The instruction should be specific and directly actionable. "
        "Look for what the AI is asked to do. Even simple instructions like "
        "'tell me about' or 'explain' can pass if the topic is clear. "
        "What matters is that the student gives a clear direction."
    ),
    "structured_output": (
        "The prompt should request output in a structured format, ideally JSON "
        "with specified field names. Look for phrases like 'Respond in JSON format' "
        "or 'Return a JSON object with keys'. Even asking for a bulleted list "
        "with specific fields shows awareness of structured output."
    ),
    "few_shot": (
        "The prompt should include at least two examples (input-output pairs) "
        "that demonstrate the desired behavior. The examples should be relevant to the "
        "task. If the prompt includes clear examples before asking for the real input, "
        "it demonstrates few-shot prompting."
    ),
    "reasoning": (
        "The prompt should instruct the AI to reason or think through the problem. "
        "Look for phrases like 'think step by step', 'reason step by step', "
        "'show your reasoning', 'explain your thought process', "
        "or 'work through this carefully before answering'."
    ),
    "defensive_constraints": (
        "The prompt should include guardrails against problematic input. "
        "This includes instructions to reject harmful requests, stay on topic, "
        "ignore prompt injection attempts, or respond with a safe default "
        "when the input is suspicious or off-topic."
    ),
}

DEFAULT_SYSTEM_PROMPT = """You are a fair but thorough prompt engineering examiner. Your job is to evaluate student-written prompts and provide constructive feedback.

## What you evaluate
You judge ONLY the principles listed for the current level. Do not evaluate principles that are not listed.

## How to evaluate
For each principle, determine whether the student's prompt successfully demonstrates it. Be fair — if the student makes a reasonable attempt at the principle, give them credit. This is a teaching tool, not a certification exam.

## Rules for your response
1. Quote the exact weak phrase or identify precisely what is missing for each failed principle.
2. Ask exactly ONE guiding question for every failed principle to help the student improve.
3. NEVER rewrite or improve the student's prompt. You only critique and ask questions.
4. Return ONLY valid JSON. No markdown, no code fences, no explanation outside the JSON.
5. The "ran_ok" field should always be true (it indicates the examination ran, not the student's prompt).

## JSON format
{
  "level": <number>,
  "principles": [
    {
      "name": "principle_name",
      "pass": true/false,
      "weakness": "quote the weak phrase or describe what's missing",
      "question": "one guiding question for improvement"
    }
  ],
  "ran_ok": true,
  "verdict": "pass" or "revise"
}

The verdict is "pass" ONLY if every principle has pass: true. Otherwise it is "revise".
"""


def _build_examiner_prompt(level: int, principles: list[str]) -> str:
    """
    Build the full meta-prompt for the examiner, including the definitions
    of the principles relevant to the current level.
    """
    principle_section = "\n".join(
        f"- **{p}**: {PRINCIPLE_DEFINITIONS.get(p, 'No definition available.')}"
        for p in principles
    )

    return f"""You are a fair but thorough prompt engineering examiner.

## Level being evaluated
Level {level}

## Principles to evaluate (ONLY these)
{principle_section}

## Student's prompt to evaluate
{{student_prompt}}

## Instructions
1. Evaluate ONLY the principles listed above for Level {level}.
2. For each principle, determine pass/fail. Be fair — give credit for reasonable attempts.
3. For each FAILED principle, quote the exact weak phrase or describe what's missing, and ask exactly ONE guiding question.
4. NEVER rewrite or improve the student's prompt.
5. Return ONLY valid JSON. No markdown, no code fences, no extra text.

## JSON format
{{
  "level": {level},
  "principles": [
    {{
      "name": "principle_name",
      "pass": true/false,
      "weakness": "quote or describe what's missing (empty string if pass)",
      "question": "one guiding question (empty string if pass)"
    }}
  ],
  "ran_ok": true,
  "verdict": "pass" or "revise"
}}

The verdict is "pass" ONLY if every principle has pass: true. Otherwise it is "revise".
"""


def _call_openrouter(system_prompt: str, user_prompt: str) -> str:
    """Call the OpenRouter API and return the raw response text."""
    if not OPENROUTER_API_KEY:
        return json.dumps({
            "level": 0,
            "principles": [],
            "ran_ok": False,
            "verdict": "revise",
        })

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    try:
        resp = requests.post(OPENROUTER_BASE, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        return json.dumps({
            "level": 0,
            "principles": [],
            "ran_ok": False,
            "verdict": "revise",
        })
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        return json.dumps({
            "level": 0,
            "principles": [],
            "ran_ok": False,
            "verdict": "revise",
        })


def _parse_json_response(raw: str) -> dict | None:
    """
    Attempt to parse JSON from the raw response.
    Tries: direct parse, markdown code block extraction, brace matching.
    """
    # 1. Direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2. Extract from markdown code block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. Find first { and last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _build_fallback_result(level: int, principles: list[str]) -> dict:
    """Build a fallback result when the examiner fails to return valid JSON."""
    return {
        "level": level,
        "principles": [
            {
                "name": p,
                "pass": False,
                "weakness": "Examiner could not grade this principle due to an error.",
                "question": "Try submitting again. If the problem persists, check your API key.",
            }
            for p in principles
        ],
        "ran_ok": False,
        "verdict": "revise",
    }


def evaluate(student_prompt: str, level: int, principles: list[str]) -> dict:
    """
    Evaluate a student's prompt against the given principles.

    Args:
        student_prompt: The prompt written by the student.
        level: The current level number.
        principles: List of principle names to evaluate.

    Returns:
        A dict matching the JSON schema with grading results.
    """
    examiner_prompt = _build_examiner_prompt(level, principles)
    full_prompt = examiner_prompt.replace("{student_prompt}", student_prompt)

    raw_response = _call_openrouter(DEFAULT_SYSTEM_PROMPT, full_prompt)

    parsed = _parse_json_response(raw_response)
    if parsed is None:
        return _build_fallback_result(level, principles)

    # Validate structure
    if not isinstance(parsed, dict) or "principles" not in parsed:
        return _build_fallback_result(level, principles)

    # Ensure all expected principles are present
    expected_names = set(principles)
    actual_names = {p.get("name") for p in parsed.get("principles", [])}
    missing = expected_names - actual_names
    if missing:
        for name in missing:
            parsed["principles"].append({
                "name": name,
                "pass": False,
                "weakness": "Not evaluated by examiner.",
                "question": "Try rewriting your prompt to include this principle.",
            })

    # Ensure verdict is consistent
    all_pass = all(p.get("pass", False) for p in parsed.get("principles", []))
    parsed["verdict"] = "pass" if all_pass else "revise"
    parsed["level"] = level
    parsed["ran_ok"] = True

    return parsed