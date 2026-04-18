# Real-Time Fraud Triage System

A production-grade ML system for real-time fraud detection and triage, combining rule-based heuristics with a trained classifier. Phase 2 adds an event-driven backbone (Redpanda/Kafka) so scoring can run asynchronously and downstream systems can react to outcomes without polling.

---

## Architecture — Phase 2

```
┌──────────────┐   POST /predict    ┌─────────────────┐
│   API Client │ ─────────────────► │   FastAPI (api)  │
└──────────────┘                    └────────┬────────┘
                                             │  1. Score synchronously
                                             │  2. Persist to Postgres
                                             │  3. Publish TransactionRawEvent
                                             ▼
                                    ┌─────────────────┐
                                    │ transactions.raw │  (Redpanda topic)
                                    └────────┬────────┘
                                             │ consumed by
                                             ▼
                                    ┌──────────────────────┐
                                    │  scoring-consumer     │
                                    │  (consumer_scoring.py)│
                                    └──────┬───────────────┘
                                           │  1. Score (same pipeline)
                                           │  2. Persist to Postgres
                                           │  3. Publish TransactionScoredEvent
                                           │  4. Publish CaseCreatedEvent (REVIEW/BLOCK only)
                              ┌────────────┴────────────┐
                              ▼                         ▼
                   ┌──────────────────┐     ┌──────────────────┐
                   │transactions.scored│     │  cases.created   │
                   └──────────────────┘     └──────────────────┘
```

**Phase 2 dual-path note:** `POST /predict` scores synchronously *and* publishes to `transactions.raw`. The consumer re-scores the same transaction from the topic. Both paths write to Postgres independently, so each transaction produces two prediction rows during Phase 2. This is expected. The synchronous path will be retired in a later phase once the async path is the sole scoring entry point.

---

## Topics

| Topic | Partitions | Producer | Consumers | Purpose |
|---|---|---|---|---|
| `transactions.raw` | 3 | `api` (via `/predict`) | `scoring-consumer` | Raw transaction events awaiting scoring |
| `transactions.scored` | 3 | `scoring-consumer` | Downstream analytics | Scored events with decision + risk fields |
| `cases.created` | 1 | `scoring-consumer` | Case management systems | One event per REVIEW or BLOCK decision |

**Emission invariant:** `cases.created` only receives events when `decision` is `REVIEW` or `BLOCK`. `APPROVE` decisions are structurally excluded — `CaseCreatedEvent.decision: Literal["REVIEW", "BLOCK"]` raises `ValidationError` if `APPROVE` is passed, and a runtime guard in the consumer enforces this before construction.

---

## Event Schemas

All events share a `BaseEvent` envelope:

| Field | Type | Description |
|---|---|---|
| `event_id` | `str` (UUID4) | Unique event identifier |
| `event_type` | `Literal[...]` | One of `transaction.raw`, `transaction.scored`, `case.created` |
| `event_version` | `str` | Schema version, e.g. `"1.0"` |
| `occurred_at` | `datetime` | UTC timestamp at event creation |
| `producer` | `str` | Service that created the event (`"api"` or `"scoring-service"`) |

Schemas are defined in `src/events/schemas.py` with `model_config = {"extra": "ignore"}` so consumers tolerate new producer fields without breaking.

---

## Runtime Services

| Service | Image | Port | Role |
|---|---|---|---|
| `api` | project Dockerfile | 8000 | FastAPI — scoring endpoint, review queue, stats |
| `postgres` | postgres:16-alpine | 5432 | Primary store for scored predictions |
| `redis` | redis:7-alpine | 6379 | Cache layer (Phase 3+) |
| `redpanda` | redpandadata/redpanda:v24.1.1 | 9092 (ext), 29092 (int) | Kafka-compatible event broker |
| `redpanda-init` | redpandadata/redpanda:v24.1.1 | — | One-shot topic bootstrap (exits after creation) |
| `scoring-consumer` | project Dockerfile | — | Async scoring worker — reads `transactions.raw`, writes Postgres + publishes downstream events |
| `redpanda-console` | redpandadata/console:v2.4.3 | 8080 | Browser UI for topic inspection (dev profile only) |

**Consumer group:** `scoring-service`. Kafka tracks committed offsets per group. All replicas of `scoring-consumer` share this group ID so the broker distributes partitions across them for horizontal scaling.

**Offset management:** `enable_auto_commit=False`. The consumer commits offsets only after the DB write and both Kafka publishes complete. This prevents data loss on crash — a message is never marked done until its side effects are durable.

---

## Quick Start

### Prerequisites

- Docker Desktop running
- `.env` file with correct values (copy from `.env.example`)

```bash
cp .env.example .env
```

Key `.env` values:

```
DATABASE_URL=postgresql://fraud_user:fraud_pass@postgres:5432/fraud_db
KAFKA_BOOTSTRAP_SERVERS=redpanda:29092
```

### Start the full stack

```bash
docker compose up --build -d
```

Check all services are healthy:

```bash
docker compose ps
```

### Optional: browser topic UI

```bash
docker compose --profile dev up --build -d
# open http://localhost:8080
```

### Run migrations (first run or after schema changes)

```bash
docker compose run --rm api alembic upgrade head
```

### Stop the stack

```bash
docker compose down        # stop and remove containers
docker compose down -v     # also remove all named volumes (wipes Postgres + Redpanda data)
```

---

## Verify the Event Pipeline

The system runs in **async-only mode** (`SYNC_SCORING_ENABLED=false`). `POST /predict` returns HTTP 202 immediately; `scoring-consumer` scores and persists the result. Poll `GET /predictions/{transaction_id}` for the outcome.

### BLOCK example

```bash
# 1. Submit — returns HTTP 202 Accepted
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn_verify_block_001",
    "user_id": "usr_001", "merchant_id": "mrc_001",
    "amount": 1500.00, "currency": "USD",
    "payment_method": "credit_card",
    "timestamp": "2024-03-15T02:00:00Z",
    "country": "US", "is_international": false
  }' | python -m json.tool
# expected: {"status": "accepted", "transaction_id": "txn_verify_block_001"}

# 2. Poll until the consumer has scored (usually < 2 s; retry if 404)
curl -s http://localhost:8000/predictions/txn_verify_block_001 | python -m json.tool
# expected: full prediction row with decision=BLOCK

# 3. Verify all three pipeline layers (Postgres + two Kafka topics)
python scripts/verify_event_pipeline.py txn_verify_block_001 \
  --broker localhost:9092 \
  --db postgresql://fraud_user:fraud_pass@localhost:5432/fraud_db
```

Expected result: `ALL CHECKS PASSED (3/3)` with 1 Postgres row (async-only, no duplicate).

### APPROVE example

```bash
# 1. Submit
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn_verify_approve_001",
    "user_id": "usr_001", "merchant_id": "mrc_001",
    "amount": 25.00, "currency": "USD",
    "payment_method": "credit_card",
    "timestamp": "2024-03-15T10:00:00Z",
    "country": "US", "is_international": false
  }' | python -m json.tool

# 2. Poll
curl -s http://localhost:8000/predictions/txn_verify_approve_001 | python -m json.tool

# 3. Verify — Check 3 must show SKIP (no cases.created event for APPROVE)
python scripts/verify_event_pipeline.py txn_verify_approve_001 \
  --broker localhost:9092 \
  --db postgresql://fraud_user:fraud_pass@localhost:5432/fraud_db
```

> See `docs/phase_2_verification_guide.md` for full expected output, failure modes, and timeout tuning.

---

## Project Structure

```
real-time-fraud-triage-system/
├── src/
│   ├── api/            # FastAPI application — /predict, /review-queue, /stats
│   ├── config/         # Shared config (HIGH_AMOUNT_THRESHOLD, etc.)
│   ├── db/             # Postgres persistence layer (SQLAlchemy)
│   ├── events/
│   │   ├── schemas.py          # Pydantic v2 event schemas
│   │   ├── producer.py         # Fire-and-forget publisher for transactions.raw
│   │   └── consumer_scoring.py # Async scoring worker
│   ├── features/       # Feature engineering
│   ├── models/         # Model training and inference
│   ├── rules/          # Rule-based fraud detection
│   └── triage/         # Decision logic (APPROVE / REVIEW / BLOCK)
├── alembic/            # Database migrations
├── scripts/
│   └── verify_event_pipeline.py  # Pipeline verification utility
├── docs/
│   ├── phase_2_execution_plan.md      # Phase 2 planning and step breakdown
│   └── phase_2_verification_guide.md  # Verification walkthrough and failure modes
├── infra/postgres/     # Postgres bootstrap SQL
├── tests/              # Unit and integration tests
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Local Development (without Docker)

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# SQLite fallback — no Kafka, no Postgres required
uvicorn src.api.main:app --reload
```

Tests:

```bash
pytest tests/
```

---

## Known Limitations and Next Improvements

| # | Limitation | Resolution |
|---|---|---|
| 1 | **Dual-path duplicate rows** — `/predict` and `scoring-consumer` both write a Postgres row for the same transaction | Retire the synchronous scoring path in `/predict`; make the consumer the sole scorer |
| 2 | **No idempotency on re-delivery** — if the consumer crashes between DB write and offset commit, a redelivered message produces a duplicate row | Add a `UNIQUE` constraint on `predictions.event_id`; upsert on conflict |
| 3 | **No dead-letter topic** — poison pills are logged and skipped; failed messages are not recoverable | Route unprocessable messages to a `transactions.dead-letter` topic |
| 4 | **`persisted_at` is a consumer clock approximation** — `predictions` has no `created_at` column with a server-side default | Add `created_at TIMESTAMPTZ DEFAULT NOW()` via Alembic migration |
| 5 | **Single Redpanda node** — no replication, no fault tolerance | Multi-node cluster for production; increase `--replicas` on topic creation |
| 6 | **`cases.created` has 1 partition** — limits throughput for case fan-out | Increase partitions when case volume warrants it |
