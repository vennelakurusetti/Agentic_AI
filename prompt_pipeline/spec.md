# Prompt Pipeline Studio — Specification

## 1. Overview

**Prompt Pipeline Studio** is a Streamlit-based web application that enables users to run multi-stage LLM (Large Language Model) prompt pipelines. Each pipeline consists of 3-4 stages where the output of one stage becomes the input of the next, creating a chain of AI reasoning and generation.

## 2. Architecture

### 2.1 System Flow

```
User Input (JSON)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend (app.py)               │
│  • Sidebar: Pipeline selection, model config, theme toggle  │
│  • Main: Pipeline flow viz, input editor, results display   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                  Pipeline Engine (pipelines.py)              │
│  • Orchestrates stage-by-stage execution                    │
│  • Passes JSON output from stage N to stage N+1             │
│  • Stops on first error                                     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│              Stage Executor (retry.py → llm.py)              │
│  • Builds prompt from template + previous stage output      │
│  • Calls OpenRouter API via HTTP POST                       │
│  • Retries on JSON parse failure (up to 3 attempts)         │
│  • Returns parsed JSON or raises error                      │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    OpenRouter API                            │
│  • Routes to selected model (Claude, GPT, Gemini, etc.)    │
│  • Returns LLM response text                                │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Module Responsibilities

| Module | File | Responsibility |
|--------|------|----------------|
| **app.py** | Main entry point | Streamlit UI, session state, event handling |
| **config.py** | Configuration | Environment variables, model list, defaults |
| **llm.py** | LLM client | OpenRouter API calls, token estimation, cost calculation |
| **parser.py** | JSON parser | Parse, validate, fix, and highlight JSON |
| **retry.py** | Retry logic | Automatic retry with error feedback to LLM |
| **pipelines.py** | Pipeline engine | Stage orchestration, execution flow |
| **prompts.py** | Prompt templates | All 6 pipeline definitions with stage prompts |
| **examples.py** | Sample data | Pre-built input examples for each pipeline |
| **styles.py** | CSS styles | Light/dark theme CSS with glassmorphism |
| **utils/exporter.py** | Export | Markdown and JSON report generation |

## 3. Pipeline Definitions

### 3.1 Support Ticket Triage (4 stages)
- **Understand**: Extract structured info (priority, category, sentiment)
- **Reason**: Root cause analysis, business impact assessment
- **Produce**: Generate professional customer response
- **Critique**: QA review of response quality

### 3.2 Essay Grader (4 stages)
- **Understand**: Extract essay metadata (word count, thesis, structure)
- **Reason**: Multi-dimension scoring (clarity, evidence, grammar)
- **Produce**: Generate revised essay with improvements
- **Critique**: Supervisor review of grading fairness

### 3.3 Bug Report Analyzer (4 stages)
- **Understand**: Parse bug report (severity, component, environment)
- **Reason**: Root cause analysis, impact estimation
- **Produce**: Generate fix plan with implementation steps
- **Critique**: Code review of proposed fix

### 3.4 Meeting Notes → Action Items (3 stages)
- **Understand**: Extract key info (attendees, topics, decisions)
- **Reason**: Identify action items, owners, deadlines
- **Produce**: Generate formatted meeting summary

### 3.5 Recipe Adapter (3 stages)
- **Understand**: Parse recipe (ingredients, times, dietary flags)
- **Reason**: Calculate scaling, substitutions, adjustments
- **Produce**: Generate adapted recipe with instructions

### 3.6 Trip Planner (3 stages)
- **Understand**: Extract travel preferences (destination, budget, interests)
- **Reason**: Optimize itinerary, budget allocation
- **Produce**: Generate day-by-day itinerary

## 4. Data Flow

### 4.1 Stage Execution

Each stage follows this flow:

1. **Build Prompt**: `stage["build_prompt"](format_json(previous_output))`
2. **Call LLM**: `call_llm(prompt, model, temperature, max_tokens, api_key)`
3. **Parse Response**: `parse_json_response(raw_text)`
4. **Retry on Failure**: If parse fails, append error feedback to prompt and retry (up to 3 times)
5. **Pass to Next Stage**: `current_input = parsed_output`

### 4.2 JSON Contract

Every stage must:
- **Receive**: Valid JSON from the previous stage
- **Produce**: Valid JSON for the next stage
- **System prompt**: Instructs LLM to return ONLY valid JSON, no markdown, no explanations

## 5. UI Components

### 5.1 Sidebar
- App branding (logo, title)
- Pipeline selector dropdown
- Model selector (10 models via OpenRouter)
- Temperature slider (0.0 - 1.0)
- Max tokens slider (256 - 8192)
- Theme toggle (Light/Dark)
- Quick actions (Load Example, Reset)
- Pipeline info card

### 5.2 Main Content
- **Home**: Hero section, pipeline cards grid (3 columns), recent executions
- **Pipeline Runner**: Pipeline header, flow visualization, JSON input editor, run controls
- **Results**: Status banner, stage expanders (metrics, prompt, input, output, raw response, retry logs), final output, export buttons, execution timeline, summary stats

### 5.3 Theme System
- CSS custom properties for all colors
- Light theme: White/gray backgrounds, dark text
- Dark theme: Dark backgrounds, light text
- Glassmorphism effects with backdrop blur
- `!important` flags to override Streamlit defaults

## 6. Error Handling

### 6.1 API Errors
- Network timeouts: 60s timeout on requests
- 401 Unauthorized: Caught and displayed as error banner
- Rate limiting: Propagated to user with error message

### 6.2 JSON Parse Errors
- Automatic retry with error feedback to LLM
- Up to 3 retry attempts
- Slightly increased temperature on each retry (+0.05)
- Retry logs displayed in UI

### 6.3 Pipeline Errors
- Stage failure stops pipeline execution
- Error message displayed in status banner
- Partial results shown for completed stages

## 7. Security

### 7.1 API Key Management
- Key loaded from `.env` file via `python-dotenv`
- No API key input field in the UI
- Key stored in Streamlit session state (server-side only)
- `.env` file excluded from git via `.gitignore`

### 7.2 Data Privacy
- All data sent to OpenRouter API (no local processing)
- No data persistence beyond session
- Execution history stored in session state only

## 8. Dependencies

```
streamlit>=1.28.0    # Web framework
requests>=2.31.0     # HTTP client for OpenRouter API
python-dotenv>=1.0.0 # Environment variable loading
```

## 9. Configuration

### 9.1 Environment Variables (.env)
```
OPENROUTER_API_KEY=sk-or-v1-...
```

### 9.2 Default Settings (config.py)
- Default model: `openai/gpt-4o-mini`
- Default temperature: 0.3
- Default max tokens: 2048
- Max retries: 3
- Retry delay: 1.0s

## 10. Cost Estimation

Token costs are estimated using ~4 characters per token. Per-model rates (per 1M tokens):

| Model | Input Cost | Output Cost |
|-------|-----------|-------------|
| Claude 3.5 Sonnet | $3.00 | $15.00 |
| Claude 3 Haiku | $0.25 | $1.25 |
| GPT-4o | $5.00 | $15.00 |
| GPT-4o Mini | $0.15 | $0.60 |
| Gemini Pro | $0.50 | $1.50 |
| Gemini Flash | $0.075 | $0.30 |
| DeepSeek V3 | $0.14 | $0.28 |
| Llama 3.3 70B | $0.59 | $0.79 |
| Mistral Large | $2.00 | $6.00 |
| Qwen 2.5 72B | $0.35 | $0.40 |

## 11. Known Limitations

1. **Token estimation**: Uses rough 4-char-per-token approximation, not actual tokenizer
2. **No streaming**: Responses are fetched in full, not streamed token-by-token
3. **Session-only history**: Execution history is lost on page refresh
4. **Single model per pipeline**: All stages use the same model
5. **No concurrent execution**: Pipelines run sequentially
6. **OpenRouter dependency**: Requires internet access and valid API key