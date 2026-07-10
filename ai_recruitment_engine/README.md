# AI Recruitment Engine

An intelligent AI-powered recruitment agent built with **LangGraph** and **OpenRouter API (GPT-4o Mini)**. Automates the entire hiring pipeline — from parsing job descriptions and resumes to scoring candidates, running guardrail checks, and scheduling interviews.

## Features

- **Job Description Analysis** — Extracts required/preferred skills, education, experience, and responsibilities
- **Resume Parsing** — Dynamically parses any resume text into structured candidate data
- **Rubric Generation** — Creates a weighted scoring rubric based on the JD
- **Candidate Scoring** — Scores each candidate against the rubric with evidence
- **Decision Engine** — SELECT / HOLD / REJECT with justification
- **Guardrail Checks** — Detects prompt injection, bias, and safety violations
- **Fairness Audit** — Audits all decisions for demographic bias
- **Interview Scheduling** — Slot selection + human approval workflow
- **Execution Trajectory** — Full LangGraph step-by-step trace
- **Audit Log** — JSON export of all decisions and tool calls

## Project Structure

```
ai_recruitment_engine/
├── app.py                    # OpenRouter API client (no mock fallback)
├── streamlit_app.py          # Premium Streamlit dashboard
├── requirements.txt          # Python dependencies
├── .env                      # API key configuration
├── README.md
│
├── data/
│   ├── jd.txt                # Sample job description
│   ├── priya.txt             # Sample resume
│   ├── rahul.txt             # Sample resume
│   └── meera.txt             # Sample resume
│
├── prompts/
│   ├── jd_prompt.py          # JD analysis prompt
│   ├── planner_prompt.py     # Planning prompt
│   ├── parser_prompt.py      # Resume parsing prompt
│   ├── scorer_prompt.py      # Scoring prompt
│   ├── decision_prompt.py    # Hiring decision prompt
│   ├── schedule_prompt.py    # Interview scheduling prompt
│   ├── guardrail_prompt.py   # Safety guardrail prompt
│   └── rubric_prompt.py      # Rubric generation prompt
│
├── tools/
│   ├── parse_resume.py       # Resume parser with injection protection
│   ├── score_candidate.py    # Candidate scorer
│   ├── availability.py       # Interview slot availability
│   ├── interview.py          # Interview scheduling & invites
│   ├── sanitizer.py          # Prompt injection sanitizer
│   └── fairness_auditor.py   # Bias detection auditor
│
├── graph/
│   ├── state.py              # LangGraph state definition
│   ├── nodes.py              # Graph node functions
│   └── graph.py              # LangGraph pipeline builder
│
├── models/
│   └── schemas.py            # Pydantic data models
│
├── ui/
│   └── components.py         # Streamlit UI components
│
└── trajectory/
    └── tracker.py            # Execution trajectory tracker
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Create a `.env` file in the `ai_recruitment_engine/` directory:

```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
MODEL=openai/gpt-4o-mini
```

Get a free API key from [OpenRouter.ai](https://openrouter.ai/keys).

### 3. Run the Dashboard

```bash
streamlit run ai_recruitment_engine/streamlit_app.py
```

Or use the batch file:

```bash
run_recruitment.bat
```

Open **http://localhost:8502** in your browser.

## Usage

1. **Upload Job Description** — Upload a `.txt` or `.pdf` file containing the job description
2. **Upload Resumes** — Upload one or more candidate resume files
3. **Click "Run Recruitment Agent"** — The agent processes all candidates through the pipeline
4. **Review Results** — View scores, decisions, and evidence in the Home tab
5. **Approve Interviews** — Select interview slots and approve candidates in the Interview tab

### Dashboard Tabs

| Tab | Description |
|-----|-------------|
| 🏠 **Home** | Dashboard metrics, candidate ranking, execution log |
| 🔄 **Trajectory** | LangGraph step-by-step execution trace |
| 🛡️ **Guardrails** | Compliance checks, injection detection, bias audit |
| 📋 **Audit** | Decision log, tool calls, JSON export |
| 🎯 **Interview** | Slot selection and human approval workflow |

## Scoring Thresholds

| Score Range | Decision |
|-------------|----------|
| < 0.40 | REJECT |
| 0.40 – 0.60 | HOLD |
| > 0.60 | LLM decides (SELECT/REJECT) |

## Guardrail Rules

If a guardrail violation is detected (prompt injection, safety issue, bias):
- Score is set to **0.0**
- Decision is overridden to **REJECT**
- Violation reason is logged and displayed in the UI
- Candidate is excluded from interview scheduling

## Tech Stack

- **LangGraph** — Stateful agent orchestration
- **OpenRouter API** — GPT-4o Mini (or any supported model)
- **Streamlit** — Interactive dashboard
- **Pydantic** — Data validation and schemas
- **PyPDF2** — PDF file parsing