# Consumer Durability Architecture

**Project:** Real-Time Fraud Intelligence Console
**Phase:** Phase 19B — Consumer Durability Architecture
**Status:** Reference document — read only. No implementation changes in this phase.

---

## 1. Purpose

This document defines the current durability posture of the two event consumers in the Real-Time
Fraud Intelligence Console: the scoring consumer and the investigation consumer. It captures the
offset management strategy, idempotency guarantees, crash-recovery behavior, and failure-type
handling that are implemented as of Phase 19. It also identifies the production gaps that would
need to be addressed before institution-grade deployment in a regulated or shared-infrastructure
environment.

This document does not implement any changes. Dead-letter topics, retry counters, consumer refactors,
Kafka topology changes, database migrations, and alerting infrastructure are all explicitly deferred
— the appropriate controls are designed here for reference and for future implementation phases.

---

## 2. Consumer Inventory

| Consumer | Module | Topic (in) | Topic (out) | Consumer Group |
|---|---|---|---|---|
| Scoring consumer | `src/events/consumer_scoring.py` | `transactions.raw` | `transactions.scored`, `cases.created` | `scoring-service` |
| Investigation consumer | `src/investigation/consumer.py` | `cases.investigate` | _(none — writes to Postgres only)_ | `investigation-service` |

Both consumers run as independent Python processes under `docker compose` with `restart: on-failure`.
Both use `enable_auto_commit=False` and commit offsets manually after each message is fully
processed. Both handle SIGINT and SIGTERM gracefully, finishing the current message before stopping.

---

## 3. Scoring Consumer Durability

### 3.1 Offset management

```
enable_auto_commit=False
max_poll_records=1
```

Offsets are committed manually at three points in the consume loop:

```
Successful processing:  _process() returns normally → consumer.commit()
Poison pill:            ValueError / ValidationError caught → consumer.commit()
Unexpected exception:   Exception caught → consumer.commit()
```

The critical distinction: **all three paths commit the offset**. The scoring consumer never leaves
an offset uncommitted on any handled exception. If `_process()` raises an unexpected error (scoring
pipeline failure, transient DB error), the offset is committed and the message is permanently
skipped. An `ERROR`-level log entry is written, but no retry mechanism exists. The source code
comment at this path explicitly notes: _"A production system would route this to a dead-letter
topic."_

This is an intentional design decision for the local development stack — the consumer stays running
and continues to the next message rather than stalling. For production, see Section 6.

### 3.2 Idempotency

Migration `0002_add_event_id_to_predictions.py` adds a unique constraint on `predictions.event_id`.
`log_prediction()` in `src/db/postgres_logger.py` returns the new row id on success, or `None` if
the `event_id` already exists (uniqueness violation). When `_persist()` returns `None`, `_process()`
returns immediately and all downstream side effects — publishing to `transactions.scored` and
`cases.created` — are skipped.

This guarantees **at-most-once downstream publication per unique event_id**, regardless of how many
times the broker redelivers the same message.

### 3.3 Downstream publish behavior

After the DB write, the scoring consumer publishes to `transactions.scored` and (for REVIEW/BLOCK
decisions) to `cases.created`. Both publishes use `.get(timeout=5)` to wait for broker
acknowledgment. Critically, `KafkaError` exceptions from both publish calls are caught and swallowed
**inside `_process()`** — they do not propagate to the outer consume loop. If either publish fails:

- The error is logged at `ERROR` level.
- Execution continues to the next step.
- `_process()` returns normally.
- `consumer.commit()` executes in the outer loop.

Consequence: the DB row is durable, but the downstream `transactions.scored` and `cases.created`
events are permanently lost for that message. Any downstream consumer (e.g., a future real-time
alerting service subscribed to `transactions.scored`) will never see the event. This is acceptable
in a local development context; in production, publish failures should be retried or routed to a DLQ.

### 3.4 Crash scenarios

| Scenario | Outcome | Notes |
|---|---|---|
| Crash before `_persist()` | Message redelivered; processed cleanly on restart | No DB row written; event_id not seen before |
| Crash after `_persist()`, before `consumer.commit()` | Message redelivered; `log_prediction()` returns `None` (duplicate); downstream publish skipped; offset committed | DB row is correct; `transactions.scored` and `cases.created` events are permanently lost for this delivery |
| Crash during `_publish_scored()` | KafkaError caught internally; `_process()` returns normally; `consumer.commit()` executes; event lost from topic | Publish is NOT retried |
| `_process()` raises unexpected exception mid-flight | Caught by outer `except Exception`; offset committed; message permanently skipped | No DLQ; error log only |

### 3.5 Production gaps

| Gap | Description |
|---|---|
| No dead-letter topic | Unexpected processing failures commit the offset and discard the message. No quarantine or replay path exists. |
| No retry mechanism | A transient failure (momentary DB flap, brief scoring pipeline error) cannot be retried automatically. The message is lost. |
| No downstream publish retry | `KafkaError` on `_publish_scored` or `_publish_case_created` is swallowed. The scored result is in Postgres but never reaches downstream topic consumers. |
| No consumer lag monitoring | There is no alerting on consumer group lag for `scoring-service`. A stalled or crashed consumer is not observable from the application. |
| No operational replay tooling | There is no tooling to replay a range of offsets from `transactions.raw` through the scoring pipeline without producing duplicate Postgres rows. |

---

## 4. Investigation Consumer Durability

### 4.1 Offset management

```
enable_auto_commit=False
max_poll_records=1
```

Offsets are committed at two points and deliberately withheld at a third:

```
Successful processing:  _process() returns normally → consumer.commit()
Poison pill:            ValueError / ValidationError caught → consumer.commit()
Unexpected exception:   Exception caught → offset NOT committed
```

The investigation consumer makes a deliberate architectural choice that the scoring consumer does
not: **unexpected errors do not commit the offset**. The message is left available for redelivery
so a transient failure can be retried on the next consumer restart. The source code comment at this
path reads: _"Do NOT commit the offset — leave the message available for redelivery so a transient
failure can be retried on the next consumer run."_

### 4.2 Poison-pill behavior

Malformed JSON (`json.JSONDecodeError` wrapped as `ValueError`) and schema validation failures
(`pydantic.ValidationError`) are treated as poison pills: the offset is committed and the message
is skipped permanently. These messages are structurally invalid — no amount of retrying will make
them processable.

### 4.3 Investigation pipeline exception handling — Phase 18C context

Phase 18C introduced `_classify_investigation_error()` and moved all exception handling inside
`process_case()` in `src/investigation/service.py`. As of Phase 18C:

- `process_case()` **never raises**. Every exception type — Ollama connectivity failures, LLM
  content failures, and generic unexpected errors — is caught and converted into a FAILED
  `InvestigationReport` with a bounded, analyst-readable `error_message`.
- A FAILED report is a **durable outcome**. `log_investigation()` persists the FAILED row to
  Postgres. The consumer's `consumer.commit()` executes after `log_investigation()` returns.
- The investigation panel in the frontend (`fraud-console/components/cases/InvestigationPanel.tsx`)
  renders the FAILED state with the bounded error message and a "Retry Investigation" trigger.

The practical consequence: the only exception that can now propagate out of `_process()` and
leave the offset uncommitted is a **Postgres failure in `log_investigation()`**. Ollama being
down, the LLM returning invalid structured output, or any other pipeline error results in a
committed FAILED report row, not an uncommitted offset.

### 4.4 Retry-on-restart behavior

When `log_investigation()` raises (Postgres unavailable), the offset is not committed. On consumer
restart, the broker redelivers the same `cases.investigate` message. The consumer retries the
full investigation pipeline from scratch. This is correct behavior for a transient DB failure: once
Postgres recovers, the next restart will process the message and persist the report successfully.

### 4.5 Production gaps

| Gap | Description |
|---|---|
| No bounded retry limit | If Postgres remains persistently unavailable, the consumer will redeliver and fail the same message on every restart, indefinitely. There is no retry counter, retry budget, or backoff strategy. |
| No circuit breaker | No mechanism exists to detect a sustained dependency failure and pause the consumer gracefully rather than repeatedly failing. |
| No dead-letter topic | A message that cannot be persisted after N retries has no quarantine path. In practice, for the current implementation, this only triggers on sustained Postgres failures (all other errors produce FAILED reports). |
| No consumer lag monitoring | There is no alerting on consumer group lag for `investigation-service`. A stalled consumer is not observable. |
| No investigation retry rate alerting | A high rate of FAILED investigation reports (e.g., Ollama down for 30 minutes) produces error logs but no operational alert. |

---

## 5. Failure-Type Matrix

The table below documents every relevant failure mode, the current behavior of each consumer, the
durability risk, and the production recommendation.

| Failure Type | Consumer | Current Behavior | Durability Risk | Production Recommendation |
|---|---|---|---|---|
| Malformed JSON | Both | Poison pill → offset committed → message skipped permanently | Low — message is unprocessable; skipping is correct | Log to dead-letter topic for manual inspection |
| Schema validation failure | Both | Poison pill → offset committed → message skipped permanently | Low — structurally invalid; skipping is correct | Log to dead-letter topic; alert on persistent volume |
| DB transient failure (write) | Scoring | Caught by `except Exception` → offset committed → message permanently skipped | **High** — scored result is lost silently; no retry | Route to dead-letter topic; retry with exponential backoff before committing |
| DB transient failure (write) | Investigation | `log_investigation()` raises → offset NOT committed → message retried on restart | Medium — message will retry on restart; no backoff | Add bounded retry counter; exponential backoff; DLQ after N failures |
| Duplicate event delivery | Scoring | `log_prediction()` returns `None` → downstream skipped → offset committed | Low — idempotency key prevents duplicate DB row | No change needed; downstream publish loss is the remaining gap |
| Kafka publish failure (`transactions.scored`) | Scoring | KafkaError swallowed inside `_process()` → offset committed | Medium — DB row persists but downstream consumers miss the event | Retry publish with backoff before swallowing; route to DLQ if retries exhausted |
| Kafka publish failure (`cases.created`) | Scoring | KafkaError swallowed inside `_process()` → offset committed | Medium — case creation event lost from topic | Same as above |
| Ollama unavailable | Investigation | `process_case()` catches → FAILED report returned → persisted → offset committed | Low — FAILED report is a durable outcome; analyst can retry from the UI | No change needed at this tier; monitor FAILED report rate as an Ollama health signal |
| LLM invalid structured response | Investigation | `RuntimeError` from exhausted retries caught → FAILED report → persisted | Low — FAILED report persisted; bounded error message surfaced in UI | Monitor FAILED-by-content-failure rate; alert if above threshold |
| Consumer crash before DB write | Both | Message redelivered; processed cleanly | Low — clean at-least-once delivery | No change needed |
| Consumer crash after DB write, before offset commit | Scoring | Redelivered; idempotency key fires; downstream publish skipped; offset committed | Medium — event_id deduplicated correctly but downstream publish is permanently lost | Separate DB write from Kafka publish with explicit retry on publish |
| Consumer crash after DB write, before offset commit | Investigation | Redelivered; `log_investigation()` may produce a duplicate row if no unique constraint on `investigation_id` | Low-Medium — `investigation_id` is a UUID generated per request; two rows for same investigation_id would appear; frontend returns latest | Add unique constraint on `investigations.investigation_id` |
| Persistent Postgres outage | Scoring | Unexpected Exception → offset committed → messages permanently lost | **Critical** — all messages during outage are silently dropped | DLQ required; never commit on DB failure |
| Persistent Postgres outage | Investigation | Offset not committed → infinite retry on restart | Medium — messages queue up; no forward progress; no backoff | Bounded retry with circuit breaker; DLQ after budget exhausted |

---

## 6. Production Recommendation Matrix

The following controls are not implemented in the current local development stack. Each is a
prerequisite for institution-grade deployment.

| Control | Priority | Description |
|---|---|---|
| **Dead-letter topic (DLQ)** | Critical | Add a `transactions.raw.dlq` topic (and `cases.investigate.dlq`). Route any message that fails after N retries to the DLQ rather than committing and discarding. The DLQ becomes the forensic record of processing failures. |
| **Retry counter / retry budget** | Critical | Track the number of delivery attempts per `event_id` / `investigation_id`. After a configurable budget (e.g., 5 attempts), route to the DLQ. Prevents infinite-retry loops on persistent failures. |
| **Exponential backoff** | High | Between retries (for investigation consumer), back off with exponential delay (e.g., 1s, 2s, 4s, 8s, 16s). Prevents hammering a recovering dependency and reduces Redpanda/Postgres load during cascading failures. |
| **Poison-pill quarantine topic** | Medium | Current poison-pill handling commits the offset with an ERROR log. A dedicated `*.invalid` topic should receive these messages for manual inspection and root-cause analysis. |
| **Idempotency key on `investigations`** | High | Add a unique constraint on `investigations.investigation_id`. Prevents duplicate investigation rows from message redelivery after a crash between DB write and offset commit in the investigation consumer. |
| **Separate publish retry from offset commit (scoring)** | High | In the scoring consumer, retry `_publish_scored` and `_publish_case_created` independently before committing the offset. The current design commits regardless of publish outcome, permanently losing downstream events. |
| **Consumer lag monitoring** | High | Integrate Redpanda's consumer group lag metrics (via `/public_metrics` or the Admin API) into the operational health system. Alert when consumer group lag exceeds a configurable threshold (e.g., >100 messages or >5 minutes behind). |
| **FAILED investigation rate alerting** | Medium | Monitor the rate of FAILED investigation reports in the `investigations` table (by `error_message` category). A sustained spike in `"LLM service unreachable"` reports is an Ollama outage signal that the existing health endpoint confirms but no alert fires on. |
| **Runbook ownership** | Medium | Each consumer should have a named runbook defining: what to do when the DLQ grows, how to drain and replay it, how to reset a consumer group offset manually, and what the escalation path is for sustained processing failures. |
| **Consumer restart policy hardening** | Low | `restart: on-failure` in `docker-compose.yml` is appropriate for local dev. In production, a proper process supervisor (Kubernetes Deployment with liveness/readiness probes, or systemd with exponential restart backoff) is required. |

---

## 7. Explicit Non-Goals for Phase 19B

Phase 19B is a documentation-only phase. The following are explicitly out of scope and will not be
implemented here:

- Dead-letter topic creation (`transactions.raw.dlq`, `cases.investigate.dlq`)
- Retry counter fields in any table or in-memory state
- Consumer loop refactoring
- Kafka or Redpanda topology changes (`docker-compose.yml` unchanged)
- Database migrations (no new tables, no new constraints)
- Prometheus, OpenTelemetry, or external metrics integration
- Frontend changes of any kind
- Auth/RBAC implementation
- Deployment configuration changes
- Any modification to `src/events/consumer_scoring.py` or `src/investigation/consumer.py`

---

## 8. Conclusion

The scoring and investigation consumers implement a correct and well-reasoned durability posture
for a controlled local development fraud intelligence console.

The investigation consumer is the stronger of the two: unexpected errors do not commit the offset,
Phase 18C ensures all Ollama/LLM failures produce durable FAILED report rows rather than
uncommitted offsets, and the consumer resumes cleanly after a Postgres recovery without message
loss. The primary remaining gap is the absence of a bounded retry limit for sustained Postgres
failures.

The scoring consumer takes a more permissive approach: all handled errors commit the offset to
ensure forward progress. This is appropriate in a local development context where availability
of the consumer outweighs the risk of losing individual messages. The significant gaps for
production are the absence of a dead-letter path for unexpected failures, the swallowed publish
errors to `transactions.scored` and `cases.created`, and the lack of retry logic before discarding
a message.

Both consumers share the same structural gaps: no consumer lag monitoring, no retry budget, no
dead-letter topic, and no operational replay tooling. Closing these gaps is a prerequisite before
this system operates in a regulated financial services environment at production volume.

The idempotency guarantee provided by the `event_id` uniqueness constraint on `predictions` is
sound and protects against the most common at-least-once delivery scenario (crash before offset
commit). The investigation consumer's `investigation_id` lacks a corresponding unique constraint,
which is a low-risk gap given the UUID-per-request design but should be addressed before
high-throughput production deployment.

---

*Document version: Phase 19B. Source references: `src/events/consumer_scoring.py`,
`src/investigation/consumer.py`, `src/db/postgres_logger.py`, `alembic/versions/0002_add_event_id_to_predictions.py`.*
