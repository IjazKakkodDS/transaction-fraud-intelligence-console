# Dirty Data Resilience -- Phase 14

Phase 14 -- Dirty Data and Stream Resilience Testing.
This document covers both Phase 14 working slices:
- Slice 1: CSV / Portfolio Risk Scan dirty-data resilience
- Slice 2: Stream consumer event-boundary resilience (in-memory / schema-level validation)

---

## Scope

This slice verifies that the Portfolio Risk Scan CSV upload path handles real-world data
quality problems gracefully -- without crashes, silent failures, or undefined behavior.

Covered path:
- `src/risk_scan/validator.py` -- CSV parse, column validation, row-level validation
- `src/risk_scan/processor.py` -- chunked async scan orchestration (structurally reviewed)

Not in scope for Slice 1 (covered by Slice 2 below):
- Redpanda / Kafka stream consumer event-boundary resilience

Not in scope for either slice:
- Live Redpanda broker integration testing
- Database migration changes
- Scoring weight or threshold changes
- Frontend changes

---

## Dirty-Data Taxonomy Tested

| # | Category | Expected outcome |
|---|---|---|
| 1 | Missing required column (structural) | `RiskScanValidationError` raised before any row processing |
| 2 | Unparseable / non-CSV bytes (structural) | `RiskScanParseError` raised |
| 3 | Row limit exceeded (structural) | `RiskScanValidationError` raised |
| 4 | Missing `transaction_id` (blank) | Row: INVALID, non-silent error message |
| 5 | Blank `amount` | Row: INVALID, non-silent error message |
| 6 | Non-numeric `amount` (e.g., "not-a-number") | Row: INVALID, non-silent error message |
| 7 | Negative `amount` (e.g., -150.00) | Row: VALID -- **known limit** (see below) |
| 8 | Extremely large `amount` (e.g., 9999999999.99) | Row: VALID -- **known limit** (see below) |
| 9 | Duplicate `transaction_id` | Row: SKIPPED, non-silent error message |
| 10 | Completely empty row (all fields blank) | Row: INVALID, multiple error messages |
| 11 | Extra unexpected column in CSV header | No crash; extra column silently ignored; row VALID |
| 12 | Malformed `timestamp` (e.g., "not-a-timestamp") | Row: INVALID, non-silent error message |
| 13 | Missing `country` | Row: INVALID, non-silent error message |
| 14 | Missing `payment_method` | Row: INVALID, non-silent error message |

---

## Generator Script

**Path:** `scripts/generate_dirty_data_csv.py`

Generates a 61-row controlled CSV to `scripts/test_dirty_data_scan.csv` (gitignored).

Row layout:
- Rows 1-50: clean baseline (all VALID)
- Row 51: missing transaction_id (INVALID)
- Row 52: blank amount (INVALID)
- Row 53: non-numeric amount (INVALID)
- Row 54: negative amount (VALID -- known limit)
- Row 55: extremely large amount (VALID -- known limit)
- Row 56: duplicate transaction_id = row 1 (SKIPPED)
- Row 57: completely empty row (INVALID)
- Row 58: extra_unexpected_column populated (VALID)
- Row 59: malformed timestamp (INVALID)
- Row 60: missing country (INVALID)
- Row 61: missing payment_method (INVALID)

Expected counts: total=61, valid=53, invalid=7, skipped=1.

Generated CSV is gitignored. Do not commit it.

---

## Verification Script

**Path:** `scripts/verify_dirty_data_handling.py`

Runs 15 in-memory test cases directly against `validate_csv()` and `validate_dataframe()`
from `src/risk_scan/validator.py`. No API server, database, or external service required.

Test structure:
- 3 structural tests (missing column, unparseable bytes, row limit)
- 11 row-level isolation tests (one dirty category per test)
- 1 combined test (all 61 rows, verifies correct aggregate counts)

All 15 tests verified PASS. Exit code 0 on success, 1 on any failure.

---

## Validation Outcomes

### VALID rows

Rows that pass all validation checks proceed to scoring via the XGBoost + rule pipeline.
VALID status is assigned per row and surfaced in the scan result.

### INVALID rows

Rows that fail one or more field checks are assigned INVALID status. They do not proceed
to scoring. Each INVALID row has a non-empty `validation_errors` list with specific,
human-readable messages such as:

- "Missing required field: transaction_id"
- "Invalid value for field: amount"
- "Missing required field: timestamp"
- "Invalid value for field: timestamp"
- "Missing required field: country"
- "Missing required field: payment_method"

INVALID row counts are tracked in the scan result (`invalid_rows`) and surfaced in the
frontend progress card and summary panel.

### SKIPPED rows

Rows with a `transaction_id` that has already been seen earlier in the same upload are
assigned SKIPPED status. They do not proceed to scoring.

Error message: "Duplicate transaction_id in uploaded file"

SKIPPED row counts are tracked in the scan result (`skipped_rows`). When
`RISK_SCAN_ENABLE_IN_MEMORY_DEDUP=true` (default), duplicate detection spans all chunks
in the upload. When set to false, only intra-chunk duplicates are detected.

---

## Rejected / Skipped Row Behavior

| Status | What happens | Surfaced to user |
|---|---|---|
| INVALID | Row excluded from scoring; validation_errors populated | invalid_rows count in scan result |
| SKIPPED | Row excluded from scoring; reason recorded as duplicate | skipped_rows count in scan result |

No silent failures: every excluded row has a non-empty `validation_errors` entry explaining
the reason for exclusion.

---

## Known Limits

| Limit | Behavior | Location |
|---|---|---|
| Negative amounts | Accepted as VALID; no lower-bound check | `validator.py` `validate_dataframe()` |
| Extremely large amounts | Accepted as VALID; no upper-bound check | `validator.py` `validate_dataframe()` |

These are policy decisions, not crashes. The validator checks type (numeric) but not range.
Adding range checks would require a policy decision on acceptable bounds and would change
the VALID/INVALID classification for existing uploaded files. This is out of scope for the
current resilience slice.

---

## Implementation Changes

| File | Changed | Notes |
|---|---|---|
| `src/risk_scan/validator.py` | No | No gap found; no change required |
| `src/risk_scan/processor.py` | No | No gap found; no change required |
| `scripts/generate_dirty_data_csv.py` | Created | Dirty-data CSV generator (Phase 14) |
| `scripts/verify_dirty_data_handling.py` | Created | In-memory dirty-data verification (Phase 14) |
| `docs/DIRTY_DATA_RESILIENCE.md` | Created | This document |
| `docs/PRODUCT_STAGES.md` | Updated | Phase 14 set to Current / In progress |
| `.gitignore` | Updated | Added exceptions for two new tracked scripts |

---

## Legacy 10k Regression

**Not rerun.** Neither `validator.py` nor `processor.py` changed in this slice. Per the Phase 14
regression rule, the legacy 10k API scan is only rerun when runtime CSV-path code changes.

Reference distribution from Phase 13G (last verified run):
P0: 1546 / P1: 913 / P2: 0 / P3: 7541
Scan ID: `7d2d5345-b523-4d83-b6e7-b0ac8f00827b`

---

## Stream Resilience -- Slice 2

### Scope

Controlled stream-resilience validation of the event parsing and schema validation
boundaries for both the scoring consumer (`transactions.raw`) and the investigation
consumer (`cases.investigate`). Verification uses in-memory payloads and direct
Pydantic schema validation only. No live Redpanda broker, no DB writes, no API calls.

Covered path:
- `src/events/schemas.py` -- TransactionRawEvent, CaseCreatedEvent, TransactionScoredEvent
- `src/investigation/schemas.py` -- InvestigationRequest
- Consumer parsing logic replicated inline (json.loads + model_validate boundary)

Import boundary:
- Consumer modules (`consumer_scoring.py`, `investigation/consumer.py`) were intentionally
  not imported. They register OS signal handlers and initialise infrastructure clients at
  module level, which is unsafe in an offline verification context. The boundary under test
  -- JSON parse then Pydantic model_validate -- is a two-line sequence replicated directly
  in the verification script, precisely matching the code path in both consumers.

---

### Stream Dirty-Event Taxonomy

**Scoring consumer -- transactions.raw**

| ID | Case | Schema constraint | Expected action |
|---|---|---|---|
| S01 | Empty bytes | n/a | json_error -> commit-and-skip |
| S02 | Non-JSON payload | n/a | json_error -> commit-and-skip |
| S03 | JSON list instead of object | model must receive a mapping | schema_error -> commit-and-skip |
| S04 | Missing `transaction_id` | required str | schema_error -> commit-and-skip |
| S05 | Missing all required fields | multiple required fields | schema_error -> commit-and-skip |
| S06 | Invalid `amount` type (e.g., "abc") | float, coercion fails | schema_error -> commit-and-skip |
| S07 | Null `transaction_id` | required str, None rejected | schema_error -> commit-and-skip |
| S08 | `amount = 0` | `gt=0` | schema_error -> commit-and-skip |
| S09 | Negative `amount` | `gt=0` | schema_error -> commit-and-skip |
| S10 | `country` wrong length (e.g., "USA") | `max_length=2` | schema_error -> commit-and-skip |
| S11 | Wrong `event_type` (e.g., "case.created") | `Literal["transaction.raw"]` | schema_error -> commit-and-skip |
| S12 | Extra unexpected fields | `extra="ignore"` | VALID -- extra fields silently dropped |
| S13 | Partial enrichment (optional fields absent) | optional fields have defaults | VALID -- safe defaults applied |
| S14 | Duplicate event shape | valid schema; idempotency via DB | VALID at schema level -- DB dedup handles |

**Investigation consumer -- cases.investigate**

| ID | Case | Schema constraint | Expected action |
|---|---|---|---|
| I01 | Non-JSON payload | n/a | json_error -> commit-and-skip |
| I02 | Missing `case_id` | required int | schema_error -> commit-and-skip |
| I03 | Non-integer `case_id` (e.g., "abc") | int, coercion fails | schema_error -> commit-and-skip |
| I04 | Extra unexpected fields | `extra="ignore"` | VALID -- extra fields silently dropped |
| I05 | Empty bytes | n/a | json_error -> commit-and-skip |
| I06 | Null `case_id` | required int, None rejected | schema_error -> commit-and-skip |

**Structural invariants**

| ID | Case | Constraint | Expected action |
|---|---|---|---|
| INV1 | `CaseCreatedEvent` with `decision="APPROVE"` | `Literal["REVIEW","BLOCK"]` | ValidationError -- APPROVE structurally blocked |
| INV2 | `TransactionScoredEvent` with `risk_score=1.5` | `le=1.0` | ValidationError -- out-of-bounds score rejected |

---

### Consumer Resilience Boundaries

**Scoring consumer** (`src/events/consumer_scoring.py`)

The scoring consumer uses manual offset commits with two error handling tiers:

- JSON decode errors and Pydantic ValidationErrors are caught as `(ValueError, ValidationError)`
  and the offset is committed immediately. The message is permanently skipped.
- All other exceptions (DB write failures, scoring pipeline errors, downstream Kafka publish
  failures) are caught by a broad `except Exception` block and the offset is also committed.

Current operational resilience boundary: the scoring consumer treats transient infrastructure
failures (database unreachable, model error) identically to structurally unprocessable messages
(malformed JSON, schema violation). Both result in a committed offset with no retry. This is the
intended Phase 2 design; the source comments note that a deployment-hardened system would route
unexpected failures to a dead-letter topic rather than silently committing them.

**Investigation consumer** (`src/investigation/consumer.py`)

The investigation consumer uses a split error handling strategy:

- JSON decode errors and Pydantic ValidationErrors are caught and the offset is committed.
  The message is permanently skipped (structurally unprocessable; retrying will not help).
- All other exceptions (Postgres failure, Ollama timeout, pipeline error) are caught but the
  offset is NOT committed. The consumer logs the error and continues polling. The broker
  redelivers the message on the next run, allowing transient failures to be retried
  without message loss.

This is the stronger resilience posture of the two consumers.

---

### Operational Resilience Limits

| Limit | Scope | Recommended hardening path |
|---|---|---|
| No dead-letter topic (DLQ) | Scoring consumer -- unexpected errors | Add a quarantine topic; route non-poison failures there instead of committing |
| Poison pill vs transient error not separated | Scoring consumer | Separate `(ValueError, ValidationError)` handling from `Exception` handling; apply retry for the latter |
| No stream resilience metrics | Both consumers | Add counters for skipped messages, retry attempts, and DLQ events; expose via monitoring endpoint |
| No alerting for skipped malformed events | Both consumers | Emit a structured log event or metric on every commit-and-skip so operations can detect a flood of malformed messages |
| DB idempotency constraint not yet added | Scoring consumer | Add `uq_predictions_event_id` unique constraint (noted as Phase 2 follow-up in source comments) |

---

### Recommended Deployment Hardening Path

1. **DLQ / quarantine topic** -- route non-poison unexpected errors from the scoring consumer
   to a `transactions.raw.dlq` topic instead of silently committing. Enables reprocessing
   and forensic investigation without data loss.

2. **Retry-policy separation** -- distinguish poison pills (permanent skip) from transient
   errors (time-bounded retry with backoff). Apply the investigation consumer's pattern to
   the scoring consumer.

3. **Stream resilience metrics** -- instrument both consumers with per-message outcome
   counters (accepted, poison-skipped, error-committed, retried) and surface them via the
   existing reliability metrics endpoint or a dedicated stream health endpoint.

4. **Alerting on skipped malformed events** -- a spike in commit-and-skip events indicates
   either a schema-breaking producer change or a data quality incident upstream. Structured
   log events per skip enable detection and triage.

---

### Stream Verification Script

**Path:** `scripts/verify_stream_resilience.py`

Runs 22 in-memory test cases covering both consumers and key structural invariants. No
Redpanda broker, database, or API connection required.

Test structure:
- 14 scoring consumer cases (S01-S14): 11 poison-pill boundary, 3 schema-valid
- 6 investigation consumer cases (I01-I06): 5 poison-pill boundary, 1 schema-valid
- 2 structural invariant checks (INV1-INV2)

All 22 tests verified PASS. Exit code 0 on success, 1 on any failure.

---

## CSV Verification Result

```
Phase 14 -- CSV Dirty-Data Verification Report
Total rows tested   : 61  (combined test)
  Valid             : 53  (50 clean + 3 dirty-but-valid known limits)
  Invalid           : 7
  Skipped           : 1  (duplicate transaction_id)
Cases covered       : 10/10 dirty categories + 3 structural
Known limits        : 2
  - Negative amounts are accepted as VALID (no amount range check)
  - Extremely large amounts are accepted as VALID (no upper bound check)
OVERALL: PASS  (15/15 tests)
```

---

## Stream Verification Result

```
Phase 14 -- Stream Resilience Verification Report
Total cases tested          : 22
  Malformed / rejected      : 13  (poison-pill boundary)
  Schema-valid / accepted   : 4  (extra fields, partial enrichment, duplicate shape, extra inv. fields)
  Structural invariants     : 2  (CaseCreatedEvent APPROVE guard, risk_score bounds)

Consumer actions verified (from source code inspection):
  Scoring consumer   -- JSON/schema errors            : commit-and-skip (permanent)
  Scoring consumer   -- unexpected runtime errors     : commit-and-skip [operational limit]
  Investigation consumer -- JSON/schema errors        : commit-and-skip (permanent)
  Investigation consumer -- unexpected runtime errors : NOT committed (retryable)

Live Redpanda used  : No
DB mutation         : No
Source code changed : No
OVERALL: PASS  (22/22 tests)
```
