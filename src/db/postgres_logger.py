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
# Public interface
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
