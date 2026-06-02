"""
Phase 14 -- CSV dirty-data resilience verification.

Tests the validator path directly using in-memory CSV bytes and DataFrames.
No API server, database, or external service is required.

Dirty-data categories covered:
  (1)  Structural: missing required column
  (2)  Structural: unparseable / non-CSV bytes
  (3)  Structural: row limit exceeded
  (4)  Row: missing required field (transaction_id)
  (5)  Row: blank amount
  (6)  Row: non-numeric amount
  (7)  Row: negative amount               [known limit -- accepted as VALID]
  (8)  Row: extremely large amount        [known limit -- accepted as VALID]
  (9)  Row: duplicate transaction_id      -> SKIPPED
  (10) Row: completely empty row          -> INVALID (all fields missing)
  (11) Row: extra unexpected column       -> VALID (extra columns silently ignored)
  (12) Row: malformed timestamp
  (13) Row: missing country
  (14) Row: missing payment_method
  (15) Combined: mixed clean + dirty CSV  -> correct counts across all categories

Exit codes:
  0 -- all assertions passed
  1 -- one or more assertions failed
"""

import io
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.risk_scan.validator import (
    RiskScanParseError,
    RiskScanValidationError,
    validate_csv,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASS_COUNT = 0
_FAIL_COUNT = 0
_KNOWN_LIMITS: list[str] = []


def _assert(condition: bool, message: str) -> None:
    global _FAIL_COUNT
    if not condition:
        _FAIL_COUNT += 1
        raise AssertionError(message)


def _pass(label: str) -> None:
    global _PASS_COUNT
    _PASS_COUNT += 1
    print(f"[PASS]  {label}")


def _fail(label: str, reason: str) -> None:
    global _FAIL_COUNT
    _FAIL_COUNT += 1
    print(f"[FAIL]  {label}  -- {reason}")


def _known_limit(note: str) -> None:
    _KNOWN_LIMITS.append(note)


def _csv_bytes(*rows: str, header: str | None = None) -> bytes:
    """Build minimal CSV bytes from a header string and row strings."""
    if header is None:
        header = "transaction_id,amount,timestamp,country,payment_method"
    lines = [header] + list(rows)
    return "\n".join(lines).encode("utf-8")


_GOOD_ROW = "txn_clean,250.00,2024-03-15T10:00:00,US,debit_card"
_GOOD_ROW_2 = "txn_clean_b,180.00,2024-06-01T14:30:00,GB,credit_card"


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_structural_missing_column() -> None:
    label = "[1] Structural: missing required column raises RiskScanValidationError"
    try:
        data = _csv_bytes(
            "txn_001,100.00,2024-01-01T12:00:00,US",
            header="transaction_id,amount,timestamp,country",  # missing payment_method
        )
        try:
            validate_csv(data)
            _fail(label, "expected RiskScanValidationError but no exception raised")
        except RiskScanValidationError as exc:
            _assert("payment_method" in str(exc).lower() or "missing" in str(exc).lower(),
                    "error message does not mention missing column")
            _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_structural_unparseable() -> None:
    label = "[2] Structural: unparseable bytes raises RiskScanParseError"
    try:
        garbage = b"\x00\x01\x02\x03\xff\xfe not valid CSV content at all"
        try:
            validate_csv(garbage)
            _fail(label, "expected RiskScanParseError but no exception raised")
        except RiskScanParseError:
            _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_structural_row_limit() -> None:
    label = "[3] Structural: row limit exceeded raises RiskScanValidationError"
    try:
        rows = [f"txn_{i:04d},100.00,2024-01-01T12:00:00,US,debit_card" for i in range(20)]
        data = _csv_bytes(*rows)
        try:
            validate_csv(data, max_rows=10)
            _fail(label, "expected RiskScanValidationError but no exception raised")
        except RiskScanValidationError as exc:
            _assert("exceeds" in str(exc).lower() or "maximum" in str(exc).lower(),
                    "error message does not mention row limit")
            _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_row_missing_transaction_id() -> None:
    label = "[4] Row: missing transaction_id -> INVALID with non-silent error"
    try:
        data = _csv_bytes(
            ",250.00,2024-01-01T10:00:00,US,debit_card",
        )
        result = validate_csv(data)
        row = result.all_rows[0]
        _assert(row["validation_status"] == "INVALID", "expected INVALID")
        _assert(result.invalid_rows == 1, "invalid_rows count wrong")
        _assert(row["validation_errors"] is not None and len(row["validation_errors"]) > 0,
                "validation_errors is empty (silent rejection)")
        _assert(any("transaction_id" in e for e in row["validation_errors"]),
                "error message does not reference transaction_id")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_row_blank_amount() -> None:
    label = "[5] Row: blank amount -> INVALID with non-silent error"
    try:
        data = _csv_bytes(
            "txn_ba,,2024-01-01T10:00:00,US,debit_card",
        )
        result = validate_csv(data)
        row = result.all_rows[0]
        _assert(row["validation_status"] == "INVALID", "expected INVALID")
        _assert(row["validation_errors"] is not None and len(row["validation_errors"]) > 0,
                "validation_errors is empty")
        _assert(any("amount" in e for e in row["validation_errors"]),
                "error message does not reference amount")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_row_nonnumeric_amount() -> None:
    label = "[6] Row: non-numeric amount -> INVALID with non-silent error"
    try:
        data = _csv_bytes(
            "txn_na,not-a-number,2024-01-01T10:00:00,US,credit_card",
        )
        result = validate_csv(data)
        row = result.all_rows[0]
        _assert(row["validation_status"] == "INVALID", "expected INVALID")
        _assert(row["validation_errors"] is not None,
                "validation_errors is None for non-numeric amount")
        _assert(any("amount" in e for e in row["validation_errors"]),
                "error message does not reference amount")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_row_negative_amount() -> None:
    label = "[7] Row: negative amount -> VALID (known limit: no range check)"
    try:
        data = _csv_bytes(
            "txn_neg,-150.00,2024-01-01T10:00:00,US,debit_card",
        )
        result = validate_csv(data)
        row = result.all_rows[0]
        _assert(row["validation_status"] == "VALID",
                f"expected VALID for negative amount but got {row['validation_status']}")
        _assert(result.valid_rows == 1, "valid_rows count wrong")
        _known_limit("Negative amounts are accepted as VALID (no amount range check in validator.py)")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_row_extremely_large_amount() -> None:
    label = "[8] Row: extremely large amount -> VALID (known limit: no range check)"
    try:
        data = _csv_bytes(
            "txn_big,9999999999.99,2024-01-01T10:00:00,US,bank_transfer",
        )
        result = validate_csv(data)
        row = result.all_rows[0]
        _assert(row["validation_status"] == "VALID",
                f"expected VALID for large amount but got {row['validation_status']}")
        _known_limit("Extremely large amounts are accepted as VALID (no upper bound check in validator.py)")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_row_duplicate_transaction_id() -> None:
    label = "[9] Row: duplicate transaction_id -> SKIPPED with non-silent error"
    try:
        data = _csv_bytes(
            "txn_dup,100.00,2024-01-01T10:00:00,US,debit_card",
            "txn_dup,200.00,2024-01-02T10:00:00,GB,credit_card",
        )
        result = validate_csv(data)
        _assert(result.valid_rows == 1, f"expected 1 valid, got {result.valid_rows}")
        _assert(result.skipped_rows == 1, f"expected 1 skipped, got {result.skipped_rows}")
        skipped = [r for r in result.all_rows if r["validation_status"] == "SKIPPED"]
        _assert(len(skipped) == 1, "no SKIPPED row found")
        _assert(
            skipped[0]["validation_errors"] is not None and len(skipped[0]["validation_errors"]) > 0,
            "SKIPPED row has no validation_errors (silent skip)"
        )
        _assert(
            any("duplicate" in e.lower() for e in skipped[0]["validation_errors"]),
            "SKIPPED error message does not mention 'duplicate'"
        )
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_row_empty_row() -> None:
    label = "[10] Row: completely empty row -> INVALID (all required fields missing)"
    try:
        data = _csv_bytes(
            ",,,,",
        )
        result = validate_csv(data)
        row = result.all_rows[0]
        _assert(row["validation_status"] == "INVALID", "expected INVALID for empty row")
        _assert(row["validation_errors"] is not None and len(row["validation_errors"]) >= 3,
                f"expected 3+ errors for fully empty row, got {row['validation_errors']}")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_row_extra_column() -> None:
    label = "[11] Row: extra unexpected column -> does not crash, row is VALID"
    try:
        data = _csv_bytes(
            "txn_extra,99.00,2024-01-01T10:00:00,US,debit_card,unexpected_value",
            header="transaction_id,amount,timestamp,country,payment_method,extra_unexpected_column",
        )
        result = validate_csv(data)
        row = result.all_rows[0]
        _assert(row["validation_status"] == "VALID",
                f"extra column caused rejection: {row['validation_errors']}")
        _assert(result.valid_rows == 1, "valid_rows count wrong with extra column")
        _pass(label)
    except (AssertionError, Exception) as exc:
        _fail(label, str(exc))


def test_row_malformed_timestamp() -> None:
    label = "[12] Row: malformed timestamp -> INVALID with non-silent error"
    try:
        data = _csv_bytes(
            "txn_ts,150.00,not-a-timestamp,US,debit_card",
        )
        result = validate_csv(data)
        row = result.all_rows[0]
        _assert(row["validation_status"] == "INVALID", "expected INVALID")
        _assert(row["validation_errors"] is not None,
                "validation_errors is None for malformed timestamp")
        _assert(any("timestamp" in e for e in row["validation_errors"]),
                "error message does not reference timestamp")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_row_missing_country() -> None:
    label = "[13] Row: missing country -> INVALID with non-silent error"
    try:
        data = _csv_bytes(
            "txn_nc,300.00,2024-01-01T10:00:00,,credit_card",
        )
        result = validate_csv(data)
        row = result.all_rows[0]
        _assert(row["validation_status"] == "INVALID", "expected INVALID")
        _assert(row["validation_errors"] is not None,
                "validation_errors is None for missing country")
        _assert(any("country" in e for e in row["validation_errors"]),
                "error message does not reference country")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_row_missing_payment_method() -> None:
    label = "[14] Row: missing payment_method -> INVALID with non-silent error"
    try:
        data = _csv_bytes(
            "txn_npm,200.00,2024-01-01T10:00:00,AU,",
        )
        result = validate_csv(data)
        row = result.all_rows[0]
        _assert(row["validation_status"] == "INVALID", "expected INVALID")
        _assert(row["validation_errors"] is not None,
                "validation_errors is None for missing payment_method")
        _assert(any("payment_method" in e for e in row["validation_errors"]),
                "error message does not reference payment_method")
        _pass(label)
    except AssertionError as exc:
        _fail(label, str(exc))


def test_combined_mixed_csv() -> None:
    """
    Full mixed CSV matching the generate_dirty_data_csv.py layout.
    50 clean rows + 11 dirty rows = 61 total.
    Expected: valid=53, invalid=7, skipped=1.
    """
    label = "[15] Combined: mixed clean+dirty CSV -> correct counts"
    import random
    import csv
    import io as _io
    from datetime import datetime, timedelta

    rng = random.Random(14)
    COUNTRIES = ["US", "GB", "DE", "AU", "CA", "RU", "CN", "NG"]
    PM = ["credit_card", "debit_card", "digital_wallet", "bank_transfer"]
    MC = ["grocery", "electronics", "gaming", "travel", "retail"]
    BASE_DT = datetime(2024, 1, 1)

    def _ts(i: int) -> str:
        dt = BASE_DT + timedelta(days=i % 365, hours=i % 24, minutes=i % 60)
        return dt.strftime("%Y-%m-%dT%H:%M:%S")

    rows = []
    for i in range(1, 51):
        rows.append({
            "transaction_id": f"clean_{i:04d}",
            "amount": round(rng.uniform(5.0, 2000.0), 2),
            "timestamp": _ts(i),
            "country": rng.choice(COUNTRIES),
            "payment_method": rng.choice(PM),
            "merchant_category": rng.choice(MC),
            "device_id": f"dev_{rng.randint(1000,9999)}",
            "extra_unexpected_column": "",
        })

    # Row 51: missing transaction_id -> INVALID
    rows.append({"transaction_id": "", "amount": "250.00", "timestamp": _ts(51),
                 "country": "US", "payment_method": "debit_card",
                 "merchant_category": "grocery", "device_id": "dev_5100",
                 "extra_unexpected_column": ""})
    # Row 52: blank amount -> INVALID
    rows.append({"transaction_id": "dirty_052", "amount": "", "timestamp": _ts(52),
                 "country": "US", "payment_method": "debit_card",
                 "merchant_category": "grocery", "device_id": "dev_5200",
                 "extra_unexpected_column": ""})
    # Row 53: non-numeric amount -> INVALID
    rows.append({"transaction_id": "dirty_053", "amount": "not-a-number", "timestamp": _ts(53),
                 "country": "US", "payment_method": "credit_card",
                 "merchant_category": "electronics", "device_id": "dev_5300",
                 "extra_unexpected_column": ""})
    # Row 54: negative amount -> VALID (known limit)
    rows.append({"transaction_id": "dirty_054", "amount": "-150.00", "timestamp": _ts(54),
                 "country": "US", "payment_method": "debit_card",
                 "merchant_category": "grocery", "device_id": "dev_5400",
                 "extra_unexpected_column": ""})
    # Row 55: extremely large amount -> VALID (known limit)
    rows.append({"transaction_id": "dirty_055", "amount": "9999999999.99", "timestamp": _ts(55),
                 "country": "US", "payment_method": "bank_transfer",
                 "merchant_category": "travel", "device_id": "dev_5500",
                 "extra_unexpected_column": ""})
    # Row 56: duplicate transaction_id -> SKIPPED
    rows.append({"transaction_id": "clean_0001", "amount": "500.00", "timestamp": _ts(56),
                 "country": "GB", "payment_method": "credit_card",
                 "merchant_category": "retail", "device_id": "dev_5600",
                 "extra_unexpected_column": ""})
    # Row 57: completely empty -> INVALID
    rows.append({"transaction_id": "", "amount": "", "timestamp": "",
                 "country": "", "payment_method": "",
                 "merchant_category": "", "device_id": "",
                 "extra_unexpected_column": ""})
    # Row 58: extra column populated -> VALID
    rows.append({"transaction_id": "dirty_058", "amount": "75.00", "timestamp": _ts(58),
                 "country": "DE", "payment_method": "debit_card",
                 "merchant_category": "grocery", "device_id": "dev_5800",
                 "extra_unexpected_column": "unexpected_value_xyz"})
    # Row 59: malformed timestamp -> INVALID
    rows.append({"transaction_id": "dirty_059", "amount": "200.00", "timestamp": "not-a-timestamp",
                 "country": "US", "payment_method": "credit_card",
                 "merchant_category": "gaming", "device_id": "dev_5900",
                 "extra_unexpected_column": ""})
    # Row 60: missing country -> INVALID
    rows.append({"transaction_id": "dirty_060", "amount": "300.00", "timestamp": _ts(60),
                 "country": "", "payment_method": "debit_card",
                 "merchant_category": "grocery", "device_id": "dev_6000",
                 "extra_unexpected_column": ""})
    # Row 61: missing payment_method -> INVALID
    rows.append({"transaction_id": "dirty_061", "amount": "400.00", "timestamp": _ts(61),
                 "country": "AU", "payment_method": "",
                 "merchant_category": "retail", "device_id": "dev_6100",
                 "extra_unexpected_column": ""})

    fieldnames = ["transaction_id", "amount", "timestamp", "country",
                  "payment_method", "merchant_category", "device_id", "extra_unexpected_column"]
    buf = _io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    data = buf.getvalue().encode("utf-8")

    try:
        result = validate_csv(data)

        expected_total = 61
        expected_valid = 53   # 50 clean + rows 54, 55, 58
        expected_invalid = 7  # rows 51, 52, 53, 57, 59, 60, 61
        expected_skipped = 1  # row 56

        _assert(result.total_rows == expected_total,
                f"total_rows: expected {expected_total}, got {result.total_rows}")
        _assert(result.valid_rows == expected_valid,
                f"valid_rows: expected {expected_valid}, got {result.valid_rows}")
        _assert(result.invalid_rows == expected_invalid,
                f"invalid_rows: expected {expected_invalid}, got {result.invalid_rows}")
        _assert(result.skipped_rows == expected_skipped,
                f"skipped_rows: expected {expected_skipped}, got {result.skipped_rows}")

        all_statuses = [r["validation_status"] for r in result.all_rows]
        _assert(all_statuses.count("VALID") == expected_valid, "VALID count mismatch in all_rows")
        _assert(all_statuses.count("INVALID") == expected_invalid, "INVALID count mismatch in all_rows")
        _assert(all_statuses.count("SKIPPED") == expected_skipped, "SKIPPED count mismatch in all_rows")

        invalid_rows = [r for r in result.all_rows if r["validation_status"] == "INVALID"]
        for r in invalid_rows:
            _assert(
                r["validation_errors"] is not None and len(r["validation_errors"]) > 0,
                f"INVALID row {r['row_number']} has empty validation_errors (silent rejection)"
            )

        _pass(label)
        return result

    except AssertionError as exc:
        _fail(label, str(exc))
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print()
    print("=" * 60)
    print("Phase 14 -- CSV Dirty-Data Verification Report")
    print("=" * 60)

    test_structural_missing_column()
    test_structural_unparseable()
    test_structural_row_limit()
    test_row_missing_transaction_id()
    test_row_blank_amount()
    test_row_nonnumeric_amount()
    test_row_negative_amount()
    test_row_extremely_large_amount()
    test_row_duplicate_transaction_id()
    test_row_empty_row()
    test_row_extra_column()
    test_row_malformed_timestamp()
    test_row_missing_country()
    test_row_missing_payment_method()
    combined = test_combined_mixed_csv()

    print()
    print("-" * 60)
    if combined is not None:
        print(f"Total rows tested   : {combined.total_rows}  (combined test)")
        print(f"  Valid             : {combined.valid_rows}  (50 clean + 3 dirty-but-valid known limits)")
        print(f"  Invalid           : {combined.invalid_rows}")
        print(f"  Skipped           : {combined.skipped_rows}  (duplicate transaction_id)")
        print(f"  Duplicate rows    : {combined.skipped_rows}")
    print(f"Cases covered       : 10/10 dirty categories + 3 structural")
    if _KNOWN_LIMITS:
        print(f"Known limits        : {len(_KNOWN_LIMITS)}")
        for lim in _KNOWN_LIMITS:
            print(f"  - {lim}")
    print("-" * 60)

    if _FAIL_COUNT == 0:
        print(f"OVERALL: PASS  ({_PASS_COUNT}/{_PASS_COUNT + _FAIL_COUNT} tests)")
    else:
        print(f"OVERALL: FAIL  ({_FAIL_COUNT} failure(s) out of {_PASS_COUNT + _FAIL_COUNT} tests)")
    print("=" * 60)
    print()

    return 0 if _FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"\nFATAL: unhandled exception in verify_dirty_data_handling.py: {exc}")
        sys.exit(1)
