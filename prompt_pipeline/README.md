# 🚀 Prompt Pipeline Studio

A production-ready Streamlit application for multi-stage LLM prompt engineering pipelines. Visualize how multiple AI prompts collaborate to solve complex tasks through a transparent, inspectable pipeline.

## ✨ Features

- **6 Built-in Pipelines**: Support Ticket Triage, Essay Grader, Bug Report Analyzer, Meeting Notes → Action Items, Recipe Adapter, Trip Planner
- **Multi-stage Architecture**: 3-4 stages per pipeline (Understand → Reason → Produce → Critique)
- **JSON Handoff**: Every stage receives structured JSON and produces JSON for the next stage
- **Full Transparency**: Inspect every stage's prompt, input, output, and raw response
- **Automatic Retry**: Failed JSON parsing triggers automatic retry with error feedback
- **Light/Dark Theme**: Premium Apple-inspired design with seamless theme switching
- **Export**: Download results as Markdown reports or JSON
- **10+ Models**: Claude, GPT, Gemini, DeepSeek, Llama, Mistral via OpenRouter

## 🛠️ Tech Stack

- **Frontend**: Streamlit with custom CSS (glassmorphism, animations, responsive)
- **Backend**: Python, OpenRouter API
- **Deployment**: Local Streamlit server

## 📁 Project Structure

```
prompt_pipeline/
├── app.py              # Main Streamlit application
├── config.py           # Configuration and settings
├── llm.py              # OpenRouter API interaction
├── parser.py           # JSON parsing with error recovery
├── retry.py            # Automatic retry logic
├── prompts.py          # Prompt templates for all 6 pipelines
├── pipelines.py        # Pipeline execution engine
├── examples.py         # Sample inputs for each pipeline
├── styles.py           # Custom CSS (light/dark theme)
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (API key)
├── spec.md             # Application specification
├── utils/
│   ├── exporter.py     # Export to Markdown/JSON
│   └── logger.py       # Logging utility
├── assets/             # Static assets
└── sample_outputs/     # Sample output storage
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd prompt_pipeline
pip install -r requirements.txt
```

### 2. Set Up API Key

Create a `.env` file in the `prompt_pipeline/` folder:

```
OPENROUTER_API_KEY=your_api_key_here
```

Get your API key from [OpenRouter](https://openrouter.ai/keys).

### 3. Run the Application

```bash
streamlit run app.py
```

### 4. Open in Browser

Navigate to `http://localhost:8501`

## 🎯 Usage

1. **Select a pipeline** from the sidebar (or click a card on the home page)
2. **Enter input** as JSON in the text area
3. Click **Load Example** to test with sample data
4. Click **Run Full Pipeline** to execute all stages
5. Or click **Run Single Stage** to execute just the first stage
6. **Inspect** each stage's prompt, input, output, and raw response
7. **Export** results as Markdown or JSON

## 🧠 How It Works

Each pipeline consists of 3-4 stages:

```
Input → Stage 1 (Understand) → JSON → Stage 2 (Reason) → JSON → Stage 3 (Produce) → JSON → [Stage 4 (Critique)] → Final Output
```

### Stage 1: Understand
- Role-based prompt extraction
- Structured JSON output
- Extracts key information from input

### Stage 2: Reason
- Chain-of-thought analysis
- Deep reasoning about the data
- Identifies patterns and insights

### Stage 3: Produce
- Goal-oriented generation
- Creates final output based on analysis
- Follows specific constraints

### Stage 4: Critique (Optional)
- Review and evaluation
- Quality assessment
- Improvement suggestions

## 🎨 Design

- **Apple-inspired UI** with premium spacing and typography
- **Glassmorphism** cards with backdrop blur
- **Smooth animations** for transitions and loading states
- **Gradient accents** for visual hierarchy
- **Light/Dark mode** with instant switching
- **Responsive layout** for all screen sizes

## 🤖 Supported Models

Via [OpenRouter](https://openrouter.ai/):
- Claude 3.5 Sonnet & 3 Haiku
- GPT-4o & GPT-4o Mini
- Gemini Pro & Gemini Flash
- DeepSeek V3
- Llama 3.3 70B
- Mistral Large
- Qwen 2.5 72B

## 🔐 Security Notes

- The API key is loaded from `.env` file automatically
- No API key input in the UI — key is never exposed in the frontend
- The `.env` file is in `.gitignore` — never commit it to version control
- If your key is compromised, regenerate it at https://openrouter.ai/keys

## 📄 License

MIT