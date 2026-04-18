"""
End-to-end fraud triage pipeline.
"""

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

from src.features.transaction_features import generate_basic_features
from src.rules.fraud_rules import apply_fraud_rules
from src.triage.investigator import triage_decision

FEATURES = ["amount", "is_night_transaction", "is_high_amount"]
PREVIEW_COLS = ["amount", "is_high_amount", "is_night_transaction", "rule_flag", "model_prediction", "decision"]


def run_fraud_pipeline():
    df = pd.read_csv("data/synthetic/transactions.csv")
    df = generate_basic_features(df)

    X = df[FEATURES]
    y = df["is_fraud"]
    X_train, _, y_train, _ = train_test_split(X, y, test_size=0.2, random_state=42)

    model = LogisticRegression()
    model.fit(X_train, y_train)

    df["model_prediction"] = model.predict(X)

    df = apply_fraud_rules(df)
    df = triage_decision(df)

    print(df[PREVIEW_COLS].head())
    return df


if __name__ == "__main__":
    run_fraud_pipeline()
