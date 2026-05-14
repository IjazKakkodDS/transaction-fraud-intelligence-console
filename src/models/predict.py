"""
Inference logic for loading a trained model and producing fraud predictions.
"""

import joblib
import pandas as pd

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
MODEL_PATH = "saved_models/fraud_model.pkl"

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = joblib.load(MODEL_PATH)
    return _model


def predict(df: pd.DataFrame) -> list:
    model = _get_model()
    return model.predict(df[FEATURES]).tolist()
