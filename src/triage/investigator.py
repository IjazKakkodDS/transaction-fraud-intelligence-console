"""
Triage logic for routing flagged transactions to the appropriate investigation queue.
"""

import numbers

import pandas as pd

from src.config.config import MODEL_WEIGHT, RULE_WEIGHT, REVIEW_THRESHOLD, BLOCK_THRESHOLD

# ---------------------------------------------------------------------------
# Rich signal boost weights (Phase 12F-3)
#
# These features are extracted by generate_basic_features() from optional
# rich CSV columns. Legacy CSVs without these columns receive scalar 0 for
# every rich feature, so the boost is exactly 0.0 and legacy scoring is
# fully preserved.
#
# Max possible boost: 0.10+0.10+0.12+0.15+0.08+0.15+0.10+0.08+0.25 = 1.13
# Capped at 1.0 via .clip(upper=1.0).
# ---------------------------------------------------------------------------
_RICH_BOOST_WEIGHTS: dict = {
    "is_low_trust_device":         0.10,  # device_trust_score < 0.4
    "is_geo_anomaly":              0.10,  # geo_distance_km > 500
    "is_high_velocity_1h":         0.12,  # txn_count_1h > 5
    "has_failed_attempts":         0.15,  # failed_attempts_1h >= 4
    "is_high_risk_merchant_score": 0.08,  # merchant_risk_score >= 0.7
    "is_new_payee_high_value":     0.15,  # new_payee_flag = true and amount > 500
    "has_chargebacks":             0.10,  # chargeback_count_90d >= 2
    "is_amount_anomaly":           0.08,  # amount > 3 × avg_transaction_amount_30d
    "is_rich_fraud_scenario":      0.25,  # scenario_family present and not 'normal'
}

# ---------------------------------------------------------------------------
# Behavioural boost weights (Phase 13D)
# Bounded, additive, optional, and neutral when history is absent.
# ---------------------------------------------------------------------------
_BEHAVIOURAL_BOOST_WEIGHTS: dict = {
    "amount_deviation_ratio": 0.05,
    "velocity_deviation_ratio": 0.05,
    "balance_drop_ratio": 0.04,
    "new_device_for_customer": 0.03,
    "new_country_for_customer": 0.03,
    "new_counterparty_for_account": 0.03,
    "unusual_channel_for_customer": 0.02,
    "unusual_merchant_for_customer": 0.02,
}
_BEHAVIOURAL_BOOST_CAP = 0.20

# ---------------------------------------------------------------------------
# Graph boost weights (Phase 15D)
# Bounded, additive, evidence-gated, and neutral when graph context is absent.
#
# Only the four first-slice boolean flags contribute. Raw count columns
# (accounts_per_device, device_cluster_size, etc.) are available on the row
# but are deferred to later slices for boost contribution.
#
# Max possible uncapped boost: 0.05+0.07+0.05+0.05 = 0.22.
# Cap applied at 0.15 -- tighter than behavioural (0.20) because graph signals
# are batch-scoped and apply to every row sharing the same entity.
#
# These weights are provisional and will be calibrated in Phase 15E/15G
# after reason codes and analyst-facing evidence are validated.
# ---------------------------------------------------------------------------
_GRAPH_BOOST_WEIGHTS: dict = {
    "shared_device_flag":         0.05,  # device shared across >= 2 accounts
    "cross_account_device_reuse": 0.07,  # device shared across DIFFERENT customers
    "counterparty_fan_in_flag":   0.05,  # counterparty receives from > 3 accounts
    "counterparty_fan_out_flag":  0.05,  # account distributes to > 3 counterparties
}
_GRAPH_BOOST_CAP = 0.15


def calculate_graph_boost(row: pd.Series) -> float:
    """
    Compute a bounded graph boost for a single row.

    Reads the four first-slice boolean graph indicator columns produced by
    extract_graph_features() in transaction_features.py. Returns 0.0 when
    graph entity fields were absent (all indicators default to False) or when
    no indicator exceeds its threshold.

    The same-customer same-device pattern does NOT trigger cross_account_device_reuse
    (that flag is False when all accounts share the same customer_id), so a
    legitimate multi-account customer on one device receives at most 0.05 boost
    from shared_device_flag alone.

    Note: graph indicator columns are stored as numpy.bool_ from Pandas boolean
    comparisons. Unlike the int-cast behavioural features, these cannot be checked
    with `== 1`. bool() is used directly to handle numpy.bool_, Python bool,
    and integer 0/1 uniformly. pd.NA raises TypeError from bool(), which is
    caught and treated as False.
    """
    def _as_bool(value) -> bool:
        try:
            return bool(value)
        except (TypeError, ValueError):
            return False

    boost = 0.0
    for col, weight in _GRAPH_BOOST_WEIGHTS.items():
        if _as_bool(row.get(col, False)):
            boost += weight
    return min(boost, _GRAPH_BOOST_CAP)


def calculate_behavioural_boost(row: pd.Series) -> float:
    """
    Compute a bounded behavioural boost for a single row.

    Returns 0.0 when behavioural features are missing or neutral.
    """
    def _safe_float(value) -> float:
        try:
            if value is None or (isinstance(value, float) and pd.isna(value)):
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _safe_truthy(value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, numbers.Number) and not pd.isna(value):
            return value == 1
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes", "y"}
        return False

    boost = 0.0

    if _safe_float(row.get("amount_deviation_ratio", 0.0)) >= 3.0:
        boost += _BEHAVIOURAL_BOOST_WEIGHTS["amount_deviation_ratio"]
    if _safe_float(row.get("velocity_deviation_ratio", 0.0)) >= 3.0:
        boost += _BEHAVIOURAL_BOOST_WEIGHTS["velocity_deviation_ratio"]
    if _safe_float(row.get("balance_drop_ratio", 0.0)) >= 0.20:
        boost += _BEHAVIOURAL_BOOST_WEIGHTS["balance_drop_ratio"]

    if _safe_truthy(row.get("new_device_for_customer", 0)):
        boost += _BEHAVIOURAL_BOOST_WEIGHTS["new_device_for_customer"]
    if _safe_truthy(row.get("new_country_for_customer", 0)):
        boost += _BEHAVIOURAL_BOOST_WEIGHTS["new_country_for_customer"]
    if _safe_truthy(row.get("new_counterparty_for_account", 0)):
        boost += _BEHAVIOURAL_BOOST_WEIGHTS["new_counterparty_for_account"]
    if _safe_truthy(row.get("unusual_channel_for_customer", 0)):
        boost += _BEHAVIOURAL_BOOST_WEIGHTS["unusual_channel_for_customer"]
    if _safe_truthy(row.get("unusual_merchant_for_customer", 0)):
        boost += _BEHAVIOURAL_BOOST_WEIGHTS["unusual_merchant_for_customer"]

    return min(boost, _BEHAVIOURAL_BOOST_CAP)


def triage_decision(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute risk_score and decision for each row.

    Legacy path (no rich columns): risk_score = 0.6 * model_prediction + 0.4 * rule_flag.
    Rich path (rich columns present): adds a deterministic signal boost derived from
    optional rich features extracted by generate_basic_features(). The boost is
    additive and capped at 1.0. Legacy rows receive a boost of exactly 0.0.
    """
    base_score = MODEL_WEIGHT * df["model_prediction"] + RULE_WEIGHT * df["rule_flag"]

    # Accumulate rich signal boost (vectorised; safe for any DataFrame size)
    rich_boost = sum(
        df[feat] * weight
        for feat, weight in _RICH_BOOST_WEIGHTS.items()
        if feat in df.columns
    )
    # rich_boost is 0 (int scalar) when no rich feature columns exist
    if not isinstance(rich_boost, pd.Series):
        rich_boost = 0

    df["rich_signal_boost"] = rich_boost

    behavioural_boost = df.apply(calculate_behavioural_boost, axis=1)
    df["behavioural_boost"] = behavioural_boost

    # Graph boost (Phase 15D) -- additive, bounded at _GRAPH_BOOST_CAP (0.15).
    # Legacy rows with no entity fields produce 0.0 via the indicator defaults.
    graph_boost = df.apply(calculate_graph_boost, axis=1)
    df["graph_boost"] = graph_boost

    df["risk_score"] = (base_score + rich_boost + behavioural_boost + graph_boost).clip(upper=1.0)

    def decide(score: float) -> str:
        if score >= BLOCK_THRESHOLD:
            return "BLOCK"
        if score >= REVIEW_THRESHOLD:
            return "REVIEW"
        return "APPROVE"

    df["decision"] = df["risk_score"].apply(decide)
    return df
