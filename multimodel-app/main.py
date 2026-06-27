"""
multimodel-app — first version.

Sends one hardcoded question to a single model via the OpenRouter API
and prints the answer. Later versions will compare several models.
"""

import os
import time

from dotenv import load_dotenv
from openai import OpenAI, APITimeoutError, APIStatusError

# 1. Load the secret key from the .env file into the environment.
load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")

# 2. Create an OpenAI client, but point it at OpenRouter's endpoint.
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

# 3. The free models from the spec.
MODELS = [
    "google/gemma-4-31b-it:free",
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-nano-9b-v2:free",
]

# Price per million tokens (input, output) in USD.
# All current models are free; add paid models here as needed.
PRICES = {
    "google/gemma-4-31b-it:free":    {"in": 0.0, "out": 0.0},
    "openai/gpt-oss-20b:free":       {"in": 0.0, "out": 0.0},
    "nvidia/nemotron-nano-9b-v2:free":{"in": 0.0, "out": 0.0},
}

# 4. The question we want to ask (hardcoded for now).
question = "Explain recursion in one short sentence."


def ask(question, model):
    """Send the question to one model.

    Returns a dict with:
      answer   - the model's reply text
      latency  - wall-clock seconds for the API call
      in_tok   - prompt tokens used
      out_tok  - completion tokens used
      cost_usd - estimated cost in USD
    """
    t0 = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": question}],
        timeout=30,  # seconds before giving up on a slow provider
    )
    latency = time.perf_counter() - t0

    usage = response.usage
    in_tok  = usage.prompt_tokens
    out_tok = usage.completion_tokens

    price   = PRICES.get(model, {"in": 0.0, "out": 0.0})
    cost_usd = (in_tok * price["in"] + out_tok * price["out"]) / 1_000_000

    return {
        "answer":   response.choices[0].message.content,
        "latency":  latency,
        "in_tok":   in_tok,
        "out_tok":  out_tok,
        "cost_usd": cost_usd,
    }


if __name__ == "__main__":
    COL_MODEL   = 34
    COL_PREVIEW = 48
    COL_LATENCY =  9
    COL_COST    = 12

    def _preview(text, width):
        text = text.replace("\n", " ").strip()
        return text if len(text) <= width else text[: width - 1] + "…"

    def print_table(rows):
        header = (
            f"{'Model':<{COL_MODEL}}"
            f"{'Preview':<{COL_PREVIEW}}"
            f"{'Latency':>{COL_LATENCY}}"
            f"{'Cost':>{COL_COST}}"
        )
        rule = "─" * len(header)
        print()
        print(header)
        print(rule)
        for r in rows:
            model_col   = r["model"][:COL_MODEL].ljust(COL_MODEL)
            preview_col = _preview(r.get("preview", r.get("error", "")), COL_PREVIEW).ljust(COL_PREVIEW)
            latency_col = (f"{r['latency']:.2f}s" if r["ok"] else "—").rjust(COL_LATENCY)
            cost_col    = (f"${r['cost_usd']:.6f}" if r["ok"] else "—").rjust(COL_COST)
            print(f"{model_col}{preview_col}{latency_col}{cost_col}")
        print(rule)

    print(f"\nQuestion: {question}\n")
    rows = []
    for model in MODELS:
        print(f"  querying {model} …", end="", flush=True)
        try:
            result = ask(question, model)
            rows.append({
                "model":    model,
                "ok":       True,
                "preview":  result["answer"],
                "latency":  result["latency"],
                "cost_usd": result["cost_usd"],
            })
            print(" done")
        except APITimeoutError:
            rows.append({"model": model, "ok": False, "error": "timed out after 30s",
                         "latency": 0, "cost_usd": 0})
            print(" timed out")
        except APIStatusError as e:
            rows.append({"model": model, "ok": False, "error": f"{e.status_code}: {e.message}",
                         "latency": 0, "cost_usd": 0})
            print(f" error {e.status_code}")
        except Exception as e:
            rows.append({"model": model, "ok": False, "error": str(e),
                         "latency": 0, "cost_usd": 0})
            print(" error")

    print_table(rows)

    print()
    for r in rows:
        print(f"=== {r['model']} ===")
        print(r.get("preview") or f"[{r.get('error')}]")
        print()
