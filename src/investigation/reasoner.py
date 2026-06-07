"""
LLM reasoning layer for the investigation pipeline — Phase 3.

generate_summary() assembles a compact structured prompt from gathered evidence
and calls a local Ollama instance via its HTTP API. The response is expected
to be a JSON object with constrained enum fields. On parse or validation
failure the call is retried up to MAX_RETRIES times before raising.

Recommendation values mirror the InvestigationReport schema:
  CONFIRM_FRAUD | FALSE_POSITIVE | ESCALATE

Confidence values:
  HIGH | MEDIUM | LOW

Environment variables:
  OLLAMA_BASE_URL — base URL of the Ollama server
                    (default: http://host.docker.internal:11434)
  OLLAMA_MODEL    — model tag to use (default: mistral:latest)
  OLLAMA_TIMEOUT  — HTTP timeout in seconds (default: 300)
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from decimal import Decimal

logger = logging.getLogger("investigation-reasoner")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
_MODEL = os.getenv("OLLAMA_MODEL", "mistral:latest")
_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "300"))
MAX_RETRIES = 2  # attempts beyond the initial call

_GENERATE_ENDPOINT = f"{_BASE_URL.rstrip('/')}/api/generate"

_VALID_RECOMMENDATIONS = {"CONFIRM_FRAUD", "FALSE_POSITIVE", "ESCALATE"}
_VALID_CONFIDENCES = {"HIGH", "MEDIUM", "LOW"}

_REQUIRED_KEYS = {
    "summary",
    "risk_factors",
    "mitigating_factors",
    "recommendation",
    "recommendation_rationale",
    "confidence",
    "confidence_rationale",
}

_OLLAMA_OPTIONS = {
    "temperature": 0,
    "num_predict": 300,
    "num_ctx": 2048,
}

# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

_GROUP_ORDER: list[tuple[str, str]] = [
    ("base",        "Base / Transaction Signals"),
    ("rich",        "Rich Signals"),
    ("behavioural", "Behavioural Signals"),
    ("graph",       "Graph Intelligence"),
    ("scenario",    "Scenario Context"),
]

_PROMPT_TEMPLATE = """\
You are a fraud analyst. Analyze the evidence below and respond with ONLY a \
valid JSON object — no markdown, no code fences, no extra text.

Required JSON keys:
  summary (string), risk_factors (list), mitigating_factors (list),
  recommendation (CONFIRM_FRAUD | FALSE_POSITIVE | ESCALATE),
  recommendation_rationale (string), confidence (HIGH | MEDIUM | LOW),
  confidence_rationale (string)

Rules:
- recommendation must be exactly: CONFIRM_FRAUD, FALSE_POSITIVE, or ESCALATE
- confidence must be exactly: HIGH, MEDIUM, or LOW
- risk_factors and mitigating_factors must be non-empty lists of strings
- Use only the evidence provided; do not invent facts
- Prefer ESCALATE when evidence is ambiguous or user history is unavailable

## CASE
transaction_id: {transaction_id}
amount: {amount}
risk_score: {risk_score}
decision: {decision}

## EVIDENCE GROUPS
{evidence_groups_section}

## FEATURES
{features_section}

## PLAYBOOK KNOWLEDGE
{knowledge_section}

## POLICY CONTEXT
{policy_section}
{extra_instruction}
Respond with the JSON object only:"""


def _build_prompt(
    case: dict,
    evidence_groups: dict,
    feature_breakdown: dict,
    knowledge: list[dict],
    extra_instruction: str = "",
) -> str:
    # Build evidence groups section — only include groups that have items
    group_lines: list[str] = []
    for key, header in _GROUP_ORDER:
        items = evidence_groups.get(key, [])
        if items:
            group_lines.append(f"{header}:")
            for item in items:
                group_lines.append(f"  - {item['label']}")
    evidence_groups_section = "\n".join(group_lines) if group_lines else "None"

    features_section = "\n".join(
        f"  {k}: {float(v) if isinstance(v, Decimal) else v}"
        for k, v in feature_breakdown.items()
    )

    knowledge_snippets = knowledge[:2]
    if knowledge_snippets:
        parts = []
        for doc in knowledge_snippets:
            content = (doc.get("content") or "")[:500]
            parts.append(f"[{doc.get('source', 'unknown')}] {content}")
        knowledge_section = "\n\n".join(parts)
    else:
        knowledge_section = "None"

    policy_section = (
        "No policy documents are available for this investigation. "
        "Base your analysis on the playbook guidance above."
    )

    extra = f"\nNote: {extra_instruction}" if extra_instruction else ""

    return _PROMPT_TEMPLATE.format(
        transaction_id=case.get("transaction_id", "N/A"),
        amount=case.get("amount", "N/A"),
        risk_score=case.get("risk_score", "N/A"),
        decision=case.get("decision", "N/A"),
        evidence_groups_section=evidence_groups_section,
        features_section=features_section,
        knowledge_section=knowledge_section,
        policy_section=policy_section,
        extra_instruction=extra,
    )


# ---------------------------------------------------------------------------
# Parsing and validation
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> str:
    """
    Strip markdown code fences if present and return the raw JSON string.
    Falls back to returning the original text so json.loads can surface the error.
    """
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)

    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1)

    return text


def _validate(parsed: dict) -> None:
    """Raise ValueError with a descriptive message if the parsed dict is invalid."""
    missing = _REQUIRED_KEYS - parsed.keys()
    if missing:
        raise ValueError(f"LLM response missing required keys: {missing}")

    rec = parsed.get("recommendation", "")
    if rec not in _VALID_RECOMMENDATIONS:
        raise ValueError(
            f"Invalid recommendation {rec!r}. "
            f"Must be one of {_VALID_RECOMMENDATIONS}"
        )

    conf = parsed.get("confidence", "")
    if conf not in _VALID_CONFIDENCES:
        raise ValueError(
            f"Invalid confidence {conf!r}. "
            f"Must be one of {_VALID_CONFIDENCES}"
        )

    if not isinstance(parsed.get("risk_factors"), list):
        raise ValueError("risk_factors must be a list")

    if not isinstance(parsed.get("mitigating_factors"), list):
        raise ValueError("mitigating_factors must be a list")


# ---------------------------------------------------------------------------
# Ollama HTTP call
# ---------------------------------------------------------------------------

def _call_ollama(prompt: str) -> str:
    """
    POST to the Ollama /api/generate endpoint and return the full response text.

    Uses urllib from the standard library — no extra dependency required.

    Raises:
        urllib.error.URLError: on connection failure.
        RuntimeError: if the Ollama response is missing the expected field.
    """
    payload = json.dumps({
        "model": _MODEL,
        "prompt": prompt,
        "stream": False,
        "options": _OLLAMA_OPTIONS,
    }).encode("utf-8")

    req = urllib.request.Request(
        _GENERATE_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    if "response" not in body:
        raise RuntimeError(
            f"Ollama response missing 'response' field. Got keys: {list(body.keys())}"
        )

    return body["response"].strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_summary(
    case: dict,
    evidence_groups: dict,
    feature_breakdown: dict,
    knowledge: list[dict],
) -> dict:
    """
    Call the local Ollama LLM with a structured evidence-grouped prompt and
    return a structured investigation summary.

    Retries up to MAX_RETRIES times on JSON parse or validation failure,
    appending the previous error to the prompt so the model can self-correct.

    Args:
        case:              Predictions row dict from Postgres.
        evidence_groups:   Grouped evidence dict from get_evidence_groups
                           (keys: base/rich/behavioural/graph/scenario).
        feature_breakdown: Feature dict from get_feature_breakdown.
        knowledge:         Retrieved playbook docs from retrieve_knowledge.

    Returns:
        dict with keys:
          summary, risk_factors, mitigating_factors,
          recommendation, recommendation_rationale,
          confidence, confidence_rationale

    Raises:
        RuntimeError: if all attempts are exhausted without a valid response.
        urllib.error.URLError: on unrecoverable connection errors.
    """
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 2):  # attempts: 1, 2, 3
        logger.info(
            "generate_summary: attempt=%d/%d model=%s endpoint=%s",
            attempt,
            MAX_RETRIES + 1,
            _MODEL,
            _GENERATE_ENDPOINT,
        )

        extra_instruction = ""
        if attempt > 1 and last_error:
            extra_instruction = (
                f"Previous attempt failed validation: {last_error}. "
                "Correct this and return ONLY the JSON object."
            )

        prompt = _build_prompt(
            case,
            evidence_groups,
            feature_breakdown,
            knowledge,
            extra_instruction=extra_instruction,
        )

        try:
            raw_text = _call_ollama(prompt)
        except (urllib.error.URLError, OSError) as exc:
            logger.error(
                "generate_summary: Ollama connection error on attempt %d — %s",
                attempt,
                exc,
            )
            raise

        logger.debug(
            "generate_summary: raw response (attempt %d): %r",
            attempt,
            raw_text[:500],
        )

        try:
            json_str = _extract_json(raw_text)
            parsed = json.loads(json_str)
            _validate(parsed)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc
            logger.warning(
                "generate_summary: parse/validation failed on attempt %d — %s",
                attempt,
                exc,
            )
            if attempt == MAX_RETRIES + 1:
                raise RuntimeError(
                    f"LLM reasoning failed after {MAX_RETRIES + 1} attempts. "
                    f"Last error: {exc}"
                ) from exc
            continue

        logger.info(
            "generate_summary: success on attempt=%d recommendation=%s confidence=%s",
            attempt,
            parsed.get("recommendation"),
            parsed.get("confidence"),
        )

        return {
            "summary":                  parsed["summary"],
            "risk_factors":             parsed["risk_factors"],
            "mitigating_factors":       parsed["mitigating_factors"],
            "recommendation":           parsed["recommendation"],
            "recommendation_rationale": parsed["recommendation_rationale"],
            "confidence":               parsed["confidence"],
            "confidence_rationale":     parsed["confidence_rationale"],
        }

    # Unreachable — loop always raises or returns — kept for type checkers.
    raise RuntimeError("generate_summary: exhausted all attempts")
