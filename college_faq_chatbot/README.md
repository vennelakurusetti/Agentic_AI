# 🎓 College FAQ Chatbot

A production-quality **Retrieval-Augmented Generation (RAG)** chatbot for BVRIT Hyderabad College of Engineering for Women. Built with LangChain, ChromaDB, Streamlit, and OpenRouter.

## ✨ Features

- **📄 Smart Document Parsing** — Uses `python-docx` to parse DOCX preserving heading styles (Heading 1, Heading 2) as section metadata — no more "Unknown Section"
- **🔍 Intelligent Retrieval** — Top-K configurable (default 8), metadata filtering, relevance scoring, thin-chunk filtering, debug mode
- **🤖 LLM-Powered Answers** — GPT-4o Mini via OpenRouter, strictly grounded in retrieved context with section citations
- **💬 Beautiful Streamlit UI** — Modern gradient interface, streaming responses, citation badges, latency display
- **🧠 Conversation Memory** — Follow-up question support via query rewriting
- **📊 Evaluation** — Automated test pipeline with answer rate metrics, per-question breakdown, and recommendations
- **🔄 Auto-Rebuild** — Automatically detects when vector store needs rebuilding (e.g. after metadata format changes)

## 🏗️ Project Structure

```
college_faq_chatbot/
├── app.py              # Streamlit UI (main chat interface)
├── ingest.py           # Document ingestion with python-docx heading detection
├── rag.py              # Retrieval-Augmented Generation pipeline
├── prompts.py          # System prompt templates
├── evaluator.py        # Test case generation and evaluation pipeline
├── config.py           # Central configuration
├── utils.py            # Logging and utility functions
├── debug_retrieval.py  # Debugging tool for retrieval issues
├── requirements.txt    # Python dependencies
├── .env                # API keys and model configuration
├── .env.example        # Environment template
├── run.bat             # Helper batch script for Windows
├── README.md           # This file
│
├── data/
│   └── knowledge_base.docx   # Source document (BVRIT Hyderabad knowledge base)
│
├── chroma_db/          # Persistent vector database (created by ingest.py)
│
├── test_cases/         # Generated test cases for evaluation
│
└── evaluation/         # Evaluation reports and metrics
    └── report.json     # Evaluation report
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd college_faq_chatbot
pip install -r requirements.txt
```

### 2. Configure API Keys

Copy `.env.example` to `.env` and add your OpenRouter API key:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Get your API key from [OpenRouter](https://openrouter.ai/).

### 3. Ingest the Knowledge Base

The first run will auto-detect that the vector store needs building:

```bash
python ingest.py
```

This will:
- Load `data/knowledge_base.docx` using `python-docx` (paragraph-by-paragraph)
- Detect Heading 1 and Heading 2 styles to extract section names
- Group paragraphs by section and split into chunks (500 chars, 50 overlap)
- Generate embeddings via `text-embedding-3-small`
- Store vectors in persistent ChromaDB with section metadata

To force re-ingestion after updating the document:

```bash
python ingest.py --force
```

### 4. Start the Chatbot

```bash
streamlit run app.py
```

Open your browser to `http://localhost:8501`.

If the default `pip`/`streamlit` commands don't work due to a broken virtual environment, use the system Python directly:

```bash
C:\Users\madha\AppData\Local\Programs\Python\Python312\python.exe -m streamlit run app.py
```

## 🎯 Usage

### Chat Interface

- Type any question about BVRIT Hyderabad in the chat input
- Click example questions in the sidebar
- View citations showing the exact section name from the knowledge base
- Toggle Debug Mode to see retrieved chunks with relevance scores

### Example Questions

- "What is the admission process?"
- "What departments are available?"
- "Tell me about placements"
- "What campus facilities are available?"
- "How is the research at the college?"
- "What are the TS EAMCET cutoff ranks?"
- "Tell me about the CSE department"
- "What student clubs are there?"

### Sidebar Controls

- **Document Status** — Shows if `knowledge_base.docx` is loaded
- **Vector Store Status** — Shows chunk count and database readiness
- **Chunking Settings** — Displays chunk size, overlap, and total chunks
- **Top-K Slider** — Adjust number of retrieved chunks (1-10, default 8)
- **Debug Mode** — Toggle to see retrieved chunks in responses
- **Example Questions** — One-click question buttons

## 📊 Evaluation

### Run Evaluation

```bash
python evaluator.py
```

This will:
1. Test 15 predefined questions covering all knowledge base sections
2. Run the RAG pipeline on each question
3. Calculate answer rate, average chunks retrieved, and per-question breakdown
4. Save results to `evaluation/report.json`

To specify custom number of questions:

```bash
python evaluator.py --questions 20
```

## 🧠 Architecture

```
User Question
    │
    ▼
Query Rewriting (with conversation history)
    │
    ▼
Embedding Generation (text-embedding-3-small)
    │
    ▼
ChromaDB Similarity Search (Top-K = 8)
    │
    ▼
Thin Chunk Filtering (skip < 80 chars)
    │
    ▼
Context Assembly (chunks + section metadata)
    │
    ▼
LLM Generation (GPT-4o Mini via OpenRouter)
    │
    ▼
Answer + Section Citations
```

## 📄 Document Parsing

The `ingest.py` uses `python-docx` to read the DOCX file paragraph by paragraph:

1. **Heading 1** → Sets the current section (e.g. "6. Admissions")
2. **Heading 2** → Creates sub-section (e.g. "6. Admissions - Admission Process")
3. **Numbered headings** → Auto-detected as section boundaries
4. **ALL CAPS lines** → Detected as section headings
5. **Regular paragraphs** → Grouped under the current section heading
6. **Grouped by section** → Each section becomes a document with metadata
7. **Split into chunks** → Each chunk inherits the section metadata

This ensures no "Unknown Section" appears in citations.

## 🔧 Configuration

All settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `CHUNK_SIZE` | 500 | Characters per chunk |
| `CHUNK_OVERLAP` | 50 | Overlap between chunks |
| `TOP_K` | 8 | Number of chunks to retrieve |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `LLM_MODEL` | `openai/gpt-4o-mini` | OpenRouter LLM model |
| `LLM_TEMPERATURE` | 0.0 | LLM temperature (deterministic) |
| `LLM_MAX_TOKENS` | 1024 | Maximum response tokens |

## 🛡️ Quality

- **Type Hints** — All functions use Python type hints
- **Docstrings** — Every module and function has docstrings
- **Error Handling** — Graceful fallbacks for API failures, missing files, JSON parsing errors
- **Logging** — Comprehensive logging with timestamps and levels
- **No Hardcoded Keys** — All credentials via `.env`
- **No "Unknown Section"** — All chunks carry proper section metadata from DOCX headings

## 🐛 Debugging Retrieval Issues

If the chatbot can't answer a question you expect it to:

1. Run the debug script:
   ```bash
   python debug_retrieval.py
   ```
2. This shows what sections exist in the database
3. Tests retrieval for specific queries with relevance scores
4. Shows full content of problematic sections
5. Thin chunks (< 80 chars) are automatically filtered out during generation

## 📋 Requirements

```
langchain>=0.3.0
langchain-community>=0.3.0
langchain-chroma>=0.2.0
langchain-openai>=0.3.0
chromadb>=0.6.0
streamlit>=1.28.0
python-dotenv>=1.0.0
pandas>=2.0.0
tiktoken>=0.9.0
docx2txt>=0.9
python-docx>=1.0.0
```

## 📄 License

MIT

## Specification

See the project specification: [spec.md](spec.md)