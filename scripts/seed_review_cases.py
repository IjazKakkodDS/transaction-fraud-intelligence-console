"""
Review case seeder for the Fraud Intelligence Console.

Creates two canonical review cases via HTTP API calls only:
  1. case_fp_review_001    -- REVIEW decision, FALSE_POSITIVE verdict
  2. case_hr_showcase_001  -- BLOCK decision, unreviewed (intake handoff)

Usage:
    python scripts/seed_review_cases.py

Requirements:
    requests library (pip install requests)
    API running at http://localhost:8000
"""

import sys
import time
from typing import Optional
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "http://localhost:8000"
POLL_INTERVAL_S = 6        # seconds between each poll attempt
POLL_MAX_ATTEMPTS = 40     # max polls per step (~4 minutes)
SCORE_POLL_ATTEMPTS = 15   # scoring is fast; fewer retries needed

TIMESTAMP_NIGHT = "2026-05-14T02:00:00Z"
TIMESTAMP_NIGHT_2 = "2026-05-14T02:30:00Z"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def get(path: str, params: Optional[dict] = None) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", params=params, timeout=15)


def post(path: str, body: Optional[dict] = None) -> requests.Response:
    return requests.post(f"{BASE_URL}{path}", json=body, timeout=15)


def check_health() -> None:
    print("Checking API health...")
    resp = get("/health")
    if resp.status_code != 200 or resp.json().get("status") != "ok":
        _abort(f"Health check failed: HTTP {resp.status_code} — {resp.text}")
    print("  API healthy.\n")


# ---------------------------------------------------------------------------
# Step: submit a transaction and wait for it to be scored
# ---------------------------------------------------------------------------

def submit_and_score(payload: dict) -> dict:
    txn_id = payload["transaction_id"]

    # Idempotency: reuse if already scored
    existing = _fetch_prediction(txn_id)
    if existing:
        print(f"  [{txn_id}] Already scored — reusing case {existing['id']}.")
        return existing

    print(f"  [{txn_id}] Submitting to POST /predict ...")
    resp = post("/predict", payload)
    if resp.status_code not in (200, 202):
        _abort(f"POST /predict failed: HTTP {resp.status_code} — {resp.text}")

    print(f"  [{txn_id}] Polling for scored result ...")
    for attempt in range(1, SCORE_POLL_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL_S)
        prediction = _fetch_prediction(txn_id)
        if prediction:
            print(f"  [{txn_id}] Scored on attempt {attempt}: "
                  f"decision={prediction['decision']}  "
                  f"risk_score={prediction['risk_score']}")
            return prediction
        print(f"  [{txn_id}] Not yet scored (attempt {attempt}/{SCORE_POLL_ATTEMPTS}) ...")

    _abort(f"[{txn_id}] Scoring did not complete within the polling window.")


def _fetch_prediction(txn_id: str) -> Optional[dict]:
    resp = get(f"/predictions/{txn_id}")
    if resp.status_code == 200:
        return resp.json()
    return None


# ---------------------------------------------------------------------------
# Step: trigger investigation and wait for COMPLETE
# ---------------------------------------------------------------------------

def trigger_and_wait_investigation(case_id: int, txn_id: str) -> dict:
    # Check if already complete before triggering
    current = _fetch_investigation(case_id)
    if current and current.get("status") == "COMPLETE":
        print(f"  [{txn_id}] Investigation already COMPLETE.")
        return current

    print(f"  [{txn_id}] Triggering investigation via POST /cases/{case_id}/investigate ...")
    resp = post(f"/cases/{case_id}/investigate")
    if resp.status_code not in (200, 202):
        _abort(f"POST /cases/{case_id}/investigate failed: HTTP {resp.status_code} — {resp.text}")

    print(f"  [{txn_id}] Polling for investigation COMPLETE ...")
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL_S)
        investigation = _fetch_investigation(case_id)
        if investigation and investigation.get("status") == "COMPLETE":
            rec = investigation.get("recommendation", "—")
            conf = investigation.get("confidence", "—")
            print(f"  [{txn_id}] Investigation COMPLETE on attempt {attempt}: "
                  f"recommendation={rec}  confidence={conf}")
            return investigation
        status = investigation.get("status", "pending") if investigation else "pending"
        print(f"  [{txn_id}] Investigation status={status} (attempt {attempt}/{POLL_MAX_ATTEMPTS}) ...")

    _abort(f"[{txn_id}] Investigation did not complete within the polling window.")


def _fetch_investigation(case_id: int) -> Optional[dict]:
    resp = get(f"/cases/{case_id}/investigation")
    if resp.status_code == 200:
        return resp.json()
    return None


# ---------------------------------------------------------------------------
# Step: submit analyst verdict
# ---------------------------------------------------------------------------

def submit_verdict(case_id: int, txn_id: str, analyst_status: str, notes: str) -> None:
    print(f"  [{txn_id}] Submitting verdict: {analyst_status} ...")
    resp = post(f"/review-case/{case_id}", {
        "analyst_status": analyst_status,
        "analyst_notes": notes,
    })
    if resp.status_code != 200:
        _abort(f"POST /review-case/{case_id} failed: HTTP {resp.status_code} — {resp.text}")
    print(f"  [{txn_id}] Verdict recorded.")


# ---------------------------------------------------------------------------
# Step: dispatch workflow and confirm audit event
# ---------------------------------------------------------------------------

def dispatch_and_confirm_workflow(case_id: int, txn_id: str) -> str:
    print(f"  [{txn_id}] Dispatching workflow via POST /workflow/notify-case/{case_id} ...")
    resp = post(f"/workflow/notify-case/{case_id}")
    if resp.status_code != 200:
        print(f"  [{txn_id}] WARNING: Workflow dispatch returned HTTP {resp.status_code}. "
              "n8n may not be active. Continuing.")
        return "dispatch_failed"

    print(f"  [{txn_id}] Waiting for workflow audit event ...")
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL_S)
        events = _fetch_workflow_events(case_id)
        success_events = [e for e in events if e.get("status") == "SUCCESS"
                          and e.get("source") == "n8n"]
        if success_events:
            action = success_events[0].get("workflow_action", "—")
            print(f"  [{txn_id}] Workflow audit event confirmed on attempt {attempt}: "
                  f"action={action}")
            return "success"
        any_events = len(events)
        print(f"  [{txn_id}] Waiting for SUCCESS event (attempt {attempt}/{POLL_MAX_ATTEMPTS}, "
              f"total events so far: {any_events}) ...")

    print(f"  [{txn_id}] WARNING: No SUCCESS workflow event appeared within polling window.")
    return "no_success_event"


def _fetch_workflow_events(case_id: int) -> list:
    resp = get("/workflow/events", params={"case_id": case_id})
    if resp.status_code == 200:
        return resp.json()
    return []


# ---------------------------------------------------------------------------
# Review case 1: REVIEW false positive
# ---------------------------------------------------------------------------

REVIEW_PROFILES = [
    {"amount": 750,  "transaction_id": "case_fp_review_001_a750"},
    {"amount": 600,  "transaction_id": "case_fp_review_001_a600"},
    {"amount": 450,  "transaction_id": "case_fp_review_001_a450"},
]

REVIEW_BASE_PAYLOAD = {
    "user_id":           "reviewer_user_fp_001",
    "merchant_id":       "reviewer_merchant_elec_002",
    "timestamp":         TIMESTAMP_NIGHT,
    "currency":          "USD",
    "country":           "RU",
    "city":              "Moscow",
    "payment_method":    "credit_card",
    "merchant_category": "electronics",
    "is_international":  True,
    "device_id":         None,
    "device_type":       "mobile",
    "ip_address":        "185.220.101.42",
}


def build_review_case() -> dict:
    print("=" * 60)
    print("REVIEW CASE 1: case_fp_review_001 (target: REVIEW)")
    print("=" * 60)

    for profile in REVIEW_PROFILES:
        txn_id = profile["transaction_id"]
        payload = {**REVIEW_BASE_PAYLOAD, "transaction_id": txn_id, "amount": profile["amount"]}

        prediction = submit_and_score(payload)
        decision = prediction.get("decision")
        case_id = prediction["id"]

        if decision == "REVIEW":
            print(f"  REVIEW decision confirmed for {txn_id} (case {case_id}).\n")

            investigation = trigger_and_wait_investigation(case_id, txn_id)

            submit_verdict(
                case_id, txn_id,
                analyst_status="FALSE_POSITIVE",
                notes="Low-value international transaction. Fraud signal insufficient. Marked false positive.",
            )

            workflow_status = dispatch_and_confirm_workflow(case_id, txn_id)

            return {
                "role":                "false_positive_review",
                "transaction_id":      txn_id,
                "case_id":             case_id,
                "decision":            decision,
                "risk_score":          prediction.get("risk_score"),
                "rule_flag":           prediction.get("rule_flag"),
                "analyst_status":      "FALSE_POSITIVE",
                "investigation_status": investigation.get("status"),
                "workflow_event_status": workflow_status,
                "notes":               f"Amount ${profile['amount']}. REVIEW confirmed.",
            }

        print(f"  [{txn_id}] decision={decision} (not REVIEW) — trying next amount profile.\n")

    _abort(
        "Could not produce a REVIEW decision across all amount profiles "
        f"({[p['amount'] for p in REVIEW_PROFILES]}). "
        "Check scoring thresholds and model behaviour."
    )


# ---------------------------------------------------------------------------
# Review case 2: BLOCK intake showcase
# ---------------------------------------------------------------------------

INTAKE_PAYLOAD = {
    "transaction_id":    "case_hr_showcase_001",
    "user_id":           "reviewer_user_hr_001",
    "merchant_id":       "reviewer_merchant_elec_001",
    "amount":            8500,
    "timestamp":         TIMESTAMP_NIGHT_2,
    "currency":          "USD",
    "country":           "RU",
    "city":              "Moscow",
    "payment_method":    "credit_card",
    "merchant_category": "electronics",
    "is_international":  True,
    "device_id":         None,
    "device_type":       "mobile",
    "ip_address":        "185.220.101.42",
}


def build_intake_case() -> dict:
    print("=" * 60)
    print("REVIEW CASE 2: case_hr_showcase_001 (target: BLOCK)")
    print("=" * 60)

    txn_id = INTAKE_PAYLOAD["transaction_id"]
    prediction = submit_and_score(INTAKE_PAYLOAD)
    decision = prediction.get("decision")
    case_id = prediction["id"]

    if decision != "BLOCK":
        _abort(f"[{txn_id}] Expected BLOCK but got {decision}. "
               "Check HIGH_AMOUNT_THRESHOLD and scoring configuration.")

    print(f"  BLOCK decision confirmed for {txn_id} (case {case_id}).\n")

    investigation = trigger_and_wait_investigation(case_id, txn_id)

    # No verdict -- leave analyst_status as null for intake handoff
    print(f"  [{txn_id}] Skipping verdict (case left unreviewed for intake handoff).")

    workflow_status = dispatch_and_confirm_workflow(case_id, txn_id)

    return {
        "role":                "intake_showcase_block",
        "transaction_id":      txn_id,
        "case_id":             case_id,
        "decision":            decision,
        "risk_score":          prediction.get("risk_score"),
        "rule_flag":           prediction.get("rule_flag"),
        "analyst_status":      "null (unreviewed)",
        "investigation_status": investigation.get("status"),
        "workflow_event_status": workflow_status,
        "notes":               "Sample high-risk case. Unreviewed P0.",
    }


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def print_summary(results: list[dict]) -> None:
    print("\n" + "=" * 60)
    print("REVIEW SEED SUMMARY")
    print("=" * 60)

    fields = [
        ("Role",                "role"),
        ("Transaction ID",      "transaction_id"),
        ("Case ID",             "case_id"),
        ("Decision",            "decision"),
        ("Risk Score",          "risk_score"),
        ("Rule Flag",           "rule_flag"),
        ("Analyst Status",      "analyst_status"),
        ("Investigation",       "investigation_status"),
        ("Workflow Event",      "workflow_event_status"),
        ("Notes",               "notes"),
    ]

    for result in results:
        print()
        for label, key in fields:
            value = result.get(key, "—")
            print(f"  {label:<22} {value}")

    print()


# ---------------------------------------------------------------------------
# Error helper
# ---------------------------------------------------------------------------

def _abort(message: str) -> None:
    print(f"\nERROR: {message}", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("\nFraud Intelligence Console - Review Case Seeder")
    print("=" * 60)
    print(f"Target API: {BASE_URL}")
    print(f"Poll interval: {POLL_INTERVAL_S}s  Max attempts: {POLL_MAX_ATTEMPTS}")
    print()

    check_health()

    results = []
    results.append(build_review_case())
    print()
    results.append(build_intake_case())

    print_summary(results)

    print("Review case seeder complete. Both cases prepared successfully.")
    print("Seeded review cases for the Fraud Console. See README.md for review workflow context.\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
