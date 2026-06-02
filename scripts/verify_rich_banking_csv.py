"""
Verify a rich synthetic banking CSV produced by generate_rich_banking_csv.py.

Checks:
  - File exists and parses as CSV
  - All 5 legacy required columns present
  - All 42 output columns present
  - Row count > 0, no missing transaction_id, all IDs unique
  - scenario_family populated and from known set
  - expected_priority in {P0, P1, P2, P3}
  - synthetic_fraud_label in {0, 1}
  - amount is numeric on all rows
  - Prints scenario, priority, and fraud-label distributions

Usage:
  python scripts/verify_rich_banking_csv.py <path/to/file.csv>
"""

import csv
import os
import sys
from collections import Counter

# ---------------------------------------------------------------------------
# Column sets
# ---------------------------------------------------------------------------

REQUIRED_LEGACY = {
    "transaction_id", "amount", "timestamp", "country", "payment_method",
}

ALL_EXPECTED_COLUMNS = [
    "transaction_id", "amount", "timestamp", "country", "payment_method",
    "event_timestamp", "account_id", "customer_id", "merchant_id",
    "currency", "account_balance_before", "account_balance_after",
    "daily_spend_to_date", "available_limit",
    "channel", "device_id", "device_type", "device_trust_score",
    "ip_country", "billing_country", "shipping_country", "geo_distance_km",
    "is_international",
    "merchant_category", "merchant_risk_score", "merchant_country",
    "counterparty_age_days", "new_payee_flag",
    "customer_tenure_days", "avg_transaction_amount_30d",
    "txn_count_1h", "txn_count_24h", "failed_attempts_1h", "chargeback_count_90d",
    "scenario_label", "scenario_family", "synthetic_fraud_label",
    "rule_trigger_count", "primary_risk_reason",
    "expected_priority", "recommended_action", "analyst_queue_hint",
]

VALID_SCENARIO_FAMILIES = {
    "normal",
    "account_takeover",
    "card_testing",
    "high_velocity_spend",
    "unusual_geography",
    "new_payee_transfer",
    "merchant_risk_spike",
    "mule_account_behaviour",
    "refund_chargeback_abuse",
    "dormant_account_reactivation",
    "cross_border_high_value",
    "device_mismatch",
    "suspicious_repeated_attempts",
}

VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(msg: str)   -> None: print(f"  OK    {msg}")
def _fail(msg: str) -> None: print(f"  FAIL  {msg}")
def _info(msg: str) -> None: print(f"        {msg}")


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def verify(path: str) -> bool:
    print(f"\nVerifying: {path}")
    print("-" * 62)

    if not os.path.isfile(path):
        _fail(f"File not found: {path}")
        return False
    _ok("File exists")

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            headers = list(reader.fieldnames or [])
            rows = list(reader)
    except Exception as exc:
        _fail(f"CSV parse error: {exc}")
        return False
    _ok(f"CSV parsed — {len(rows):,} data rows, {len(headers)} columns")

    passed = True

    # 1. Legacy required columns
    missing_legacy = REQUIRED_LEGACY - set(headers)
    if missing_legacy:
        _fail(f"Missing legacy required columns: {sorted(missing_legacy)}")
        passed = False
    else:
        _ok("All 5 legacy required columns present")

    # 2. All expected columns
    missing_rich = [c for c in ALL_EXPECTED_COLUMNS if c not in headers]
    if missing_rich:
        _fail(f"Missing {len(missing_rich)} expected columns: {missing_rich}")
        passed = False
    else:
        _ok(f"All {len(ALL_EXPECTED_COLUMNS)} expected columns present")

    # 3. Row count
    if len(rows) == 0:
        _fail("No data rows found")
        return False
    _ok(f"Row count: {len(rows):,}")

    # 4. No blank transaction_id
    blank_tid = sum(1 for r in rows if not r.get("transaction_id", "").strip())
    if blank_tid:
        _fail(f"Missing transaction_id on {blank_tid:,} rows")
        passed = False
    else:
        _ok("All rows have transaction_id")

    # 5. Unique transaction_ids
    tids = [r["transaction_id"] for r in rows]
    dups = len(tids) - len(set(tids))
    if dups:
        _fail(f"Duplicate transaction_ids: {dups:,}")
        passed = False
    else:
        _ok("All transaction_ids unique")

    # 6. scenario_family valid
    bad_sf = [r["transaction_id"] for r in rows
              if r.get("scenario_family", "") not in VALID_SCENARIO_FAMILIES]
    if bad_sf:
        _fail(f"Invalid scenario_family on {len(bad_sf):,} rows (first: {bad_sf[0]})")
        passed = False
    else:
        _ok("All scenario_family values valid")

    # 7. expected_priority valid
    bad_ep = [r["transaction_id"] for r in rows
              if r.get("expected_priority", "") not in VALID_PRIORITIES]
    if bad_ep:
        _fail(f"Invalid expected_priority on {len(bad_ep):,} rows (first: {bad_ep[0]})")
        passed = False
    else:
        _ok("All expected_priority values valid (P0/P1/P2/P3)")

    # 8. synthetic_fraud_label in {0, 1}
    bad_lbl = [r["transaction_id"] for r in rows
               if str(r.get("synthetic_fraud_label", "")).strip() not in {"0", "1"}]
    if bad_lbl:
        _fail(f"Invalid synthetic_fraud_label on {len(bad_lbl):,} rows")
        passed = False
    else:
        _ok("All synthetic_fraud_label values in {0, 1}")

    # 9. amount is numeric
    bad_amt = []
    for r in rows:
        try:
            float(r.get("amount", ""))
        except (ValueError, TypeError):
            bad_amt.append(r.get("transaction_id", "?"))
    if bad_amt:
        _fail(f"Non-numeric amount on {len(bad_amt):,} rows")
        passed = False
    else:
        _ok("All amount values numeric")

    # ---------------------------------------------------------------------------
    # Distributions
    # ---------------------------------------------------------------------------
    n = len(rows)
    scenarios  = Counter(r["scenario_family"]       for r in rows)
    priorities = Counter(r["expected_priority"]     for r in rows)
    labels     = Counter(str(r["synthetic_fraud_label"]) for r in rows)

    print()
    print("  Scenario distribution:")
    for fam, cnt in sorted(scenarios.items(), key=lambda x: -x[1]):
        _info(f"{fam:<35} {cnt:>6,}  ({cnt/n*100:.1f}%)")

    print()
    print("  Expected priority:")
    for tier in ["P0", "P1", "P2", "P3"]:
        cnt = priorities.get(tier, 0)
        _info(f"{tier}  {cnt:>6,}  ({cnt/n*100:.1f}%)")

    print()
    print("  Fraud label:")
    for lbl, name in [("0", "Legitimate"), ("1", "Fraud     ")]:
        cnt = labels.get(lbl, 0)
        _info(f"{name} ({lbl})  {cnt:>6,}  ({cnt/n*100:.1f}%)")

    print()
    result = "PASSED" if passed else "FAILED"
    line = f"  Result: {result}"
    print(line)
    print("-" * 62)
    return passed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <csv_path>")
        sys.exit(1)
    ok = verify(sys.argv[1])
    sys.exit(0 if ok else 1)
