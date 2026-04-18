"""
FastAPI application entry point for the Real-Time Fraud Triage System.
"""

import logging
from datetime import datetime, timezone
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.api.schemas import ReviewCaseRequest
from src.db.postgres_logger import (
    get_prediction_by_id,
    get_prediction_by_transaction_id,
    get_review_queue_filtered,
    get_stats,
    log_prediction,
    update_review,
)
from src.config.config import HIGH_AMOUNT_THRESHOLD, SYNC_SCORING_ENABLED
from src.events.producer import send_transaction_raw_event
from src.events.schemas import TransactionRawEvent
from src.features.transaction_features import generate_basic_features
from src.models.predict import predict
from src.rules.fraud_rules import apply_fraud_rules
from src.triage.investigator import triage_decision

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Real-Time Fraud Triage System",
    version="0.1.0",
)


@app.get("/")
def root():
    return {"message": "Real-Time Fraud Triage System API is running"}


@app.get("/stats")
def stats():
    return get_stats()


@app.get("/review-queue")
def get_review_queue(analyst_status: Literal["CONFIRMED_FRAUD", "FALSE_POSITIVE", "APPROVED", "UNREVIEWED"] | None = None):
    return get_review_queue_filtered(analyst_status)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/predict")
def predict_transaction(transaction: dict):
    # Always publish to transactions.raw so the scoring consumer processes
    # every transaction regardless of which scoring path is active.
    # Fire-and-forget: failures are logged but never propagate to the caller.
    try:
        event = TransactionRawEvent(producer="api", **transaction)
        send_transaction_raw_event(event)
    except ValidationError as exc:
        logger.warning(
            "Skipping transaction.raw publish — payload failed schema validation | "
            "transaction_id=%s errors=%s",
            transaction.get("transaction_id", "<unknown>"),
            exc.error_count(),
        )
    except Exception as exc:
        logger.error(
            "Unexpected error building transaction.raw event | "
            "transaction_id=%s error=%s",
            transaction.get("transaction_id", "<unknown>"),
            exc,
        )

    if not SYNC_SCORING_ENABLED:
        # Async-only path: scoring-consumer is the sole scorer.
        # Clients poll GET /predictions/{transaction_id} for the scored result.
        # See docs/dual_path_retirement_plan.md for the full transition plan.
        return JSONResponse(
            status_code=202,
            content={"status": "accepted", "transaction_id": transaction.get("transaction_id")},
        )

    # Synchronous scoring path — Phase 2 dual-path mode (to be retired).
    # Active when SYNC_SCORING_ENABLED=true (the default).
    # Both this path and the consumer score the same transaction, producing
    # two Postgres rows. This resolves when SYNC_SCORING_ENABLED is set to false.
    df = pd.DataFrame([transaction])
    df = generate_basic_features(df)
    df["model_prediction"] = predict(df)
    df = apply_fraud_rules(df)
    df = triage_decision(df)

    row = df.iloc[0]

    reasons = []
    if row["amount"] > HIGH_AMOUNT_THRESHOLD:
        reasons.append("High transaction amount")
    if row["is_night_transaction"] == 1:
        reasons.append("Unusual transaction time")
    if row["model_prediction"] == 1:
        reasons.append("Model flagged as suspicious")

    response = {
        "decision": row["decision"],
        "rule_flag": int(row["rule_flag"]),
        "model_prediction": int(row["model_prediction"]),
        "reasons": reasons,
    }

    log_prediction({
        "transaction_id": transaction.get("transaction_id", ""),
        "amount": transaction.get("amount", ""),
        "timestamp": transaction.get("timestamp", ""),
        "rule_flag": response["rule_flag"],
        "model_prediction": response["model_prediction"],
        "risk_score": float(row["risk_score"]),
        "decision": response["decision"],
        "reasons": "|".join(reasons),
    })

    return response


@app.get("/predictions/{transaction_id}")
def get_prediction(transaction_id: str):
    """
    Poll for the scored result of a submitted transaction.

    Returns the most recent prediction row for the given transaction_id, or
    404 if scoring has not completed yet. Clients should retry with backoff
    when 404 is returned — the scoring consumer may still be processing.

    Intended as the polling counterpart to POST /predict in async-only mode
    (SYNC_SCORING_ENABLED=false), but works in both modes.
    """
    prediction = get_prediction_by_transaction_id(transaction_id)
    if prediction is None:
        raise HTTPException(
            status_code=404,
            detail=f"No prediction found for transaction_id={transaction_id}. "
                   "Scoring may still be in progress — retry shortly.",
        )
    return prediction


@app.get("/case/{case_id}")
def get_case(case_id: int):
    case = get_prediction_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
    return case


@app.post("/review-case/{case_id}")
def review_case(case_id: int, body: ReviewCaseRequest):
    case = get_prediction_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    reviewed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    update_review(case_id, body.analyst_status, body.analyst_notes, reviewed_at)

    return {
        "message": "Case updated successfully",
        "case_id": case_id,
        "analyst_status": body.analyst_status,
        "reviewed_at": reviewed_at,
    }
