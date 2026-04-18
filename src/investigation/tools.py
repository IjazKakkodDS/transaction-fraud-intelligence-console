"""
Deterministic investigation tools — Phase 3, Step 6.

Every function in this module is pure or DB-backed; none call an LLM.

DB-backed tools (get_transaction_history, get_user_profile, get_merchant_profile)
are safe placeholders: the current predictions schema lacks user_id and
merchant_id columns, so they cannot be implemented without a schema migration.
They detect this limitation at call time, log a warning, and return a structured
empty response instead of raising or fabricating data.

Fully working tools (get_rule_explanations, get_feature_breakdown) are
implemented deterministically using only the case dict and config values.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from src.config.config import HIGH_AMOUNT_THRESHOLD
from src.db.postgres_logger import predictions

logger = logging.getLogger("investigation-tools")

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _prediction_columns() -> set[str]:
    """Return the set of column names present in the predictions table."""
    return {col.name for col in predictions.columns}


def _supports_user_history() -> bool:
    return "user_id" in _prediction_columns()


def _supports_merchant_profile() -> bool:
    return "merchant_id" in _prediction_columns()


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce value to float; return default on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_iso_timestamp(ts: str | None) -> datetime | None:
    """
    Parse an ISO-8601 timestamp string into a UTC-aware datetime.
    Returns None if ts is absent or unparseable.
    """
    if not ts:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(ts, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    logger.warning("_parse_iso_timestamp: could not parse %r", ts)
    return None


def _reason_explanation(reason: str) -> str:
    """
    Map a short pipe-delimited reason token to a human-readable explanation.
    Unknown tokens are returned unchanged so no information is silently dropped.
    """
    _EXPLANATIONS: dict[str, str] = {
        "High transaction amount":      "Transaction amount exceeds the high-value threshold configured for rule-based flagging.",
        "Unusual transaction time":     "Transaction occurred between 00:00 and 05:59 UTC, a period associated with elevated fraud rates.",
        "Model flagged as suspicious":  "The gradient-boosted classifier produced a positive fraud prediction.",
        "Velocity spike":               "Unusual number of transactions were submitted in a short window, indicating potential card-testing or account takeover.",
        "New merchant":                 "The merchant has not been seen in this user's prior transaction history.",
        "Cross-border":                 "Transaction originated from a country different from the user's registered country.",
        "High risk score":              "The ML model assigned a risk score above the REVIEW threshold.",
        "Rule flagged":                 "At least one deterministic rule fired on this transaction.",
        "Suspicious IP":                "The originating IP address matches a known high-risk subnet or proxy exit node.",
        "Card not present":             "Transaction was submitted without physical card presence, increasing fraud surface area.",
    }
    return _EXPLANATIONS.get(reason, reason)


# ---------------------------------------------------------------------------
# DB-backed tools — safe placeholders
# ---------------------------------------------------------------------------

def get_transaction_history(user_id: str, lookback_days: int = 30) -> dict:
    """
    Return recent transaction history for user_id over the last lookback_days.

    SCHEMA LIMITATION: the predictions table has no user_id column.
    This function cannot be implemented without a schema migration.
    Returns a structured empty response and logs a warning.

    Args:
        user_id:       Identifier of the user to look up.
        lookback_days: Number of days to look back (default 30).

    Returns:
        dict with keys:
          available  — False (schema limitation)
          user_id    — echo of the requested id
          reason     — human-readable explanation of the limitation
          transactions — empty list
    """
    if not _supports_user_history():
        logger.warning(
            "get_transaction_history: user_id=%s lookback_days=%d — "
            "SCHEMA LIMITATION: predictions table has no user_id column; "
            "returning empty history",
            user_id,
            lookback_days,
        )
        return {
            "available": False,
            "user_id": user_id,
            "lookback_days": lookback_days,
            "reason": (
                "Transaction history requires a user_id column in the predictions table. "
                "This column does not exist in the current schema. "
                "Migrate the schema (add user_id) to enable this tool."
            ),
            "transactions": [],
            "transaction_count": 0,
        }

    # Reachable only after a schema migration adds user_id.
    # Kept as a forward stub so the caller interface is stable.
    logger.info(
        "get_transaction_history: user_id=%s lookback_days=%d — "
        "schema supports user_id (stub — query not yet implemented)",
        user_id,
        lookback_days,
    )
    return {
        "available": False,
        "user_id": user_id,
        "lookback_days": lookback_days,
        "reason": "Query implementation pending schema migration completion.",
        "transactions": [],
        "transaction_count": 0,
    }


def get_user_profile(user_id: str) -> dict:
    """
    Return the risk profile for user_id.

    SCHEMA LIMITATION: the predictions table has no user_id column.
    Returns a structured empty response and logs a warning.

    Args:
        user_id: Identifier of the user to look up.

    Returns:
        dict with keys:
          available — False (schema limitation)
          user_id   — echo of the requested id
          reason    — human-readable explanation of the limitation
          profile   — None
    """
    if not _supports_user_history():
        logger.warning(
            "get_user_profile: user_id=%s — "
            "SCHEMA LIMITATION: predictions table has no user_id column; "
            "returning empty profile",
            user_id,
        )
        return {
            "available": False,
            "user_id": user_id,
            "reason": (
                "User profile lookup requires a user_id column in the predictions table. "
                "This column does not exist in the current schema. "
                "Migrate the schema (add user_id) to enable this tool."
            ),
            "profile": None,
        }

    logger.info(
        "get_user_profile: user_id=%s — "
        "schema supports user_id (stub — query not yet implemented)",
        user_id,
    )
    return {
        "available": False,
        "user_id": user_id,
        "reason": "Query implementation pending schema migration completion.",
        "profile": None,
    }


def get_merchant_profile(merchant_id: str) -> dict:
    """
    Return the risk profile for merchant_id.

    SCHEMA LIMITATION: the predictions table has no merchant_id column.
    Returns a structured empty response and logs a warning.

    Args:
        merchant_id: Identifier of the merchant to look up.

    Returns:
        dict with keys:
          available   — False (schema limitation)
          merchant_id — echo of the requested id
          reason      — human-readable explanation of the limitation
          profile     — None
    """
    if not _supports_merchant_profile():
        logger.warning(
            "get_merchant_profile: merchant_id=%s — "
            "SCHEMA LIMITATION: predictions table has no merchant_id column; "
            "returning empty profile",
            merchant_id,
        )
        return {
            "available": False,
            "merchant_id": merchant_id,
            "reason": (
                "Merchant profile lookup requires a merchant_id column in the predictions table. "
                "This column does not exist in the current schema. "
                "Migrate the schema (add merchant_id) to enable this tool."
            ),
            "profile": None,
        }

    logger.info(
        "get_merchant_profile: merchant_id=%s — "
        "schema supports merchant_id (stub — query not yet implemented)",
        merchant_id,
    )
    return {
        "available": False,
        "merchant_id": merchant_id,
        "reason": "Query implementation pending schema migration completion.",
        "profile": None,
    }


# ---------------------------------------------------------------------------
# Fully deterministic tools
# ---------------------------------------------------------------------------

def get_rule_explanations(rule_flag: int, reasons: list[str]) -> list[str]:
    """
    Convert raw rule signals into human-readable explanations.

    Args:
        rule_flag: 0 or 1 — whether any deterministic rule fired.
        reasons:   List of short reason tokens (as stored in the predictions
                   table, pipe-delimited strings split by the caller).

    Returns:
        List of human-readable explanation strings, one per reason token.
    """
    triggered = bool(rule_flag)
    clean_reasons = [r.strip() for r in reasons if r and r.strip()]

    explanations = [
        _reason_explanation(r)
        for r in clean_reasons
    ]

    logger.info(
        "get_rule_explanations: rule_triggered=%s triggered_count=%d",
        triggered,
        len(explanations),
    )

    return explanations


def get_feature_breakdown(case: dict) -> dict:
    """
    Compute interpretable feature values from a case (predictions row).

    Derived fields:
      hour_of_day          — UTC hour extracted from case['timestamp'] (0–23); None if unparseable.
      is_night_transaction — True when hour_of_day is in [0, 5] (midnight–05:59 UTC).
      amount_vs_threshold  — Ratio of transaction amount to HIGH_AMOUNT_THRESHOLD (e.g. 1.5 = 50% above).
      risk_score           — Normalised float in [0.0, 1.0] from case['risk_score'].

    Args:
        case: Dict representation of a predictions row from Postgres.

    Returns:
        dict with the four derived fields plus the raw amount and threshold
        for reference.
    """
    amount = _safe_float(case.get("amount"), default=0.0)
    risk_score = _safe_float(case.get("risk_score"), default=0.0)
    timestamp_str = case.get("timestamp")

    dt = _parse_iso_timestamp(timestamp_str)
    hour_of_day: int | None = dt.hour if dt is not None else None
    is_night_transaction: bool | None = (
        hour_of_day in range(0, 6) if hour_of_day is not None else None
    )

    amount_vs_threshold: float | None = (
        round(amount / HIGH_AMOUNT_THRESHOLD, 4)
        if HIGH_AMOUNT_THRESHOLD > 0
        else None
    )

    breakdown = {
        "hour_of_day": hour_of_day,
        "is_night_transaction": is_night_transaction,
        "amount": amount,
        "high_amount_threshold": HIGH_AMOUNT_THRESHOLD,
        "amount_vs_threshold": amount_vs_threshold,
        "risk_score": round(risk_score, 4),
    }

    logger.info(
        "get_feature_breakdown: hour_of_day=%s is_night=%s "
        "amount=%.4f threshold=%.2f amount_vs_threshold=%s risk_score=%.4f",
        hour_of_day,
        is_night_transaction,
        amount,
        HIGH_AMOUNT_THRESHOLD,
        amount_vs_threshold,
        risk_score,
    )

    return breakdown
