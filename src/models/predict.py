"""
Inference logic for loading a trained model and producing fraud predictions.
"""

import joblib
import pandas as pd

FEATURES = ["amount", "is_night_transaction", "is_high_amount"]
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
