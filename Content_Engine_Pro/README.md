# Content Engine Pro

**Extends the AI Content Engine** with three powerful new features:
AI Self-Critique, Voiceover Generation, and Multi-Channel Adaptation.

Built with **DeepSeek Flash** (deepseek/deepseek-chat) via OpenRouter.

---

## ✨ Features

### Original (Preserved)
- **🏷️ Campaign Tagline** — Dynamic few-shot prompting with tone-specific examples
- **📝 Blog Introduction** — Role-based prompting for ~200 word blog intros
- **📱 Social Media Posts** — Structured JSON for Twitter, Instagram, LinkedIn
- **🖼️ Hero Image** — Programmatic prompt building + AI image generation
- **🎬 Video Concept** — Production-level video storyboard document

### New in Pro
- **🔍 AI Self-Critique Loop** — Senior content strategist LLM evaluates all assets. PASS/FAIL cards. Auto-regenerates failed assets with critic feedback injection (max 2 retries). Shows "⚠ Failed after 2 retries" for persistent failures.
- **🎙️ Voiceover Generation** — Converts blog intro to narration script → TTS (OpenAI TTS via OpenRouter). Audio player + MP3 download.
- **📡 Multi-Channel Adaptation** — Rewrites tagline/blog/social for B2B LinkedIn, Gen-Z TikTok, or Parents Facebook. Hero image and video remain unchanged. Instant channel switching.

---

## 📁 Project Structure

```
Content_Engine_Pro/
├── app.py              # Streamlit UI (extended with 3 new sections)
├── text_gen.py         # Text generation + critic feedback injection
├── image_gen.py        # Image prompt builder + generation
├── video_gen.py        # Video concept document generation
├── critic.py           # Self-critique loop module
├── voiceover_gen.py    # TTS generation module
├── adapter.py          # Multi-channel adaptation module
├── config.py           # Constants, models, retry settings, examples
├── utils.py            # Logging and error handling utilities
├── .env                # API keys and model overrides
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd Content_Engine_Pro
pip install -r requirements.txt
```

### 2. Configure API Keys

Edit `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_IMAGE_KEY=sk-or-v1-your-key-here

# DeepSeek Flash for all text tasks
OPENROUTER_TEXT_MODEL=deepseek/deepseek-chat
OPENROUTER_CRITIC_MODEL=deepseek/deepseek-chat
OPENROUTER_ADAPTATION_MODEL=deepseek/deepseek-chat
```

### 3. Run the App

```bash
streamlit run app.py
```

---

## 🔄 Pipeline Flow

```
Product Brief
      │
      ▼
Generate Tagline ──┬──► Generate Blog ──┬──► Generate Social Posts
      │            │                     │
      │            ▼                     ▼
      │       Image Prompt ──► Hero Image ──► Video Concept
      │
      ▼
Self-Critique ──► Regenerate Failed Assets (max 2 retries)
      │
      ▼
Generate Voiceover
      │
      ▼
Adapt Campaign for Selected Channel
```

---

## 🔍 Self-Critique Details

- **Critic System Prompt**: "Senior content strategist" evaluating brand tone, audience alignment, product accuracy, originality, and length.
- **Fail Criteria**: Brand tone mismatch, audience ignored, product contradiction, generic wording, length violation.
- **Regeneration**: Failed asset is regenerated with critic feedback injected into the prompt.
- **Max Retries**: 2 attempts per asset.
- **Display**: Green PASS cards / Red FAIL cards with issue descriptions and retry history.

## 🎙️ Voiceover Details

1. Blog intro → LLM rewrites as narration script (short sentences, max 15 words, commas for breathing, ellipses for drama)
2. Script → OpenAI TTS (`openai/tts-1`) via OpenRouter
3. Output: Audio player + download button for `voiceover.mp3`

## 📡 Channel Adaptation Details

| Channel | Tone | Vocabulary | Emoji |
|---------|------|------------|-------|
| B2B LinkedIn | Professional, data-driven | ROI, metrics, solutions | Minimal |
| Gen-Z TikTok | Casual, energetic | Slang, trends, viral | Heavy |
| Parents Facebook | Warm, trustworthy | Family, safety, value | Moderate |

Hero image and video concept show "Reused from original campaign" badge.

---

## 🧠 Models Used

| Task | Default Model |
|------|--------------|
| Text generation | `deepseek/deepseek-chat` |
| Image generation | `google/gemini-3.1-flash-image` |
| Video concept | `deepseek/deepseek-chat` |
| Critic evaluation | `deepseek/deepseek-chat` |
| Channel adaptation | `deepseek/deepseek-chat` |
| Text-to-Speech | `openai/tts-1` |

---

## 🛡️ Error Handling

- Empty product/audience → Streamlit warnings
- Invalid API responses → Graceful fallbacks
- JSON parsing failures → Retry + empty defaults
- TTS failures → Warning, script still displayed
- Critic failures → Assets treated as passed

## 📋 Logging

All retries, critic feedback, API latency, and generation time are logged via Python's `logging` module at INFO level.

---

## 📄 License

MIT

## Specification

See the project specification: [spec.md](spec.md)