"""
critic.py — AI Self-Critique Loop Module

After generating tagline, blog, and social posts, runs a second LLM call
acting as a senior content reviewer. Automatically regenerates failed
assets with critic feedback injection (max 2 retries).
"""

import json
import logging
import time
from typing import Any

from config import (
    CRITIC_MODEL,
    CRITIC_RETRIES,
    MAX_CRITIC_RETRIES,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    RETRY_BACKOFF,
)
from text_gen import (
    generate_blog_intro,
    generate_social_posts,
    generate_tagline,
    _call_openrouter,
)

logger = logging.getLogger(__name__)


# ── Critic System Prompt ────────────────────────────────────────────────

CRITIC_SYSTEM_PROMPT: str = (
    "You are a senior content strategist reviewing campaign copy.\n\n"
    "Evaluate each asset independently.\n\n"
    "Return ONLY valid JSON.\n"
    '{\n'
    '  "tagline":{\n'
    '      "pass":true,\n'
    '      "issue":null\n'
    '  },\n'
    '  "blog":{\n'
    '      "pass":true,\n'
    '      "issue":null\n'
    '  },\n'
    '  "social":{\n'
    '      "pass":true,\n'
    '      "issue":null\n'
    '  }\n'
    '}\n\n'
    "Fail an asset if:\n"
    "- brand tone doesn't match\n"
    "- audience ignored\n"
    "- product description contradicted\n"
    "- wording sounds generic\n"
    "- length exceeds requested limits"
)


# ── Data Structures ──────────────────────────────────────────────────────


class CriticResult:
    """Stores the evaluation result for a single asset."""

    def __init__(self, asset_name: str, passed: bool, issue: str | None) -> None:
        """Initialise a critic result entry.

        Args:
            asset_name: Name of the asset ('tagline', 'blog', 'social').
            passed: Whether the asset passed review.
            issue: Description of the issue if failed, else None.
        """
        self.asset_name: str = asset_name
        self.passed: bool = passed
        self.issue: str | None = issue
        self.retries_used: int = 0
        self.retry_history: list[str] = []

    def add_retry(self, attempt: int, feedback: str) -> None:
        """Record a retry attempt with feedback.

        Args:
            attempt: Which retry number this was.
            feedback: The critic feedback that triggered the retry.
        """
        self.retries_used = attempt
        self.retry_history.append(f"Retry {attempt}: {feedback}")


class CriticReport:
    """Full critic evaluation report for all assets."""

    def __init__(self) -> None:
        """Initialise an empty critic report."""
        self.results: dict[str, CriticResult] = {}
        self.all_passed: bool = True

    def add_result(self, result: CriticResult) -> None:
        """Add a critic result to the report.

        Args:
            result: CriticResult instance.
        """
        self.results[result.asset_name] = result
        if not result.passed:
            self.all_passed = False

    def to_dict(self) -> dict[str, Any]:
        """Convert report to a serialisable dict for logging/display.

        Returns:
            Dict representation of the report.
        """
        return {
            name: {
                "pass": r.passed,
                "issue": r.issue,
                "retries_used": r.retries_used,
                "retry_history": r.retry_history,
            }
            for name, r in self.results.items()
        }


# ── Critic Evaluation ────────────────────────────────────────────────────


def _parse_critic_json(raw: str) -> dict[str, Any] | None:
    """Parse the JSON response from the critic LLM.

    Args:
        raw: Raw response string.

    Returns:
        Parsed dict with tagline/blog/social keys, or None on failure.
    """
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data: dict[str, Any] = json.loads(cleaned)
        for key in ("tagline", "blog", "social"):
            if key not in data or "pass" not in data[key]:
                return None
        return data
    except (json.JSONDecodeError, TypeError):
        return None


def _run_critic_evaluation(
    product: str,
    audience: str,
    tone: str,
    tagline: str,
    blog: str,
    social: dict[str, str],
) -> dict[str, Any] | None:
    """Call the critic LLM to evaluate all generated assets.

    Args:
        product: Product name.
        audience: Target audience.
        tone: Brand tone.
        tagline: Generated tagline.
        blog: Generated blog introduction.
        social: Generated social posts dict.

    Returns:
        Parsed critic verdict dict, or None on failure.
    """
    social_text = json.dumps(social, indent=2)
    user_prompt = (
        f"Product: {product}\n"
        f"Target Audience: {audience}\n"
        f"Brand Tone: {tone}\n\n"
        f"--- Tagline ---\n{tagline}\n\n"
        f"--- Blog Introduction ---\n{blog}\n\n"
        f"--- Social Media Posts ---\n{social_text}\n\n"
        "Evaluate each asset and return JSON verdict:"
    )

    try:
        raw = _call_openrouter(
            CRITIC_SYSTEM_PROMPT,
            user_prompt,
            max_retries=CRITIC_RETRIES,
            model=CRITIC_MODEL,
        )
        parsed = _parse_critic_json(raw)
        if parsed:
            logger.info("Critic evaluation parsed successfully: %s", parsed)
            return parsed
        logger.warning("Critic JSON parse failed. Raw: %s", raw[:200])
    except Exception as e:
        logger.error("Critic evaluation call failed: %s", e)

    return None


# ── Self-Critique Pipeline ──────────────────────────────────────────────


def run_self_critique(
    product: str,
    audience: str,
    tone: str,
    tagline: str,
    blog: str,
    social: dict[str, str],
) -> tuple[dict[str, Any], CriticReport]:
    """Run the full self-critique loop: evaluate, regenerate failed assets.

    Args:
        product: Product name.
        audience: Target audience.
        tone: Brand tone.
        tagline: Generated tagline.
        blog: Generated blog introduction.
        social: Generated social posts dict.

    Returns:
        Tuple of (final_assets dict with tagline/blog/social, CriticReport).
    """
    # Initialise with current values
    assets: dict[str, Any] = {
        "tagline": tagline,
        "blog": blog,
        "social": social,
    }
    report = CriticReport()

    # Run initial evaluation
    verdict = _run_critic_evaluation(
        product, audience, tone,
        assets["tagline"], assets["blog"], assets["social"],
    )

    if verdict is None:
        # Critic failed to produce valid JSON — treat all as passed
        logger.warning("Critic evaluation returned None. Skipping critique.")
        for name in ("tagline", "blog", "social"):
            report.add_result(CriticResult(name, True, None))
        return assets, report

    # Process each asset
    failed_assets = []

    for asset_name in ("tagline", "blog", "social"):
        asset_verdict = verdict.get(asset_name, {})
        passed = asset_verdict.get("pass", True)
        issue = asset_verdict.get("issue", None)

        result = CriticResult(asset_name, passed, issue)

        if not passed:
            failed_assets.append((asset_name, issue))
            logger.info(
                "Asset '%s' FAILED critic: %s", asset_name, issue,
            )

        report.add_result(result)

    # Regenerate failed assets (max MAX_CRITIC_RETRIES attempts)
    for asset_name, issue in failed_assets:
        for attempt in range(1, MAX_CRITIC_RETRIES + 1):
            logger.info(
                "Regenerating '%s' (attempt %d/%d) with feedback: %s",
                asset_name, attempt, MAX_CRITIC_RETRIES, issue,
            )

            try:
                if asset_name == "tagline":
                    assets["tagline"] = generate_tagline(
                        product, tone, critic_feedback=issue,
                    )
                elif asset_name == "blog":
                    assets["blog"] = generate_blog_intro(
                        product, audience, assets["tagline"], tone,
                        critic_feedback=issue,
                    )
                elif asset_name == "social":
                    assets["social"] = generate_social_posts(
                        product, audience, tone, critic_feedback=issue,
                    )
            except Exception as e:
                logger.error("Regeneration of '%s' failed: %s", asset_name, e)
                continue

            # Re-evaluate the regenerated asset
            new_verdict = _run_critic_evaluation(
                product, audience, tone,
                assets["tagline"], assets["blog"], assets["social"],
            )

            if new_verdict and new_verdict.get(asset_name, {}).get("pass", False):
                # Asset passed after regeneration
                report.results[asset_name].passed = True
                report.results[asset_name].issue = None
                report.results[asset_name].add_retry(attempt, issue)
                logger.info("Asset '%s' passed after retry %d", asset_name, attempt)
                break
            else:
                report.results[asset_name].add_retry(attempt, issue)
                if attempt < MAX_CRITIC_RETRIES:
                    # Update issue for next attempt
                    if new_verdict:
                        issue = new_verdict.get(asset_name, {}).get(
                            "issue", "Regenerated version still needs improvement"
                        )
                    logger.warning(
                        "Asset '%s' still failing after retry %d", asset_name, attempt,
                    )
        else:
            # All retries exhausted
            logger.warning(
                "Asset '%s' failed after %d retries", asset_name, MAX_CRITIC_RETRIES,
            )

    # Final re-evaluation to update report
    final_verdict = _run_critic_evaluation(
        product, audience, tone,
        assets["tagline"], assets["blog"], assets["social"],
    )

    if final_verdict:
        for asset_name in ("tagline", "blog", "social"):
            asset_verdict = final_verdict.get(asset_name, {})
            passed = asset_verdict.get("pass", True)
            report.results[asset_name].passed = passed
            if not passed:
                report.results[asset_name].issue = asset_verdict.get("issue", None)

    # Recalculate all_passed
    report.all_passed = all(
        r.passed for r in report.results.values()
    )

    return assets, report