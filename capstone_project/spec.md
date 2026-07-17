# Compliance Advisory & Triage Agent — Specification

## 1. Overview

The **Compliance Advisory & Triage Agent** is a production-quality AI application that answers compliance questions, classifies risk, and enforces governance guardrails. It is designed for organisations that need a reliable, auditable first-line compliance assistant covering regulations such as GDPR, AML/KYC, vendor management, and information security.

The system ingests internal policy documents (PDFs), builds a vector knowledge base, and answers user questions grounded exclusively in those documents. Questions outside the corpus are refused rather than hallucinated. All interactions are permanently logged to an immutable audit trail.

---

## 2. Goals

- Provide accurate, grounded answers to compliance questions using only loaded policy documents.
- Automatically classify every question by topic, risk level, and responsible owner.
- Refuse or escalate when the question is outside the corpus or carries HIGH risk.
- Maintain a tamper-evident audit log of every interaction (question, answer, metadata).
- Present results through a clean, accessible Streamlit dashboard.
- Be deployable by a single developer with only a Python environment and an OpenRouter API key.

---

## 3. Non-Goals

- Does not provide legal advice or replace qualified legal/compliance personnel.
- Does not support real-time regulatory updates (documents must be manually updated).
- Does not handle authentication or multi-user role-based access control.
- Does not integrate directly with external compliance platforms (e.g., OneTrust, Archer).
- Does not generate, modify, or store policy documents.

---

## 4. User Stories

| # | As a… | I want to… | So that… |
|---|-------|-----------|----------|
| 1 | Compliance analyst | Ask a question about GDPR data retention | I get an answer sourced from our policy, not a hallucination |
| 2 | Compliance analyst | Know the risk level of my query | I understand whether to proceed or escalate |
| 3 | Compliance manager | See all past queries and answers | I can audit the team's use of the tool |
| 4 | Developer / admin | Load new policy PDFs without code changes | I keep the knowledge base current |
| 5 | Compliance analyst | Receive a clear refusal for out-of-scope questions | I am not misled by fabricated answers |
| 6 | Compliance manager | Have HIGH-risk queries flagged for human review | Dangerous actions are never auto-approved |

---

## 5. Architecture

```
User (browser)
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  Streamlit UI  (main.py + app/ui/)                      │
│  ┌───────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │  Advisor  │  │  Audit Log  │  │   Evaluation     │   │
│  └─────┬─────┘  └─────────────┘  └──────────────────┘   │
│        │                                                │
│        ▼                                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Compliance Agent  (LangGraph StateGraph)        │   │
│  │                                                  │   │
│  │  retrieve → route → govern → answer → escalate   │   │
│  │                              → output            │   │
│  └──────┬──────────────────────────────────────────┘    │
│         │                                               │
│   ┌─────┴──────┐  ┌──────────────┐  ┌──────────────┐    │
│   │ RAG Layer  │  │ Governance   │  │ Audit Logger  │   │
│   │ ChromaDB   │  │ refusal.py   │  │ JSON + SQLite │   │
│   │ SentTrans. │  │ confidence.py│  └──────────────┘    │
│   │ LangChain  │  │ escalation.py│                      │
│   └────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
                        │ LLM calls
                        ▼
              OpenRouter  (Mistral-7B-Instruct)
```

---

## 6. Component Specifications

### 6.1 RAG Pipeline (`app/rag/`)

| Module | Responsibility |
|--------|---------------|
| `loader.py` | Ingests PDF files from `data/policies/` using `pypdf` and `pdfplumber`. Returns `LoadedDocumentInfo` objects with metadata. |
| `chunker.py` | Splits documents into overlapping chunks using `RecursiveCharacterTextSplitter` (LangChain). |
| `embeddings.py` | Wraps `SentenceTransformers` (`all-MiniLM-L6-v2` by default). Writes a `.model` sentinel file alongside ChromaDB so mismatches trigger auto-rebuild. |
| `retriever.py` | Manages ChromaDB vector store — `build_vectorstore`, `load_vectorstore`, `rebuild_vectorstore`, `vectorstore_exists`. `retrieve()` returns `(List[DocumentChunk], debug_info)`. |

**Key behaviour:** On startup the app checks whether the existing ChromaDB was built with the same embedding model. If not, it automatically deletes and rebuilds the store.

### 6.2 Routing Agent (`app/agents/routing_agent.py`)

Implements a two-stage classifier:

1. **LLM path** — structured JSON call to OpenRouter (Mistral-7B) that returns `{topic, risk_level, owner, reasoning}`.
2. **Keyword fallback** — deterministic rule-based matching that activates when the LLM call fails (network/API error).

**Outputs a `RoutingDecision`:**

| Field | Values |
|-------|--------|
| `topic` | `GDPR`, `AML`, `Vendor`, `Security`, `Privacy`, `Legal`, `General Compliance` |
| `risk_level` | `LOW`, `MEDIUM`, `HIGH` |
| `owner` | DPO, AML Officer, Procurement Team, Security Team, Legal Counsel, Compliance Officer |

Also exposes `is_bypass_question()` to detect questions attempting to circumvent compliance controls (e.g., "ignore GDPR for this client").

### 6.3 Compliance Agent (`app/agents/compliance_agent.py`)

A `LangGraph StateGraph` with six nodes:

| Node | Responsibility |
|------|---------------|
| `retrieve` | Calls `retriever.retrieve()` to fetch top-K chunks from ChromaDB. |
| `route` | Calls `routing_agent.classify_question()`. Detects bypass intent and forces `HIGH` risk. |
| `govern` | Deduplicates chunks by SHA-256, checks Layer-1 keyword guard, runs `should_refuse()`. Computes governance decision. |
| `answer` | Filters to OOC-cleared chunks only, builds LLM context, synthesizes grounded answer via OpenRouter. |
| `escalate` | Applies escalation rules; sets `escalated` and `requires_human_review` flags. |
| `output` | Packages final `ComplianceAnswer` Pydantic object. |

### 6.4 Governance Layer (`app/governance/`)

#### `refusal.py` — Anti-hallucination gate

Two layers of defence:

**Layer 1 — Keyword guard (pre-retrieval):**
`is_unsupported_standard()` matches known unsupported regulations (DPDP, HIPAA, ISO 9001, SOC 2, PCI DSS, CCPA, ISO 27017, etc.) before the retriever is called.

**Layer 2 — Score gate (post-retrieval):**
`should_refuse()` compares the top chunk relevance score against `OOC_THRESHOLD = 0.50`.

Three refusal cases:
- `REASON_EMPTY` — retriever returned zero chunks.
- `REASON_OOC` — top score < 0.50 (out of corpus).
- `REASON_LOW_SCORE` — safety-net edge case.

When refused, the response is the canonical `OOC_REFUSAL_MESSAGE` and the LLM is **not** called.

#### `confidence.py`

Scores confidence `[0.0 – 1.0]` based on retrieval score, number of sources, and answer length heuristics.

#### `escalation.py`

`should_escalate()` triggers on three independent rules:
1. `risk_level == HIGH` — non-negotiable escalation.
2. Dangerous intent phrases in the question (e.g., "bypass sanctions", "delete audit trail").
3. LLM answer contains approval language for a risky action (e.g., "you can proceed", "this can be bypassed").

### 6.5 Audit Logger (`app/audit/logger.py`)

Writes every interaction to two persistent stores:

| Store | Path | Format |
|-------|------|--------|
| JSON log | `logs/audit.json` | Append-only NDJSON (one record per line) |
| SQLite | `logs/audit.db` | Indexed by session, timestamp, topic, risk |

Each `AuditRecord` contains: `id` (UUID), `timestamp`, `question`, `answer`, `sources`, `confidence`, `topic`, `risk_level`, `owner`, `escalated`, `refused`, `session_id`.

### 6.6 UI (`app/ui/`)

#### `components.py`
- `inject_theme_css()` — dark/light mode toggle with custom CSS.
- `render_sidebar()` — shows loaded document list, vector DB status, debug mode toggle.
- `render_answer_card()` — displays answer, confidence badge, topic/risk/owner chips, sources, escalation banner, optional debug panel.
- `render_audit_table()` — paginated audit history with download button.
- `render_stats_dashboard()` — query count, topic distribution, risk breakdown, refusal rate.

#### `evaluation.py`
Runs a built-in PASS/FAIL test suite with `EvalCase` + `EvalResult` models. Test cases cover:
- Correct topic classification for GDPR, AML, Security, Vendor queries.
- Correct HIGH-risk escalation.
- Correct refusal for out-of-corpus questions.
- Correct handling of bypass-intent questions.

---

## 7. Data Models

### `ComplianceAnswer`
```
question          str
answer            str
sources           List[DocumentChunk]
confidence        float  [0.0 – 1.0]
topic             ComplianceTopic
risk_level        RiskLevel
owner             ComplianceOwner
escalated         bool
requires_human_review  bool
refused           bool
timestamp         datetime
retrieval_debug   Any   (debug panel only, excluded from serialisation)
agent_debug       Any   (debug panel only, excluded from serialisation)
```

### `DocumentChunk`
```
content           str
source            str   (filename)
page              int?
chunk_index       int
relevance_score   float
```

### `AuditRecord`
```
id                str   (UUID)
timestamp         str   (ISO-8601)
question          str
answer            str
sources           List[str]
confidence        float
topic             str
risk_level        str
owner             str
escalated         bool
refused           bool
session_id        str
```

---

## 8. Configuration

All settings are loaded from `.env` and validated by Pydantic `BaseSettings`.

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | _(required)_ | OpenRouter API key |
| `OPENROUTER_MODEL` | `mistralai/mistral-7b-instruct` | LLM model identifier |
| `CHROMA_PERSIST_DIR` | `./data/chroma_db` | ChromaDB storage directory |
| `POLICIES_DIR` | `./data/policies` | Directory for policy PDFs |
| `AUDIT_LOG_PATH` | `./logs/audit.json` | JSON audit log path |
| `RETRIEVAL_TOP_K` | `5` | Number of chunks to retrieve per query |
| `SIMILARITY_MIN_SCORE` | `0.10` | Floor score for refusal gate |
| `CONFIDENCE_THRESHOLD` | `0.65` | Minimum confidence before human review flag |

---

## 9. Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| UI | Streamlit | ≥ 1.35 |
| Agent orchestration | LangGraph | ≥ 0.1.14 |
| LLM client | LangChain + OpenRouter | ≥ 0.2.5 |
| LLM model | Mistral-7B-Instruct | via OpenRouter |
| Vector store | ChromaDB | ≥ 0.5.0 |
| Embeddings | SentenceTransformers (`all-MiniLM-L6-v2`) | ≥ 3.0.0 |
| PDF ingestion | pypdf + pdfplumber | ≥ 4.2 / ≥ 0.11 |
| Data validation | Pydantic v2 | ≥ 2.7 |
| Audit store | JSON (NDJSON) + SQLite | stdlib |
| Visualisation | Plotly | ≥ 5.20 |
| Logging | Loguru | ≥ 0.7 |
| Language | Python | 3.11+ |

---

## 10. Project Structure

```
capstone_project/
├── main.py                          # Streamlit entry point (3 pages)
├── requirements.txt
├── .env                             # Local secrets (not committed)
├── .streamlit/
│   └── config.toml                  # Dark-mode theme defaults
├── app/
│   ├── agents/
│   │   ├── compliance_agent.py      # LangGraph StateGraph (6 nodes)
│   │   └── routing_agent.py         # Topic / risk / owner classifier
│   ├── governance/
│   │   ├── refusal.py               # Anti-hallucination gate (2 layers)
│   │   ├── confidence.py            # Confidence scorer
│   │   └── escalation.py           # Escalation rules
│   ├── rag/
│   │   ├── loader.py                # PDF ingestion
│   │   ├── chunker.py               # Text splitting
│   │   ├── embeddings.py            # SentenceTransformers wrapper
│   │   └── retriever.py             # ChromaDB CRUD + retrieve()
│   ├── audit/
│   │   └── logger.py                # Audit trail (JSON + SQLite)
│   ├── ui/
│   │   ├── components.py            # Streamlit widgets
│   │   └── evaluation.py            # PASS/FAIL test suite page
│   └── utils/
│       ├── models.py                # Pydantic data models
│       └── config.py                # Settings (loaded from .env)
├── data/
│   ├── policies/                    # Drop PDF policy documents here
│   └── chroma_db/                   # Auto-generated vector store
└── logs/
    ├── audit.json                   # Append-only JSON audit log
    └── audit.db                     # SQLite audit database
```

---

## 11. Supported Policy Domains

The corpus supports the following compliance areas out of the box (depending on loaded PDFs):

| Domain | Example regulations / policies |
|--------|-------------------------------|
| GDPR | EU General Data Protection Regulation |
| AML | FATF recommendations, KYC / CDD requirements |
| Vendor | Third-party / supplier management policies |
| Security | Password policy, incident response procedures |
| Privacy | Data handling and consent frameworks |
| Legal | General legal compliance guidelines |

Questions about **unsupported** standards (DPDP, HIPAA, ISO 9001, SOC 2, PCI DSS, CCPA, ISO 27017) are refused at the keyword-guard layer before retrieval.

---

## 12. Evaluation Criteria

The built-in evaluation page tests the following:

| Category | Test cases |
|----------|-----------|
| Topic classification | GDPR, AML, Security, Vendor topics correctly identified |
| Risk classification | HIGH-risk questions identified as HIGH |
| Escalation | HIGH-risk answers flagged for human review |
| Refusal | Out-of-corpus questions refused (not hallucinated) |
| Bypass detection | "Ignore GDPR" / "bypass sanctions" questions escalated |
| Confidence | In-corpus answers score ≥ 0.60 confidence |

---

## 13. Known Constraints

- The LLM (Mistral-7B via OpenRouter) has a context window limit. Very large documents should be chunked aggressively.
- Cosine similarity scoring can produce false-positives for questions about data-protection regulations not in the corpus. The keyword-guard layer mitigates this but is not exhaustive.
- `st.cache_resource` caches the vector store for the Streamlit session; a server restart is required after loading new PDFs.
- The audit log is append-only by design; there is no delete or edit endpoint.
- No authentication layer — intended for trusted internal use or local deployment only.

---

## 14. Setup Quick Reference

```bash
# 1. Install dependencies
cd capstone_project
pip install -r requirements.txt

# 2. Configure environment
copy .env.example .env
# Edit .env: set OPENROUTER_API_KEY

# 3. Add policy PDFs
# Copy PDFs into data/policies/

# 4. Run
streamlit run main.py
```

App available at `http://localhost:8501`.
