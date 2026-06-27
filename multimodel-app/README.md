# multimodel-app

Ask one prompt and compare answers from several LLMs side by side, using the
[OpenRouter](https://openrouter.ai) API.

## What it does
You type a question once. The app sends it to every model in the `MODELS` list
(in `main.py`) and prints each model's answer in its own labeled block — handy
for seeing how different models respond to the same prompt.

## Requirements
- Python 3.9 or newer
- An OpenRouter API key — get one at https://openrouter.ai/keys

## Setup

1. **Clone / open the project folder**
   ```bash
   cd multimodel-app
   ```

2. **Create and activate a virtual environment**

   Windows (PowerShell):
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```

   macOS / Linux:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install the dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Add your API key**

   Open the `.env` file and replace the placeholder with your real key:
   ```
   OPENROUTER_API_KEY=sk-or-your-real-key
   ```
   The `.env` file is git-ignored, so your key stays private.

## Run
```bash
python main.py
```
Type your prompt when asked (press Enter with no prompt to use the default).

## Configure which models are used
Edit the `MODELS` list near the top of `main.py`. Find model IDs at
https://openrouter.ai/models — for example:
```python
MODELS = [
    "openai/gpt-4o-mini",
    "anthropic/claude-3.5-haiku",
    "google/gemini-flash-1.5",
]
```

## Project layout
```
multimodel-app/
├─ .env              your OpenRouter API key  (SECRET — never commit)
├─ .gitignore        what git should ignore (.env, .venv, caches)
├─ spec.md           the specification
├─ requirements.txt  the libraries the app needs
├─ main.py           the application itself (entry point)
└─ README.md         this file
```

## Note
Never commit your `.env` file or share your API key publicly.
