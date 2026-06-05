"""
Adversarial synthetic fraud generator -- Phase 16B.

Generates adversarial CSV datasets designed to evade the current fraud intelligence stack.
Scenarios are defined by evasion constraints, not by the signals they trigger.
See docs/ADVERSARIAL_FRAUD_DESIGN.md for the full design contract.

All data is synthetic. No real banking data is used or implied.

Usage:
  python scripts/generate_adversarial_csv.py --rows 1000 --seed 42
  python scripts/generate_adversarial_csv.py --rows 1000 --seed 99 --output C:\\tmp\\adv.csv
"""

import argparse
import csv
import os
import random
import sys
from collections import Counter
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Output columns -- 42 total (identical order to generate_rich_banking_csv.py)
# ---------------------------------------------------------------------------
FIELDNAMES = [
    # Required by current risk scan validator (legacy)
    "transaction_id",
    "amount",
    "timestamp",
    "country",
    "payment_method",
    # Transaction Identity (rich)
    "event_timestamp",
    "account_id",
    "customer_id",
    "merchant_id",
    # Monetary
    "currency",
    "account_balance_before",
    "account_balance_after",
    "daily_spend_to_date",
    "available_limit",
    # Channel / Device
    "channel",
    "device_id",
    "device_type",
    "device_trust_score",
    "ip_country",
    "billing_country",
    "shipping_country",
    "geo_distance_km",
    "is_international",
    # Merchant / Counterparty
    "merchant_category",
    "merchant_risk_score",
    "merchant_country",
    "counterparty_age_days",
    "new_payee_flag",
    # Customer Behaviour
    "customer_tenure_days",
    "avg_transaction_amount_30d",
    "txn_count_1h",
    "txn_count_24h",
    "failed_attempts_1h",
    "chargeback_count_90d",
    # Fraud Scenario
    "scenario_label",
    "scenario_family",
    "synthetic_fraud_label",
    "rule_trigger_count",
    "primary_risk_reason",
    # Operational
    "expected_priority",
    "recommended_action",
    "analyst_queue_hint",
]

# ---------------------------------------------------------------------------
# Reference data (self-contained -- does not import from rich generator)
# ---------------------------------------------------------------------------
LOW_RISK_COUNTRIES  = ["US", "GB", "DE", "FR", "AU", "CA", "NL", "JP", "SE", "CH"]
HIGH_RISK_COUNTRIES = ["RU", "CN", "NG", "PK", "VN", "UA", "KE", "ID", "BY", "IR"]

HIGH_RISK_PAYMENT_METHODS = {"credit_card", "digital_wallet"}

NORMAL_CATEGORIES = ["grocery", "food", "retail", "healthcare", "utilities"]

HOME_CURRENCIES = {
    "US": "USD", "GB": "GBP", "DE": "EUR", "FR": "EUR",
    "AU": "AUD", "CA": "CAD", "NL": "EUR", "JP": "JPY",
    "SE": "SEK", "CH": "CHF",
}

HIGH_AMOUNT_THRESHOLD = 1000.0
BASE_DATE = datetime(2024, 1, 1)

# ---------------------------------------------------------------------------
# Cluster sizes for graph evasion scenarios
# ---------------------------------------------------------------------------
GRAPH_CLUSTER_SIZES = {
    "graph_evasion_fan_in":          3,
    "graph_evasion_fan_in_detected": 4,
}

VALID_ADVERSARIAL_FAMILIES = {
    "low_and_slow",
    "victim_mirror",
    "threshold_straddle",
    "graph_evasion_fan_in",
    "graph_evasion_fan_in_detected",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hex8() -> str:
    return format(random.randint(0, 0xFFFFFFFF), "08x")


def _ts(hour_min: int = 0, hour_max: int = 23) -> str:
    hour = random.randint(hour_min, hour_max)
    dt = BASE_DATE + timedelta(
        days=random.randint(0, 364),
        hours=hour,
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _is_night(ts: str) -> bool:
    h = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").hour
    return h < 6 or h > 22


def _rule_count(row: dict) -> int:
    """Count how many legacy deterministic rule conditions fire for this row."""
    n = 0
    amount   = float(row["amount"])
    is_high  = amount > HIGH_AMOUNT_THRESHOLD
    is_night = _is_night(row["timestamp"])
    is_intl  = str(row.get("is_international", "false")).lower() in ("true", "1")
    is_hr_c  = row.get("country", "US") in set(HIGH_RISK_COUNTRIES)
    is_hr_pm = row.get("payment_method", "") in HIGH_RISK_PAYMENT_METHODS
    if is_high and is_night:
        n += 1
    if is_high and is_intl and is_hr_c:
        n += 1
    if is_hr_pm and is_night and is_high:
        n += 1
    return n


# ---------------------------------------------------------------------------
# Scenario generators
# ---------------------------------------------------------------------------

def gen_low_and_slow(idx: int, instance: int) -> dict:
    """
    Low-and-slow amount splitting.
    Evades: HIGH_AMOUNT_THRESHOLD rule, night signal, country signal, device/geo/velocity.
    All values kept safely below detection thresholds.
    """
    home       = random.choice(LOW_RISK_COUNTRIES)
    avg_amount = round(random.uniform(600, 900), 2)
    amount     = round(random.uniform(750, 980), 2)
    bal_bef    = round(random.uniform(1000, 10000), 2)
    ts         = _ts(9, 17)

    row = {
        "transaction_id":            f"adv_{idx:08d}",
        "amount":                    amount,
        "timestamp":                 ts,
        "country":                   home,
        "payment_method":            "bank_transfer",
        "event_timestamp":           ts,
        "account_id":                f"acct_{_hex8()}",
        "customer_id":               f"cust_{_hex8()}",
        "merchant_id":               f"merch_{_hex8()}",
        "currency":                  HOME_CURRENCIES.get(home, "USD"),
        "account_balance_before":    bal_bef,
        "account_balance_after":     round(bal_bef - amount, 2),
        "daily_spend_to_date":       round(random.uniform(200, 800), 2),
        "available_limit":           round(random.uniform(5000, 15000), 2),
        "channel":                   random.choice(["web", "mobile_app"]),
        "device_id":                 f"dev_{_hex8()}",
        "device_type":               random.choice(["desktop", "mobile"]),
        "device_trust_score":        round(random.uniform(0.60, 0.92), 3),
        "ip_country":                home,
        "billing_country":           home,
        "shipping_country":          home,
        "geo_distance_km":           round(random.uniform(10, 150), 1),
        "is_international":          "false",
        "merchant_category":         random.choice(NORMAL_CATEGORIES),
        "merchant_risk_score":       round(random.uniform(0.05, 0.30), 3),
        "merchant_country":          home,
        "counterparty_age_days":     random.randint(60, 730),
        "new_payee_flag":            "false",
        "customer_tenure_days":      random.randint(180, 3000),
        "avg_transaction_amount_30d": avg_amount,
        "txn_count_1h":              random.randint(0, 3),
        "txn_count_24h":             random.randint(1, 5),
        "failed_attempts_1h":        0,
        "chargeback_count_90d":      0,
        "scenario_label":            f"low_and_slow_{instance:04d}",
        "scenario_family":           "low_and_slow",
        "synthetic_fraud_label":     1,
        "rule_trigger_count":        0,
        "primary_risk_reason":       "LOW_AND_SLOW_AMOUNT_SPLITTING",
        "expected_priority":         "P3",
        "recommended_action":        "APPROVE",
        "analyst_queue_hint":        "Sub-threshold repeated transfer; review for accumulation pattern",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_victim_mirror(idx: int, instance: int) -> dict:
    """
    Victim profile mirroring.
    Evades: is_amount_anomaly (3x threshold), is_low_trust_device (< 0.40),
    is_geo_anomaly (> 500km), behavioural boost (deviation ratios too small).
    """
    home       = random.choice(LOW_RISK_COUNTRIES)
    avg_amount = round(random.uniform(80, 400), 2)
    multiplier = round(random.uniform(1.10, 2.40), 2)
    amount     = round(avg_amount * multiplier, 2)
    bal_bef    = round(random.uniform(500, 8000), 2)
    ts         = _ts(8, 20)

    row = {
        "transaction_id":            f"adv_{idx:08d}",
        "amount":                    amount,
        "timestamp":                 ts,
        "country":                   home,
        "payment_method":            random.choices(
                                         ["debit_card", "bank_transfer"],
                                         weights=[60, 40]
                                     )[0],
        "event_timestamp":           ts,
        "account_id":                f"acct_{_hex8()}",
        "customer_id":               f"cust_{_hex8()}",
        "merchant_id":               f"merch_{_hex8()}",
        "currency":                  HOME_CURRENCIES.get(home, "USD"),
        "account_balance_before":    bal_bef,
        "account_balance_after":     round(bal_bef - amount, 2),
        "daily_spend_to_date":       round(random.uniform(0, amount * 0.5), 2),
        "available_limit":           round(random.uniform(3000, 12000), 2),
        "channel":                   random.choice(["mobile_app", "web"]),
        "device_id":                 f"dev_{_hex8()}",
        "device_type":               random.choice(["mobile", "desktop"]),
        "device_trust_score":        round(random.uniform(0.42, 0.70), 3),
        "ip_country":                home,
        "billing_country":           home,
        "shipping_country":          home,
        "geo_distance_km":           round(random.uniform(50, 480), 1),
        "is_international":          "false",
        "merchant_category":         random.choice(NORMAL_CATEGORIES),
        "merchant_risk_score":       round(random.uniform(0.05, 0.30), 3),
        "merchant_country":          home,
        "counterparty_age_days":     random.randint(30, 365),
        "new_payee_flag":            "false",
        "customer_tenure_days":      random.randint(180, 3000),
        "avg_transaction_amount_30d": avg_amount,
        "txn_count_1h":              random.randint(2, 4),
        "txn_count_24h":             random.randint(1, 6),
        "failed_attempts_1h":        0,
        "chargeback_count_90d":      0,
        "scenario_label":            f"victim_mirror_{instance:04d}",
        "scenario_family":           "victim_mirror",
        "synthetic_fraud_label":     1,
        "rule_trigger_count":        0,
        "primary_risk_reason":       "VICTIM_PROFILE_MIRRORING",
        "expected_priority":         "P3",
        "recommended_action":        "APPROVE",
        "analyst_queue_hint":        "Amount within historical profile; evasion via mirroring suspected",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_threshold_straddle(idx: int, instance: int) -> dict:
    """
    Compound threshold straddling.
    Simultaneously evades all six rich signal thresholds:
      device_trust_score < 0.40, geo_distance_km > 500, txn_count_1h > 5,
      failed_attempts_1h >= 4, merchant_risk_score >= 0.70, amount > 1000.
    """
    home       = random.choice(LOW_RISK_COUNTRIES)
    avg_amount = round(random.uniform(350, 400), 2)
    amount     = round(random.uniform(850, 999), 2)
    bal_bef    = round(random.uniform(1000, 10000), 2)
    ts         = _ts(7, 21)

    row = {
        "transaction_id":            f"adv_{idx:08d}",
        "amount":                    amount,
        "timestamp":                 ts,
        "country":                   home,
        "payment_method":            random.choice(["debit_card", "bank_transfer"]),
        "event_timestamp":           ts,
        "account_id":                f"acct_{_hex8()}",
        "customer_id":               f"cust_{_hex8()}",
        "merchant_id":               f"merch_{_hex8()}",
        "currency":                  HOME_CURRENCIES.get(home, "USD"),
        "account_balance_before":    bal_bef,
        "account_balance_after":     round(bal_bef - amount, 2),
        "daily_spend_to_date":       round(random.uniform(200, 600), 2),
        "available_limit":           round(random.uniform(3000, 12000), 2),
        "channel":                   random.choice(["web", "mobile_app"]),
        "device_id":                 f"dev_{_hex8()}",
        "device_type":               random.choice(["desktop", "mobile"]),
        "device_trust_score":        round(random.uniform(0.41, 0.44), 3),
        "ip_country":                home,
        "billing_country":           home,
        "shipping_country":          home,
        "geo_distance_km":           round(random.uniform(480, 498), 1),
        "is_international":          "false",
        "merchant_category":         random.choice(NORMAL_CATEGORIES),
        "merchant_risk_score":       round(random.uniform(0.55, 0.68), 3),
        "merchant_country":          home,
        "counterparty_age_days":     random.randint(30, 365),
        "new_payee_flag":            "false",
        "customer_tenure_days":      random.randint(30, 3000),
        "avg_transaction_amount_30d": avg_amount,
        "txn_count_1h":              random.randint(4, 5),
        "txn_count_24h":             random.randint(2, 8),
        "failed_attempts_1h":        random.randint(2, 3),
        "chargeback_count_90d":      1,
        "scenario_label":            f"threshold_straddle_{instance:04d}",
        "scenario_family":           "threshold_straddle",
        "synthetic_fraud_label":     1,
        "rule_trigger_count":        0,
        "primary_risk_reason":       "COMPOUND_THRESHOLD_STRADDLING",
        "expected_priority":         "P3",
        "recommended_action":        "APPROVE",
        "analyst_queue_hint":        "All signals sub-threshold; compound evasion suspected",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_graph_evasion_cluster(idx_start: int, cluster_id: int, family: str) -> list:
    """
    Generate a coordinated cluster of rows sharing one merchant_id.
    family == 'graph_evasion_fan_in'          -> cluster_size = 3 (at threshold, no flag)
    family == 'graph_evasion_fan_in_detected' -> cluster_size = 4 (above threshold, flag fires)

    Each cluster uses:
    - One shared merchant_id (guarantees accounts_per_counterparty = cluster_size)
    - Distinct account_id, customer_id, device_id per row (no shared device signals)
    """
    cluster_size = GRAPH_CLUSTER_SIZES[family]
    home         = random.choice(LOW_RISK_COUNTRIES)
    currency     = HOME_CURRENCIES.get(home, "USD")
    shared_merch = f"merch_adv_{cluster_id:06d}"
    is_detected  = (family == "graph_evasion_fan_in_detected")

    primary_reason = (
        "GRAPH_FAN_IN_ABOVE_THRESHOLD"
        if is_detected else
        "GRAPH_FAN_IN_AT_THRESHOLD"
    )
    hint = (
        f"Fan-in above threshold ({cluster_size} accounts); counterparty_fan_in_flag fires"
        if is_detected else
        f"Fan-in at threshold ({cluster_size} accounts); counterparty_fan_in_flag does NOT fire"
    )
    priority = "P1" if is_detected else "P3"
    action   = "REVIEW" if is_detected else "APPROVE"

    rows = []
    for i in range(cluster_size):
        idx    = idx_start + i
        amount = round(random.uniform(200, 800), 2)
        bal_bef = round(random.uniform(1000, 8000), 2)
        ts      = _ts(8, 20)

        row = {
            "transaction_id":            f"adv_{idx:08d}",
            "amount":                    amount,
            "timestamp":                 ts,
            "country":                   home,
            "payment_method":            random.choice(["debit_card", "bank_transfer"]),
            "event_timestamp":           ts,
            "account_id":                f"acct_adv_{cluster_id:06d}_{i}",
            "customer_id":               f"cust_adv_{cluster_id:06d}_{i}",
            "merchant_id":               shared_merch,
            "currency":                  currency,
            "account_balance_before":    bal_bef,
            "account_balance_after":     round(bal_bef - amount, 2),
            "daily_spend_to_date":       round(random.uniform(50, 400), 2),
            "available_limit":           round(random.uniform(3000, 12000), 2),
            "channel":                   random.choice(["web", "mobile_app"]),
            "device_id":                 f"dev_adv_{cluster_id:06d}_{i}",
            "device_type":               random.choice(["desktop", "mobile"]),
            "device_trust_score":        round(random.uniform(0.50, 0.90), 3),
            "ip_country":                home,
            "billing_country":           home,
            "shipping_country":          home,
            "geo_distance_km":           round(random.uniform(10, 200), 1),
            "is_international":          "false",
            "merchant_category":         random.choice(NORMAL_CATEGORIES),
            "merchant_risk_score":       round(random.uniform(0.10, 0.40), 3),
            "merchant_country":          home,
            "counterparty_age_days":     random.randint(0, 90),
            "new_payee_flag":            "false",
            "customer_tenure_days":      random.randint(90, 2000),
            "avg_transaction_amount_30d": round(random.uniform(100, 600), 2),
            "txn_count_1h":              random.randint(0, 2),
            "txn_count_24h":             random.randint(1, 4),
            "failed_attempts_1h":        0,
            "chargeback_count_90d":      0,
            "scenario_label":            f"{family}_{cluster_id:04d}_{i}",
            "scenario_family":           family,
            "synthetic_fraud_label":     1,
            "rule_trigger_count":        0,
            "primary_risk_reason":       primary_reason,
            "expected_priority":         priority,
            "recommended_action":        action,
            "analyst_queue_hint":        hint,
        }
        row["rule_trigger_count"] = _rule_count(row)
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Row count allocation
# ---------------------------------------------------------------------------

def _allocate_rows(n: int) -> dict:
    """
    Allocate n rows across adversarial families.
    Graph families are snapped to their required cluster divisors.
    Non-graph families receive the remainder, distributed proportionally.
    """
    raw = {
        "low_and_slow":                  round(n * 0.300),
        "victim_mirror":                 round(n * 0.300),
        "threshold_straddle":            round(n * 0.250),
        "graph_evasion_fan_in":          round(n * 0.090),
        "graph_evasion_fan_in_detected": round(n * 0.060),
    }

    # Snap graph families to their cluster divisor
    for family, size in GRAPH_CLUSTER_SIZES.items():
        raw_count = raw[family]
        snapped   = max(size, (raw_count // size) * size)
        raw[family] = snapped

    # Distribute the non-graph remainder proportionally using initial weights
    graph_total = sum(raw[f] for f in GRAPH_CLUSTER_SIZES)
    non_graph   = ["low_and_slow", "victim_mirror", "threshold_straddle"]
    ng_budget   = max(len(non_graph), n - graph_total)

    # Initial weights for proportional split
    ng_weights  = [0.300, 0.300, 0.250]
    ng_wsum     = sum(ng_weights)
    allocated   = 0
    for i, fam in enumerate(non_graph[:-1]):
        cnt = round(ng_budget * ng_weights[i] / ng_wsum)
        raw[fam] = cnt
        allocated += cnt
    raw[non_graph[-1]] = ng_budget - allocated

    return raw


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _print_summary(rows: list, output_path: str, seed: int) -> None:
    n          = len(rows)
    scenarios  = Counter(r["scenario_family"]       for r in rows)
    priorities = Counter(r["expected_priority"]     for r in rows)
    labels     = Counter(r["synthetic_fraud_label"] for r in rows)
    amounts    = [float(r["amount"]) for r in rows]
    srt        = sorted(amounts)

    print(f"\n{'='*62}")
    print(f"  Adversarial Dataset -- Generation Summary")
    print(f"{'='*62}")
    print(f"  Output   : {output_path}")
    print(f"  Rows     : {n:,}")
    print(f"  Columns  : {len(FIELDNAMES)}")
    print(f"  Seed     : {seed}")
    print()
    print(f"  Scenario distribution:")
    for fam, cnt in sorted(scenarios.items(), key=lambda x: -x[1]):
        print(f"    {fam:<42} {cnt:>5,}  ({cnt/n*100:.1f}%)")
    print()
    print(f"  Expected priority:")
    for tier in ["P0", "P1", "P2", "P3"]:
        cnt = priorities.get(tier, 0)
        print(f"    {tier}  {cnt:>5,}  ({cnt/n*100:.1f}%)")
    print()
    print(f"  Fraud label:")
    for lbl in [1, 0]:
        name = "Fraud     " if lbl == 1 else "Legitimate"
        cnt  = labels.get(lbl, 0)
        print(f"    {name} ({lbl})  {cnt:>5,}  ({cnt/n*100:.1f}%)")
    print()
    print(f"  Amount summary:")
    print(f"    Min    : ${min(amounts):>10,.2f}")
    print(f"    Max    : ${max(amounts):>10,.2f}")
    print(f"    Mean   : ${sum(amounts)/n:>10,.2f}")
    print(f"    Median : ${srt[n//2]:>10,.2f}")
    print(f"{'='*62}\n")


# ---------------------------------------------------------------------------
# CLI and main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate an adversarial synthetic fraud CSV (Phase 16B).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python scripts/generate_adversarial_csv.py --rows 1000 --seed 42
  python scripts/generate_adversarial_csv.py --rows 1000 --seed 99 --output C:\\tmp\\adv.csv
""",
    )
    p.add_argument("--rows",   type=int, default=1000,
                   help="Rows to generate (default: 1000, minimum: 100)")
    p.add_argument("--seed",   type=int, default=42,
                   help="Random seed (default: 42)")
    p.add_argument("--output", type=str, default="",
                   help="Output CSV path (default: scripts/test_adversarial_<rows>.csv)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    seed = args.seed
    n    = args.rows
    random.seed(seed)

    if n < 100:
        print(f"ERROR: --rows must be >= 100 (got {n})", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        script_dir  = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, f"test_adversarial_{n}.csv")

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    alloc = _allocate_rows(n)
    print(f"Adversarial row allocation:")
    for fam, cnt in alloc.items():
        print(f"  {fam:<42} {cnt:,}")
    total_alloc = sum(alloc.values())
    print(f"  {'TOTAL':<42} {total_alloc:,}")
    print()

    generated = []
    idx = 1

    # -- Independent scenarios --
    for family, gen_fn in [
        ("low_and_slow",       gen_low_and_slow),
        ("victim_mirror",      gen_victim_mirror),
        ("threshold_straddle", gen_threshold_straddle),
    ]:
        for instance in range(alloc[family]):
            generated.append(gen_fn(idx, instance))
            idx += 1

    # -- Cluster-based graph evasion scenarios --
    for family, cluster_size in GRAPH_CLUSTER_SIZES.items():
        n_clusters = alloc[family] // cluster_size
        for cluster_id in range(n_clusters):
            cluster = gen_graph_evasion_cluster(idx, cluster_id, family)
            generated.extend(cluster)
            idx += cluster_size

    # Shuffle rows so scenarios are interleaved (reproducible with fixed seed)
    random.shuffle(generated)

    print(f"Writing CSV...")
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(generated)

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"Written {total_alloc:,} rows -> {output_path}  ({size_mb:.2f} MB)")
    _print_summary(generated, output_path, seed)


if __name__ == "__main__":
    main()
