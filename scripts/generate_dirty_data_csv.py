"""
Generate a small controlled dirty-data CSV for Phase 14 resilience testing.

Output: scripts/test_dirty_data_scan.csv
All data is synthetic. No real banking data used.

Row breakdown (61 total):
  Rows 1-50   : clean baseline (VALID)
  Row 51      : missing transaction_id             -> INVALID
  Row 52      : blank amount                       -> INVALID
  Row 53      : non-numeric amount                 -> INVALID
  Row 54      : negative amount                    -> VALID (known limit: no range check)
  Row 55      : extremely large amount             -> VALID (known limit: no range check)
  Row 56      : duplicate transaction_id (=row 1)  -> SKIPPED
  Row 57      : completely empty row               -> INVALID
  Row 58      : extra unexpected column populated  -> VALID (extra columns ignored)
  Row 59      : malformed timestamp                -> INVALID
  Row 60      : missing country                    -> INVALID
  Row 61      : missing payment_method             -> INVALID
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(14)

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "test_dirty_data_scan.csv")

COUNTRIES = ["US", "GB", "DE", "AU", "CA", "RU", "CN", "NG"]
PAYMENT_METHODS = ["credit_card", "debit_card", "digital_wallet", "bank_transfer"]
MERCHANT_CATEGORIES = ["grocery", "electronics", "gaming", "travel", "retail"]
BASE_DATE = datetime(2024, 1, 1, 0, 0, 0)

FIELDNAMES = [
    "transaction_id",
    "amount",
    "timestamp",
    "country",
    "payment_method",
    "merchant_category",
    "device_id",
    "extra_unexpected_column",
]


def _ts(idx: int) -> str:
    dt = BASE_DATE + timedelta(days=idx % 365, hours=idx % 24, minutes=idx % 60)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _clean(idx: int) -> dict:
    return {
        "transaction_id": f"clean_{idx:04d}",
        "amount": round(random.uniform(5.0, 2000.0), 2),
        "timestamp": _ts(idx),
        "country": random.choice(COUNTRIES),
        "payment_method": random.choice(PAYMENT_METHODS),
        "merchant_category": random.choice(MERCHANT_CATEGORIES),
        "device_id": f"dev_{random.randint(1000, 9999)}",
        "extra_unexpected_column": "",
    }


def main() -> None:
    rows: list[dict] = []

    # Rows 1-50: clean baseline
    for i in range(1, 51):
        rows.append(_clean(i))

    # Row 51: missing transaction_id
    rows.append({
        "transaction_id": "",
        "amount": "250.00",
        "timestamp": _ts(51),
        "country": "US",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "device_id": "dev_5100",
        "extra_unexpected_column": "",
    })

    # Row 52: blank amount
    rows.append({
        "transaction_id": "dirty_052",
        "amount": "",
        "timestamp": _ts(52),
        "country": "US",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "device_id": "dev_5200",
        "extra_unexpected_column": "",
    })

    # Row 53: non-numeric amount
    rows.append({
        "transaction_id": "dirty_053",
        "amount": "not-a-number",
        "timestamp": _ts(53),
        "country": "US",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "device_id": "dev_5300",
        "extra_unexpected_column": "",
    })

    # Row 54: negative amount (known limit: no range check, passes as VALID)
    rows.append({
        "transaction_id": "dirty_054",
        "amount": "-150.00",
        "timestamp": _ts(54),
        "country": "US",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "device_id": "dev_5400",
        "extra_unexpected_column": "",
    })

    # Row 55: extremely large amount (known limit: no range check, passes as VALID)
    rows.append({
        "transaction_id": "dirty_055",
        "amount": "9999999999.99",
        "timestamp": _ts(55),
        "country": "US",
        "payment_method": "bank_transfer",
        "merchant_category": "travel",
        "device_id": "dev_5500",
        "extra_unexpected_column": "",
    })

    # Row 56: duplicate of row 1 transaction_id -> SKIPPED
    rows.append({
        "transaction_id": "clean_0001",
        "amount": "500.00",
        "timestamp": _ts(56),
        "country": "GB",
        "payment_method": "credit_card",
        "merchant_category": "retail",
        "device_id": "dev_5600",
        "extra_unexpected_column": "",
    })

    # Row 57: completely empty row -> INVALID
    rows.append({
        "transaction_id": "",
        "amount": "",
        "timestamp": "",
        "country": "",
        "payment_method": "",
        "merchant_category": "",
        "device_id": "",
        "extra_unexpected_column": "",
    })

    # Row 58: extra_unexpected_column populated -> VALID (extra columns silently ignored)
    rows.append({
        "transaction_id": "dirty_058",
        "amount": "75.00",
        "timestamp": _ts(58),
        "country": "DE",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "device_id": "dev_5800",
        "extra_unexpected_column": "unexpected_value_xyz",
    })

    # Row 59: malformed timestamp -> INVALID
    rows.append({
        "transaction_id": "dirty_059",
        "amount": "200.00",
        "timestamp": "not-a-timestamp",
        "country": "US",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "device_id": "dev_5900",
        "extra_unexpected_column": "",
    })

    # Row 60: missing country -> INVALID
    rows.append({
        "transaction_id": "dirty_060",
        "amount": "300.00",
        "timestamp": _ts(60),
        "country": "",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "device_id": "dev_6000",
        "extra_unexpected_column": "",
    })

    # Row 61: missing payment_method -> INVALID
    rows.append({
        "transaction_id": "dirty_061",
        "amount": "400.00",
        "timestamp": _ts(61),
        "country": "AU",
        "payment_method": "",
        "merchant_category": "retail",
        "device_id": "dev_6100",
        "extra_unexpected_column": "",
    })

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    clean = 50
    dirty_valid = 3   # rows 54 (negative), 55 (large amount), 58 (extra column)
    dirty_invalid = 7  # rows 51, 52, 53, 57, 59, 60, 61
    dirty_skipped = 1  # row 56 (duplicate)

    print(f"Generated {total} rows -> {OUTPUT_PATH}")
    print(f"  Clean baseline rows   : {clean}")
    print(f"  Dirty -> expected VALID    : {dirty_valid}  (rows 54, 55, 58 -- known limits / extra column)")
    print(f"  Dirty -> expected INVALID  : {dirty_invalid}  (rows 51, 52, 53, 57, 59, 60, 61)")
    print(f"  Dirty -> expected SKIPPED  : {dirty_skipped}  (row 56 -- duplicate transaction_id)")
    print(f"  Expected total valid       : {clean + dirty_valid}")
    print(f"  Expected total invalid     : {dirty_invalid}")
    print(f"  Expected total skipped     : {dirty_skipped}")
    print("Note: generated CSV is gitignored and must not be committed.")


if __name__ == "__main__":
    main()
