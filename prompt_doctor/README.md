# 🩺 Prompt Doctor

A prompt engineering learning tool built with Streamlit. Write prompts, see live AI output, and get graded by an AI examiner — all in a two-panel interface.

## What It Does

Prompt Doctor teaches prompt engineering across **5 progressive levels**. Each level introduces a new principle. You write a prompt, the app runs it against a sample input via OpenRouter, and an AI examiner grades your prompt against the level's principles.

## Levels & Principles

| Level | Title | Domain | Principles |
|-------|-------|--------|------------|
| 1 | Role & Clear Instruction | Education & Tutoring | `role`, `clear_instruction` |
| 2 | Structured Output (JSON) | Data & Analytics | + `structured_output` |
| 3 | Few-Shot Examples | Customer Support | + `few_shot` |
| 4 | Reasoning for Multi-Step Tasks | Software Engineering | + `reasoning` |
| 5 | Defensive Constraints | Customer Support | + `defensive_constraints` |

Each level builds on all previous principles — by level 5, your prompt must demonstrate all six.

## Project Structure

```
prompt_doctor/
├── app.py          # Streamlit UI — two-panel layout, session state, level navigation
├── examiner.py     # AI examiner — builds meta-prompts, calls OpenRouter, parses grading JSON
├── levels.py       # Level & domain definitions — tasks, sample inputs, principle lists
├── runner.py       # Prompt runner — sends user prompt + sample input to OpenRouter
└── .env            # API key configuration (not committed)
```

## Setup

**1. Install dependencies**

```bash
pip install streamlit requests python-dotenv
```

**2. Configure your API key**

Create a `.env` file (or edit the existing one):

```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_MODEL=openai/gpt-4o-mini
```

Get a free API key at [openrouter.ai](https://openrouter.ai).

**3. Run the app**

```bash
streamlit run app.py
```

## How It Works

1. **Select a level** from the left panel.
2. **Read the task** and optional hint.
3. **Write your prompt** in the text area (optionally override the sample input).
4. **Hit Submit** — your prompt runs against the sample input via OpenRouter.
5. **See the results** on the right panel: the raw AI output, examiner verdict (`pass` / `revise`), and per-principle feedback.
6. **Pass a level** to unlock the next one. The examiner never rewrites your prompt — it only asks guiding questions.

## Principle Definitions

- **role** — Assign a clear identity to the AI (e.g., "You are a software engineer").
- **clear_instruction** — Give a specific, directly actionable instruction.
- **structured_output** — Request output in a defined format (ideally JSON with named fields).
- **few_shot** — Include at least two input-output examples before the real task.
- **reasoning** — Instruct the AI to think step by step before answering.
- **defensive_constraints** — Add guardrails to handle harmful, off-topic, or adversarial input.
