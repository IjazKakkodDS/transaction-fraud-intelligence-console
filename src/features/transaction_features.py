"""
Feature engineering for transaction data.
"""

import pandas as pd

from src.config.config import (
    HIGH_AMOUNT_THRESHOLD,
    HIGH_RISK_MERCHANT_CATEGORIES,
    HIGH_RISK_PAYMENT_METHODS,
    LOW_RISK_COUNTRIES,
)


def generate_reasons(df: pd.DataFrame) -> pd.Series:
    """
    Return a pipe-delimited reasons string for each row in a fully scored DataFrame.

    Expects df to contain the columns produced by generate_basic_features, predict,
    apply_fraud_rules, and triage_decision before this call. Works on both single-row
    and multi-row DataFrames. An empty string is returned for rows with no active
    signals (all conditions false).
    """
    def _row_reasons(row) -> str:
        parts = []
        if row["amount"] > HIGH_AMOUNT_THRESHOLD:
            parts.append("High transaction amount")
        if row["is_night_transaction"] == 1:
            parts.append("Unusual transaction time")
        if row["model_prediction"] == 1:
            parts.append("Model flagged as suspicious")
        if row.get("is_international", 0) == 1 and row.get("is_high_risk_country", 0) == 1:
            parts.append("International transaction from elevated-risk region")
        if row.get("is_high_risk_payment_method", 0) == 1:
            parts.append("High-risk payment method")
        if row.get("is_high_risk_merchant_category", 0) == 1:
            parts.append("High-risk merchant category")
        if row.get("has_device_id", 1) == 0:
            parts.append("No device identifier present")
        return "|".join(parts)

    return df.apply(_row_reasons, axis=1)


def generate_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    df["hour_of_day"] = pd.to_datetime(df["timestamp"]).dt.hour
    df["is_night_transaction"] = df["hour_of_day"].apply(lambda h: 1 if h < 6 or h > 22 else 0)
    df["is_high_amount"] = df["amount"].apply(lambda a: 1 if a > HIGH_AMOUNT_THRESHOLD else 0)
    df["is_international"] = (
        df.get("is_international", pd.Series([False] * len(df), index=df.index))
        .fillna(False)
        .astype(int)
    )
    df["is_high_risk_payment_method"] = (
        df.get("payment_method", pd.Series([""] * len(df), index=df.index))
        .fillna("")
        .apply(lambda m: 1 if str(m).lower() in HIGH_RISK_PAYMENT_METHODS else 0)
    )
    df["is_high_risk_country"] = (
        df.get("country", pd.Series(["US"] * len(df), index=df.index))
        .fillna("US")
        .apply(lambda c: 0 if str(c).upper() in LOW_RISK_COUNTRIES else 1)
    )
    df["is_high_risk_merchant_category"] = (
        df.get("merchant_category", pd.Series([None] * len(df), index=df.index))
        .fillna("")
        .apply(lambda c: 1 if str(c).lower() in HIGH_RISK_MERCHANT_CATEGORIES else 0)
    )
    df["has_device_id"] = (
        df.get("device_id", pd.Series([None] * len(df), index=df.index))
        .apply(lambda d: 0 if (d is None or str(d).strip() == "" or str(d).lower() == "none") else 1)
    )
    df["is_mobile_device"] = (
        df.get("device_type", pd.Series([None] * len(df), index=df.index))
        .fillna("")
        .apply(lambda t: 1 if str(t).lower() == "mobile" else 0)
    )
    return df
