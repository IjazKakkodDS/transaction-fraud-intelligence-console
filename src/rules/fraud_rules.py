"""
Rule-based fraud detection heuristics.
"""

import pandas as pd


def apply_fraud_rules(df: pd.DataFrame) -> pd.DataFrame:
    df["rule_flag"] = ((df["is_high_amount"] == 1) & (df["is_night_transaction"] == 1)).astype(int)
    return df
