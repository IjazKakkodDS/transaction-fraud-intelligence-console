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


def get_workflow_metrics() -> dict:
    """
    Return observability metrics for the workflow automation layer.

    Queries workflow_events only. Top-level scalars use COALESCE so they
    return 0 rather than NULL on an empty table. Breakdown queries each
    return a list of {key, count} rows for flexible frontend rendering.
    """
    from datetime import datetime, timezone

    with engine.connect() as conn:
        scalars = conn.execute(text("""
            SELECT
                COALESCE(COUNT(*), 0)                                                              AS total_workflow_events,
                COALESCE(SUM(CASE WHEN status = 'SUCCESS'               THEN 1 ELSE 0 END), 0)    AS total_success_events,
                COALESCE(SUM(CASE WHEN status = 'FAILED'                THEN 1 ELSE 0 END), 0)    AS total_failed_events,
                COALESCE(SUM(CASE WHEN source = 'n8n'                   THEN 1 ELSE 0 END), 0)    AS total_n8n_events,
                COALESCE(SUM(CASE WHEN source = 'manual'                THEN 1 ELSE 0 END), 0)    AS total_manual_events,
                COALESCE(SUM(CASE WHEN case_id IS NOT NULL              THEN 1 ELSE 0 END), 0)    AS total_case_specific_events,
                COALESCE(SUM(CASE WHEN case_id IS NULL                  THEN 1 ELSE 0 END), 0)    AS total_global_events,
                COALESCE(SUM(CASE WHEN workflow_action = 'ESCALATE_TO_FRAUD_OPS'
                                                                        THEN 1 ELSE 0 END), 0)    AS total_escalation_events,
                COALESCE(SUM(CASE WHEN workflow_action = 'STALE_CASE_REMINDER'
                                                                        THEN 1 ELSE 0 END), 0)    AS total_stale_reminders,
                COALESCE(SUM(CASE WHEN workflow_action = 'DAILY_FRAUD_OPS_SUMMARY'
                                                                        THEN 1 ELSE 0 END), 0)    AS total_daily_summaries,
                COALESCE(SUM(CASE WHEN workflow_action = 'WORKFLOW_DISPATCH_FAILED'
                                                                        THEN 1 ELSE 0 END), 0)    AS total_dispatch_failures,
                MAX(created_at)                                                                    AS latest_workflow_event_at
            FROM workflow_events
        """)).mappings().first()

        by_action = conn.execute(text("""
            SELECT workflow_action, COUNT(*) AS count
            FROM workflow_events
            GROUP BY workflow_action
            ORDER BY count DESC
        """)).mappings().all()

        by_source = conn.execute(text("""
            SELECT source, COUNT(*) AS count
            FROM workflow_events
            GROUP BY source
            ORDER BY count DESC
        """)).mappings().all()

        by_status = conn.execute(text("""
            SELECT status, COUNT(*) AS count
            FROM workflow_events
            GROUP BY status
            ORDER BY count DESC
        """)).mappings().all()

    latest_at = scalars["latest_workflow_event_at"]

    return {
        "generated_at":                 datetime.now(timezone.utc).isoformat(),
        "total_workflow_events":        int(scalars["total_workflow_events"]),
        "total_success_events":         int(scalars["total_success_events"]),
        "total_failed_events":          int(scalars["total_failed_events"]),
        "total_n8n_events":             int(scalars["total_n8n_events"]),
        "total_manual_events":          int(scalars["total_manual_events"]),
        "total_case_specific_events":   int(scalars["total_case_specific_events"]),
        "total_global_events":          int(scalars["total_global_events"]),
        "total_escalation_events":      int(scalars["total_escalation_events"]),
        "total_stale_reminders":        int(scalars["total_stale_reminders"]),
        "total_daily_summaries":        int(scalars["total_daily_summaries"]),
        "total_dispatch_failures":      int(scalars["total_dispatch_failures"]),
        "latest_workflow_event_at":     latest_at.isoformat() if latest_at is not None else None,
        "events_by_workflow_action":    [{"workflow_action": r["workflow_action"], "count": int(r["count"])} for r in by_action],
        "events_by_source":             [{"source": r["source"], "count": int(r["count"])} for r in by_source],
        "events_by_status":             [{"status": r["status"], "count": int(r["count"])} for r in by_status],
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


# ---------------------------------------------------------------------------
# Public interface — portfolio scans
#
# portfolio_scans and portfolio_scan_results are managed via Alembic migration
# 0006. Raw SQL is used here; the migration is the authoritative schema source.
# Lists and dicts are JSON-serialised before storage and deserialised on read.
# ---------------------------------------------------------------------------

def create_portfolio_scan(record: dict) -> str:
    """
    Insert one row into portfolio_scans and return the scan_id.

    risk_summary is stored as a JSON string when a dict/list is passed.
    All other fields are written as-is; None values are preserved.
    """
    risk_summary = record.get("risk_summary")
    if isinstance(risk_summary, (dict, list)):
        risk_summary = json.dumps(risk_summary)

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO portfolio_scans (
                    scan_id, filename, status,
                    total_rows, valid_rows, invalid_rows, skipped_rows,
                    low_count, medium_count, high_count, critical_count,
                    p0_count, p1_count, p2_count, p3_count,
                    total_amount, critical_amount, high_amount,
                    risk_summary, completed_at, error_message
                ) VALUES (
                    :scan_id, :filename, :status,
                    :total_rows, :valid_rows, :invalid_rows, :skipped_rows,
                    :low_count, :medium_count, :high_count, :critical_count,
                    :p0_count, :p1_count, :p2_count, :p3_count,
                    :total_amount, :critical_amount, :high_amount,
                    :risk_summary, :completed_at, :error_message
                )
            """),
            {
                "scan_id":         record.get("scan_id"),
                "filename":        record.get("filename"),
                "status":          record.get("status", "COMPLETE"),
                "total_rows":      record.get("total_rows", 0),
                "valid_rows":      record.get("valid_rows", 0),
                "invalid_rows":    record.get("invalid_rows", 0),
                "skipped_rows":    record.get("skipped_rows", 0),
                "low_count":       record.get("low_count", 0),
                "medium_count":    record.get("medium_count", 0),
                "high_count":      record.get("high_count", 0),
                "critical_count":  record.get("critical_count", 0),
                "p0_count":        record.get("p0_count", 0),
                "p1_count":        record.get("p1_count", 0),
                "p2_count":        record.get("p2_count", 0),
                "p3_count":        record.get("p3_count", 0),
                "total_amount":    record.get("total_amount", 0),
                "critical_amount": record.get("critical_amount", 0),
                "high_amount":     record.get("high_amount", 0),
                "risk_summary":    risk_summary,
                "completed_at":    record.get("completed_at"),
                "error_message":   record.get("error_message"),
            },
        )

    return record["scan_id"]


def get_portfolio_scan(scan_id: str) -> dict | None:
    """
    Fetch one portfolio_scans row by scan_id.
    Returns a plain dict or None if not found.
    risk_summary is parsed from JSON string back to dict when possible.
    """
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM portfolio_scans WHERE scan_id = :scan_id"),
            {"scan_id": scan_id},
        ).mappings().first()

    if row is None:
        return None

    record = dict(row)
    if record.get("risk_summary"):
        try:
            record["risk_summary"] = json.loads(record["risk_summary"])
        except (json.JSONDecodeError, TypeError):
            pass

    return record


def bulk_insert_scan_results(scan_id: str, rows: list[dict]) -> int:
    """
    Insert many portfolio_scan_results rows for one scan.

    validation_errors is stored as a JSON string when a list/dict is passed.
    Returns the number of rows inserted. Returns 0 without querying if rows
    is empty.
    """
    if not rows:
        return 0

    params = []
    for row in rows:
        validation_errors = row.get("validation_errors")
        if isinstance(validation_errors, (list, dict)):
            validation_errors = json.dumps(validation_errors)

        params.append({
            "scan_id":              scan_id,
            "row_number":           row.get("row_number"),
            "transaction_id":       row.get("transaction_id"),
            "amount":               row.get("amount"),
            "timestamp":            row.get("timestamp"),
            "country":              row.get("country"),
            "payment_method":       row.get("payment_method"),
            "merchant_category":    row.get("merchant_category"),
            "device_id":            row.get("device_id"),
            "rule_flag":            row.get("rule_flag"),
            "model_prediction":     row.get("model_prediction"),
            "risk_score":           row.get("risk_score"),
            "decision":             row.get("decision"),
            "risk_tier":            row.get("risk_tier"),
            "operational_priority": row.get("operational_priority"),
            "reasons":              row.get("reasons"),
            "validation_status":    row.get("validation_status"),
            "validation_errors":    validation_errors,
            "promoted":             row.get("promoted", False),
            "promoted_case_id":     row.get("promoted_case_id"),
            "promoted_at":          row.get("promoted_at"),
        })

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO portfolio_scan_results (
                    scan_id, row_number, transaction_id, amount, timestamp,
                    country, payment_method, merchant_category, device_id,
                    rule_flag, model_prediction, risk_score, decision,
                    risk_tier, operational_priority, reasons,
                    validation_status, validation_errors,
                    promoted, promoted_case_id, promoted_at
                ) VALUES (
                    :scan_id, :row_number, :transaction_id, :amount, :timestamp,
                    :country, :payment_method, :merchant_category, :device_id,
                    :rule_flag, :model_prediction, :risk_score, :decision,
                    :risk_tier, :operational_priority, :reasons,
                    :validation_status, :validation_errors,
                    :promoted, :promoted_case_id, :promoted_at
                )
            """),
            params,
        )

    return len(rows)


def get_scan_results(
    scan_id: str,
    tier: str | None = None,
    decision: str | None = None,
    validation_status: str | None = None,
    promoted: bool | None = None,
) -> list[dict]:
    """
    Fetch portfolio_scan_results rows for one scan with optional filters.

    tier filters on operational_priority (P0/P1/P2/P3).
    decision filters on APPROVE/REVIEW/BLOCK.
    validation_status filters on VALID/INVALID/SKIPPED.
    promoted filters on true/false.

    Results are ordered by risk_score DESC NULLS LAST, then row_number ASC
    so that scored rows surface first and unscored rows follow in upload order.

    validation_errors is parsed from JSON string back to list when possible.
    """
    where_parts = ["scan_id = :scan_id"]
    params: dict = {"scan_id": scan_id}

    if tier is not None:
        where_parts.append("operational_priority = :tier")
        params["tier"] = tier
    if decision is not None:
        where_parts.append("decision = :decision")
        params["decision"] = decision
    if validation_status is not None:
        where_parts.append("validation_status = :validation_status")
        params["validation_status"] = validation_status
    if promoted is not None:
        where_parts.append("promoted = :promoted")
        params["promoted"] = promoted

    sql = text(
        "SELECT * FROM portfolio_scan_results "
        "WHERE " + " AND ".join(where_parts) + " "
        "ORDER BY risk_score DESC NULLS LAST, row_number ASC"
    )

    with engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()

    result = []
    for row in rows:
        record = dict(row)
        if record.get("validation_errors"):
            try:
                record["validation_errors"] = json.loads(record["validation_errors"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(record)

    return result


def get_scan_result_by_id(result_id: int) -> dict | None:
    """
    Fetch one portfolio_scan_results row by primary key id.
    Returns a plain dict or None if not found.
    validation_errors is parsed from JSON string back to list when possible.
    """
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM portfolio_scan_results WHERE id = :result_id"),
            {"result_id": result_id},
        ).mappings().first()

    if row is None:
        return None

    record = dict(row)
    if record.get("validation_errors"):
        try:
            record["validation_errors"] = json.loads(record["validation_errors"])
        except (json.JSONDecodeError, TypeError):
            pass

    return record


def mark_result_promoted(
    result_id: int,
    case_id: int,
    promoted_at: str | None = None,
) -> None:
    """
    Mark a portfolio_scan_results row as promoted after a successful case creation.

    Sets promoted=true, promoted_case_id, and promoted_at.
    promoted_at defaults to the current UTC timestamp when not provided.
    """
    if promoted_at is None:
        from datetime import datetime, timezone
        promoted_at = datetime.now(timezone.utc).isoformat()

    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE portfolio_scan_results
                SET promoted = :promoted,
                    promoted_case_id = :case_id,
                    promoted_at = :promoted_at
                WHERE id = :result_id
            """),
            {
                "result_id":   result_id,
                "promoted":    True,
                "case_id":     case_id,
                "promoted_at": promoted_at,
            },
        )
