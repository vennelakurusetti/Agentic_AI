"""
app/governance/refusal.py
--------------------------
Implements the anti-hallucination refusal gate.

This module is the SOLE enforcement point for deciding whether retrieved
chunks are good enough to answer from. The retriever returns all candidates
ranked by score; this gate decides whether to answer or refuse.

Three refusal cases:
  1. EMPTY_RETRIEVAL  — retriever returned zero chunks (empty collection).
  2. OUT_OF_CORPUS    — top chunk score is below OOC_THRESHOLD (≈0.35),
                        meaning the question is genuinely outside the loaded
                        policy documents. Unrelated chunks are NOT sent to the LLM.
  3. LOW_SIMILARITY   — some chunks exist above the noise floor but none clears
                        the corpus threshold (shouldn't happen often — mainly a
                        safety net for edge cases).

OOC_THRESHOLD is the key lever:
  - Below it → refuse; the best match is too weak to be relevant
  - Above it → pass to LLM with those chunks as context

Why 0.35?
  Cosine similarity between completely unrelated texts typically falls in
  [0.10, 0.30]. Legitimate policy questions reliably score ≥ 0.40 against
  the loaded corpus. 0.35 sits in the gap, catching ISO-9001/HIPAA/PCI-DSS
  questions (score ~0.20–0.28) while passing GDPR/AML/Password questions
  (score ~0.45–0.85).
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from loguru import logger

from app.utils.models import DocumentChunk


# ── Refusal messages ───────────────────────────────────────────

# Returned when the question is outside the loaded corpus
OOC_REFUSAL_MESSAGE: str = (
    "This question is outside the available compliance corpus. "
    "I cannot provide a policy-based answer because the uploaded documents "
    "do not cover this topic. "
    "Please consult the appropriate Compliance Officer."
)

# Generic fallback (empty collection etc.)
REFUSAL_MESSAGE: str = (
    "This question is outside the available compliance corpus. "
    "I was unable to find relevant information in the loaded policy documents. "
    "Please consult your Compliance Officer directly or check whether the "
    "relevant policy document has been uploaded to the system."
)

# ── Reason codes ────────────────────────────────────────────────
REASON_EMPTY      = "EMPTY_RETRIEVAL"
REASON_OOC        = "OUT_OF_CORPUS"
REASON_LOW_SCORE  = "LOW_SIMILARITY"
REASON_OK         = None  # no refusal

# ── Thresholds ──────────────────────────────────────────────────
# Minimum top-chunk score for the question to be considered in-corpus.
# Questions whose best match falls below this score are refused without
# sending any context to the LLM.
OOC_THRESHOLD: float = 0.35

# Noise floor — chunks below this are completely ignored even when we answer.
NOISE_FLOOR: float = 0.10


def should_refuse(
    chunks: List[DocumentChunk],
    min_score: Optional[float] = None,
    ooc_threshold: Optional[float] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Decide whether the agent should refuse to answer.

    Parameters
    ----------
    chunks:
        Retrieved DocumentChunk objects, sorted descending by relevance_score.
        The retriever passes ALL candidates; this function filters.
    min_score:
        Noise floor — chunks below this are ignored (defaults to NOISE_FLOOR).
    ooc_threshold:
        Minimum top-chunk score to be considered in-corpus (defaults to OOC_THRESHOLD).

    Returns
    -------
    (refuse, reason)
        ``refuse`` — True → refuse, do not send context to the LLM.
        ``reason`` — REASON_EMPTY | REASON_OOC | REASON_LOW_SCORE | None.
    """
    floor     = min_score     if min_score     is not None else NOISE_FLOOR
    ooc_level = ooc_threshold if ooc_threshold is not None else OOC_THRESHOLD

    # ── Case 1: No chunks at all ───────────────────────────────
    if not chunks:
        logger.warning(
            f"[refusal] REFUSE ({REASON_EMPTY}): retriever returned zero chunks."
        )
        return True, REASON_EMPTY

    # ── Case 2: Out-of-corpus (top score too low) ──────────────
    # Sort defensively — chunks should already be sorted descending
    sorted_chunks = sorted(chunks, key=lambda c: c.relevance_score, reverse=True)
    top_score  = sorted_chunks[0].relevance_score
    top_source = sorted_chunks[0].source

    if top_score < ooc_level:
        logger.warning(
            f"[refusal] REFUSE ({REASON_OOC}): "
            f"top chunk score={top_score:.4f} is below OOC threshold={ooc_level:.2f}. "
            f"Best match: '{top_source}'. "
            f"Question is outside the loaded corpus — refusing without sending context."
        )
        return True, REASON_OOC

    # ── Case 3: All above-noise chunks still below ooc level ──
    # (Redundant safety net after Case 2, but kept for clarity)
    useful = [c for c in sorted_chunks if c.relevance_score >= floor]
    if not useful:
        logger.warning(
            f"[refusal] REFUSE ({REASON_LOW_SCORE}): "
            f"all {len(chunks)} chunk(s) below noise floor={floor:.2f}."
        )
        return True, REASON_LOW_SCORE

    # ── Pass ───────────────────────────────────────────────────
    above_ooc = [c for c in useful if c.relevance_score >= ooc_level]
    logger.info(
        f"[refusal] PASS: top_score={top_score:.4f} ≥ ooc_threshold={ooc_level:.2f} | "
        f"{len(above_ooc)}/{len(chunks)} chunks above OOC threshold | "
        f"top source='{top_source}'"
    )
    return False, REASON_OK


def filter_relevant_chunks(
    chunks: List[DocumentChunk],
    ooc_threshold: Optional[float] = None,
) -> List[DocumentChunk]:
    """
    Return only chunks that cleared the OOC threshold.

    Used by the answer node to build the LLM context block — ensures that
    unrelated chunks (score < OOC_THRESHOLD) are never sent to the LLM even
    when the question as a whole passed the refusal gate.

    Parameters
    ----------
    chunks:
        All deduplicated chunks from the govern node.
    ooc_threshold:
        Minimum score to include. Defaults to OOC_THRESHOLD.

    Returns
    -------
    List[DocumentChunk]
        Filtered list, still sorted descending by relevance_score.
    """
    level = ooc_threshold if ooc_threshold is not None else OOC_THRESHOLD
    relevant = [c for c in chunks if c.relevance_score >= level]

    dropped = len(chunks) - len(relevant)
    if dropped:
        logger.debug(
            f"[refusal] filter_relevant_chunks: dropped {dropped} chunk(s) "
            f"below OOC threshold={level:.2f}. {len(relevant)} remain."
        )
    return relevant


def build_refusal_response(owner_name: str) -> str:
    """
    Build a contextualised refusal message that includes the escalation contact.
    """
    return (
        f"{OOC_REFUSAL_MESSAGE}\n\n"
        f"**Suggested contact:** {owner_name}"
    )
