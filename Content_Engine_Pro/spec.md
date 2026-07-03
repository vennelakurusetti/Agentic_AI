# Content Engine Pro — Specification

Purpose
- Extended content engine with self-critique, voiceover, and channel adaptation.

Scope
- Campaign asset generation, critic loop, TTS voiceovers, channel rewrites.

Key components
- `critic.py`, `voiceover_gen.py`, `adapter.py`, plus core generators from the base engine.

How to run
1. Install `requirements.txt`.
2. Configure `.env` with OpenRouter keys and DeepSeek provider if used.
3. Run `streamlit run app.py`.

Notes
- Avoid committing credentials; use `.env` and `.gitignore`.
