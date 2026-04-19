"""
Postgres persistence layer for the fraud triage system.

Exposes the same function signatures as src/monitoring/logger.py so that
src/api/main.py only needs its import line changed — no other logic moves.

Two additional functions cover the inline SQLite queries in main.py:
  - get_stats()               → powers GET /stats
  - get_review_queue_filtered() → powers GET /review-queue

DATABASE_URL is read from the environment.
Defaults to the local SQLite file so the system works without Docker.
"""

import json
import os

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    select,
    text,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

load_dotenv()

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database/fraud.db")

# StaticPool + check_same_thread=False are SQLite-only requirements.
# They are harmless when the URL points at Postgres.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    poolclass=StaticPool if DATABASE_URL.startswith("sqlite") else None,
)

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

metadata = MetaData()

predictions = Table(
    "predictions",
    metadata,
    # Primary key — SERIAL in Postgres, AUTOINCREMENT in SQLite
    Column("id", Integer, primary_key=True, autoincrement=True),
    # Idempotency key — stores the event_id of the TransactionRawEvent that
    # triggered this scoring run. The UNIQUE constraint prevents the consumer
    # from inserting a duplicate row if the same Kafka message is redelivered.
    # NULL is allowed: rows inserted by the synchronous /predict path have no
    # originating event, and SQL treats NULL != NULL so multiple NULLs never
    # conflict.
    Column("event_id", String(64), nullable=True),
    # Transaction identity
    Column("transaction_id", String(64)),
    # NUMERIC(12, 4) avoids floating-point imprecision for financial amounts.
    # SQLAlchemy maps this to REAL on SQLite (which has no NUMERIC type),
    # so both backends behave correctly.
    Column("amount", Numeric(12, 4)),
    Column("timestamp", String(32)),
    # Scoring outputs
    Column("rule_flag", SmallInteger),           # 0 or 1
    Column("model_prediction", SmallInteger),    # 0 or 1
    Column("risk_score", Numeric(6, 4)),          # 0.0000 – 1.0000
    Column("decision", String(10)),              # APPROVE / REVIEW / BLOCK
    Column("reasons", Text),                     # pipe-delimited, e.g. "High amount|Night tx"
    # Analyst review fields — all nullable
    Column("analyst_status", String(20)),        # CONFIRMED_FRAUD / FALSE_POSITIVE / APPROVED
    Column("analyst_notes", Text),
    Column("reviewed_at", String(32)),           # ISO-8601 string
    UniqueConstraint("event_id", name="uq_predictions_event_id"),
)

# Create the table if it does not already exist.
# Alembic is the authoritative migration path; this call is a convenience
# fallback for local SQLite use and fresh test environments.
metadata.create_all(engine)


# ---------------------------------------------------------------------------
# Public interface — predictions
# ---------------------------------------------------------------------------

def log_prediction(record: dict) -> int | None:
    """
    Insert a new scored transaction record and return the generated primary key.

    Expected keys: transaction_id, amount, timestamp, rule_flag,
                   model_prediction, risk_score, decision, reasons.
    Optional key:  event_id — idempotency key (raw Kafka event_id). When
                   provided, a duplicate event_id causes no insert and returns
                   None instead of raising. Callers should treat None as
                   "already processed".

    Returns the auto-generated row id (SERIAL in Postgres, AUTOINCREMENT in
    SQLite), or None if the event_id already exists (duplicate detected).
    """
    try:
        with engine.begin() as conn:
            result = conn.execute(
                predictions.insert().values(
                    event_id=record.get("event_id"),
                    transaction_id=record.get("transaction_id"),
                    amount=record.get("amount"),
                    timestamp=record.get("timestamp"),
                    rule_flag=record.get("rule_flag"),
                    model_prediction=record.get("model_prediction"),
                    risk_score=record.get("risk_score"),
                    decision=record.get("decision"),
                    reasons=record.get("reasons"),
                )
            )
        return result.inserted_primary_key[0]
    except IntegrityError:
        return None


def get_prediction_by_id(prediction_id: int) -> dict | None:
    """
    Fetch a single prediction row by primary key.
    Returns a plain dict or None if not found.
    """
    with engine.connect() as conn:
        row = conn.execute(
            select(predictions).where(predictions.c.id == prediction_id)
        ).mappings().first()

    return dict(row) if row else None


def get_prediction_by_transaction_id(transaction_id: str) -> dict | None:
    """
    Fetch the most recent prediction row for a given transaction_id.
    Returns the latest row by primary key, or None if not yet scored.

    Used by GET /predictions/{transaction_id} to let clients poll for the
    scored result after submitting via POST /predict in async-only mode.
    """
    with engine.connect() as conn:
        row = conn.execute(
            select(predictions)
            .where(predictions.c.transaction_id == transaction_id)
            .order_by(predictions.c.id.desc())
            .limit(1)
        ).mappings().first()

    return dict(row) if row else None


def update_review(
    prediction_id: int,
    analyst_status: str,
    analyst_notes: str | None,
    reviewed_at: str,
) -> None:
    """
    Write an analyst verdict onto an existing prediction row.
    """
    with engine.begin() as conn:
        conn.execute(
            update(predictions)
            .where(predictions.c.id == prediction_id)
            .values(
                analyst_status=analyst_status,
                analyst_notes=analyst_notes,
                reviewed_at=reviewed_at,
            )
        )


def get_review_queue_filtered(analyst_status: str | None = None) -> list[dict]:
    """
    Return all REVIEW and BLOCK cases, optionally filtered by analyst_status.

    Mirrors the inline SQLite queries in src/api/main.py /review-queue.

    analyst_status values:
      None             → all REVIEW/BLOCK cases regardless of analyst action
      "UNREVIEWED"     → REVIEW/BLOCK cases where analyst_status IS NULL
      anything else    → REVIEW/BLOCK cases matching that analyst_status value
    """
    stmt = select(
        predictions.c.id,
        predictions.c.transaction_id,
        predictions.c.amount,
        predictions.c.timestamp,
        predictions.c.rule_flag,
        predictions.c.model_prediction,
        predictions.c.risk_score,
        predictions.c.decision,
        predictions.c.reasons,
        predictions.c.analyst_status,
        predictions.c.analyst_notes,
        predictions.c.reviewed_at,
    ).where(predictions.c.decision.in_(["REVIEW", "BLOCK"]))

    if analyst_status == "UNREVIEWED":
        stmt = stmt.where(predictions.c.analyst_status.is_(None))
    elif analyst_status is not None:
        stmt = stmt.where(predictions.c.analyst_status == analyst_status)

    with engine.connect() as conn:
        rows = conn.execute(stmt).mappings().all()

    return [dict(row) for row in rows]


def get_stats() -> dict:
    """
    Return aggregate counts for the GET /stats endpoint.

    Mirrors the inline SQLite queries in src/api/main.py /stats.
    Each count is a single SELECT COUNT(*) query — no full table scans.
    """
    def _count(where_clause=None) -> int:
        stmt = select(func.count()).select_from(predictions)
        if where_clause is not None:
            stmt = stmt.where(where_clause)
        with engine.connect() as conn:
            return conn.execute(stmt).scalar()

    return {
        "total_transactions":     _count(),
        "total_flagged_by_rules": _count(predictions.c.rule_flag == 1),
        "total_flagged_by_model": _count(predictions.c.model_prediction == 1),
        "total_review":           _count(predictions.c.decision == "REVIEW"),
        "total_approved":         _count(predictions.c.decision == "APPROVE"),
    }


# ---------------------------------------------------------------------------
# Public interface — investigations
#
# The investigations table schema is managed via Alembic migration.
# This function uses raw SQL so no SQLAlchemy Table definition is required
# here — the migration is the authoritative schema source.
# Lists and dicts are serialised to JSON strings before storage.
# ---------------------------------------------------------------------------

def get_latest_investigation(case_id: int) -> dict | None:
    """
    Fetch the most recent investigation row for a given case_id.
    Returns the latest row by primary key, or None if no investigation exists.

    Used by GET /cases/{case_id}/investigation to let analysts poll for the
    investigation result after triggering via POST /cases/{case_id}/investigate.
    """
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT * FROM investigations "
                "WHERE case_id = :case_id "
                "ORDER BY id DESC "
                "LIMIT 1"
            ),
            {"case_id": case_id},
        ).mappings().first()

    return dict(row) if row else None


def log_investigation(report) -> int:
    """
    Insert an InvestigationReport into the investigations table and return
    the generated primary key.

    Accepts an InvestigationReport instance. Lists and dicts are JSON-encoded
    before storage. Enum fields are stored as their string values.

    Uses RETURNING id — Postgres only (Phase 3 runs exclusively on Postgres).
    """
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO investigations (
                    investigation_id,
                    case_id,
                    agent_version,
                    investigated_at,
                    status,
                    transaction_count_30d,
                    amount_percentile,
                    merchant_seen_before,
                    rules_triggered,
                    feature_breakdown,
                    summary,
                    risk_factors,
                    mitigating_factors,
                    recommendation,
                    recommendation_rationale,
                    confidence,
                    confidence_rationale,
                    playbooks_referenced,
                    policies_referenced,
                    error_message
                ) VALUES (
                    :investigation_id,
                    :case_id,
                    :agent_version,
                    :investigated_at,
                    :status,
                    :transaction_count_30d,
                    :amount_percentile,
                    :merchant_seen_before,
                    :rules_triggered,
                    :feature_breakdown,
                    :summary,
                    :risk_factors,
                    :mitigating_factors,
                    :recommendation,
                    :recommendation_rationale,
                    :confidence,
                    :confidence_rationale,
                    :playbooks_referenced,
                    :policies_referenced,
                    :error_message
                ) RETURNING id
            """),
            {
                "investigation_id":        report.investigation_id,
                "case_id":                 report.case_id,
                "agent_version":           report.agent_version,
                "investigated_at":         report.investigated_at.isoformat(),
                "status":                  report.status.value,
                "transaction_count_30d":   report.transaction_count_30d,
                "amount_percentile":       report.amount_percentile,
                "merchant_seen_before":    report.merchant_seen_before,
                "rules_triggered":         json.dumps(report.rules_triggered),
                "feature_breakdown":       json.dumps(report.feature_breakdown),
                "summary":                 report.summary,
                "risk_factors":            json.dumps(report.risk_factors),
                "mitigating_factors":      json.dumps(report.mitigating_factors),
                "recommendation":          report.recommendation.value if report.recommendation else None,
                "recommendation_rationale": report.recommendation_rationale,
                "confidence":              report.confidence.value if report.confidence else None,
                "confidence_rationale":    report.confidence_rationale,
                "playbooks_referenced":    json.dumps(report.playbooks_referenced),
                "policies_referenced":     json.dumps(report.policies_referenced),
                "error_message":           report.error_message,
            },
        ).fetchone()

    return row[0]


# ---------------------------------------------------------------------------
# Public interface — workflow events
#
# The workflow_events table schema is managed via Alembic migration 0004.
# Raw SQL is used here so no additional SQLAlchemy Table definition is needed.
# ---------------------------------------------------------------------------

def log_workflow_event(event: dict) -> dict:
    """
    Insert a workflow audit event and return the inserted row as a dict.

    Expected keys: case_id, workflow_name, workflow_action, status,
                   escalation_priority, message, payload, source.
    The payload value (if provided) must be a JSON-serialisable dict;
    it is stored as a TEXT column containing the JSON string.
    """
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO workflow_events (
                    case_id,
                    workflow_name,
                    workflow_action,
                    status,
                    escalation_priority,
                    message,
                    payload,
                    source
                ) VALUES (
                    :case_id,
                    :workflow_name,
                    :workflow_action,
                    :status,
                    :escalation_priority,
                    :message,
                    :payload,
                    :source
                ) RETURNING id, case_id, workflow_name, workflow_action,
                            status, escalation_priority, message, payload,
                            source, created_at
            """),
            {
                "case_id":             event.get("case_id"),
                "workflow_name":       event.get("workflow_name"),
                "workflow_action":     event.get("workflow_action"),
                "status":              event.get("status", "SUCCESS"),
                "escalation_priority": event.get("escalation_priority"),
                "message":             event.get("message"),
                "payload":             json.dumps(event["payload"]) if event.get("payload") else None,
                "source":              event.get("source", "n8n"),
            },
        ).fetchone()

    result = dict(row._mapping)
    if result.get("created_at") is not None:
        result["created_at"] = result["created_at"].isoformat()
    return result


def get_stale_cases(minutes: int = 120) -> list[dict]:
    """
    Return unreviewed REVIEW/BLOCK cases whose transaction timestamp is older
    than the given number of minutes.

    The predictions.timestamp column is stored as an ISO-8601 text string
    (e.g. "2024-03-15T14:32:07Z"). Postgres can cast this directly to
    TIMESTAMPTZ, allowing a clean age comparison against NOW().

    Returns up to 100 rows ordered newest-first by primary key.
    """
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id,
                       transaction_id,
                       amount,
                       "timestamp",
                       risk_score,
                       decision,
                       reasons,
                       analyst_status
                FROM predictions
                WHERE decision IN ('REVIEW', 'BLOCK')
                  AND (analyst_status IS NULL OR analyst_status = '')
                  AND "timestamp"::TIMESTAMPTZ < NOW() - make_interval(mins => :minutes)
                ORDER BY id DESC
                LIMIT 100
            """),
            {"minutes": minutes},
        ).mappings().all()

    return [dict(row) for row in rows]


def get_daily_fraud_summary() -> dict:
    """
    Return an operational summary covering all-time case volume, decision
    distribution, analyst review status, and workflow automation events.

    All counts use COALESCE so they return 0 rather than NULL when no rows
    match. Both tables are queried in a single connection to avoid partial reads.
    """
    from datetime import datetime, timezone

    with engine.connect() as conn:
        pred = conn.execute(text("""
            SELECT
                COALESCE(COUNT(*), 0)                                                    AS total_cases,
                COALESCE(SUM(CASE WHEN decision = 'REVIEW'  THEN 1 ELSE 0 END), 0)      AS total_review,
                COALESCE(SUM(CASE WHEN decision = 'BLOCK'   THEN 1 ELSE 0 END), 0)      AS total_block,
                COALESCE(SUM(CASE WHEN decision = 'APPROVE' THEN 1 ELSE 0 END), 0)      AS total_approve,
                COALESCE(SUM(CASE WHEN analyst_status IS NULL
                                    OR analyst_status = ''  THEN 1 ELSE 0 END), 0)      AS unreviewed_cases,
                COALESCE(SUM(CASE WHEN analyst_status = 'CONFIRMED_FRAUD'
                                                            THEN 1 ELSE 0 END), 0)      AS confirmed_fraud,
                COALESCE(SUM(CASE WHEN analyst_status = 'FALSE_POSITIVE'
                                                            THEN 1 ELSE 0 END), 0)      AS false_positive,
                ROUND(CAST(AVG(risk_score) AS NUMERIC), 4)                               AS average_risk_score
            FROM predictions
        """)).mappings().first()

        wf = conn.execute(text("""
            SELECT
                COALESCE(COUNT(*), 0)                                                         AS total_workflow_events,
                COALESCE(SUM(CASE WHEN workflow_action = 'ESCALATE_TO_FRAUD_OPS'
                                  THEN 1 ELSE 0 END), 0)                                      AS total_escalation_events,
                COALESCE(SUM(CASE WHEN workflow_action = 'STALE_CASE_REMINDER'
                                  THEN 1 ELSE 0 END), 0)                                      AS total_stale_reminders,
                MAX(created_at)                                                                AS latest_workflow_event_at
            FROM workflow_events
        """)).mappings().first()

    latest_wf_at = wf["latest_workflow_event_at"]

    return {
        "window":                    "all_time_local_demo",
        "generated_at":              datetime.now(timezone.utc).isoformat(),
        "total_cases":               int(pred["total_cases"]),
        "total_review":              int(pred["total_review"]),
        "total_block":               int(pred["total_block"]),
        "total_approve":             int(pred["total_approve"]),
        "unreviewed_cases":          int(pred["unreviewed_cases"]),
        "confirmed_fraud":           int(pred["confirmed_fraud"]),
        "false_positive":            int(pred["false_positive"]),
        "average_risk_score":        float(pred["average_risk_score"]) if pred["average_risk_score"] is not None else 0.0,
        "total_workflow_events":     int(wf["total_workflow_events"]),
        "total_escalation_events":   int(wf["total_escalation_events"]),
        "total_stale_reminders":     int(wf["total_stale_reminders"]),
        "latest_workflow_event_at":  latest_wf_at.isoformat() if latest_wf_at is not None else None,
    }


def get_workflow_events(case_id: int | None = None) -> list[dict]:
    """
    Return workflow audit events, ordered newest first.

    If case_id is provided, filters to events for that case only.
    Otherwise returns the 100 most recent events across all cases.
    """
    if case_id is not None:
        sql = text(
            "SELECT id, case_id, workflow_name, workflow_action, status, "
            "escalation_priority, message, payload, source, created_at "
            "FROM workflow_events "
            "WHERE case_id = :case_id "
            "ORDER BY id DESC"
        )
        params: dict = {"case_id": case_id}
    else:
        sql = text(
            "SELECT id, case_id, workflow_name, workflow_action, status, "
            "escalation_priority, message, payload, source, created_at "
            "FROM workflow_events "
            "ORDER BY id DESC "
            "LIMIT 100"
        )
        params = {}

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()

    result = []
    for row in rows:
        record = dict(row)
        if record.get("created_at") is not None:
            record["created_at"] = record["created_at"].isoformat()
        result.append(record)
    return result
