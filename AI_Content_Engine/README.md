# AI Multimodal Content Engine

A production-ready Streamlit application that generates complete marketing campaign assets using AI — taglines, blog introductions, social media posts, hero images, and video concepts — all connected in a single automated pipeline.

## ✨ Features

- **🏷️ Campaign Tagline** — Dynamic few-shot prompting with tone-specific examples
- **📝 Blog Introduction** — Role-based prompting for engaging ~200 word blog intros
- **📱 Social Media Posts** — Structured JSON output for Twitter, Instagram, and LinkedIn
- **🖼️ Hero Image** — Programmatic prompt building + AI image generation
- **🎬 Video Concept** — Production-level video storyboard document generation
- **⛓️ Chained Pipeline** — Each stage consumes outputs from previous stages
- **🔄 Auto Retry** — Exponential backoff for all external API calls
- **📥 Download** — Download buttons for all generated assets

## 📁 Project Structure

```
content_engine/
├── app.py              # Streamlit UI (two-column dashboard)
├── text_gen.py         # Text generation (tagline, blog, social posts)
├── image_gen.py        # Image prompt builder + generation
├── video_gen.py        # Video concept document generation
├── config.py           # Constants, models, retry settings, examples
├── .env                # API keys and model overrides
└── README.md           # This file
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install streamlit requests python-dotenv
```

### 2. Configure API Keys

Edit `.env` in the project root:

```env
# API Keys
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_IMAGE_KEY=sk-or-v1-your-key-here

# Models (optional — defaults work out of the box)
OPENROUTER_TEXT_MODEL=openai/gpt-4o-mini
OPENROUTER_IMAGE_MODEL=google/gemini-3.1-flash-image
OPENROUTER_VIDEO_MODEL=openai/gpt-4o-mini
```

> **Note:** You can use the same API key for both `OPENROUTER_API_KEY` and `OPENROUTER_IMAGE_KEY`.

### 3. Run the App

```bash
streamlit run app.py
```

### 4. Use It

1. Fill in the **Campaign Brief** in the sidebar
2. Choose a **Brand Tone** (Premium, Playful, Eco, Professional, Luxury, Minimal, Friendly)
3. Click **Generate Campaign**
4. Watch the pipeline progress and download your assets

## 🧠 Models Used

| Task | Default Model | Alternative Options |
|------|--------------|-------------------|
| Text generation | `openai/gpt-4o-mini` | Any OpenRouter text model |
| Image generation | `google/gemini-3.1-flash-image` | `openai/gpt-5-image-mini`, `openai/gpt-5-image` |
| Video concept | `openai/gpt-4o-mini` | (Generates text-based video briefs — no video models available on OpenRouter) |

### Image Model Pricing (per token)

| Model | Prompt Cost | Completion Cost |
|-------|------------|----------------|
| `google/gemini-2.5-flash-image` | $0.0000003 | $0.0000025 |
| `google/gemini-3.1-flash-image` | $0.0000005 | $0.000003 |
| `openai/gpt-5-image-mini` | $0.0000025 | $0.000002 |
| `google/gemini-3-pro-image` | $0.000002 | $0.000012 |
| `openai/gpt-5-image` | $0.00001 | $0.00001 |

> 🔄 You can also add provider keys (Google AI Studio, etc.) in your [OpenRouter dashboard](https://openrouter.ai/settings) under **Providers** to use your own API credits.

## 🎨 Brand Tones

| Tone | Description |
|------|-------------|
| **Premium** | Photorealistic, luxury studio quality |
| **Playful** | Bright, colorful, energetic |
| **Eco** | Earthy, natural, sustainable |
| **Professional** | Clean, modern, corporate |
| **Luxury** | Cinematic, high-end |
| **Minimal** | Scandinavian, clean aesthetics |
| **Friendly** | Warm, inviting, approachable |

## 🔄 Pipeline Flow

```
Product Brief
      │
      ▼
Campaign Tagline  ────┬───► Blog Introduction
      │               │
      │               └───► Image Prompt ──► Hero Image ──► Video Concept
      │
      └───► Social Media Posts (Twitter, Instagram, LinkedIn)
```

Each stage passes its output to the next stage for context-aware generation.

## ⚙️ Configuration

All settings are in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `TEXT_RETRIES` | 3 | Max retries for text API calls |
| `IMAGE_RETRIES` | 2 | Max retries for image API calls |
| `RETRY_BACKOFF` | [1, 2, 4] | Exponential backoff in seconds |
| `SUPPORTED_TONES` | 7 tones | Available brand tones |
| `FEW_SHOT_EXAMPLES` | 2 per tone | Dynamic few-shot examples for tagline generation |
| `STYLE_MAP` | 7 styles | Image style descriptions per tone |

## 🛠️ Troubleshooting

### "402 Payment Required"
Your API key doesn't have enough credits. Add credits at [OpenRouter settings](https://openrouter.ai/settings/credits).

### "429 Quota Exceeded"
Your provider key (e.g., Google AI Studio) has hit its rate limit or free tier quota. Upgrade to a paid plan or wait for the quota to reset.

### Image generation returns empty
- Check that your image API key has sufficient credits
- Verify the image model is correctly specified in `.env`
- Some free-tier accounts don't support image generation

### Video shows as text concept
OpenRouter currently does not host video generation models. The app generates a detailed video production brief instead.

## 📄 License

MIT

## Specification

See the project specification: [spec.md](spec.md)