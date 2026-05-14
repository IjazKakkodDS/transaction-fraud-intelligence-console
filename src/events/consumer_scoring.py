"""
Scoring consumer for the transactions.raw topic.

Reads TransactionRawEvent messages from Redpanda, runs the full fraud scoring
pipeline (identical logic to POST /predict), writes the result to Postgres,
and publishes a TransactionScoredEvent to transactions.scored.

This is an independent process — it shares no runtime state with the FastAPI
application. Both the sync (/predict) path and this async path are live
simultaneously during Phase 2. They use the same underlying scoring modules.

Running
-------
From the project root:
    python -m src.events.consumer_scoring

Environment variables required:
    KAFKA_BOOTSTRAP_SERVERS  — e.g. "localhost:9092" (host) or "redpanda:29092" (Docker)
    DATABASE_URL             — same value as the API uses

Design notes
------------
Offset management:
    enable_auto_commit=False. The offset is committed manually after every
    message is fully processed (DB write + Kafka publish). This prevents
    data loss on crash: a message is never marked "done" until its side
    effects are durable. Poison pills (unparseable / invalid messages) are
    logged at ERROR level and committed so the consumer does not stall.

Idempotency:
    The predictions table has no event_id uniqueness constraint yet. If the
    broker redelivers a message (e.g. after a crash between DB write and
    offset commit), a duplicate row will be inserted. This is a known
    limitation for Phase 2. A unique constraint on predictions.event_id is
    required before running at production volume — tracked as a Phase 2
    follow-up migration.

Postgres writes — Phase 2 dual-path behavior (temporary):
    POST /predict scores synchronously AND publishes a TransactionRawEvent to
    transactions.raw. This consumer then picks up that same event and scores
    the transaction a second time, inserting a second predictions row. This
    double-scoring is intentional and expected during Phase 2 while both paths
    coexist. It is not a bug. The synchronous /predict path will be retired in
    a later phase once the async path is the sole scoring entry point.
"""

import json
import logging
import os
import signal
import sys
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from pydantic import ValidationError

from src.config.config import HIGH_AMOUNT_THRESHOLD
from src.db.postgres_logger import log_prediction
from src.events.schemas import CaseCreatedEvent, TransactionRawEvent, TransactionScoredEvent
from src.features.transaction_features import generate_basic_features
from src.models.predict import predict
from src.rules.fraud_rules import apply_fraud_rules
from src.triage.investigator import triage_decision

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("scoring-consumer")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
TOPIC_IN = "transactions.raw"
TOPIC_OUT = "transactions.scored"
TOPIC_CASE = "cases.created"

# Consumer group ID — intentionally hardcoded, not env-configurable.
# Kafka uses this ID to track committed offsets for this consumer group.
# All replicas of this service share the same group so the broker distributes
# partitions across them (horizontal scaling). Changing this value causes the
# consumer to start from the beginning of the topic (or latest, depending on
# auto_offset_reset) because no committed offsets exist for the new group ID.
# Only change this if you intend to replay the topic from scratch.
CONSUMER_GROUP = "scoring-service"

# ---------------------------------------------------------------------------
# Shutdown flag — set by signal handler so the consume loop exits cleanly
# ---------------------------------------------------------------------------

_shutdown_requested = False


def _handle_signal(signum, frame) -> None:
    global _shutdown_requested
    logger.info("Shutdown signal received (%s). Finishing current message then stopping.", signum)
    _shutdown_requested = True


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# ---------------------------------------------------------------------------
# Kafka clients
# ---------------------------------------------------------------------------

def _build_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        TOPIC_IN,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=CONSUMER_GROUP,
        # Start from the beginning of the topic if this consumer group has no
        # committed offset yet (first run). On subsequent runs it resumes from
        # the last committed offset.
        auto_offset_reset="earliest",
        # Manual commit — offsets are committed only after successful processing.
        enable_auto_commit=False,
        # Deserialise bytes → str; json.loads is called explicitly below so
        # that we can catch and log malformed JSON before it reaches Pydantic.
        value_deserializer=lambda b: b.decode("utf-8"),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
        request_timeout_ms=15000,
        # Poll at most one message at a time — keeps the processing loop simple
        # and the commit granularity tight.
        max_poll_records=1,
    )


def _build_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks=1,
        request_timeout_ms=3000,
    )


# ---------------------------------------------------------------------------
# Scoring pipeline
# Reconstructs exactly the same steps as POST /predict in src/api/main.py.
# ---------------------------------------------------------------------------

def _score(raw: TransactionRawEvent) -> TransactionScoredEvent:
    """
    Run the full fraud scoring pipeline on a TransactionRawEvent and return
    a TransactionScoredEvent. Raises on any unexpected pipeline error.
    """
    df = pd.DataFrame([{
        "transaction_id": raw.transaction_id,
        "amount": raw.amount,
        "timestamp": raw.timestamp,
        "payment_method": raw.payment_method,
        "country": raw.country,
        "is_international": raw.is_international,
        "merchant_category": raw.merchant_category,
        "device_id": raw.device_id,
        "device_type": raw.device_type,
    }])

    df = generate_basic_features(df)
    df["model_prediction"] = predict(df)
    df = apply_fraud_rules(df)
    df = triage_decision(df)

    row = df.iloc[0]

    reasons: list[str] = []
    if raw.amount > HIGH_AMOUNT_THRESHOLD:
        reasons.append("High transaction amount")
    if row["is_night_transaction"] == 1:
        reasons.append("Unusual transaction time")
    if int(row["model_prediction"]) == 1:
        reasons.append("Model flagged as suspicious")
    if row.get("is_international", 0) == 1 and row.get("is_high_risk_country", 0) == 1:
        reasons.append("International transaction from elevated-risk region")
    if row.get("is_high_risk_payment_method", 0) == 1:
        reasons.append("High-risk payment method")
    if row.get("is_high_risk_merchant_category", 0) == 1:
        reasons.append("High-risk merchant category")
    if row.get("has_device_id", 1) == 0:
        reasons.append("No device identifier present")

    return TransactionScoredEvent(
        producer=CONSUMER_GROUP,
        source_event_id=raw.event_id,
        transaction_id=raw.transaction_id,
        rule_flag=int(row["rule_flag"]),
        model_prediction=int(row["model_prediction"]),
        risk_score=float(row["risk_score"]),
        decision=row["decision"],
        reasons=reasons,
    )


# ---------------------------------------------------------------------------
# Side effects — DB write and downstream publish
# ---------------------------------------------------------------------------

def _persist(raw: TransactionRawEvent, scored: TransactionScoredEvent) -> int | None:
    """
    Write the scored result to Postgres and return the generated row id.
    The id is used as case_id when emitting a CaseCreatedEvent.

    Return contract:
      int  — row was inserted successfully; value is the new predictions.id.
      None — uq_predictions_event_id constraint fired; raw.event_id already
             exists in the table. The caller MUST treat None as "already
             processed" and skip every downstream side effect (Kafka publish,
             case creation). Do NOT raise on None — it is a normal, expected
             outcome on Kafka message re-delivery.
    """
    return log_prediction({
        # raw.event_id is the stable Kafka message identity — it does not
        # change on redelivery, making it the correct idempotency key.
        "event_id": raw.event_id,
        "transaction_id": raw.transaction_id,
        "amount": raw.amount,
        "timestamp": raw.timestamp,
        "rule_flag": scored.rule_flag,
        "model_prediction": scored.model_prediction,
        "risk_score": scored.risk_score,
        "decision": scored.decision,
        "reasons": "|".join(scored.reasons),
    })


def _publish_case_created(
    producer: KafkaProducer,
    scored: TransactionScoredEvent,
    case_id: int,
    created_at: datetime,
) -> None:
    """
    Publish a CaseCreatedEvent to cases.created.

    MUST only be called when scored.decision is REVIEW or BLOCK.
    The Pydantic schema enforces this — passing APPROVE raises ValidationError.

    Blocks until the broker acknowledges or the request times out (3 s).
    Raises KafkaError on delivery failure — caller decides how to handle.
    """
    event = CaseCreatedEvent(
        producer=CONSUMER_GROUP,
        case_id=case_id,
        transaction_id=scored.transaction_id,
        source_event_id=scored.event_id,
        decision=scored.decision,  # type: ignore[arg-type]  # narrowed by caller guard
        risk_score=scored.risk_score,
        created_at=created_at,
    )
    future = producer.send(
        TOPIC_CASE,
        key=str(case_id),
        value=event.model_dump(mode="json"),
    )
    future.get(timeout=5)
    logger.info(
        "Case event | case_id=%d event_id=%s transaction_id=%s decision=%s topic=%s",
        case_id,
        event.event_id,
        scored.transaction_id,
        scored.decision,
        TOPIC_CASE,
    )


def _publish_scored(producer: KafkaProducer, scored: TransactionScoredEvent) -> None:
    """
    Publish TransactionScoredEvent to transactions.scored.
    Blocks until the broker acknowledges or the request times out (3 s).
    Raises KafkaError on delivery failure — caller decides how to handle.
    """
    future = producer.send(
        TOPIC_OUT,
        key=scored.transaction_id,
        value=scored.model_dump(mode="json"),
    )
    # .get() blocks until the broker acks or request_timeout_ms elapses.
    # This is acceptable here because the consumer has no HTTP latency
    # requirement. A delivery failure raises and is caught by the caller.
    future.get(timeout=5)


# ---------------------------------------------------------------------------
# Per-message processing
# ---------------------------------------------------------------------------

def _process(message, producer: KafkaProducer) -> None:
    """
    Handle one Kafka message end-to-end:
      deserialise → validate → score → persist → publish

    Raises on unrecoverable errors. The caller is responsible for committing
    or skipping the offset based on the outcome.
    """
    raw_value: str = message.value

    # Step 1 — parse JSON
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in message: {exc}") from exc

    # Step 2 — validate against schema
    raw_event = TransactionRawEvent.model_validate(payload)

    logger.info(
        "Consumed | event_id=%s transaction_id=%s partition=%d offset=%d",
        raw_event.event_id,
        raw_event.transaction_id,
        message.partition,
        message.offset,
    )

    # Step 3 — score
    scored_event = _score(raw_event)

    logger.info(
        "Scored   | event_id=%s transaction_id=%s decision=%s risk_score=%.4f",
        raw_event.event_id,
        raw_event.transaction_id,
        scored_event.decision,
        scored_event.risk_score,
    )

    # Step 4 — persist to Postgres; capture the generated row id for case creation.
    # persisted_at is a consumer-side timestamp taken immediately before the DB
    # write. It is an approximation of the actual row insertion time — not the
    # DB server clock. The predictions table has no server-generated created_at
    # column, so the true commit timestamp is not retrievable without a schema
    # migration to add one (e.g. created_at TIMESTAMPTZ DEFAULT NOW()).
    persisted_at = datetime.now(timezone.utc)
    case_id = _persist(raw_event, scored_event)

    if case_id is None:
        # uq_predictions_event_id fired — this raw event was already persisted.
        # The broker redelivered a message whose offset was not committed before
        # the previous crash. Safe to skip all downstream side effects.
        logger.info(
            "Duplicate | event_id=%s transaction_id=%s partition=%d offset=%d"
            " — already persisted, skipping downstream publish",
            raw_event.event_id,
            raw_event.transaction_id,
            message.partition,
            message.offset,
        )
        return

    logger.info(
        "Persisted | event_id=%s transaction_id=%s decision=%s case_id=%d",
        raw_event.event_id,
        raw_event.transaction_id,
        scored_event.decision,
        case_id,
    )

    # Step 5 — publish to transactions.scored
    try:
        _publish_scored(producer, scored_event)
        logger.info(
            "Published | event_id=%s transaction_id=%s topic=%s",
            scored_event.event_id,
            scored_event.transaction_id,
            TOPIC_OUT,
        )
    except KafkaError as exc:
        # The DB row is already committed. Log the publish failure and
        # continue — the scored event is durable in Postgres even if it
        # never reaches transactions.scored. A monitoring alert should fire.
        logger.error(
            "Publish to %s failed — row is in Postgres but downstream "
            "consumers will not see this event | transaction_id=%s error=%s",
            TOPIC_OUT,
            raw_event.transaction_id,
            exc,
        )

    # Step 6 — emit CaseCreatedEvent for REVIEW and BLOCK decisions only.
    # APPROVE decisions are explicitly excluded — this guard is the runtime
    # enforcement of the emission invariant defined in CaseCreatedEvent.
    if scored_event.decision in ("REVIEW", "BLOCK"):
        try:
            _publish_case_created(producer, scored_event, case_id, persisted_at)
        except KafkaError as exc:
            logger.error(
                "Publish to %s failed — case row exists in Postgres but "
                "downstream consumers will not see this event | "
                "case_id=%d transaction_id=%s source_event_id=%s error=%s",
                TOPIC_CASE,
                case_id,
                raw_event.transaction_id,
                scored_event.event_id,
                exc,
            )
    else:
        logger.info(
            "No case event | decision=%s transaction_id=%s event_id=%s — "
            "APPROVE decisions do not emit to %s",
            scored_event.decision,
            raw_event.transaction_id,
            raw_event.event_id,
            TOPIC_CASE,
        )


# ---------------------------------------------------------------------------
# Main consume loop
# ---------------------------------------------------------------------------

def run() -> None:
    logger.info(
        "Starting scoring consumer | "
        "brokers=%s group=%s "
        "topic_in=%s topic_out=%s topic_case=%s",
        BOOTSTRAP_SERVERS, CONSUMER_GROUP,
        TOPIC_IN, TOPIC_OUT, TOPIC_CASE,
    )

    consumer = _build_consumer()
    producer = _build_producer()

    logger.info("Consumer and producer ready. Waiting for messages...")

    try:
        for message in consumer:
            if _shutdown_requested:
                break

            try:
                _process(message, producer)
                consumer.commit()

            except (ValueError, ValidationError) as exc:
                # Poison pill — bad JSON or schema mismatch.
                # Commit the offset to skip it; retrying will not help.
                logger.error(
                    "Skipping invalid message | partition=%d offset=%d error=%s",
                    message.partition, message.offset, exc,
                )
                consumer.commit()

            except Exception as exc:
                # Unexpected error (scoring pipeline failure, DB error, etc.).
                # Commit to skip this message and keep the consumer running.
                # A production system would route this to a dead-letter topic.
                logger.error(
                    "Unexpected error processing message | partition=%d offset=%d error=%s",
                    message.partition, message.offset, exc,
                    exc_info=True,
                )
                consumer.commit()

    finally:
        logger.info("Shutting down — flushing producer and closing consumer...")
        try:
            producer.flush(timeout=5)
            producer.close(timeout=5)
        except Exception as exc:
            logger.warning("Producer shutdown error | error=%s", exc)
        consumer.close()
        logger.info("Scoring consumer stopped.")


if __name__ == "__main__":
    if not BOOTSTRAP_SERVERS:
        logger.error(
            "KAFKA_BOOTSTRAP_SERVERS is not set. "
            "Set it to the broker address before starting the consumer "
            "(e.g. export KAFKA_BOOTSTRAP_SERVERS=localhost:9092). Exiting."
        )
        sys.exit(1)
    run()
