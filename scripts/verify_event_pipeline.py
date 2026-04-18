#!/usr/bin/env python3
"""
Event pipeline verification utility.

Checks that a scored transaction is consistent across three layers:
  1. Postgres predictions table     — row exists with expected fields
  2. transactions.scored topic      — scored event exists
  3. cases.created topic            — case event exists (REVIEW/BLOCK only)
                                      or is correctly absent (APPROVE)

Usage
-----
  # From the project root:
  python scripts/verify_event_pipeline.py <transaction_id>

  # Examples:
  python scripts/verify_event_pipeline.py txn_9f3a2c1b4e7d
  python scripts/verify_event_pipeline.py txn_9f3a2c1b4e7d --broker localhost:9092
  python scripts/verify_event_pipeline.py txn_9f3a2c1b4e7d --timeout 8

Environment variables (read from .env automatically):
  KAFKA_BOOTSTRAP_SERVERS   broker address (default: localhost:9092)
  DATABASE_URL              Postgres or SQLite URL (default: sqlite:///database/fraud.db)

Exit codes
----------
  0 — all applicable checks passed
  1 — one or more checks failed or the transaction was not found

Notes
-----
Kafka reads use an ephemeral consumer group (verify-<random-suffix>) that is
unique per invocation. This ensures the script never advances the committed
offsets of the production 'scoring-service' group — all topic reads here are
purely observational and leave no lasting state on the broker.
"""

import argparse
import json
import os
import sys
import uuid
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration — read from environment, same as the consumer/API
# ---------------------------------------------------------------------------

DEFAULT_BROKER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
DEFAULT_DB_URL = os.getenv("DATABASE_URL", "sqlite:///database/fraud.db")
TOPIC_SCORED = "transactions.scored"
TOPIC_CASE = "cases.created"

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

_PASS = "  PASS"
_FAIL = "  FAIL"
_SKIP = "  SKIP"
_WARN = "  WARN"


def _header(text: str) -> None:
    print(f"\n{text}")
    print("-" * len(text))


def _rule() -> None:
    print("=" * 60)


# ---------------------------------------------------------------------------
# Postgres check
# ---------------------------------------------------------------------------

def _check_postgres(transaction_id: str, db_url: str) -> list[dict[str, Any]]:
    """
    Return all prediction rows for the given transaction_id.
    Uses a direct SQLAlchemy connection — does not import src/.
    """
    from sqlalchemy import create_engine, text

    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
    engine = create_engine(db_url, connect_args=connect_args)
    with engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT id, transaction_id, decision, risk_score, "
                "rule_flag, model_prediction, reasons "
                "FROM predictions WHERE transaction_id = :txn_id "
                "ORDER BY id"
            ),
            {"txn_id": transaction_id},
        )
        return [dict(row._mapping) for row in result]


# ---------------------------------------------------------------------------
# Kafka topic scan
# ---------------------------------------------------------------------------

def _scan_topic(topic: str, transaction_id: str, broker: str, timeout_ms: int) -> list[dict]:
    """
    Consume a topic from the beginning using an ephemeral consumer group and
    return all messages whose 'transaction_id' field matches.

    Uses a random group_id so no committed offsets are created or affected —
    this call is entirely read-only from the broker's perspective.
    """
    from kafka import KafkaConsumer, TopicPartition

    ephemeral_group = f"verify-{uuid.uuid4().hex[:8]}"

    consumer = KafkaConsumer(
        bootstrap_servers=broker,
        group_id=ephemeral_group,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
        # Stop iterating after this many ms with no new messages — this is
        # how we detect "we've consumed everything available".
        consumer_timeout_ms=timeout_ms,
        request_timeout_ms=15000,
    )

    # Assign all partitions explicitly and seek to the beginning so we
    # always scan the full topic regardless of group history.
    consumer.subscribe([topic])
    consumer.poll(timeout_ms=1000)  # trigger partition assignment
    consumer.seek_to_beginning()

    matches = []
    try:
        for msg in consumer:
            try:
                payload = msg.value
                if isinstance(payload, dict) and payload.get("transaction_id") == transaction_id:
                    matches.append(payload)
            except Exception:
                pass
    finally:
        consumer.close()

    return matches


# ---------------------------------------------------------------------------
# Verification logic
# ---------------------------------------------------------------------------

def _verify(transaction_id: str, broker: str, db_url: str, timeout_ms: int) -> bool:
    """
    Run all checks for transaction_id. Prints results and returns True if all
    applicable checks pass.
    """
    _rule()
    print(f"Verifying pipeline for transaction_id: {transaction_id}")
    print(f"  broker : {broker}")
    print(f"  db     : {db_url}")
    _rule()

    all_passed = True
    db_decision = None

    # ------------------------------------------------------------------
    # Check 1 — Postgres
    # ------------------------------------------------------------------
    _header(f"[1] Postgres — predictions table")
    rows = _check_postgres(transaction_id, db_url)

    if not rows:
        print(f"{_FAIL}  no row found for transaction_id={transaction_id}")
        print()
        print("Cannot continue — transaction has not been scored yet.")
        print("Send the transaction through /predict or the event-driven path first.")
        _rule()
        return False

    # Use the most recent row if there are duplicates (Phase 2 dual-path)
    row = rows[-1]
    db_decision = row["decision"]

    if len(rows) > 1:
        print(f"{_WARN}  {len(rows)} rows found (Phase 2 dual-path expected — both /predict and consumer wrote a row)")
    else:
        print(f"{_PASS}  1 row found")

    print(f"        id={row['id']}  decision={row['decision']}  "
          f"risk_score={row['risk_score']}  "
          f"rule_flag={row['rule_flag']}  model_prediction={row['model_prediction']}")
    if row.get("reasons"):
        print(f"        reasons: {row['reasons']}")

    # ------------------------------------------------------------------
    # Check 2 — transactions.scored
    # ------------------------------------------------------------------
    _header(f"[2] Kafka — {TOPIC_SCORED}")
    print(f"       scanning topic (timeout={timeout_ms}ms) ...")
    scored_events = _scan_topic(TOPIC_SCORED, transaction_id, broker, timeout_ms)

    if not scored_events:
        print(f"{_FAIL}  no event found in {TOPIC_SCORED}")
        print(f"        Possible causes: consumer has not processed the message yet,")
        print(f"        or KAFKA_BOOTSTRAP_SERVERS is pointing at the wrong broker.")
        all_passed = False
    else:
        ev = scored_events[-1]
        print(f"{_PASS}  {len(scored_events)} event(s) found")
        print(f"        event_id={ev.get('event_id', '?')}  "
              f"decision={ev.get('decision')}  "
              f"risk_score={ev.get('risk_score')}")
        scored_decision = ev.get("decision")
        if scored_decision != db_decision:
            print(f"{_WARN}  decision mismatch: Postgres={db_decision}  Kafka={scored_decision}")

    # ------------------------------------------------------------------
    # Check 3 — cases.created
    # ------------------------------------------------------------------
    _header(f"[3] Kafka — {TOPIC_CASE}")
    print(f"       scanning topic (timeout={timeout_ms}ms) ...")
    case_events = _scan_topic(TOPIC_CASE, transaction_id, broker, timeout_ms)

    if db_decision in ("REVIEW", "BLOCK"):
        print(f"       decision={db_decision} — case event expected")
        if not case_events:
            print(f"{_FAIL}  no event found in {TOPIC_CASE}")
            print(f"        A {db_decision} decision must produce a cases.created event.")
            all_passed = False
        else:
            ev = case_events[-1]
            print(f"{_PASS}  {len(case_events)} event(s) found")
            print(f"        case_id={ev.get('case_id', '?')}  "
                  f"event_id={ev.get('event_id', '?')}  "
                  f"decision={ev.get('decision')}  "
                  f"risk_score={ev.get('risk_score')}")
    else:
        print(f"       decision={db_decision} — no case event expected (APPROVE)")
        if case_events:
            print(f"{_FAIL}  {len(case_events)} unexpected event(s) found in {TOPIC_CASE}")
            print(f"        APPROVE decisions must NOT emit a cases.created event.")
            all_passed = False
        else:
            print(f"{_SKIP}  correctly absent from {TOPIC_CASE}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    _rule()
    checks_total = 3
    checks_passed = sum([
        bool(rows),
        bool(scored_events),
        (case_events and db_decision in ("REVIEW", "BLOCK"))
        or (not case_events and db_decision == "APPROVE"),
    ])
    if all_passed:
        print(f"Result: ALL CHECKS PASSED  ({checks_passed}/{checks_total})")
    else:
        print(f"Result: CHECKS FAILED  ({checks_passed}/{checks_total} passed)")

    if len(rows) > 1:
        print()
        print(f"  NOTE  {len(rows)} Postgres rows exist for this transaction_id.")
        print( "        This is expected in Phase 2 dual-path mode: POST /predict scores")
        print( "        synchronously and the scoring consumer re-scores from transactions.raw,")
        print( "        each writing its own predictions row. This resolves when the sync")
        print( "        /predict scoring path is retired in a later phase.")

    _rule()

    return all_passed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify that a transaction was processed consistently across Postgres and Kafka topics.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "transaction_id",
        help="The transaction_id to look up (e.g. txn_9f3a2c1b4e7d)",
    )
    parser.add_argument(
        "--broker",
        default=DEFAULT_BROKER,
        help=f"Kafka bootstrap server address (default: {DEFAULT_BROKER})",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_URL,
        dest="db_url",
        help="SQLAlchemy database URL (default: from DATABASE_URL env var)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5000,
        metavar="MS",
        help="Kafka consumer poll timeout in milliseconds (default: 5000). "
             "Increase if the broker is slow to respond.",
    )
    args = parser.parse_args()

    passed = _verify(
        transaction_id=args.transaction_id,
        broker=args.broker,
        db_url=args.db_url,
        timeout_ms=args.timeout,
    )
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
