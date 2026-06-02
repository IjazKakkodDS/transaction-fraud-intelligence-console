# Dirty Data Resilience -- Phase 14 (CSV Slice)

Phase 14 -- Dirty Data and Stream Resilience Testing.
This document covers the first working slice: CSV / Portfolio Risk Scan dirty-data resilience.
Stream consumer / Redpanda poison-pill testing is not yet started.

---

## Scope

This slice verifies that the Portfolio Risk Scan CSV upload path handles real-world data
quality problems gracefully -- without crashes, silent failures, or undefined behavior.

Covered path:
- `src/risk_scan/validator.py` -- CSV parse, column validation, row-level validation
- `src/risk_scan/processor.py` -- chunked async scan orchestration (structurally reviewed)

Not in scope for this slice:
- Redpanda / Kafka stream consumer
- Poison-pill or late-arriving event handling
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

## Stream Consumer Testing

Stream consumer / Redpanda poison-pill testing is **not started** in this slice. The approved
scope for the first Phase 14 working slice is CSV / Portfolio Risk Scan dirty-data resilience
only. Stream resilience testing (partial enrichment, poison-pill events, out-of-order messages)
is the next planned sub-phase within Phase 14.

---

## Verification Result

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
