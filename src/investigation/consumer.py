"""
Investigation consumer for the cases.investigate topic.

Reads InvestigationRequest messages from Redpanda, delegates to
service.process_case(), and persists the resulting InvestigationReport
to Postgres via log_investigation().

Running
-------
From the project root:
    python -m src.investigation.consumer

Environment variables required:
    KAFKA_BOOTSTRAP_SERVERS  — e.g. "localhost:9092" (host) or "redpanda:29092" (Docker)
    DATABASE_URL             — same value as the API and scoring consumer use

Offset management
-----------------
enable_auto_commit=False. Offsets are committed selectively based on error type:

  Poison pills (malformed JSON, schema validation failure):
    The offset IS committed and the message is skipped. These messages are
    structurally unprocessable — retrying will never succeed.

  Unexpected errors (Postgres failure, pipeline error, LLM timeout, etc.):
    The offset is NOT committed. The error is logged and the consumer
    continues to the next poll. The broker will redeliver the message on
    the next run, allowing a transient failure to be retried.

Consumer group
--------------
CONSUMER_GROUP = "investigation-service"
All replicas share this group so the broker distributes partitions across them.
Change only if intentionally replaying the topic from the beginning.
"""

import json
import logging
import os
import signal
import sys

from dotenv import load_dotenv
from kafka import KafkaConsumer
from pydantic import ValidationError

from src.db.postgres_logger import log_investigation
from src.investigation.schemas import InvestigationRequest
from src.investigation.service import process_case

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("investigation-consumer")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
TOPIC_IN          = "cases.investigate"
CONSUMER_GROUP    = "investigation-service"

# ---------------------------------------------------------------------------
# Shutdown flag
# ---------------------------------------------------------------------------

_shutdown_requested = False


def _handle_signal(signum, frame) -> None:
    global _shutdown_requested
    logger.info("Shutdown signal received (%s). Finishing current message then stopping.", signum)
    _shutdown_requested = True


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)

# ---------------------------------------------------------------------------
# Kafka client
# ---------------------------------------------------------------------------

def _build_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        TOPIC_IN,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=CONSUMER_GROUP,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda b: b.decode("utf-8"),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
        request_timeout_ms=15000,
        max_poll_records=1,
    )

# ---------------------------------------------------------------------------
# Per-message processing
# ---------------------------------------------------------------------------

def _process(message) -> None:
    """
    Handle one Kafka message end-to-end:
      deserialise → validate → process_case → log_investigation

    Raises on any error. The caller is responsible for deciding whether to
    commit the offset (poison pill) or leave it uncommitted (retryable error).
    The offset is never committed until log_investigation() returns successfully.
    """
    raw_value: str = message.value

    # Step 1 — parse JSON
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON in message: {exc}") from exc

    # Step 2 — validate against schema
    request = InvestigationRequest.model_validate(payload)

    logger.info(
        "Consumed | investigation_id=%s case_id=%d partition=%d offset=%d",
        request.investigation_id,
        request.case_id,
        message.partition,
        message.offset,
    )

    # Step 3 — run investigation pipeline
    report = process_case(request)

    # Step 4 — persist report to Postgres
    row_id = log_investigation(report)

    logger.info(
        "Persisted | investigation_id=%s case_id=%d status=%s db_id=%d",
        report.investigation_id,
        report.case_id,
        report.status,
        row_id,
    )

# ---------------------------------------------------------------------------
# Main consume loop
# ---------------------------------------------------------------------------

def run() -> None:
    logger.info(
        "Starting investigation consumer | brokers=%s group=%s topic_in=%s",
        BOOTSTRAP_SERVERS,
        CONSUMER_GROUP,
        TOPIC_IN,
    )

    consumer = _build_consumer()
    logger.info("Consumer ready. Waiting for messages...")

    try:
        for message in consumer:
            if _shutdown_requested:
                break

            try:
                _process(message)
                consumer.commit()

            except (ValueError, ValidationError) as exc:
                # Poison pill — bad JSON or schema mismatch.
                # Commit the offset to skip permanently; retrying will not help.
                logger.error(
                    "Skipping invalid message | partition=%d offset=%d error=%s",
                    message.partition,
                    message.offset,
                    exc,
                )
                consumer.commit()

            except Exception as exc:
                # Unexpected error (Postgres failure, pipeline error, LLM timeout, etc.).
                # Do NOT commit the offset — leave the message available for redelivery
                # so a transient failure can be retried on the next consumer run.
                logger.error(
                    "Processing error — offset not committed, message will be retried"
                    " | partition=%d offset=%d error=%s",
                    message.partition,
                    message.offset,
                    exc,
                    exc_info=True,
                )

    finally:
        logger.info("Shutting down — closing consumer...")
        consumer.close()
        logger.info("Investigation consumer stopped.")


if __name__ == "__main__":
    if not BOOTSTRAP_SERVERS:
        logger.error(
            "KAFKA_BOOTSTRAP_SERVERS is not set. "
            "Set it to the broker address before starting the consumer "
            "(e.g. export KAFKA_BOOTSTRAP_SERVERS=localhost:9092). Exiting."
        )
        sys.exit(1)
    run()
