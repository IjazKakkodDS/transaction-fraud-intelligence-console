"""
Validate behavioural feature extraction outputs for Phase 13B.

This script builds small in-memory rows and confirms that behavioural features
are neutral when history is absent and non-neutral when valid baselines exist.
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


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _build_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _check_neutral_row(row: pd.Series) -> None:
    _assert(row["amount_deviation_ratio"] == 0.0, "amount_deviation_ratio not neutral")
    _assert(row["velocity_deviation_ratio"] == 0.0, "velocity_deviation_ratio not neutral")
    _assert(row["balance_drop_ratio"] == 0.0, "balance_drop_ratio not neutral")
    _assert(row["new_device_for_customer"] == 0, "new_device_for_customer not neutral")
    _assert(row["new_country_for_customer"] == 0, "new_country_for_customer not neutral")
    _assert(row["new_counterparty_for_account"] == 0, "new_counterparty_for_account not neutral")
    _assert(row["unusual_channel_for_customer"] == 0, "unusual_channel_for_customer not neutral")
    _assert(row["unusual_merchant_for_customer"] == 0, "unusual_merchant_for_customer not neutral")
    _assert(calculate_behavioural_boost(row) == 0.0, "behavioural_boost not neutral")
    _assert(extract_behavioural_reason_codes(row) == [], "behavioural reason codes not neutral")


def _check_behavioural_row(row: pd.Series) -> float:
    _assert(row["amount_deviation_ratio"] == 4.0, "amount_deviation_ratio mismatch")
    _assert(row["velocity_deviation_ratio"] == 3.0, "velocity_deviation_ratio mismatch")
    _assert(abs(row["balance_drop_ratio"] - 0.2) < 1e-9, "balance_drop_ratio mismatch")
    _assert(row["new_device_for_customer"] == 1, "new_device_for_customer mismatch")
    _assert(row["new_country_for_customer"] == 1, "new_country_for_customer mismatch")
    _assert(row["new_counterparty_for_account"] == 1, "new_counterparty_for_account mismatch")
    _assert(row["unusual_channel_for_customer"] == 1, "unusual_channel_for_customer mismatch")
    _assert(row["unusual_merchant_for_customer"] == 1, "unusual_merchant_for_customer mismatch")
    boost = calculate_behavioural_boost(row)
    _assert(boost > 0.0, "behavioural_boost not applied")
    _assert(boost <= 0.20, "behavioural_boost exceeds cap")
    expected_codes = {
        "BEHAVIOURAL_AMOUNT_DEVIATION",
        "BEHAVIOURAL_VELOCITY_DEVIATION",
        "BALANCE_DROP_ANOMALY",
        "NEW_DEVICE_FOR_CUSTOMER",
        "NEW_COUNTRY_FOR_CUSTOMER",
        "NEW_COUNTERPARTY_FOR_ACCOUNT",
        "UNUSUAL_CHANNEL_FOR_CUSTOMER",
        "BEHAVIOURAL_PROFILE_SHIFT",
    }
    actual_codes = set(extract_behavioural_reason_codes(row))
    _assert(actual_codes == expected_codes, "behavioural reason codes mismatch")
    return boost


def _check_risk_score_cap(existing_score: float, boost: float) -> None:
    capped = min(1.0, existing_score + boost)
    _assert(capped <= 1.0, "risk_score exceeds cap")


def _check_neutral_behavioural_codes(row: pd.Series) -> None:
    _assert(calculate_behavioural_boost(row) == 0.0, "behavioural_boost not neutral")
    _assert(extract_behavioural_reason_codes(row) == [], "behavioural reason codes not neutral")


def main() -> int:
    legacy_row = {
        "transaction_id": "t_legacy",
        "timestamp": "2024-01-01T12:00:00",
        "amount": 100.0,
        "payment_method": "debit_card",
        "country": "US",
        "merchant_category": "grocery",
        "device_id": "dev_1",
        "device_type": "mobile",
    }

    behavioural_row = {
        "transaction_id": "t_behavioural",
        "timestamp": "2024-01-01T12:00:00",
        "amount": 200.0,
        "payment_method": "debit_card",
        "country": "CA",
        "merchant_category": "grocery",
        "device_id": "dev_2",
        "device_type": "mobile",
        "customer_avg_amount_30d": 50.0,
        "customer_txn_count_24h_baseline": 2,
        "txn_count_24h": 6,
        "account_avg_balance_30d": 1000.0,
        "account_balance_before": 1200.0,
        "device_seen_count_90d": 0,
        "counterparty_seen_before": "false",
        "usual_country": "US",
        "usual_channel": "web",
        "channel": "mobile_app",
        "merchant_customer_frequency_90d": 0,
    }

    zero_baseline_row = {
        "transaction_id": "t_zero_baseline",
        "timestamp": "2024-01-01T12:00:00",
        "amount": 150.0,
        "payment_method": "debit_card",
        "country": "US",
        "merchant_category": "grocery",
        "device_id": "dev_3",
        "device_type": "mobile",
        "customer_avg_amount_30d": 0,
        "customer_txn_count_24h_baseline": 0,
        "txn_count_24h": 5,
        "account_avg_balance_30d": 0,
        "account_balance_before": 500.0,
    }

    rich_no_behavioural_row = {
        "transaction_id": "t_rich_no_behavioural",
        "timestamp": "2024-01-01T12:00:00",
        "amount": 250.0,
        "payment_method": "debit_card",
        "country": "US",
        "merchant_category": "grocery",
        "device_id": "dev_4",
        "device_type": "mobile",
        "txn_count_1h": 6,
        "failed_attempts_1h": 4,
        "merchant_risk_score": 0.8,
        "avg_transaction_amount_30d": 50.0,
    }

    neutral_behavioural_row = {
        "transaction_id": "t_neutral_behavioural",
        "timestamp": "2024-01-01T12:00:00",
        "amount": 100.0,
        "payment_method": "debit_card",
        "country": "US",
        "merchant_category": "grocery",
        "device_id": "dev_5",
        "device_type": "mobile",
        "customer_avg_amount_30d": 120.0,
        "customer_txn_count_24h_baseline": 5,
        "txn_count_24h": 3,
        "account_avg_balance_30d": 1000.0,
        "account_balance_before": 2000.0,
        "device_seen_count_90d": 5,
        "counterparty_seen_before": "true",
        "usual_country": "US",
        "usual_channel": "web",
        "channel": "web",
        "merchant_customer_frequency_90d": 2,
    }

    df = _build_df([
        legacy_row,
        behavioural_row,
        zero_baseline_row,
        rich_no_behavioural_row,
        neutral_behavioural_row,
    ])
    result = generate_basic_features(df)

    _check_neutral_row(result.iloc[0])
    behavioural_boost = _check_behavioural_row(result.iloc[1])
    _check_neutral_row(result.iloc[2])
    _check_neutral_row(result.iloc[3])
    _check_neutral_behavioural_codes(result.iloc[4])

    _check_risk_score_cap(0.95, behavioural_boost)

    extreme_row = {
        "amount_deviation_ratio": 10.0,
        "velocity_deviation_ratio": 10.0,
        "balance_drop_ratio": 1.0,
        "new_device_for_customer": 1,
        "new_country_for_customer": 1,
        "new_counterparty_for_account": 1,
        "unusual_channel_for_customer": 1,
        "unusual_merchant_for_customer": 1,
    }
    extreme_boost = calculate_behavioural_boost(pd.Series(extreme_row))
    _assert(extreme_boost <= 0.20, "behavioural_boost cap not enforced")

    print("PASS: behavioural feature extraction validation")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)
