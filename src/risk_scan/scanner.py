"""
Batch scoring for portfolio risk scan valid rows.
"""

import pandas as pd

from src.features.transaction_features import generate_basic_features, generate_reasons
from src.models.predict import predict
from src.rules.fraud_rules import apply_fraud_rules
from src.triage.investigator import triage_decision
from src.risk_scan.tier import assign_tier


def score_dataframe(valid_df: pd.DataFrame) -> list[dict]:
    """
    Score a DataFrame of validated rows through the full fraud pipeline.

    Expects valid_df to contain only VALID rows (as produced by validator.validate_csv)
    with a row_number column. Does not write to the database.

    Returns a list of result dicts, one per input row, with scoring outputs and
    promotion tracking fields set to their default (unscored) values.
    """
    if valid_df.empty:
        return []

    df = valid_df.copy()
    # Normalise amount to float — pandas may infer object dtype when the
    # source CSV contains any non-numeric value in that column (even on
    # rows that were rejected as INVALID), causing threshold comparisons
    # in generate_basic_features to raise TypeError.
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = generate_basic_features(df)
    df["model_prediction"] = predict(df)
    df = apply_fraud_rules(df)
    df = triage_decision(df)
    reasons_series = generate_reasons(df)

    results: list[dict] = []
    for i, (_, row) in enumerate(df.iterrows()):
        risk_score = float(row["risk_score"])
        risk_tier, operational_priority = assign_tier(risk_score)

        results.append({
            "row_number": int(row["row_number"]),
            "transaction_id": row.get("transaction_id"),
            "amount": row.get("amount"),
            "timestamp": row.get("timestamp"),
            "country": row.get("country"),
            "payment_method": row.get("payment_method"),
            "merchant_category": row.get("merchant_category"),
            "device_id": row.get("device_id"),
            "rule_flag": int(row["rule_flag"]),
            "model_prediction": int(row["model_prediction"]),
            "risk_score": risk_score,
            "decision": row["decision"],
            "risk_tier": risk_tier,
            "operational_priority": operational_priority,
            "reasons": reasons_series.iloc[i],
            "validation_status": "VALID",
            "validation_errors": None,
            "promoted": False,
            "promoted_case_id": None,
            "promoted_at": None,
        })

    return results