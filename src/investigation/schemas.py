"""
Schemas for the Phase 3 investigation service.

Two top-level types:

  InvestigationRequest  — minimal trigger payload published to cases.investigate
                          by the API. Contains only the investigation identity
                          and the case to investigate. The investigation service
                          fetches all base-case data (transaction details, scoring
                          outputs, reasons) directly from Postgres using case_id.

  InvestigationReport   — structured output produced by the investigation
                          pipeline and written to the investigations table.
                          Every field is populated on success; LLM-produced
                          fields are explicitly typed and enum-constrained.

Enums
-----
  InvestigationStatus   — lifecycle state of an investigation run
  Recommendation        — constrained LLM output: CONFIRM_FRAUD | FALSE_POSITIVE | ESCALATE
  Confidence            — constrained LLM output: HIGH | MEDIUM | LOW
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class InvestigationStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE    = "COMPLETE"
    FAILED      = "FAILED"


class Recommendation(str, Enum):
    CONFIRM_FRAUD  = "CONFIRM_FRAUD"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ESCALATE       = "ESCALATE"


class Confidence(str, Enum):
    HIGH   = "HIGH"
    MEDIUM = "MEDIUM"
    LOW    = "LOW"


# ---------------------------------------------------------------------------
# InvestigationRequest
#
# Published to cases.investigate by the API when an analyst triggers an
# investigation. Intentionally minimal — only the identifiers needed to
# locate the case. The investigation service is responsible for fetching
# all case data (amount, timestamp, risk_score, reasons, etc.) from Postgres
# using case_id before running the pipeline.
# ---------------------------------------------------------------------------

class InvestigationRequest(BaseModel):
    investigation_id: str = Field(
        default_factory=_new_uuid,
        description="UUID assigned by the API at trigger time. Idempotency key.",
    )
    case_id: int = Field(
        description="Primary key of the predictions row to investigate.",
    )

    model_config = {"extra": "ignore"}


# ---------------------------------------------------------------------------
# InvestigationReport
#
# Written to the investigations table on completion. Every non-optional field
# must be populated before the row is committed. LLM-produced fields use
# constrained enums — the validate_output node rejects any value outside the
# enum and retries rather than persisting an invalid recommendation.
# ---------------------------------------------------------------------------

class InvestigationReport(BaseModel):
    # --- Identity ---
    investigation_id: str = Field(default_factory=_new_uuid)
    case_id: int
    agent_version: str = Field(
        description="Identifies which prompt/tool version produced this report. "
                    "Increment on any change that affects output semantics.",
    )
    investigated_at: datetime = Field(default_factory=_now_utc)
    status: InvestigationStatus = InvestigationStatus.COMPLETE

    # --- Deterministic findings (populated by tools, no LLM) ---
    transaction_count_30d: int | None = Field(
        default=None,
        description="Number of transactions by this user in the last 30 days.",
    )
    amount_percentile: float | None = Field(
        default=None,
        description="Where this transaction amount sits in the user's 30-day history (0–100).",
    )
    merchant_seen_before: bool | None = Field(
        default=None,
        description="Whether this merchant_id appears in the user's prior transaction history.",
    )
    rules_triggered: list[str] = Field(
        default_factory=list,
        description="Expanded rule explanations for each triggered signal.",
    )
    feature_breakdown: dict = Field(
        default_factory=dict,
        description="Key feature values that drove the model and rule scores.",
    )

    # --- LLM-produced fields ---
    summary: str | None = Field(
        default=None,
        description="2-4 sentence narrative of the case written by the LLM.",
    )
    risk_factors: list[str] = Field(
        default_factory=list,
        description="Ordered signals supporting a fraud determination.",
    )
    mitigating_factors: list[str] = Field(
        default_factory=list,
        description="Signals arguing against fraud.",
    )
    recommendation: Recommendation | None = Field(
        default=None,
        description="LLM recommendation constrained to CONFIRM_FRAUD | FALSE_POSITIVE | ESCALATE.",
    )
    recommendation_rationale: str | None = Field(
        default=None,
        description="LLM reasoning behind the recommendation.",
    )
    confidence: Confidence | None = Field(
        default=None,
        description="LLM confidence in the recommendation: HIGH | MEDIUM | LOW.",
    )
    confidence_rationale: str | None = Field(
        default=None,
        description="LLM reasoning behind the confidence level.",
    )

    # --- Retrieval provenance ---
    playbooks_referenced: list[str] = Field(
        default_factory=list,
        description="Source document names of fraud playbooks retrieved during investigation.",
    )
    policies_referenced: list[str] = Field(
        default_factory=list,
        description="Policy document names used in LLM reasoning.",
    )

    # --- Error state (populated when status=FAILED) ---
    error_message: str | None = None

    model_config = {"extra": "ignore"}
