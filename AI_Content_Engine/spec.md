# AI Multimodal Content Engine — Specification

Purpose
- Generate text, image, and video campaign assets in a chained pipeline.

Scope
- Taglines, blog introductions, social posts, hero images, and video concepts.

Key components
- `app.py` — Streamlit UI
- `text_gen.py`, `image_gen.py`, `video_gen.py` — generators
- `config.py` — model and API configuration

How to run
1. Create a virtualenv and install `requirements.txt`.
2. Copy `.env.example` to `.env` and add API keys.
3. Run `streamlit run app.py`.

Notes
- Keep API keys out of source control; use `.env` and update `.gitignore` accordingly.
