# College FAQ Chatbot — Specification

Purpose
- Retrieval-Augmented Generation chatbot for college FAQs with LangChain and ChromaDB.

Core features
- Document ingestion, vector store construction, RAG retrieval, Streamlit UI, evaluation pipeline.

Primary files
- `ingest.py`, `rag.py`, `app.py`, `evaluator.py`, `config.py`, `prompts.py`.

Run
1. Install requirements: `pip install -r requirements.txt`.
2. Create `.env` from `.env.example` and add `OPENROUTER_API_KEY`.
3. `python ingest.py` then `streamlit run app.py`.
