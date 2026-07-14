"""
app/agents/routing_agent.py
---------------------------
LangGraph-powered routing agent.

Responsibilities:
  1. Classify the compliance topic (GDPR, AML, Vendor, Security, …)
  2. Assess risk level (LOW / MEDIUM / HIGH)
  3. Assign the appropriate organisational owner

The agent uses a structured LLM call via OpenRouter and falls back to
rule-based keyword matching when the LLM call fails, ensuring the
application never crashes due to an API outage.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from app.utils.config import get_settings
from app.utils.models import (
    ComplianceOwner,
    ComplianceTopic,
    RiskLevel,
    RoutingDecision,
)


# ──────────────────────────────────────────────────────────────
# Owner mapping — deterministic lookup by topic
# ──────────────────────────────────────────────────────────────
TOPIC_OWNER_MAP: Dict[ComplianceTopic, ComplianceOwner] = {
    ComplianceTopic.GDPR: ComplianceOwner.DPO,
    ComplianceTopic.AML: ComplianceOwner.AML_OFFICER,
    ComplianceTopic.VENDOR: ComplianceOwner.PROCUREMENT,
    ComplianceTopic.SECURITY: ComplianceOwner.SECURITY_TEAM,
    ComplianceTopic.PRIVACY: ComplianceOwner.DPO,
    ComplianceTopic.LEGAL: ComplianceOwner.LEGAL_COUNSEL,
    ComplianceTopic.GENERAL: ComplianceOwner.COMPLIANCE_OFFICER,
}


# ──────────────────────────────────────────────────────────────
# Keyword-based fallback classifier
# ──────────────────────────────────────────────────────────────
_TOPIC_KEYWORDS: Dict[ComplianceTopic, list[str]] = {
    ComplianceTopic.GDPR: ["gdpr", "data protection", "data subject", "dpo", "right to erasure",
                           "consent", "lawful basis", "controller", "processor"],
    ComplianceTopic.AML: ["aml", "anti-money laundering", "kyc", "sanctions", "cdd",
                          "due diligence", "fatf", "beneficial owner", "transaction monitoring"],
    ComplianceTopic.VENDOR: ["vendor", "supplier", "third party", "third-party", "procurement",
                             "outsourcing", "contract", "service provider"],
    ComplianceTopic.SECURITY: ["password", "incident", "breach", "vulnerability", "firewall",
                               "access control", "encryption", "mfa", "phishing", "malware"],
    ComplianceTopic.PRIVACY: ["privacy", "personal data", "pii", "data sharing", "data transfer",
                              "cross-border", "adequacy decision"],
    ComplianceTopic.LEGAL: ["legal", "regulation", "statute", "law", "litigation", "liability"],
}

_HIGH_RISK_KEYWORDS = [
    # Explicit bypass / circumvention intent
    "ignore", "bypass", "skip", "circumvent", "override", "disable",
    "avoid", "violate", "approve without", "process without consent",
    "transfer restricted", "prohibited",
    # Dangerous actions
    "criminal", "illegal", "fraudulent", "sanction violation",
]

_MEDIUM_RISK_KEYWORDS = [
    # AML / KYC domain
    "aml", "anti-money laundering", "kyc", "know your customer",
    "customer due diligence", "cdd", "beneficial owner", "beneficial ownership",
    "suspicious transaction", "transaction monitoring", "fatf",
    "pep", "politically exposed",
    # GDPR / Privacy domain
    "gdpr", "data protection", "data subject", "right to erasure",
    "data retention", "retention period", "lawful basis", "consent",
    "cross-border", "data transfer", "personal data",
    "dpo", "data breach notification",
    # Vendor / Information Security
    "vendor", "third party", "third-party", "supplier", "outsourcing",
    "access control", "encryption", "incident response",
    "information security", "audit",
]

# LOW risk: password policy, log management, physical security — these are
# matched by topic keywords above but do NOT appear in medium/high lists.

# ──────────────────────────────────────────────────────────────
# Bypass-intent detection
# ──────────────────────────────────────────────────────────────

# Phrases that indicate the user is asking whether a compliance control
# can be ignored, circumvented, waived, or disabled.
_BYPASS_PHRASES = [
    "ignore", "bypass", "circumvent", "skip", "disable", "override",
    "opt out", "opt-out", "get around", "avoid", "exempt",
    "not apply", "doesn't apply", "does not apply", "waive", "waiver",
    "exception", "exclude", "turn off", "switch off",
]

# Words that, when near a bypass phrase, confirm compliance-control context
_COMPLIANCE_CONTEXT_WORDS = [
    "gdpr", "aml", "policy", "regulation", "compliance", "rule", "law",
    "requirement", "control", "obligation", "kyc", "sanctions", "audit",
    "reporting", "fatf", "data protection", "privacy",
]


def is_bypass_question(question: str) -> bool:
    """
    Return True if the question asks whether a compliance control can be
    ignored, bypassed, circumvented, or disabled.

    Detection uses a two-part heuristic:
      1. The question contains a bypass phrase (ignore / skip / circumvent…)
      2. The question also references a compliance context word (GDPR / AML…)

    Both conditions must hold to avoid false positives on legitimate
    questions like "how do I disable MFA on my phone".

    Parameters
    ----------
    question:
        The raw user question string.

    Returns
    -------
    bool
        True → bypass intent detected; govern node will force HIGH risk.
    """
    q_lower = question.lower()

    has_bypass = any(phrase in q_lower for phrase in _BYPASS_PHRASES)
    if not has_bypass:
        return False

    has_compliance_context = any(word in q_lower for word in _COMPLIANCE_CONTEXT_WORDS)
    result = has_bypass and has_compliance_context

    if result:
        logger.info(
            f"[routing] Bypass intent detected: '{question[:80]}'"
        )

    return result


def _keyword_classify(question: str) -> RoutingDecision:
    """
    Rule-based fallback classifier for when the LLM is unavailable.
    Uses keyword matching to determine topic and risk level.

    Priority: HIGH > MEDIUM > LOW
    """
    q_lower = question.lower()

    # Topic detection — first match wins
    topic = ComplianceTopic.GENERAL
    for t, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            topic = t
            break

    # Risk assessment — evaluated in priority order
    bypass_hit = any(phrase in q_lower for phrase in _BYPASS_PHRASES)
    high_hit   = any(kw in q_lower for kw in _HIGH_RISK_KEYWORDS)
    medium_hit = any(kw in q_lower for kw in _MEDIUM_RISK_KEYWORDS)

    if bypass_hit or high_hit:
        risk = RiskLevel.HIGH
    elif medium_hit:
        risk = RiskLevel.MEDIUM
    else:
        # Topic-based fallback: AML/GDPR/Vendor/Privacy default to MEDIUM
        # even if no explicit medium keyword was matched
        if topic in (
            ComplianceTopic.AML,
            ComplianceTopic.GDPR,
            ComplianceTopic.PRIVACY,
            ComplianceTopic.VENDOR,
        ):
            risk = RiskLevel.MEDIUM
        else:
            risk = RiskLevel.LOW

    owner = TOPIC_OWNER_MAP[topic]

    logger.debug(
        f"[routing] keyword classify: topic={topic.value} risk={risk.value} "
        f"(bypass={bypass_hit} high={high_hit} medium={medium_hit})"
    )
    return RoutingDecision(
        topic=topic,
        risk_level=risk,
        owner=owner,
        reasoning="[Keyword-based fallback classification]",
    )


# ──────────────────────────────────────────────────────────────
# LLM-based classifier
# ──────────────────────────────────────────────────────────────
_ROUTING_SYSTEM_PROMPT = """You are a compliance routing specialist.
Given a compliance question, respond ONLY with a JSON object (no markdown fences) containing:
{
  "topic": one of ["GDPR","AML","Vendor","Security","Privacy","Legal","General Compliance"],
  "risk_level": one of ["LOW","MEDIUM","HIGH"],
  "reasoning": "brief one-sentence explanation"
}

Risk level rules — apply strictly:

HIGH — ONLY when the user explicitly asks to:
  ignore, bypass, skip, circumvent, override, disable, avoid, or violate a compliance control.
  Also HIGH for: transferring restricted data, processing without consent, prohibited actions.
  Examples: "Can we skip KYC?", "Can we ignore GDPR?", "Can we bypass AML checks?"

MEDIUM — informational or procedural questions about regulated topics:
  AML, KYC, customer due diligence, beneficial ownership, suspicious transactions, FATF,
  GDPR, data protection, data subject rights, data retention, data transfers, consent,
  vendor compliance, third-party risk, information security, audit, data breach response.
  Examples: "What is customer due diligence?", "What is GDPR?", "What are KYC requirements?"

LOW — operational/technical questions not involving regulated subject matter:
  password policy, log management, physical security, general procedures.
  Examples: "What password length is required?", "What is the log retention policy?"
"""


@lru_cache(maxsize=1)
def _get_llm() -> ChatOpenAI:
    """Return a cached LLM client for routing (lightweight model)."""
    cfg = get_settings()
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=cfg.openrouter_api_key,
        model=cfg.openrouter_model,
        temperature=0.0,          # deterministic routing
        max_tokens=256,
    )


def classify_question(question: str) -> RoutingDecision:
    """
    Classify a compliance question using the LLM with keyword fallback.

    Parameters
    ----------
    question:
        The raw user question.

    Returns
    -------
    RoutingDecision
        Structured topic, risk, owner, and reasoning.
    """
    try:
        llm = _get_llm()
        messages = [
            SystemMessage(content=_ROUTING_SYSTEM_PROMPT),
            HumanMessage(content=f"Question: {question}"),
        ]
        response = llm.invoke(messages)
        raw = response.content.strip()

        # Strip markdown fences if model wraps in ```json … ```
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

        data: Dict[str, Any] = json.loads(raw)

        # Map to enum values safely
        topic_str = data.get("topic", "General Compliance")
        risk_str = data.get("risk_level", "LOW")
        reasoning = data.get("reasoning", "")

        # Normalise topic string to enum
        topic_map = {t.value: t for t in ComplianceTopic}
        topic = topic_map.get(topic_str, ComplianceTopic.GENERAL)

        risk_map = {r.value: r for r in RiskLevel}
        risk = risk_map.get(risk_str, RiskLevel.LOW)

        owner = TOPIC_OWNER_MAP[topic]

        logger.debug(f"LLM routing: topic={topic}, risk={risk}")
        return RoutingDecision(
            topic=topic,
            risk_level=risk,
            owner=owner,
            reasoning=reasoning,
        )

    except Exception as exc:  # noqa: BLE001
        logger.warning(f"LLM routing failed ({exc}), using keyword fallback.")
        return _keyword_classify(question)
