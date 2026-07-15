"""
auto_test_generator.py — Automatic test case generation for the College FAQ RAG Chatbot.

Generates test cases using three strategies:
  1. Chunk-based: reads ChromaDB, samples chunks, uses LLM to generate questions from content
  2. Adversarial: uses LLM to generate tricky, edge-case, hallucination-bait questions
  3. Paraphrase: generates semantic paraphrases of seed questions

Results saved to evaluation/auto_generated_tests.json
"""

import json
import os
import random
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv()

import config

# ---------------------------------------------------------------------------
# LLM Helper
# ---------------------------------------------------------------------------

def _get_llm(max_tokens: int = 512):
    """Get a non-streaming LLM for generation."""
    from langchain_openai import ChatOpenAI
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")
    return ChatOpenAI(
        model=config.LLM_MODEL,
        temperature=0.7,
        max_tokens=max_tokens,
        openai_api_key=api_key,
        openai_api_base=config.OPENROUTER_BASE_URL,
        streaming=False,
    )


def _parse_json_list(raw: str, fallback: List = None) -> List:
    """Parse a JSON list from LLM output, stripping markdown fences."""
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return fallback or []
    except Exception:
        return fallback or []


# ---------------------------------------------------------------------------
# Strategy 1: Chunk-based question generation
# ---------------------------------------------------------------------------

def generate_questions_from_chunks(
    num_chunks: int = 10,
    questions_per_chunk: int = 2,
    delay: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Sample chunks from ChromaDB and generate questions from their content.

    Args:
        num_chunks:          Number of chunks to sample.
        questions_per_chunk: Questions to generate per chunk.
        delay:               Sleep between LLM calls.

    Returns:
        List of test case dicts with id, question, source, chunk_preview.
    """
    try:
        from langchain_openai import OpenAIEmbeddings
        from langchain_chroma import Chroma

        embeddings = OpenAIEmbeddings(
            model=config.EMBEDDING_MODEL,
            openai_api_key=os.getenv("OPENROUTER_API_KEY"),
            openai_api_base=config.OPENROUTER_BASE_URL,
        )
        vs = Chroma(
            collection_name=config.CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=str(config.CHROMA_DIR),
        )
        all_chunks = vs.get()
        docs = all_chunks.get("documents", [])
        metas = all_chunks.get("metadatas", [])
    except Exception as e:
        print(f"  [AutoGen] ChromaDB load failed: {e}. Returning empty list.")
        return []

    if not docs:
        return []

    # Sample chunks
    indices = random.sample(range(len(docs)), min(num_chunks, len(docs)))
    llm = _get_llm(max_tokens=512)

    generated = []
    q_id = 1

    for idx in indices:
        chunk_text = docs[idx][:600]
        section = (metas[idx] or {}).get("section", "General") if metas else "General"

        prompt = f"""You are generating test questions for a college FAQ chatbot.
Given the following text from the college knowledge base, generate exactly {questions_per_chunk} distinct, natural questions that a student or parent might ask, whose answers can be found in this text.

Text (from section: {section}):
{chunk_text}

Rules:
- Questions must be natural, specific, and answerable from this text
- Vary the question style (who, what, when, where, how)
- Do NOT ask generic questions
- Return ONLY a JSON array of strings

Example: ["What is the CSE placement rate?", "How many companies visit for recruitment?"]

Return the JSON array now:"""

        try:
            resp = llm.invoke(prompt)
            questions = _parse_json_list(resp.content, [])
            for q in questions[:questions_per_chunk]:
                if isinstance(q, str) and len(q.strip()) > 10:
                    generated.append({
                        "id": f"AUTO-CHUNK-{q_id:03d}",
                        "source": "chunk_based",
                        "question": q.strip(),
                        "origin_section": section,
                        "chunk_preview": chunk_text[:150],
                        "generated_at": datetime.now().isoformat(),
                    })
                    q_id += 1
            time.sleep(delay)
        except Exception as exc:
            print(f"    [!] LLM error for chunk {idx}: {exc}")

    print(f"  [AutoGen] Generated {len(generated)} chunk-based questions")
    return generated


# ---------------------------------------------------------------------------
# Strategy 2: Adversarial question generation
# ---------------------------------------------------------------------------

def generate_adversarial_tests(
    n_questions: int = 10,
    delay: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Generate adversarial / edge-case questions using the LLM.

    These are designed to:
    - Ask about things NOT in the knowledge base (hallucination bait)
    - Be ambiguous or misleading
    - Test robustness of the system

    Returns:
        List of test case dicts.
    """
    llm = _get_llm(max_tokens=1024)

    prompt = f"""Generate {n_questions} adversarial test questions for a college FAQ chatbot about BVRIT Hyderabad.

The chatbot should either answer correctly or say "This information is not available in the uploaded knowledge base."

Generate a mix of these types:
1. Questions about things likely NOT in the knowledge base (hallucination bait): e.g., asking for specific phone numbers, exact GPA of a professor
2. Ambiguous questions: questions that could be interpreted multiple ways
3. Leading questions: questions that contain false assumptions
4. Questions with typos or informal language
5. Very specific "trick" questions: asking for data the system shouldn't know

Return a JSON array of objects with this structure:
[
  {{
    "question": "...",
    "type": "hallucination_bait|ambiguous|leading|informal|trick",
    "expected_behavior": "refuse|answer|clarify"
  }}
]

Return ONLY the JSON array. No explanations."""

    try:
        resp = llm.invoke(prompt)
        raw_list = _parse_json_list(resp.content, [])
        generated = []
        for i, item in enumerate(raw_list[:n_questions]):
            if isinstance(item, dict) and "question" in item:
                generated.append({
                    "id": f"AUTO-ADV-{i + 1:03d}",
                    "source": "adversarial",
                    "question": item["question"],
                    "adversarial_type": item.get("type", "unknown"),
                    "expected_behavior": item.get("expected_behavior", "refuse"),
                    "generated_at": datetime.now().isoformat(),
                })
            elif isinstance(item, str):
                generated.append({
                    "id": f"AUTO-ADV-{i + 1:03d}",
                    "source": "adversarial",
                    "question": item,
                    "adversarial_type": "unknown",
                    "expected_behavior": "refuse",
                    "generated_at": datetime.now().isoformat(),
                })
        print(f"  [AutoGen] Generated {len(generated)} adversarial questions")
        time.sleep(delay)
        return generated
    except Exception as exc:
        print(f"    [!] Adversarial generation failed: {exc}")
        return []


# ---------------------------------------------------------------------------
# Strategy 3: Paraphrase generation
# ---------------------------------------------------------------------------

SEED_QUESTIONS = [
    "What is the admission process at BVRIT Hyderabad?",
    "What are the fees for B.Tech?",
    "Tell me about placements.",
    "What departments are available?",
    "Is there a hostel facility?",
]


def generate_paraphrase_tests(
    seed_questions: Optional[List[str]] = None,
    n_paraphrases: int = 2,
    delay: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Generate paraphrases of seed questions for robustness testing.

    Tests that the system can handle the same question asked differently.

    Args:
        seed_questions:  Base questions to paraphrase.
        n_paraphrases:   Number of paraphrases per seed.
        delay:           Sleep between LLM calls.

    Returns:
        List of test case dicts.
    """
    if seed_questions is None:
        seed_questions = SEED_QUESTIONS

    llm = _get_llm(max_tokens=512)
    generated = []
    q_id = 1

    for seed in seed_questions:
        prompt = f"""Generate {n_paraphrases} paraphrases of this question about a college FAQ chatbot.
Each paraphrase should:
- Ask the same thing in a different way
- Vary the phrasing, formality, or structure
- Be natural (as a student or parent would ask it)

Original: "{seed}"

Return ONLY a JSON array of strings (the paraphrases).
Example: ["How do I apply to BVRIT?", "Can you explain the application procedure?"]"""

        try:
            resp = llm.invoke(prompt)
            paraphrases = _parse_json_list(resp.content, [])
            for p in paraphrases[:n_paraphrases]:
                if isinstance(p, str) and len(p.strip()) > 10:
                    generated.append({
                        "id": f"AUTO-PARA-{q_id:03d}",
                        "source": "paraphrase",
                        "question": p.strip(),
                        "seed_question": seed,
                        "generated_at": datetime.now().isoformat(),
                    })
                    q_id += 1
            time.sleep(delay)
        except Exception as exc:
            print(f"    [!] Paraphrase generation failed for '{seed[:40]}': {exc}")

    print(f"  [AutoGen] Generated {len(generated)} paraphrase questions")
    return generated


# ---------------------------------------------------------------------------
# Save / Load
# ---------------------------------------------------------------------------

def save_test_suite(
    all_tests: List[Dict[str, Any]],
    path: Optional[str] = None,
) -> str:
    """Save the generated test suite to JSON."""
    if path is None:
        path = str(config.EVALUATION_DIR / "auto_generated_tests.json")

    config.EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

    # Deduplicate by question text
    seen = set()
    unique_tests = []
    for t in all_tests:
        q = t.get("question", "").strip().lower()
        if q and q not in seen:
            seen.add(q)
            unique_tests.append(t)

    suite = {
        "generated_at": datetime.now().isoformat(),
        "total": len(unique_tests),
        "by_source": {},
        "tests": unique_tests,
    }
    for t in unique_tests:
        src = t.get("source", "unknown")
        suite["by_source"].setdefault(src, 0)
        suite["by_source"][src] += 1

    with open(path, "w", encoding="utf-8") as f:
        json.dump(suite, f, indent=2, ensure_ascii=False)

    print(f"\n[AutoGen] Saved {len(unique_tests)} unique tests -> {path}")
    return path


def load_test_suite(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load a previously generated test suite."""
    if path is None:
        path = str(config.EVALUATION_DIR / "auto_generated_tests.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tests", [])


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def generate_full_test_suite(
    num_chunk_questions: int = 10,
    num_adversarial: int = 10,
    num_seed_paraphrases: int = 5,
    n_paraphrases_each: int = 2,
    delay: float = 0.3,
    save: bool = True,
) -> List[Dict[str, Any]]:
    """
    Run all three generation strategies and combine results.

    Returns:
        List of all generated test cases (deduplicated).
    """
    print(f"\n[AutoGen] Starting automatic test suite generation ...")
    all_tests = []

    # Strategy 1: Chunk-based
    chunks_per_batch = max(1, num_chunk_questions // 2)
    print(f"\n  Strategy 1: Chunk-based ({chunks_per_batch} chunks × 2 questions)")
    chunk_tests = generate_questions_from_chunks(
        num_chunks=chunks_per_batch,
        questions_per_chunk=2,
        delay=delay,
    )
    all_tests.extend(chunk_tests)

    # Strategy 2: Adversarial
    print(f"\n  Strategy 2: Adversarial ({num_adversarial} questions)")
    adv_tests = generate_adversarial_tests(n_questions=num_adversarial, delay=delay)
    all_tests.extend(adv_tests)

    # Strategy 3: Paraphrases
    seeds = SEED_QUESTIONS[:num_seed_paraphrases]
    print(f"\n  Strategy 3: Paraphrases ({len(seeds)} seeds × {n_paraphrases_each} paraphrases)")
    para_tests = generate_paraphrase_tests(
        seed_questions=seeds,
        n_paraphrases=n_paraphrases_each,
        delay=delay,
    )
    all_tests.extend(para_tests)

    if save:
        save_test_suite(all_tests)

    print(f"\n[AutoGen] Total generated: {len(all_tests)} tests")
    return all_tests


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Auto-generate test cases")
    parser.add_argument("--chunks", type=int, default=5, help="Number of chunks to sample")
    parser.add_argument("--adversarial", type=int, default=10, help="Number of adversarial questions")
    parser.add_argument("--seeds", type=int, default=5, help="Number of seed questions to paraphrase")
    parser.add_argument("--paraphrases", type=int, default=2, help="Paraphrases per seed")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between API calls")
    args = parser.parse_args()

    tests = generate_full_test_suite(
        num_chunk_questions=args.chunks * 2,
        num_adversarial=args.adversarial,
        num_seed_paraphrases=args.seeds,
        n_paraphrases_each=args.paraphrases,
        delay=args.delay,
    )
    print(f"\nGenerated {len(tests)} test cases.")
