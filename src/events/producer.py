"""
Kafka producer for the transactions.raw topic.

Publishes TransactionRawEvent messages to Redpanda/Kafka after a transaction
is scored via POST /predict. Publishing is fire-and-forget: it runs on the
producer's background I/O thread and never blocks or fails the HTTP response.

Configuration
-------------
KAFKA_BOOTSTRAP_SERVERS — comma-separated broker list, e.g. "redpanda:29092"
                          or "localhost:9092" when running outside Docker.
                          If unset, publishing is disabled and a warning is
                          logged once at startup. The API continues to work.

Producer lifecycle
------------------
A single KafkaProducer instance is created on the first call to
send_transaction_raw_event(). Subsequent calls reuse it. If initialization
fails (broker unreachable at startup), the module disables itself and logs
the error — it does not retry the connection on every call.
"""

import atexit
import json
import logging
import os

from kafka import KafkaProducer
from kafka.errors import KafkaError

from src.events.schemas import TransactionRawEvent

logger = logging.getLogger(__name__)

TOPIC = "transactions.raw"
_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")

# Module-level producer singleton. None means "not yet initialised".
# _disabled=True means initialisation was attempted and failed — no further
# attempts will be made so that every /predict call does not pay a retry cost.
_producer: KafkaProducer | None = None
_disabled: bool = False


def _get_producer() -> KafkaProducer | None:
    """
    Return the singleton KafkaProducer, initialising it on first call.
    Returns None if Kafka is not configured or the connection failed.
    """
    global _producer, _disabled

    if _disabled:
        return None

    if _producer is not None:
        return _producer

    if not _BOOTSTRAP_SERVERS:
        logger.warning(
            "KAFKA_BOOTSTRAP_SERVERS is not set. "
            "Event publishing is disabled. Set the variable to enable it."
        )
        _disabled = True
        return None

    try:
        _producer = KafkaProducer(
            bootstrap_servers=_BOOTSTRAP_SERVERS,
            # Serialise the message key (transaction_id) as UTF-8 bytes.
            key_serializer=lambda k: k.encode("utf-8"),
            # Serialise the message value as a UTF-8-encoded JSON string.
            # model_dump(mode="json") converts datetime/UUID to JSON-safe types.
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            # Ack from the partition leader is sufficient for this use case.
            acks=1,
            # Cap the total time the producer waits for a broker response.
            # Prevents indefinite hangs when the broker is slow or unreachable.
            request_timeout_ms=3000,
        )
        atexit.register(_shutdown)
        logger.info("KafkaProducer initialised | brokers=%s", _BOOTSTRAP_SERVERS)
    except KafkaError as exc:
        logger.error(
            "KafkaProducer initialisation failed — event publishing disabled | error=%s", exc
        )
        _disabled = True

    return _producer


# ---------------------------------------------------------------------------
# Shutdown — registered with atexit after successful producer initialisation.
# Flushes buffered messages and closes the connection before the process exits.
# Safe to call if the producer was never initialised (_producer is None).
# ---------------------------------------------------------------------------

def _shutdown() -> None:
    global _producer
    if _producer is None:
        return
    try:
        _producer.flush(timeout=5)
        _producer.close(timeout=5)
        logger.info("KafkaProducer flushed and closed on shutdown.")
    except Exception as exc:
        logger.warning("KafkaProducer shutdown encountered an error | error=%s", exc)


# ---------------------------------------------------------------------------
# Callbacks — invoked on the producer background I/O thread, not the request
# thread. Must not raise; only log.
# ---------------------------------------------------------------------------

def _on_success(metadata, *, event_id: str, transaction_id: str) -> None:
    logger.info(
        "Published transaction.raw | event_id=%s transaction_id=%s "
        "topic=%s partition=%d offset=%d",
        event_id,
        transaction_id,
        metadata.topic,
        metadata.partition,
        metadata.offset,
    )


def _on_error(exc: Exception, *, event_id: str, transaction_id: str) -> None:
    logger.error(
        "Failed to publish transaction.raw | event_id=%s transaction_id=%s error=%s",
        event_id,
        transaction_id,
        exc,
    )


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def send_transaction_raw_event(event: TransactionRawEvent) -> None:
    """
    Publish a TransactionRawEvent to the transactions.raw topic.

    Fire-and-forget: returns immediately. Delivery confirmation and errors are
    handled asynchronously via callbacks logged at INFO/ERROR level.

    Does nothing (logs a debug message) if Kafka is not configured or
    the producer failed to initialise — the caller is never affected.

    The transaction_id is used as the Kafka message key, routing all events
    for the same transaction to the same partition (ordering guarantee).
    """
    producer = _get_producer()
    if producer is None:
        logger.debug(
            "Skipping transaction.raw publish — producer unavailable | event_id=%s",
            event.event_id,
        )
        return

    producer.send(
        TOPIC,
        key=event.transaction_id,
        value=event.model_dump(mode="json"),
    ).add_callback(
        _on_success,
        event_id=event.event_id,
        transaction_id=event.transaction_id,
    ).add_errback(
        _on_error,
        event_id=event.event_id,
        transaction_id=event.transaction_id,
    )
