# 🎓 College FAQ Chatbot — BVRIT Hyderabad

A production-quality **Retrieval-Augmented Generation (RAG)** chatbot for BVRIT Hyderabad College of Engineering for Women. Built with LangChain, ChromaDB, Streamlit, and OpenRouter.

## ✨ Features

- **📄 Smart Document Parsing** — `python-docx` parses DOCX preserving Heading 1/2 styles as section metadata
- **🔍 Intelligent Retrieval** — Top-K configurable (default 8), relevance scoring, thin-chunk filtering, debug mode
- **🤖 LLM-Powered Answers** — GPT-4o Mini via OpenRouter, grounded in retrieved context with section citations
- **🔧 Function Calling Tools** — `fee_calculator`, `date_checker`, `percentage_calculator` with prompt injection protection
- **💬 Multi-page Streamlit UI** — Chat, Logs, Evaluation, and Memory pages
- **🧠 Persistent Memory** — ChromaDB-backed user memory with 30-day retention and "clear my data" command
- **📊 Observability** — JSONL logging, latency/cost/token tracking, P95, anomaly detection, A/B prompt testing
- **🧪 Evaluation Suite** — RAGAS, LLM Judge, Functional Tests, Security Tests, Auto Test Generator
- **🏛️ Governance** — DeepEval, Promptfoo, Giskard-style tests; safety scanner, fairness tests, governance report
- **🔒 Security** — Prompt injection defense, PII protection, input length validation, safety scanning

## 🏗️ Project Structure

```
college_faq_chatbot/
├── app.py                    # Main chat UI (Streamlit)
├── rag.py                    # RAG pipeline (retrieve + generate)
├── ingest.py                 # Document ingestion → ChromaDB
├── tool_rag.py               # Tool router (fee/date/percent)
├── tools.py                  # Three function-calling tools
├── intent_classifier.py      # Intent routing (greeting/tool/RAG)
├── prompts.py                # System prompt templates
├── config.py                 # Central configuration
├── utils.py                  # Logger + Timer utilities
├── requirements.txt          # Python dependencies
├── .env                      # API keys (not committed)
├── .env.example              # Template
│
├── pages/                    # Streamlit multi-page navigation
│   ├── 1_📊_Logs.py          # Observability dashboard
│   ├── 2_🧪_Evaluation.py    # Evaluation dashboard
│   └── 3_🧠_Memory.py        # Memory browser
│
├── memory/                   # Persistent user memory subsystem
│   ├── memory_manager.py     # High-level orchestrator
│   ├── memory_store.py       # ChromaDB CRUD
│   ├── memory_retriever.py   # Similarity search
│   ├── memory_extractor.py   # Extract facts from turns
│   └── memory_bootstrapper.py
│
├── observability/            # LLM call monitoring
│   ├── llm_logger.py         # JSONL logging wrapper
│   ├── session_stats.py      # P95 latency, cost, tokens
│   ├── threshold_alerts.py   # Latency/cost/error alerts
│   ├── log_analyzer.py       # Anomaly detection
│   └── ab_testing.py         # A/B prompt version testing
│
├── evaluation/               # Automated evaluation suite
│   ├── ragas_eval.py         # RAGAS metrics (LLM-as-judge)
│   ├── llm_judge.py          # 5-criterion LLM judge
│   ├── functional_tests.py   # 20 functional test cases
│   ├── security_tests.py     # 32 security/adversarial tests
│   └── auto_test_generator.py # AI-generated test cases
│
├── governance/               # AI governance tools
│   ├── report.py             # Master governance report
│   ├── deepeval_tests.py     # 7 DeepEval-style metrics
│   ├── promptfoo_tests.py    # 15 Promptfoo-style assertions
│   ├── giskard_tests.py      # 15 Giskard vulnerability scans
│   ├── safety_scanner.py     # Runtime hallucination/injection/bias
│   └── fairness_tests.py     # Fairness across user profiles
│
├── data/
│   └── knowledge_base.docx   # BVRIT Hyderabad knowledge base
│
├── chroma_db/                # Knowledge vector store (auto-created)
└── memory_db/                # User memory vector store (auto-created)
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Copy `.env.example` to `.env` and add your OpenRouter API key:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Get your key at [openrouter.ai](https://openrouter.ai/).

### 3. Ingest the Knowledge Base

```bash
python ingest.py
```

Force rebuild after updating the DOCX:
```bash
python ingest.py --force
```

### 4. Run the App

```bash
streamlit run app.py
```

Open **http://localhost:8501** — sidebar navigation gives you 4 pages:
- **🎓 Chat** — main FAQ interface
- **📊 Logs** — observability dashboard
- **🧪 Evaluation** — run and view all evaluations
- **🧠 Memory** — browse and manage user memories

If the default `streamlit` command doesn't work (broken venv), use:

```bash
C:\Users\madha\AppData\Local\Programs\Python\Python312\python.exe -m streamlit run app.py
```

## 🔧 Tools

| Tool | Trigger | Example |
|------|---------|---------|
| `fee_calculator` | fee, cost, tuition | "What is the CSE fee?" |
| `date_checker` | deadline, when is, dates | "When is EAMCET 2026?" |
| `percentage_calculator` | X out of Y, eligible | "I got 450 out of 600" |

## 📊 Evaluation

From the **🧪 Evaluation** page or CLI:

```bash
python evaluation/ragas_eval.py        # RAGAS metrics
python evaluation/llm_judge.py         # LLM judge (5 criteria)
python evaluation/functional_tests.py  # 20 functional tests
python evaluation/security_tests.py    # 32 security tests
python governance/report.py            # Full governance report
```

## 🏛️ Governance Score

The governance report (`governance/governance_report.json`) produces a 0–100 score across:
- DeepEval metrics (25 pts)
- Promptfoo assertion tests (25 pts)
- Giskard vulnerability scan (25 pts)
- Prompt injection detection (25 pts)

## 🔒 Security & Privacy

- Input length capped at 2000 characters
- Prompt injection keyword detection on all tool inputs
- Safety scanner runs on every response (hallucination + bias + toxicity)
- User memories expire after 30 days; "clear my data" deletes immediately
- DPDP compliance: privacy notice shown on first load

## ⚙️ Configuration (`config.py`)

| Setting | Default |
|---------|---------|
| `CHUNK_SIZE` | 500 chars |
| `CHUNK_OVERLAP` | 50 chars |
| `TOP_K` | 8 chunks |
| `LLM_MODEL` | `openai/gpt-4o-mini` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` |
| `MEMORY_CLEANUP_DAYS` | 30 days |
| `MAX_INPUT_LENGTH` | 2000 chars |
