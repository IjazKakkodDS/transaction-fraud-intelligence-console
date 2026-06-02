"""
Behavioural layer fraud-quality verification -- Phase 13G.

In-memory synthetic scenarios only.
No file generation. No API calls. No database access.

All results are from controlled synthetic test cases.

DISCLAIMER: Synthetic/local validation only -- not real-world fraud calibration.
Institution deployment requires labelled validation, governance, and model-risk review.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features.transaction_features import (
    extract_behavioural_reason_codes,
    generate_basic_features,
)
from src.triage.investigator import calculate_behavioural_boost

DISCLAIMER = (
    "Synthetic/local validation only -- not real-world fraud calibration."
)

_PASS = True


def _assert(condition: bool, message: str) -> None:
    global _PASS
    if not condition:
        print(f"  FAIL  {message}")
        _PASS = False


def _run(
    name: str,
    row_data: dict,
    fraud_label: int,
    expect_boost_zero: bool = False,
    expect_boost_gt_zero: bool = False,
    expect_codes: list | None = None,
    base_score: float = 0.0,
    note: str = "",
) -> None:
    """Build a one-row DataFrame, extract features, compute boost and codes."""
    df = pd.DataFrame([row_data])
    df = generate_basic_features(df)
    row = df.iloc[0]

    boost = calculate_behavioural_boost(row)
    codes = extract_behavioural_reason_codes(row)
    final_score = min(1.0, base_score + boost)

    label_str = f"fraud={fraud_label}"
    print(f"\n  [{name}]  {label_str}")
    print(f"    boost        : {boost:.4f}")
    print(f"    codes        : {codes if codes else '[]'}")
    print(f"    base={base_score:.3f}  -> final={final_score:.3f}")
    if note:
        print(f"    note         : {note}")

    _assert(boost >= 0.0,  f"{name}: boost is negative ({boost})")
    _assert(boost <= 0.20, f"{name}: boost exceeds cap ({boost:.4f} > 0.20)")
    _assert(final_score <= 1.0, f"{name}: final score exceeds 1.0 ({final_score})")

    if expect_boost_zero:
        _assert(boost == 0.0, f"{name}: expected boost=0.0, got {boost:.4f}")
    if expect_boost_gt_zero:
        _assert(boost > 0.0, f"{name}: expected boost>0.0, got {boost:.4f}")
    if expect_codes is not None:
        _assert(
            set(codes) == set(expect_codes),
            f"{name}: codes mismatch\n"
            f"    expected {sorted(expect_codes)}\n"
            f"    got      {sorted(codes)}",
        )


def main() -> int:
    global _PASS

    print("=" * 72)
    print("  Behavioural Fraud-Quality Verification  --  Phase 13G")
    print(f"  {DISCLAIMER}")
    print("=" * 72)

    # ------------------------------------------------------------------
    # A: Legitimate row -- no behavioural history
    #    No baseline columns present; boost must be 0.0.
    #    FN perspective: without history the behavioural layer is silent.
    #    Legacy model/rule signals are the only defence on such rows.
    # ------------------------------------------------------------------
    _run(
        name="A: Legit, no history",
        row_data={
            "transaction_id": "scen_A",
            "timestamp":       "2024-06-15T10:30:00",
            "amount":          85.0,
            "payment_method":  "debit_card",
            "country":         "US",
            "merchant_category": "grocery",
            "device_id":       "dev_abc123",
            "device_type":     "mobile",
        },
        fraud_label=0,
        expect_boost_zero=True,
        expect_codes=[],
        base_score=0.0,
        note=(
            "No behavioural columns -> boost=0.0. "
            "FN: if row were fraud, behavioural layer offers no additional signal."
        ),
    )

    # ------------------------------------------------------------------
    # B: Legitimate row -- normal behavioural history matches current
    #    All derived ratios below thresholds; boolean indicators false.
    #    Correctly treated as low-risk with no behavioural escalation.
    # ------------------------------------------------------------------
    _run(
        name="B: Legit, normal history",
        row_data={
            "transaction_id":   "scen_B",
            "timestamp":        "2024-06-15T10:30:00",
            "amount":           95.0,
            "payment_method":   "debit_card",
            "country":          "US",
            "merchant_category": "grocery",
            "device_id":        "dev_abc123",
            "device_type":      "mobile",
            "channel":          "web",
            "txn_count_24h":    2,
            # Baselines that match current behaviour
            "customer_avg_amount_30d":      100.0,  # ratio=0.95 < 3.0
            "customer_txn_count_24h_baseline": 3,   # ratio=0.67 < 3.0
            "account_avg_balance_30d":      5000.0,
            "account_balance_before":       4800.0, # drop=0.019 < 0.20
            "device_seen_count_90d":        12,     # established device
            "counterparty_seen_before":     "true",
            "usual_country":                "US",
            "usual_channel":                "web",
            "merchant_customer_frequency_90d": 5,
        },
        fraud_label=0,
        expect_boost_zero=True,
        expect_codes=[],
        base_score=0.0,
        note="All baselines match current behaviour -> boost=0.0; no FP escalation.",
    )

    # ------------------------------------------------------------------
    # C: Legitimate row -- behavioural anomalies present (FP risk case)
    #    Customer on holiday: new device, new country, elevated spend,
    #    higher velocity, unusual channel.  Boost is bounded (0.18).
    #    With base_score=0.0 the row stays P3/APPROVE.
    #    If model/rules raise base to 0.60, final=0.78 (P0/BLOCK) --
    #    step-up authentication warranted; not an automatic block.
    # ------------------------------------------------------------------
    _run(
        name="C: Legit, anomalies (FP risk)",
        row_data={
            "transaction_id":   "scen_C",
            "timestamp":        "2024-06-15T14:00:00",
            "amount":           450.0,
            "payment_method":   "debit_card",
            "country":          "FR",
            "merchant_category": "retail",
            "device_id":        "dev_new_999",
            "device_type":      "mobile",
            "channel":          "mobile_app",
            "txn_count_24h":    9,
            # Anomalous vs baseline
            "customer_avg_amount_30d":      80.0,   # 450/80=5.63 >= 3.0 -> AMOUNT_DEV
            "customer_txn_count_24h_baseline": 2,   # 9/2=4.5 >= 3.0 -> VELOCITY_DEV
            "account_avg_balance_30d":      4000.0,
            "account_balance_before":       3800.0, # 450/4000=0.11 < 0.20 -> no trigger
            "device_seen_count_90d":        0,      # new device -> NEW_DEVICE
            "counterparty_seen_before":     "true",
            "usual_country":                "US",   # FR != US -> NEW_COUNTRY
            "usual_channel":                "web",  # mobile_app != web -> UNUSUAL_CHANNEL
            "merchant_customer_frequency_90d": 3,   # known merchant -> no trigger
        },
        fraud_label=0,
        expect_boost_gt_zero=True,
        expect_codes=[
            "BEHAVIOURAL_AMOUNT_DEVIATION",
            "BEHAVIOURAL_VELOCITY_DEVIATION",
            "NEW_DEVICE_FOR_CUSTOMER",
            "NEW_COUNTRY_FOR_CUSTOMER",
            "UNUSUAL_CHANNEL_FOR_CUSTOMER",
        ],
        base_score=0.0,
        note=(
            "FP risk: 5 signals fire for a legit customer on holiday (boost=0.18). "
            "base=0.0 -> final=0.18 (P3, score<0.30). "
            "If base=0.60 (model+rule) -> final=0.78 (P0). "
            "Step-up auth recommended; boost does not auto-block without model/rule support."
        ),
    )

    # ------------------------------------------------------------------
    # D: Fraud row -- no behavioural history
    #    High-risk legacy signals present (high amount, night, high-risk
    #    country) but no behavioural baseline columns.
    #    Boost = 0.0; legacy signals carry detection unaided.
    #    FN limitation: behavioural layer is silent without history.
    # ------------------------------------------------------------------
    _run(
        name="D: Fraud, no history (FN limitation)",
        row_data={
            "transaction_id":   "scen_D",
            "timestamp":        "2024-01-15T02:30:00",  # night
            "amount":           2500.0,                  # high amount
            "payment_method":   "credit_card",
            "country":          "RU",                    # high-risk country
            "merchant_category": "electronics",
            "device_id":        "",                       # no device
            "device_type":      "mobile",
        },
        fraud_label=1,
        expect_boost_zero=True,
        expect_codes=[],
        base_score=1.0,  # model+rule already P0 from legacy signals
        note=(
            "FN limitation (behavioural): no history -> boost=0.0. "
            "Legacy signals (night+high+RU+no-device) carry detection; base_score=1.0. "
            "Behavioural layer not required for this fraud type."
        ),
    )

    # ------------------------------------------------------------------
    # E: Fraud row -- behavioural anomalies present
    #    All 8 behavioural signals triggered; boost capped at 0.20.
    #    Legacy signals already produce base_score=1.0; cap holds.
    #    Behavioural codes add analyst evidence without changing outcome.
    # ------------------------------------------------------------------
    _run(
        name="E: Fraud, with history (detection reinforced)",
        row_data={
            "transaction_id":   "scen_E",
            "timestamp":        "2024-01-15T02:30:00",  # night
            "amount":           2500.0,
            "payment_method":   "credit_card",
            "country":          "RU",
            "merchant_category": "electronics",
            "device_id":        "",
            "device_type":      "mobile",
            "channel":          "api",
            "txn_count_24h":    8,
            # All behavioural signals anomalous vs history
            "customer_avg_amount_30d":      150.0,  # 2500/150=16.7 >= 3.0 -> AMOUNT_DEV
            "customer_txn_count_24h_baseline": 2,   # 8/2=4.0 >= 3.0 -> VELOCITY_DEV
            "account_avg_balance_30d":      5000.0,
            "account_balance_before":       4800.0, # 2500/5000=0.50 >= 0.20 -> BALANCE_DROP
            "device_seen_count_90d":        0,      # new device -> NEW_DEVICE
            "counterparty_seen_before":     "false", # new payee -> NEW_COUNTERPARTY
            "usual_country":                "US",   # RU != US -> NEW_COUNTRY
            "usual_channel":                "web",  # api != web -> UNUSUAL_CHANNEL
            "merchant_customer_frequency_90d": 0,   # never seen -> PROFILE_SHIFT
        },
        fraud_label=1,
        expect_boost_gt_zero=True,
        expect_codes=[
            "BEHAVIOURAL_AMOUNT_DEVIATION",
            "BEHAVIOURAL_VELOCITY_DEVIATION",
            "BALANCE_DROP_ANOMALY",
            "NEW_DEVICE_FOR_CUSTOMER",
            "NEW_COUNTRY_FOR_CUSTOMER",
            "NEW_COUNTERPARTY_FOR_ACCOUNT",
            "UNUSUAL_CHANNEL_FOR_CUSTOMER",
            "BEHAVIOURAL_PROFILE_SHIFT",
        ],
        base_score=1.0,
        note=(
            "All 8 signals reinforce detection. "
            "Boost capped at 0.20; base=1.0 -> final stays 1.0 (cap holds). "
            "Behavioural codes add analyst evidence."
        ),
    )

    # ------------------------------------------------------------------
    # F: Max-boost stress test -- cap enforcement
    #    All derived features set to their maximum triggering values.
    #    Uncapped sum = 0.27; after cap = 0.20.
    #    Combined with a near-maximum base_score (0.95), final <= 1.0.
    # ------------------------------------------------------------------
    print(f"\n  [F: Max-boost cap enforcement]  fraud_label=n/a")
    extreme_row = pd.Series({
        "amount_deviation_ratio":      10.0,
        "velocity_deviation_ratio":    10.0,
        "balance_drop_ratio":           1.0,
        "new_device_for_customer":        1,
        "new_country_for_customer":       1,
        "new_counterparty_for_account":   1,
        "unusual_channel_for_customer":   1,
        "unusual_merchant_for_customer":  1,
    })
    max_boost = calculate_behavioural_boost(extreme_row)
    max_codes = extract_behavioural_reason_codes(extreme_row)
    final_extreme = min(1.0, 0.95 + max_boost)

    print(f"    boost (uncapped sum=0.27): {max_boost:.4f}")
    print(f"    codes                    : {max_codes}")
    print(f"    base=0.95 -> final       : {final_extreme:.3f}")
    print(f"    note         : Boost capped at 0.20; score cap at 1.0 enforced.")

    _assert(max_boost <= 0.20, f"F: max_boost {max_boost:.4f} exceeds cap 0.20")
    _assert(max_boost > 0.0,   "F: max_boost is 0 when all signals triggered")
    _assert(final_extreme <= 1.0, f"F: final_score {final_extreme} exceeds 1.0")
    _assert(len(max_codes) == 8, f"F: expected 8 codes, got {len(max_codes)}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 72)
    result = "PASS" if _PASS else "FAIL"
    print(f"  {result}  Behavioural fraud-quality verification  --  Phase 13G")
    print(f"  {DISCLAIMER}")
    print("=" * 72)
    return 0 if _PASS else 1


if __name__ == "__main__":
    sys.exit(main())
