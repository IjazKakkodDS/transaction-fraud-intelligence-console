"""
Feature engineering for transaction data.
"""

import pandas as pd


def generate_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    df["hour_of_day"] = pd.to_datetime(df["timestamp"]).dt.hour
    df["is_night_transaction"] = df["hour_of_day"].apply(lambda h: 1 if h < 6 or h > 22 else 0)
    df["is_high_amount"] = df["amount"].apply(lambda a: 1 if a > 1000 else 0)
    return df
