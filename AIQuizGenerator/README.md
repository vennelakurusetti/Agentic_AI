# AI Quiz Generator

A minimal quiz generator project scaffold for Python.

## Setup
1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```
2. Activate it:
   - Windows: `venv\\Scripts\\activate`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Add API keys or settings to `.env` as needed.

## Usage
- Run the CLI:
  ```bash
  python main.py
  ```
- Run the web app:
  ```bash
  uvicorn app:app --reload
  ```

## Files
- `.gitignore` — ignored files for Git
- `spec.md` — project specification
- `requirements.txt` — Python dependencies
- `main.py` — CLI entry point
- `app.py` — FastAPI application
