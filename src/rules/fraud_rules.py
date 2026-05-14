"""
Rule-based fraud detection heuristics.
"""

import pandas as pd


def apply_fraud_rules(df: pd.DataFrame) -> pd.DataFrame:
    night_high = (df["is_high_amount"] == 1) & (df["is_night_transaction"] == 1)
    intl_high = (
        (df["is_high_amount"] == 1)
        & (df["is_international"] == 1)
        & (df["is_high_risk_country"] == 1)
    )
    risky_rail = (
        (df["is_high_risk_payment_method"] == 1)
        & (df["is_night_transaction"] == 1)
        & (df["is_high_amount"] == 1)
    )
    df["rule_flag"] = (night_high | intl_high | risky_rail).astype(int)
    return df
