"""
Model training pipeline for fraud detection.
"""

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from xgboost import XGBClassifier

from src.features.transaction_features import generate_basic_features

FEATURES = [
    "amount",
    "is_high_amount",
    "is_night_transaction",
    "is_international",
    "is_high_risk_payment_method",
    "is_high_risk_country",
    "is_high_risk_merchant_category",
    "has_device_id",
    "is_mobile_device",
]
TARGET = "is_fraud"
MODEL_PATH = "saved_models/fraud_model.pkl"


def train_fraud_model():
    df = pd.read_csv("data/synthetic/transactions.csv")
    df = generate_basic_features(df)

    X = df[FEATURES]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        eval_metric="logloss",
        random_state=42,
    )
    model.fit(X_train, y_train)

    predictions = model.predict(X_test)
    accuracy = accuracy_score(y_test, predictions)
    print(f"Accuracy: {accuracy:.4f}")
    importances = dict(zip(FEATURES, model.feature_importances_))
    print("Feature importances:", importances)

    joblib.dump(model, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")

    return model


if __name__ == "__main__":
    train_fraud_model()
