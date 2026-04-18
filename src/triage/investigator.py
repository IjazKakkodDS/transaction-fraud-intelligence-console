"""
Triage logic for routing flagged transactions to the appropriate investigation queue.
"""

import pandas as pd

from src.config.config import MODEL_WEIGHT, RULE_WEIGHT, REVIEW_THRESHOLD, BLOCK_THRESHOLD


def triage_decision(df: pd.DataFrame) -> pd.DataFrame:
    df["risk_score"] = MODEL_WEIGHT * df["model_prediction"] + RULE_WEIGHT * df["rule_flag"]

    def decide(score):
        if score >= BLOCK_THRESHOLD:
            return "BLOCK"
        elif score >= REVIEW_THRESHOLD:
            return "REVIEW"
        return "APPROVE"

    df["decision"] = df["risk_score"].apply(decide)
    return df
