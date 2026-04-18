"""
Event schemas for the Phase 2 Kafka/Redpanda event backbone.

Three topics are defined:
  transactions.raw     — raw transaction as received by ingestion-service
  transactions.scored  — fraud decision produced by scoring-service
  cases.created        — triage case persisted for analyst review

Versioning strategy
-------------------
event_version follows MAJOR.MINOR:
  - MINOR bump: additive change (new optional field). Consumers ignore unknown
    fields by default (model_config extra="ignore"), so existing consumers
    continue working without redeployment.
  - MAJOR bump: breaking change (field removed, type changed, semantic change).
    Requires coordinated consumer update before producers upgrade.

All events carry a common envelope (BaseEvent). The envelope fields are
sufficient to route, deduplicate, and audit any event without deserialising
the full payload.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Base envelope — present on every event published to any topic
# ---------------------------------------------------------------------------

class BaseEvent(BaseModel):
    """
    Common metadata carried by every event regardless of topic.

    Consumer idempotency contract
    ------------------------------
    Consumers MUST deduplicate on event_id before applying any side effect
    (DB write, downstream publish, notification, etc.). Processing the same
    event_id more than once MUST produce no additional side effects — the
    outcome must be identical to processing it exactly once. This applies to
    all consumers of all topics derived from this base.
    """

    event_id: str = Field(
        default_factory=_new_uuid,
        description="UUID v4. Idempotency key — consumers must deduplicate on this field.",
    )
    event_type: str = Field(
        description="Dot-separated type string, e.g. 'transaction.raw'.",
    )
    event_version: str = Field(
        default="1.0",
        pattern=r"^\d+\.\d+$",
        description="MAJOR.MINOR version of this event schema.",
    )
    occurred_at: datetime = Field(
        default_factory=_now_utc,
        description="UTC timestamp when this event was created by the producer.",
    )
    producer: str = Field(
        description="Name of the service that published this event, e.g. 'ingestion-service'.",
    )

    model_config = {"extra": "ignore"}


# ---------------------------------------------------------------------------
# transactions.raw
#
# Published by: ingestion-service
# Consumed by:  scoring-service
#
# Carries the full raw transaction exactly as received at the ingest boundary.
# No fraud logic has been applied at this stage.
# ---------------------------------------------------------------------------

class TransactionRawEvent(BaseEvent):
    """Event published to the transactions.raw topic."""

    event_type: Literal["transaction.raw"] = "transaction.raw"

    # --- Transaction identity ---
    # KAFKA MESSAGE KEY: transaction_id is used as the Kafka/Redpanda message key when
    # publishing to transactions.raw. This guarantees that all events for the same
    # transaction are routed to the same partition, preserving strict ordering per
    # transaction across producers and consumer instances.
    transaction_id: str = Field(
        description=(
            "Stable identifier for the transaction. "
            "Used as the Kafka message key — all events sharing this transaction_id "
            "are written to the same partition, ensuring ordered, sequential processing "
            "per transaction regardless of consumer parallelism."
        ),
    )
    user_id: str
    merchant_id: str

    # --- Financial ---
    amount: Annotated[float, Field(gt=0, description="Transaction amount. Must be positive.")]
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code.",
    )
    payment_method: str = Field(
        description="e.g. 'credit_card', 'debit_card', 'bank_transfer'.",
    )

    # --- Temporal ---
    timestamp: str = Field(
        description="ISO-8601 transaction time as reported by the upstream system, e.g. '2024-03-15T14:32:07Z'.",
    )

    # --- Location ---
    country: str = Field(
        min_length=2,
        max_length=2,
        description="ISO 3166-1 alpha-2 country code.",
    )
    city: str | None = None

    # --- Device ---
    device_id: str | None = None
    ip_address: str | None = None
    device_type: str | None = Field(
        default=None,
        description="e.g. 'mobile', 'desktop', 'tablet'.",
    )

    # --- Merchant ---
    merchant_category: str | None = Field(
        default=None,
        description="e.g. 'electronics', 'groceries', 'travel'.",
    )

    # --- Flags ---
    is_international: bool = False
    is_fraud: bool | None = Field(
        default=None,
        description="Ground-truth label. Present only when known (e.g. replay of labelled data). "
                    "Must not be used by scoring logic.",
    )


# ---------------------------------------------------------------------------
# transactions.scored
#
# Published by: scoring-service
# Consumed by:  case-creation consumer, downstream dashboards, ML feedback loop
#
# Contains the fraud decision for a single transaction. The raw transaction
# fields are intentionally omitted — consumers requiring them must join on
# transaction_id or consume transactions.raw directly.
# ---------------------------------------------------------------------------

class TransactionScoredEvent(BaseEvent):
    """Event published to the transactions.scored topic."""

    event_type: Literal["transaction.scored"] = "transaction.scored"

    transaction_id: str = Field(
        description="Matches transaction_id from the originating TransactionRawEvent.",
    )
    source_event_id: str = Field(
        description="event_id of the TransactionRawEvent that triggered this scoring run. "
                    "Used for end-to-end tracing.",
    )

    # --- Scoring outputs (mirror postgres_logger.py column names exactly) ---
    rule_flag: Literal[0, 1] = Field(
        description="1 if the rule engine flagged this transaction, 0 otherwise.",
    )
    model_prediction: Literal[0, 1] = Field(
        description="1 if the ML model classified this transaction as fraudulent, 0 otherwise.",
    )
    risk_score: Annotated[float, Field(ge=0.0, le=1.0, description="Composite risk score in [0.0, 1.0].")]
    decision: Literal["APPROVE", "REVIEW", "BLOCK"] = Field(
        description="Triage decision produced by triage_decision(). "
                    "APPROVE: risk_score < REVIEW_THRESHOLD. "
                    "REVIEW: REVIEW_THRESHOLD <= risk_score < BLOCK_THRESHOLD. "
                    "BLOCK: risk_score >= BLOCK_THRESHOLD.",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Human-readable reasons for the decision, e.g. ['High transaction amount', 'Model flagged as suspicious']. "
                    "Empty list when decision is APPROVE with no notable signals.",
    )


# ---------------------------------------------------------------------------
# cases.created
#
# Published by: case-creation consumer (part of scoring-service in Phase 2)
# Consumed by:  analyst notification service, dashboard websocket feed (Phase 3+)
#
# EMISSION INVARIANT — enforced by the producer, validated by the type system:
#   MUST emit  : decision is REVIEW or BLOCK
#   MUST NOT emit: decision is APPROVE
#
# The decision field is typed as Literal["REVIEW", "BLOCK"]. Any attempt to
# construct a CaseCreatedEvent with decision="APPROVE" will raise a Pydantic
# ValidationError at the call site — this invariant is not just documented,
# it is structurally impossible to violate without bypassing validation.
# ---------------------------------------------------------------------------

class CaseCreatedEvent(BaseEvent):
    """
    Event published to the cases.created topic.

    ONLY emitted when a transaction scores REVIEW or BLOCK. APPROVE decisions
    MUST NEVER produce this event or a corresponding triage case in Postgres.
    """

    event_type: Literal["case.created"] = "case.created"

    case_id: int = Field(
        description="Primary key of the row inserted into the predictions table.",
    )
    transaction_id: str = Field(
        description="Matches transaction_id from the originating TransactionRawEvent.",
    )
    source_event_id: str = Field(
        description="event_id of the TransactionScoredEvent that triggered case creation. "
                    "Used for end-to-end tracing.",
    )
    decision: Literal["REVIEW", "BLOCK"] = Field(
        description="Must be REVIEW or BLOCK. APPROVE decisions never produce cases.",
    )
    risk_score: Annotated[float, Field(ge=0.0, le=1.0)]
    created_at: datetime = Field(
        description="UTC timestamp when the case row was committed to Postgres.",
    )
