"""
Verify an adversarial synthetic fraud CSV produced by generate_adversarial_csv.py.

Tier 1 checks (schema and integrity):
  - File exists and parses as CSV
  - All 42 expected columns present in correct order
  - All 5 legacy required columns present
  - Row count > 0, no blank transaction_id, all IDs unique
  - scenario_family only from adversarial set
  - expected_priority in {P0, P1, P2, P3}
  - synthetic_fraud_label in {0, 1}
  - amount numeric on every row

Tier 2 checks (evasion constraint verification):
  - low_and_slow: amount < 1000, hour 09-17, low-risk country,
    device_trust_score >= 0.60, geo_distance_km <= 150, txn_count_1h <= 3
  - victim_mirror: amount < 2.5x avg_transaction_amount_30d,
    device_trust_score >= 0.42, geo_distance_km < 500, failed_attempts_1h == 0
  - threshold_straddle: amount in [850, 1000), device_trust_score in [0.40, 0.45],
    geo_distance_km in [480, 500], txn_count_1h in [4, 5],
    failed_attempts_1h in [2, 3], merchant_risk_score in [0.55, 0.70]
  - graph_evasion_fan_in: each shared merchant_id has exactly 3 distinct account_ids;
    device_ids unique across each cluster
  - graph_evasion_fan_in_detected: each shared merchant_id has exactly 4 distinct account_ids

Usage:
  python scripts/verify_adversarial_csv.py <path/to/file.csv>

Exit codes: 0 on full pass, 1 on any failure.
"""

import csv
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Expected schema (identical order to generate_adversarial_csv.py)
# ---------------------------------------------------------------------------
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

REQUIRED_LEGACY = {
    "transaction_id", "amount", "timestamp", "country", "payment_method",
}

VALID_ADVERSARIAL_FAMILIES = {
    "low_and_slow",
    "victim_mirror",
    "threshold_straddle",
    "graph_evasion_fan_in",
    "graph_evasion_fan_in_detected",
}

VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}

LOW_RISK_COUNTRIES = {"US", "GB", "DE", "FR", "AU", "CA", "NL", "JP", "SE", "CH"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(msg: str)   -> None: print(f"  [OK]    {msg}")
def _fail(msg: str) -> None: print(f"  [FAIL]  {msg}")
def _info(msg: str) -> None: print(f"          {msg}")


def _safe_float(val: str, default: float = 0.0) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: str, default: int = 0) -> int:
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def _hour(ts: str) -> int:
    try:
        return datetime.strptime(ts.strip(), "%Y-%m-%dT%H:%M:%S").hour
    except Exception:
        return -1


# ---------------------------------------------------------------------------
# Main verifier
# ---------------------------------------------------------------------------

def verify(path: str) -> bool:
    print(f"\nVerifying: {path}")
    print("=" * 65)

    # -----------------------------------------------------------------------
    # Parse
    # -----------------------------------------------------------------------
    if not os.path.isfile(path):
        _fail(f"File not found: {path}")
        return False
    _ok("File exists")

    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader  = csv.DictReader(f)
            headers = list(reader.fieldnames or [])
            rows    = list(reader)
    except Exception as exc:
        _fail(f"CSV parse error: {exc}")
        return False
    _ok(f"CSV parsed -- {len(rows):,} data rows, {len(headers)} columns")

    passed = True

    # -----------------------------------------------------------------------
    # Tier 1 -- Schema and integrity
    # -----------------------------------------------------------------------
    print()
    print("-- Tier 1: Schema and integrity --")

    # Legacy required columns
    missing_legacy = REQUIRED_LEGACY - set(headers)
    if missing_legacy:
        _fail(f"Missing legacy required columns: {sorted(missing_legacy)}")
        passed = False
    else:
        _ok("All 5 legacy required columns present")

    # All 42 expected columns present
    missing_cols = [c for c in ALL_EXPECTED_COLUMNS if c not in headers]
    if missing_cols:
        _fail(f"Missing {len(missing_cols)} expected columns: {missing_cols}")
        passed = False
    else:
        _ok(f"All {len(ALL_EXPECTED_COLUMNS)} expected columns present")

    # Column order matches
    actual_order    = [h for h in headers if h in set(ALL_EXPECTED_COLUMNS)]
    expected_order  = [c for c in ALL_EXPECTED_COLUMNS if c in set(headers)]
    if actual_order != expected_order:
        _fail("Column order does not match expected schema order")
        passed = False
    else:
        _ok("Column order matches schema")

    # Row count
    if len(rows) == 0:
        _fail("No data rows found")
        return False
    _ok(f"Row count: {len(rows):,}")

    # No blank transaction_id
    blank_tid = [r for r in rows if not r.get("transaction_id", "").strip()]
    if blank_tid:
        _fail(f"Missing transaction_id on {len(blank_tid):,} rows")
        passed = False
    else:
        _ok("All rows have transaction_id")

    # Unique transaction_ids
    tids = [r["transaction_id"] for r in rows]
    dups = len(tids) - len(set(tids))
    if dups:
        _fail(f"Duplicate transaction_ids: {dups:,}")
        passed = False
    else:
        _ok("All transaction_ids unique")

    # scenario_family from adversarial set
    bad_sf = [r["transaction_id"] for r in rows
              if r.get("scenario_family", "") not in VALID_ADVERSARIAL_FAMILIES]
    if bad_sf:
        _fail(f"Invalid scenario_family on {len(bad_sf):,} rows "
              f"(first 3: {bad_sf[:3]})")
        passed = False
    else:
        _ok("All scenario_family values are adversarial families")

    # expected_priority valid
    bad_ep = [r["transaction_id"] for r in rows
              if r.get("expected_priority", "") not in VALID_PRIORITIES]
    if bad_ep:
        _fail(f"Invalid expected_priority on {len(bad_ep):,} rows")
        passed = False
    else:
        _ok("All expected_priority values valid (P0/P1/P2/P3)")

    # synthetic_fraud_label in {0, 1}
    bad_lbl = [r["transaction_id"] for r in rows
               if str(r.get("synthetic_fraud_label", "")).strip() not in {"0", "1"}]
    if bad_lbl:
        _fail(f"Invalid synthetic_fraud_label on {len(bad_lbl):,} rows")
        passed = False
    else:
        _ok("All synthetic_fraud_label values in {0, 1}")

    # amount numeric
    bad_amt = [r["transaction_id"] for r in rows
               if not _is_numeric(r.get("amount", ""))]
    if bad_amt:
        _fail(f"Non-numeric amount on {len(bad_amt):,} rows")
        passed = False
    else:
        _ok("All amount values numeric")

    # -----------------------------------------------------------------------
    # Tier 2 -- Evasion constraint checks
    # -----------------------------------------------------------------------
    print()
    print("-- Tier 2: Evasion constraint checks --")

    by_family = defaultdict(list)
    for r in rows:
        by_family[r.get("scenario_family", "")].append(r)

    # -- low_and_slow --
    fam_rows = by_family.get("low_and_slow", [])
    if fam_rows:
        violations = _check_low_and_slow(fam_rows)
        if violations:
            _fail(f"low_and_slow: {len(violations)} evasion violation(s)")
            for msg in violations[:3]:
                _info(msg)
            passed = False
        else:
            _ok(f"low_and_slow evasion constraints satisfied ({len(fam_rows)} rows)")

    # -- victim_mirror --
    fam_rows = by_family.get("victim_mirror", [])
    if fam_rows:
        violations = _check_victim_mirror(fam_rows)
        if violations:
            _fail(f"victim_mirror: {len(violations)} evasion violation(s)")
            for msg in violations[:3]:
                _info(msg)
            passed = False
        else:
            _ok(f"victim_mirror evasion constraints satisfied ({len(fam_rows)} rows)")

    # -- threshold_straddle --
    fam_rows = by_family.get("threshold_straddle", [])
    if fam_rows:
        violations = _check_threshold_straddle(fam_rows)
        if violations:
            _fail(f"threshold_straddle: {len(violations)} evasion violation(s)")
            for msg in violations[:3]:
                _info(msg)
            passed = False
        else:
            _ok(f"threshold_straddle evasion constraints satisfied ({len(fam_rows)} rows)")

    # -- graph_evasion_fan_in --
    fam_rows = by_family.get("graph_evasion_fan_in", [])
    if fam_rows:
        violations = _check_graph_evasion(fam_rows, expected_accounts=3,
                                          family="graph_evasion_fan_in")
        if violations:
            _fail(f"graph_evasion_fan_in: {len(violations)} cluster violation(s)")
            for msg in violations[:3]:
                _info(msg)
            passed = False
        else:
            _ok(f"graph_evasion_fan_in cluster structure valid ({len(fam_rows)} rows, "
                f"{len(fam_rows)//3} clusters of 3)")

    # -- graph_evasion_fan_in_detected --
    fam_rows = by_family.get("graph_evasion_fan_in_detected", [])
    if fam_rows:
        violations = _check_graph_evasion(fam_rows, expected_accounts=4,
                                          family="graph_evasion_fan_in_detected")
        if violations:
            _fail(f"graph_evasion_fan_in_detected: {len(violations)} cluster violation(s)")
            for msg in violations[:3]:
                _info(msg)
            passed = False
        else:
            _ok(f"graph_evasion_fan_in_detected cluster structure valid ({len(fam_rows)} rows, "
                f"{len(fam_rows)//4} clusters of 4)")

    # -----------------------------------------------------------------------
    # Distributions
    # -----------------------------------------------------------------------
    n = len(rows)
    scenarios  = Counter(r["scenario_family"]   for r in rows)
    priorities = Counter(r["expected_priority"] for r in rows)

    print()
    print("  Scenario distribution:")
    for fam, cnt in sorted(scenarios.items(), key=lambda x: -x[1]):
        _info(f"{fam:<44} {cnt:>6,}  ({cnt/n*100:.1f}%)")

    print()
    print("  Expected priority distribution:")
    for tier in ["P0", "P1", "P2", "P3"]:
        cnt = priorities.get(tier, 0)
        _info(f"{tier}  {cnt:>6,}  ({cnt/n*100:.1f}%)")

    # -----------------------------------------------------------------------
    # Result
    # -----------------------------------------------------------------------
    print()
    result = "PASSED" if passed else "FAILED"
    print(f"  Result: {result}")
    print("=" * 65)
    return passed


# ---------------------------------------------------------------------------
# Evasion constraint check functions
# ---------------------------------------------------------------------------

def _is_numeric(val: str) -> bool:
    try:
        float(val)
        return True
    except (ValueError, TypeError):
        return False


def _check_low_and_slow(rows: list) -> list:
    violations = []
    for r in rows:
        tid   = r["transaction_id"]
        amt   = _safe_float(r.get("amount", ""))
        hr    = _hour(r.get("timestamp", ""))
        cntry = r.get("country", "")
        dts   = _safe_float(r.get("device_trust_score", ""))
        geo   = _safe_float(r.get("geo_distance_km", ""))
        vel   = _safe_int(r.get("txn_count_1h", ""))

        if amt >= 1000:
            violations.append(f"{tid}: amount {amt:.2f} >= 1000 (threshold not evaded)")
        if not (9 <= hr <= 17):
            violations.append(f"{tid}: hour {hr} not in 09-17 (night signal risk)")
        if cntry not in LOW_RISK_COUNTRIES:
            violations.append(f"{tid}: country '{cntry}' not low-risk")
        if dts < 0.60:
            violations.append(f"{tid}: device_trust_score {dts:.3f} < 0.60")
        if geo > 150:
            violations.append(f"{tid}: geo_distance_km {geo:.1f} > 150")
        if vel > 3:
            violations.append(f"{tid}: txn_count_1h {vel} > 3")
    return violations


def _check_victim_mirror(rows: list) -> list:
    violations = []
    for r in rows:
        tid     = r["transaction_id"]
        amt     = _safe_float(r.get("amount", ""))
        avg_amt = _safe_float(r.get("avg_transaction_amount_30d", ""))
        dts     = _safe_float(r.get("device_trust_score", ""))
        geo     = _safe_float(r.get("geo_distance_km", ""))
        fails   = _safe_int(r.get("failed_attempts_1h", ""))

        if avg_amt > 0 and amt >= 2.5 * avg_amt:
            violations.append(
                f"{tid}: amount {amt:.2f} >= 2.5x avg {avg_amt:.2f} "
                f"(ratio {amt/avg_amt:.2f}; anomaly threshold risk)"
            )
        if dts < 0.42:
            violations.append(f"{tid}: device_trust_score {dts:.3f} < 0.42")
        if geo >= 500:
            violations.append(f"{tid}: geo_distance_km {geo:.1f} >= 500 (geo anomaly fires)")
        if fails != 0:
            violations.append(f"{tid}: failed_attempts_1h {fails} != 0")
    return violations


def _check_threshold_straddle(rows: list) -> list:
    violations = []
    for r in rows:
        tid  = r["transaction_id"]
        amt  = _safe_float(r.get("amount", ""))
        dts  = _safe_float(r.get("device_trust_score", ""))
        geo  = _safe_float(r.get("geo_distance_km", ""))
        vel  = _safe_int(r.get("txn_count_1h", ""))
        fail = _safe_int(r.get("failed_attempts_1h", ""))
        mrs  = _safe_float(r.get("merchant_risk_score", ""))

        if not (850 <= amt < 1000):
            violations.append(f"{tid}: amount {amt:.2f} not in [850, 1000)")
        if not (0.40 <= dts <= 0.45):
            violations.append(f"{tid}: device_trust_score {dts:.3f} not in [0.40, 0.45]")
        if not (480 <= geo <= 500):
            violations.append(f"{tid}: geo_distance_km {geo:.1f} not in [480, 500]")
        if not (4 <= vel <= 5):
            violations.append(f"{tid}: txn_count_1h {vel} not in [4, 5]")
        if not (2 <= fail <= 3):
            violations.append(f"{tid}: failed_attempts_1h {fail} not in [2, 3]")
        if not (0.55 <= mrs <= 0.70):
            violations.append(f"{tid}: merchant_risk_score {mrs:.3f} not in [0.55, 0.70]")
    return violations


def _check_graph_evasion(rows: list, expected_accounts: int, family: str) -> list:
    """
    Group rows by merchant_id. Each shared merchant must have exactly
    `expected_accounts` distinct account_ids. Device IDs must be unique per cluster.
    """
    violations = []

    by_merchant: dict = defaultdict(list)
    for r in rows:
        by_merchant[r.get("merchant_id", "")].append(r)

    for merch_id, cluster_rows in by_merchant.items():
        acct_ids   = {r.get("account_id", "") for r in cluster_rows}
        device_ids = [r.get("device_id", "") for r in cluster_rows]
        n_accounts = len(acct_ids)

        if n_accounts != expected_accounts:
            violations.append(
                f"merchant {merch_id}: expected {expected_accounts} distinct account_ids, "
                f"got {n_accounts}"
            )

        dup_devices = len(device_ids) - len(set(device_ids))
        if dup_devices:
            violations.append(
                f"merchant {merch_id}: {dup_devices} duplicate device_id(s) in cluster"
            )

    return violations


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <csv_path>")
        sys.exit(1)
    ok = verify(sys.argv[1])
    sys.exit(0 if ok else 1)
