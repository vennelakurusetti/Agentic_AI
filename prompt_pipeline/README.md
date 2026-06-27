# 🔗 Prompt Pipeline Builder

A single-file, browser-based tool for designing and testing **multi-stage LLM prompt chains**. No server required — just open `index.html`.

## What it does

Pick a task, write prompts for each pipeline stage, then run the chain live to see how data flows from one stage to the next.

## Features

- **6 built-in tasks** to choose from:
  | Task | Description |
  |---|---|
  | Support Ticket Triage | Classify and route incoming support tickets |
  | Essay Grader | Grade student essays with rubric-based scoring |
  | Bug Report Triage | Analyze bug reports and suggest fixes |
  | Meeting Notes → Actions | Convert transcripts into action items |
  | Recipe Adapter | Adapt recipes for dietary needs & servings |
  | Trip Day-Planner | Build daily itineraries from preferences |

- **3–4 stage pipelines** per task using different prompting techniques:
  - `Role + Structured Output` — Stage 1 (Understand / Extract)
  - `Chain-of-Thought` — Stage 2 (Reason / Analyze)
  - `Goal-Oriented` — Stage 3 (Produce / Generate)
  - `Critic` — Stage 4 (Critique / Review, where applicable)

- **Editable prompts** — customize each stage's system prompt inline
- **Live run panel** — executes all stages sequentially, passing output of one stage as input to the next
- **Bad input mode** — toggle "Test with bad input" to simulate error propagation through the chain
- **Reflection box** — note which stage is your weakest link; saved to `localStorage`

## Usage

1. Open `index.html` in any modern browser
2. Select a task from the grid
3. Review or edit the pre-filled prompts in each pipeline stage
4. Click **🚀 Run Pipeline** to execute the chain
5. Inspect per-stage input/output in the Live Run panel

## Connecting a Real LLM

The `callLLM()` function in `index.html` uses a mock/simulated response by default. To use a real model, replace its body with an API call:

```js
async function callLLM(prompt, stageIndex) {
  const res = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer YOUR_KEY',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: 'gpt-4o-mini',
      messages: [{ role: 'user', content: prompt }]
    })
  });
  const data = await res.json();
  return data.choices[0].message.content;
}
```

## Project Structure

```
prompt_pipeline/
└── index.html   # Entire app — HTML, CSS, and JS in one file
```

## Tech Stack

- Vanilla HTML/CSS/JavaScript (no build step, no dependencies)
- Google Fonts: Inter, Fira Code
