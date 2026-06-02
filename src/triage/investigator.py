"""
Triage logic for routing flagged transactions to the appropriate investigation queue.
"""

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
    df["risk_score"] = (base_score + rich_boost).clip(upper=1.0)

    def decide(score: float) -> str:
        if score >= BLOCK_THRESHOLD:
            return "BLOCK"
        if score >= REVIEW_THRESHOLD:
            return "REVIEW"
        return "APPROVE"

    df["decision"] = df["risk_score"].apply(decide)
    return df
