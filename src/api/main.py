"""
FastAPI application entry point for the Real-Time Fraud Triage System.
"""

import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from kafka import KafkaProducer
from kafka.errors import KafkaError
from pydantic import ValidationError

from src.api.schemas import ReviewCaseRequest, WorkflowAuditEventRequest
from src.db.postgres_logger import (
    get_daily_fraud_summary,
    get_latest_investigation,
    get_prediction_by_id,
    get_prediction_by_transaction_id,
    get_review_queue_filtered,
    get_stale_cases,
    get_stats,
    get_workflow_events,
    get_workflow_metrics,
    log_prediction,
    log_workflow_event,
    update_review,
)
from src.config.config import SYNC_SCORING_ENABLED
from src.events.producer import send_transaction_raw_event
from src.events.schemas import TransactionRawEvent
from src.features.transaction_features import generate_basic_features, generate_reasons
from src.models.predict import predict
from src.rules.fraud_rules import apply_fraud_rules
from src.triage.investigator import triage_decision

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# n8n webhook — Phase 4 workflow integration.
# ---------------------------------------------------------------------------

N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")

# ---------------------------------------------------------------------------
# Investigation producer — singleton for cases.investigate topic.
# Initialised lazily on first POST /cases/{id}/investigate call.
# ---------------------------------------------------------------------------

_INVESTIGATE_TOPIC = "cases.investigate"
_investigate_producer: KafkaProducer | None = None
_investigate_producer_disabled: bool = False


def _get_investigate_producer() -> KafkaProducer | None:
    global _investigate_producer, _investigate_producer_disabled

    if _investigate_producer_disabled:
        return None
    if _investigate_producer is not None:
        return _investigate_producer

    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
    if not bootstrap_servers:
        logger.warning(
            "KAFKA_BOOTSTRAP_SERVERS not set — investigation publishing disabled."
        )
        _investigate_producer_disabled = True
        return None

    try:
        _investigate_producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            key_serializer=lambda k: k.encode("utf-8"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks=1,
            request_timeout_ms=3000,
        )
        logger.info("Investigation KafkaProducer initialised | brokers=%s", bootstrap_servers)
    except KafkaError as exc:
        logger.error(
            "Investigation KafkaProducer init failed — publishing disabled | error=%s", exc
        )
        _investigate_producer_disabled = True

    return _investigate_producer


# ---------------------------------------------------------------------------
# Workflow dispatch failure helper — Phase 4.9A.
# Writes a WORKFLOW_DISPATCH_FAILED audit row whenever POST /workflow/notify-case
# cannot reach n8n. Never raises; failures are logged and swallowed so the
# caller can still return its intended HTTP error to the client.
# ---------------------------------------------------------------------------

def _log_workflow_dispatch_failure(
    case_id: int,
    reason: str,
    error_message: str,
    payload: dict | None = None,
) -> None:
    try:
        log_workflow_event({
            "case_id":             case_id,
            "workflow_name":       "Fraud Case Escalation Workflow",
            "workflow_action":     "WORKFLOW_DISPATCH_FAILED",
            "status":              "FAILED",
            "escalation_priority": "HIGH",
            "message":             reason,
            "payload": {
                "error_message":    error_message,
                "dispatch_payload": payload,
            },
            "source": "fastapi",
        })
    except Exception as exc:
        logger.error(
            "Failed to log workflow dispatch failure | case_id=%d reason=%s error=%s",
            case_id,
            reason,
            exc,
        )


app = FastAPI(
    title="Real-Time Fraud Triage System",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
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
            "transaction_id=%s errors=%s detail=%s",
            transaction.get("transaction_id", "<unknown>"),
            exc.error_count(),
            exc.errors(),
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
    reasons_str = generate_reasons(df).iloc[0]
    reasons = reasons_str.split("|") if reasons_str else []

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
        "reasons": reasons_str,
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


@app.get("/cases/{case_id}/investigation")
def get_investigation(case_id: int):
    """
    Retrieve the latest investigation report for a case.

    Responses:
      200 COMPLETE    — full investigation row
      200 FAILED      — {"status": "FAILED", "error_message": "..."}
      202 IN_PROGRESS — {"status": "IN_PROGRESS"}
      404             — no investigation has been triggered for this case_id
    """
    investigation = get_latest_investigation(case_id)

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail=f"No investigation found for case_id={case_id}.",
        )

    status = investigation.get("status")

    if status == "IN_PROGRESS":
        return JSONResponse(
            status_code=202,
            content={"status": "IN_PROGRESS"},
        )

    if status == "FAILED":
        return {
            "status": "FAILED",
            "error_message": investigation.get("error_message"),
        }

    return investigation


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


@app.post("/cases/{case_id}/investigate", status_code=202)
def trigger_investigation(case_id: int):
    """
    Trigger an agentic investigation for a scored case.

    Validates that the case exists, assigns a new investigation_id, and
    publishes an InvestigationRequest to the cases.investigate Kafka topic.
    The investigation-consumer picks up the message and runs the pipeline
    asynchronously. Poll GET /cases/{case_id}/investigation for the result.

    Responses:
      202 — investigation accepted and queued
      404 — case_id not found in predictions table
      503 — Kafka unavailable; investigation could not be queued
    """
    case = get_prediction_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    investigation_id = str(uuid.uuid4())

    payload = {
        "investigation_id": investigation_id,
        "case_id": case_id,
    }

    producer = _get_investigate_producer()
    if producer is None:
        raise HTTPException(
            status_code=503,
            detail="Investigation queue unavailable — Kafka is not configured or unreachable.",
        )

    try:
        producer.send(
            _INVESTIGATE_TOPIC,
            key=str(case_id),
            value=payload,
        ).get(timeout=5)
    except KafkaError as exc:
        logger.error(
            "Failed to publish to %s | case_id=%d investigation_id=%s error=%s",
            _INVESTIGATE_TOPIC,
            case_id,
            investigation_id,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail="Failed to queue investigation — broker error.",
        )

    logger.info(
        "Investigation queued | case_id=%d investigation_id=%s",
        case_id,
        investigation_id,
    )

    return JSONResponse(
        status_code=202,
        content={
            "status": "accepted",
            "investigation_id": investigation_id,
            "case_id": case_id,
        },
    )


@app.post("/workflow/audit-event")
def create_workflow_audit_event(body: WorkflowAuditEventRequest):
    """
    Persist a workflow automation event into the workflow_events audit table.

    Called by n8n (or any automation layer) after performing an action so that
    every automated decision is traceable in Postgres.

    If case_id is provided, validates that it exists in the predictions table.
    If case_id is None, the event is treated as a global workflow event (e.g.
    a daily summary) and no case validation is performed.

    Responses:
      200 — event logged successfully
      404 — case_id provided but not found in predictions table
    """
    if body.case_id is not None:
        case = get_prediction_by_id(body.case_id)
        if case is None:
            raise HTTPException(status_code=404, detail=f"Case {body.case_id} not found.")

    payload = body.payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
            payload = parsed if isinstance(parsed, dict) else {"raw": payload}
        except (json.JSONDecodeError, ValueError):
            payload = {"raw": payload}

    record = log_workflow_event({
        "case_id":             body.case_id,
        "workflow_name":       body.workflow_name,
        "workflow_action":     body.workflow_action,
        "status":              body.status,
        "escalation_priority": body.escalation_priority,
        "message":             body.message,
        "payload":             payload,
        "source":              body.source,
    })

    logger.info(
        "Workflow audit event logged | case_id=%s action=%s event_id=%s",
        body.case_id,
        body.workflow_action,
        record.get("id"),
    )

    return {
        "status": "logged",
        "case_id": body.case_id,
        "workflow_action": body.workflow_action,
        "event_id": record.get("id"),
    }


@app.get("/workflow/events")
def list_workflow_events(case_id: int | None = None):
    """
    Return workflow audit events, newest first.

    If case_id is provided, returns only events for that case.
    Otherwise returns the 100 most recent events across all cases.
    """
    return get_workflow_events(case_id)


@app.get("/workflow/metrics")
def workflow_metrics():
    """
    Return observability metrics for the workflow automation layer.

    Covers total event counts broken down by status, source, and action,
    plus named counters for each known workflow action type. Intended for
    frontend monitoring dashboards and health checks.
    """
    return get_workflow_metrics()


@app.get("/workflow/daily-summary")
def daily_fraud_summary():
    """
    Return an all-time operational summary for fraud operations managers.

    Covers case volume, decision distribution, analyst review status, and
    workflow automation event counts. Intended as the data source for scheduled
    n8n daily summary workflows.
    """
    return get_daily_fraud_summary()


@app.get("/workflow/stale-cases")
def list_stale_cases(minutes: int = 120):
    """
    Return unreviewed REVIEW/BLOCK cases older than the given minutes threshold.

    Intended for SLA monitoring and scheduled n8n reminder workflows. Cases are
    considered stale when their transaction timestamp predates NOW() by at least
    the specified number of minutes and no analyst verdict has been recorded.

    Responses:
      200 — list of stale cases (may be empty)
      400 — minutes must be a positive integer
    """
    if minutes <= 0:
        raise HTTPException(
            status_code=400,
            detail="minutes must be a positive integer.",
        )

    cases = get_stale_cases(minutes)
    return {
        "minutes": minutes,
        "count": len(cases),
        "cases": cases,
    }


@app.post("/workflow/notify-case/{case_id}")
def notify_case_workflow(case_id: int):
    """
    Send a fraud case notification payload to the configured n8n webhook.

    Fetches the prediction and latest investigation for the case, builds a
    compact payload, and POSTs it to N8N_WEBHOOK_URL. Intended to be called
    by an analyst or automated trigger after a case is scored or investigated.

    Responses:
      200 — payload sent successfully
      404 — case_id not found in predictions table
      502 — n8n webhook returned a non-2xx response
      503 — N8N_WEBHOOK_URL is not configured
    """
    case = get_prediction_by_id(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    if not N8N_WEBHOOK_URL:
        _log_workflow_dispatch_failure(
            case_id=case_id,
            reason="N8N_WEBHOOK_URL is not configured",
            error_message="N8N_WEBHOOK_URL environment variable is empty or unset.",
        )
        raise HTTPException(
            status_code=503,
            detail="N8N_WEBHOOK_URL is not configured. Set it in the environment to enable workflow notifications.",
        )

    investigation = get_latest_investigation(case_id) or {}

    def _str(val) -> str:
        return str(val) if val is not None else ""

    payload = {
        "case_id":              case_id,
        "transaction_id":       _str(case.get("transaction_id")),
        "amount":               _str(case.get("amount")),
        "timestamp":            _str(case.get("timestamp")),
        "risk_score":           _str(case.get("risk_score")),
        "decision":             _str(case.get("decision")),
        "reasons":              _str(case.get("reasons")),
        "analyst_status":       _str(case.get("analyst_status")),
        "investigation_status": _str(investigation.get("status")),
        "recommendation":       _str(investigation.get("recommendation")),
        "confidence":           _str(investigation.get("confidence")),
        "summary":              _str(investigation.get("summary")),
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        N8N_WEBHOOK_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.status
    except urllib.error.HTTPError as exc:
        logger.error(
            "n8n webhook returned error | case_id=%d status=%d url=%s",
            case_id,
            exc.code,
            N8N_WEBHOOK_URL,
        )
        _log_workflow_dispatch_failure(
            case_id=case_id,
            reason="n8n webhook returned non-2xx response",
            error_message=f"HTTP {exc.code} from {N8N_WEBHOOK_URL}",
            payload=payload,
        )
        raise HTTPException(
            status_code=502,
            detail=f"n8n webhook returned HTTP {exc.code}.",
        )
    except (urllib.error.URLError, OSError) as exc:
        logger.error(
            "n8n webhook unreachable | case_id=%d error=%s url=%s",
            case_id,
            exc,
            N8N_WEBHOOK_URL,
        )
        _log_workflow_dispatch_failure(
            case_id=case_id,
            reason="n8n webhook unreachable",
            error_message=f"{exc} — url={N8N_WEBHOOK_URL}",
            payload=payload,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach n8n webhook: {exc}",
        )

    logger.info(
        "Workflow notification sent | case_id=%d http_status=%d",
        case_id,
        status_code,
    )

    return {
        "status": "sent",
        "case_id": case_id,
        "workflow_url": "configured",
    }
