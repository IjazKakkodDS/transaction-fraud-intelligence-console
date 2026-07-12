"""
Hosted Inspection Dataset Population Utility.

Populates the hosted inspection environment with a controlled synthetic
transaction dataset so the public-facing product pages look meaningfully
populated for technical evaluation and architecture review.

All data created by this script is SYNTHETIC. No real transaction data,
no real customer data, no real financial records. Transaction IDs are
prefixed with SYNTH-INSP- to make their synthetic origin unambiguous.

Usage:
    # Populate the hosted environment (default)
    python scripts/populate_inspection_dataset.py

    # Target a specific API
    python scripts/populate_inspection_dataset.py --api-url https://fraud-console-api.onrender.com

    # Preview without making API calls
    python scripts/populate_inspection_dataset.py --dry-run

    # Reduce count for a quick test
    python scripts/populate_inspection_dataset.py --count 20

WARNING: This script creates synthetic inspection data only. It does not
reflect real fraud outcomes, real customer behaviour, or real transaction
volumes. It exists solely to make the hosted product inspection environment
look meaningfully populated.
"""

import argparse
import os
import sys
import time
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_API_URL = "https://fraud-console-api.onrender.com"
POLL_INTERVAL_S = 4
POLL_MAX_ATTEMPTS = 12
REQUEST_TIMEOUT_S = 30


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(base_url: str, path: str, params: Optional[dict] = None) -> requests.Response:
    return requests.get(f"{base_url}{path}", params=params, timeout=REQUEST_TIMEOUT_S)


def _post(base_url: str, path: str, body: Optional[dict] = None) -> requests.Response:
    return requests.post(f"{base_url}{path}", json=body, timeout=REQUEST_TIMEOUT_S)


def _fetch_prediction(base_url: str, txn_id: str) -> Optional[dict]:
    try:
        resp = _get(base_url, f"/predictions/{txn_id}")
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException:
        pass
    return None


# ---------------------------------------------------------------------------
# Submit one transaction and return the scored prediction record.
# Idempotent: reuses an existing record if the transaction_id is already scored.
# ---------------------------------------------------------------------------

def submit_transaction(base_url: str, payload: dict, dry_run: bool) -> Optional[dict]:
    txn_id = payload["transaction_id"]

    existing = _fetch_prediction(base_url, txn_id)
    if existing:
        return existing

    if dry_run:
        print(f"  [DRY-RUN] Would submit: {txn_id} amount={payload.get('amount')}")
        return None

    try:
        resp = _post(base_url, "/predict", payload)
    except requests.RequestException as exc:
        print(f"  [WARN] POST /predict failed for {txn_id}: {exc}", file=sys.stderr)
        return None

    if resp.status_code not in (200, 202):
        print(f"  [WARN] POST /predict returned HTTP {resp.status_code} for {txn_id}",
              file=sys.stderr)
        return None

    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL_S)
        prediction = _fetch_prediction(base_url, txn_id)
        if prediction:
            return prediction
    print(f"  [WARN] Scoring did not complete within polling window for {txn_id}",
          file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Submit analyst verdict for a case
# ---------------------------------------------------------------------------

def submit_verdict(
    base_url: str,
    case_id: int,
    txn_id: str,
    analyst_status: str,
    analyst_notes: str,
    dry_run: bool,
) -> bool:
    if dry_run:
        print(f"  [DRY-RUN] Would submit verdict {analyst_status} for case {case_id}")
        return True
    try:
        resp = _post(base_url, f"/review-case/{case_id}", {
            "analyst_status": analyst_status,
            "analyst_notes": analyst_notes,
        })
        return resp.status_code == 200
    except requests.RequestException as exc:
        print(f"  [WARN] Verdict submission failed for case {case_id}: {exc}",
              file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Write a workflow audit event directly (does not require n8n)
# ---------------------------------------------------------------------------

def write_workflow_event(
    base_url: str,
    case_id: int,
    workflow_action: str,
    status: str,
    message: str,
    dry_run: bool,
) -> bool:
    if dry_run:
        print(f"  [DRY-RUN] Would write workflow event {workflow_action} for case {case_id}")
        return True
    try:
        resp = _post(base_url, "/workflow/audit-event", {
            "case_id": case_id,
            "workflow_name": "Fraud Case Escalation Workflow",
            "workflow_action": workflow_action,
            "status": status,
            "escalation_priority": "HIGH" if "BLOCK" in message or "FRAUD" in message else "MEDIUM",
            "message": message,
            "source": "inspection-dataset-utility",
        })
        return resp.status_code == 200
    except requests.RequestException as exc:
        print(f"  [WARN] Workflow event write failed for case {case_id}: {exc}",
              file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Synthetic transaction definitions
#
# Designed to produce a realistic tier distribution:
#   BLOCK (high risk): amount > $1000, night time, high-risk signals
#   REVIEW:            moderate risk mix
#   APPROVE:           low-risk, domestic, small amounts
#
# All transaction_ids are prefixed SYNTH-INSP- to mark synthetic origin.
# All merchant names are clearly fictional. No real names, accounts, cards.
# ---------------------------------------------------------------------------

NIGHT_HIGH_01 = "2026-06-10T02:14:00Z"
NIGHT_HIGH_02 = "2026-06-11T03:07:00Z"
NIGHT_HIGH_03 = "2026-06-12T01:52:00Z"
NIGHT_HIGH_04 = "2026-06-13T02:44:00Z"
NIGHT_HIGH_05 = "2026-06-14T04:11:00Z"
NIGHT_MED_01  = "2026-06-10T23:45:00Z"
NIGHT_MED_02  = "2026-06-11T23:20:00Z"
NIGHT_MED_03  = "2026-06-12T00:15:00Z"
NIGHT_MED_04  = "2026-06-13T01:05:00Z"
NIGHT_MED_05  = "2026-06-14T23:55:00Z"
DAY_01        = "2026-06-10T14:22:00Z"
DAY_02        = "2026-06-11T11:05:00Z"
DAY_03        = "2026-06-12T15:48:00Z"
DAY_04        = "2026-06-13T09:33:00Z"
DAY_05        = "2026-06-14T16:20:00Z"
DAY_06        = "2026-06-15T10:44:00Z"
DAY_07        = "2026-06-16T13:09:00Z"
DAY_08        = "2026-06-17T12:17:00Z"
DAY_09        = "2026-06-18T11:50:00Z"
DAY_10        = "2026-06-19T14:38:00Z"

SYNTHETIC_TRANSACTIONS = [

    # ------------------------------------------------------------------
    # BLOCK-tier targets (10 transactions)
    # High amount + night + international high-risk country + electronics
    # Rule flag fires on: night_high (amount>1000 AND night) OR intl_high
    # ------------------------------------------------------------------
    {
        "transaction_id": "SYNTH-INSP-0001",
        "user_id": "sinsp-usr-001",
        "merchant_id": "sinsp-mrc-elec-001",
        "amount": 3500.00,
        "timestamp": NIGHT_HIGH_01,
        "currency": "USD",
        "country": "RU",
        "city": "Moscow",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.11",
    },
    {
        "transaction_id": "SYNTH-INSP-0002",
        "user_id": "sinsp-usr-002",
        "merchant_id": "sinsp-mrc-elec-002",
        "amount": 7200.00,
        "timestamp": NIGHT_HIGH_02,
        "currency": "USD",
        "country": "NG",
        "city": "Lagos",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.12",
    },
    {
        "transaction_id": "SYNTH-INSP-0003",
        "user_id": "sinsp-usr-003",
        "merchant_id": "sinsp-mrc-elec-003",
        "amount": 4800.00,
        "timestamp": NIGHT_HIGH_03,
        "currency": "USD",
        "country": "UA",
        "city": "Kharkiv",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "desktop",
        "ip_address": "198.51.100.13",
    },
    {
        "transaction_id": "SYNTH-INSP-0004",
        "user_id": "sinsp-usr-004",
        "merchant_id": "sinsp-mrc-elec-004",
        "amount": 12000.00,
        "timestamp": NIGHT_HIGH_04,
        "currency": "USD",
        "country": "RU",
        "city": "Saint Petersburg",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.14",
    },
    {
        "transaction_id": "SYNTH-INSP-0005",
        "user_id": "sinsp-usr-005",
        "merchant_id": "sinsp-mrc-elec-005",
        "amount": 5500.00,
        "timestamp": NIGHT_HIGH_05,
        "currency": "USD",
        "country": "IR",
        "city": "Tehran",
        "payment_method": "digital_wallet",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.15",
    },
    {
        "transaction_id": "SYNTH-INSP-0006",
        "user_id": "sinsp-usr-006",
        "merchant_id": "sinsp-mrc-gaming-001",
        "amount": 9100.00,
        "timestamp": NIGHT_HIGH_01,
        "currency": "USD",
        "country": "RU",
        "city": "Moscow",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": None,
        "device_type": "desktop",
        "ip_address": "198.51.100.16",
    },
    {
        "transaction_id": "SYNTH-INSP-0007",
        "user_id": "sinsp-usr-007",
        "merchant_id": "sinsp-mrc-elec-006",
        "amount": 3200.00,
        "timestamp": NIGHT_HIGH_02,
        "currency": "USD",
        "country": "NG",
        "city": "Abuja",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.17",
    },
    {
        "transaction_id": "SYNTH-INSP-0008",
        "user_id": "sinsp-usr-008",
        "merchant_id": "sinsp-mrc-elec-007",
        "amount": 6700.00,
        "timestamp": NIGHT_HIGH_03,
        "currency": "USD",
        "country": "UA",
        "city": "Kyiv",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.18",
    },
    {
        "transaction_id": "SYNTH-INSP-0009",
        "user_id": "sinsp-usr-001",
        "merchant_id": "sinsp-mrc-travel-001",
        "amount": 8300.00,
        "timestamp": NIGHT_HIGH_04,
        "currency": "USD",
        "country": "RU",
        "city": "Moscow",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.19",
    },
    {
        "transaction_id": "SYNTH-INSP-0010",
        "user_id": "sinsp-usr-009",
        "merchant_id": "sinsp-mrc-elec-008",
        "amount": 15000.00,
        "timestamp": NIGHT_HIGH_05,
        "currency": "USD",
        "country": "NG",
        "city": "Lagos",
        "payment_method": "digital_wallet",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "desktop",
        "ip_address": "198.51.100.20",
    },

    # ------------------------------------------------------------------
    # REVIEW-tier targets A (10 transactions)
    # Amount < $1000 (rule_flag stays 0), night, international high-risk
    # Model sees high-risk features -> base_score ~ 0.6 -> REVIEW
    # ------------------------------------------------------------------
    {
        "transaction_id": "SYNTH-INSP-0011",
        "user_id": "sinsp-usr-010",
        "merchant_id": "sinsp-mrc-elec-009",
        "amount": 850.00,
        "timestamp": NIGHT_HIGH_01,
        "currency": "USD",
        "country": "RU",
        "city": "Moscow",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.21",
    },
    {
        "transaction_id": "SYNTH-INSP-0012",
        "user_id": "sinsp-usr-011",
        "merchant_id": "sinsp-mrc-gaming-002",
        "amount": 640.00,
        "timestamp": NIGHT_HIGH_02,
        "currency": "USD",
        "country": "NG",
        "city": "Lagos",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.22",
    },
    {
        "transaction_id": "SYNTH-INSP-0013",
        "user_id": "sinsp-usr-012",
        "merchant_id": "sinsp-mrc-travel-002",
        "amount": 780.00,
        "timestamp": NIGHT_MED_01,
        "currency": "USD",
        "country": "UA",
        "city": "Odessa",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": None,
        "device_type": "desktop",
        "ip_address": "198.51.100.23",
    },
    {
        "transaction_id": "SYNTH-INSP-0014",
        "user_id": "sinsp-usr-013",
        "merchant_id": "sinsp-mrc-elec-010",
        "amount": 520.00,
        "timestamp": NIGHT_HIGH_03,
        "currency": "USD",
        "country": "RU",
        "city": "Novosibirsk",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.24",
    },
    {
        "transaction_id": "SYNTH-INSP-0015",
        "user_id": "sinsp-usr-014",
        "merchant_id": "sinsp-mrc-gaming-003",
        "amount": 970.00,
        "timestamp": NIGHT_MED_02,
        "currency": "USD",
        "country": "NG",
        "city": "Abuja",
        "payment_method": "digital_wallet",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.25",
    },
    {
        "transaction_id": "SYNTH-INSP-0016",
        "user_id": "sinsp-usr-015",
        "merchant_id": "sinsp-mrc-elec-011",
        "amount": 730.00,
        "timestamp": NIGHT_HIGH_04,
        "currency": "USD",
        "country": "UA",
        "city": "Lviv",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "desktop",
        "ip_address": "198.51.100.26",
    },
    {
        "transaction_id": "SYNTH-INSP-0017",
        "user_id": "sinsp-usr-016",
        "merchant_id": "sinsp-mrc-gaming-004",
        "amount": 480.00,
        "timestamp": NIGHT_MED_03,
        "currency": "USD",
        "country": "RU",
        "city": "Kazan",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.27",
    },
    {
        "transaction_id": "SYNTH-INSP-0018",
        "user_id": "sinsp-usr-017",
        "merchant_id": "sinsp-mrc-travel-003",
        "amount": 890.00,
        "timestamp": NIGHT_HIGH_05,
        "currency": "USD",
        "country": "NG",
        "city": "Port Harcourt",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.28",
    },
    {
        "transaction_id": "SYNTH-INSP-0019",
        "user_id": "sinsp-usr-018",
        "merchant_id": "sinsp-mrc-elec-012",
        "amount": 610.00,
        "timestamp": NIGHT_MED_04,
        "currency": "USD",
        "country": "UA",
        "city": "Dnipro",
        "payment_method": "digital_wallet",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "198.51.100.29",
    },
    {
        "transaction_id": "SYNTH-INSP-0020",
        "user_id": "sinsp-usr-019",
        "merchant_id": "sinsp-mrc-gaming-005",
        "amount": 810.00,
        "timestamp": NIGHT_MED_05,
        "currency": "USD",
        "country": "RU",
        "city": "Vladivostok",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": None,
        "device_type": "desktop",
        "ip_address": "198.51.100.30",
    },

    # ------------------------------------------------------------------
    # REVIEW-tier targets B (10 transactions)
    # Higher amounts, day time, low-risk country but international + high-risk category
    # rule_flag=0 (no risky_rail since day; intl but low-risk country)
    # model sees: is_high_amount=1, is_international=1, is_high_risk_category=1 -> model may flag
    # ------------------------------------------------------------------
    {
        "transaction_id": "SYNTH-INSP-0021",
        "user_id": "sinsp-usr-020",
        "merchant_id": "sinsp-mrc-elec-013",
        "amount": 1400.00,
        "timestamp": DAY_01,
        "currency": "USD",
        "country": "GB",
        "city": "London",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": "sinsp-dev-001",
        "device_type": "desktop",
        "ip_address": "198.51.100.31",
    },
    {
        "transaction_id": "SYNTH-INSP-0022",
        "user_id": "sinsp-usr-021",
        "merchant_id": "sinsp-mrc-gaming-006",
        "amount": 2200.00,
        "timestamp": DAY_02,
        "currency": "USD",
        "country": "CA",
        "city": "Toronto",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": "sinsp-dev-002",
        "device_type": "desktop",
        "ip_address": "198.51.100.32",
    },
    {
        "transaction_id": "SYNTH-INSP-0023",
        "user_id": "sinsp-usr-022",
        "merchant_id": "sinsp-mrc-travel-004",
        "amount": 1850.00,
        "timestamp": DAY_03,
        "currency": "USD",
        "country": "DE",
        "city": "Berlin",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": "sinsp-dev-003",
        "device_type": "mobile",
        "ip_address": "198.51.100.33",
    },
    {
        "transaction_id": "SYNTH-INSP-0024",
        "user_id": "sinsp-usr-023",
        "merchant_id": "sinsp-mrc-elec-014",
        "amount": 1200.00,
        "timestamp": DAY_04,
        "currency": "USD",
        "country": "AU",
        "city": "Sydney",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": "sinsp-dev-004",
        "device_type": "desktop",
        "ip_address": "198.51.100.34",
    },
    {
        "transaction_id": "SYNTH-INSP-0025",
        "user_id": "sinsp-usr-024",
        "merchant_id": "sinsp-mrc-gaming-007",
        "amount": 2500.00,
        "timestamp": DAY_05,
        "currency": "USD",
        "country": "FR",
        "city": "Paris",
        "payment_method": "digital_wallet",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": "sinsp-dev-005",
        "device_type": "mobile",
        "ip_address": "198.51.100.35",
    },
    {
        "transaction_id": "SYNTH-INSP-0026",
        "user_id": "sinsp-usr-025",
        "merchant_id": "sinsp-mrc-travel-005",
        "amount": 1680.00,
        "timestamp": DAY_06,
        "currency": "USD",
        "country": "JP",
        "city": "Tokyo",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": "sinsp-dev-006",
        "device_type": "mobile",
        "ip_address": "198.51.100.36",
    },
    {
        "transaction_id": "SYNTH-INSP-0027",
        "user_id": "sinsp-usr-026",
        "merchant_id": "sinsp-mrc-elec-015",
        "amount": 1950.00,
        "timestamp": DAY_07,
        "currency": "USD",
        "country": "NL",
        "city": "Amsterdam",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": "sinsp-dev-007",
        "device_type": "desktop",
        "ip_address": "198.51.100.37",
    },
    {
        "transaction_id": "SYNTH-INSP-0028",
        "user_id": "sinsp-usr-027",
        "merchant_id": "sinsp-mrc-gaming-008",
        "amount": 1300.00,
        "timestamp": DAY_08,
        "currency": "USD",
        "country": "GB",
        "city": "Manchester",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": "sinsp-dev-008",
        "device_type": "mobile",
        "ip_address": "198.51.100.38",
    },
    {
        "transaction_id": "SYNTH-INSP-0029",
        "user_id": "sinsp-usr-028",
        "merchant_id": "sinsp-mrc-travel-006",
        "amount": 2100.00,
        "timestamp": DAY_09,
        "currency": "USD",
        "country": "CA",
        "city": "Vancouver",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": "sinsp-dev-009",
        "device_type": "desktop",
        "ip_address": "198.51.100.39",
    },
    {
        "transaction_id": "SYNTH-INSP-0030",
        "user_id": "sinsp-usr-029",
        "merchant_id": "sinsp-mrc-elec-016",
        "amount": 1750.00,
        "timestamp": DAY_10,
        "currency": "USD",
        "country": "DE",
        "city": "Munich",
        "payment_method": "digital_wallet",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": "sinsp-dev-010",
        "device_type": "desktop",
        "ip_address": "198.51.100.40",
    },

    # ------------------------------------------------------------------
    # MEDIUM cases (25 transactions)
    # Mixed signals -- some REVIEW, some APPROVE
    # Night domestic + electronics (model flags but rule_flag=0 if amount<1000)
    # Or domestic day moderate amount + travel
    # ------------------------------------------------------------------
    {
        "transaction_id": "SYNTH-INSP-0031",
        "user_id": "sinsp-usr-030",
        "merchant_id": "sinsp-mrc-travel-007",
        "amount": 420.00,
        "timestamp": NIGHT_MED_01,
        "currency": "USD",
        "country": "US",
        "city": "New York",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": False,
        "device_id": "sinsp-dev-011",
        "device_type": "mobile",
        "ip_address": "203.0.113.51",
    },
    {
        "transaction_id": "SYNTH-INSP-0032",
        "user_id": "sinsp-usr-031",
        "merchant_id": "sinsp-mrc-gaming-009",
        "amount": 280.00,
        "timestamp": NIGHT_MED_02,
        "currency": "USD",
        "country": "US",
        "city": "Los Angeles",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": False,
        "device_id": None,
        "device_type": "desktop",
        "ip_address": "203.0.113.52",
    },
    {
        "transaction_id": "SYNTH-INSP-0033",
        "user_id": "sinsp-usr-032",
        "merchant_id": "sinsp-mrc-elec-017",
        "amount": 650.00,
        "timestamp": NIGHT_MED_03,
        "currency": "USD",
        "country": "US",
        "city": "Chicago",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": False,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "203.0.113.53",
    },
    {
        "transaction_id": "SYNTH-INSP-0034",
        "user_id": "sinsp-usr-033",
        "merchant_id": "sinsp-mrc-travel-008",
        "amount": 380.00,
        "timestamp": DAY_01,
        "currency": "USD",
        "country": "MX",
        "city": "Mexico City",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": "sinsp-dev-012",
        "device_type": "mobile",
        "ip_address": "203.0.113.54",
    },
    {
        "transaction_id": "SYNTH-INSP-0035",
        "user_id": "sinsp-usr-034",
        "merchant_id": "sinsp-mrc-gaming-010",
        "amount": 190.00,
        "timestamp": NIGHT_MED_04,
        "currency": "USD",
        "country": "US",
        "city": "Houston",
        "payment_method": "digital_wallet",
        "merchant_category": "gaming",
        "is_international": False,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "203.0.113.55",
    },
    {
        "transaction_id": "SYNTH-INSP-0036",
        "user_id": "sinsp-usr-035",
        "merchant_id": "sinsp-mrc-elec-018",
        "amount": 540.00,
        "timestamp": DAY_02,
        "currency": "USD",
        "country": "BR",
        "city": "Sao Paulo",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": "sinsp-dev-013",
        "device_type": "mobile",
        "ip_address": "203.0.113.56",
    },
    {
        "transaction_id": "SYNTH-INSP-0037",
        "user_id": "sinsp-usr-036",
        "merchant_id": "sinsp-mrc-travel-009",
        "amount": 710.00,
        "timestamp": DAY_03,
        "currency": "USD",
        "country": "IN",
        "city": "Mumbai",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": "sinsp-dev-014",
        "device_type": "desktop",
        "ip_address": "203.0.113.57",
    },
    {
        "transaction_id": "SYNTH-INSP-0038",
        "user_id": "sinsp-usr-037",
        "merchant_id": "sinsp-mrc-gaming-011",
        "amount": 330.00,
        "timestamp": NIGHT_MED_05,
        "currency": "USD",
        "country": "US",
        "city": "Phoenix",
        "payment_method": "digital_wallet",
        "merchant_category": "gaming",
        "is_international": False,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "203.0.113.58",
    },
    {
        "transaction_id": "SYNTH-INSP-0039",
        "user_id": "sinsp-usr-038",
        "merchant_id": "sinsp-mrc-elec-019",
        "amount": 460.00,
        "timestamp": DAY_04,
        "currency": "USD",
        "country": "CN",
        "city": "Shanghai",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": "sinsp-dev-015",
        "device_type": "desktop",
        "ip_address": "203.0.113.59",
    },
    {
        "transaction_id": "SYNTH-INSP-0040",
        "user_id": "sinsp-usr-039",
        "merchant_id": "sinsp-mrc-travel-010",
        "amount": 590.00,
        "timestamp": DAY_05,
        "currency": "USD",
        "country": "TR",
        "city": "Istanbul",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": "sinsp-dev-016",
        "device_type": "mobile",
        "ip_address": "203.0.113.60",
    },
    {
        "transaction_id": "SYNTH-INSP-0041",
        "user_id": "sinsp-usr-040",
        "merchant_id": "sinsp-mrc-gaming-012",
        "amount": 250.00,
        "timestamp": DAY_06,
        "currency": "USD",
        "country": "US",
        "city": "San Antonio",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": False,
        "device_id": "sinsp-dev-017",
        "device_type": "mobile",
        "ip_address": "203.0.113.61",
    },
    {
        "transaction_id": "SYNTH-INSP-0042",
        "user_id": "sinsp-usr-041",
        "merchant_id": "sinsp-mrc-elec-020",
        "amount": 810.00,
        "timestamp": DAY_07,
        "currency": "USD",
        "country": "ZA",
        "city": "Johannesburg",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": "sinsp-dev-018",
        "device_type": "desktop",
        "ip_address": "203.0.113.62",
    },
    {
        "transaction_id": "SYNTH-INSP-0043",
        "user_id": "sinsp-usr-042",
        "merchant_id": "sinsp-mrc-travel-011",
        "amount": 175.00,
        "timestamp": NIGHT_HIGH_01,
        "currency": "USD",
        "country": "US",
        "city": "Dallas",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": False,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "203.0.113.63",
    },
    {
        "transaction_id": "SYNTH-INSP-0044",
        "user_id": "sinsp-usr-043",
        "merchant_id": "sinsp-mrc-gaming-013",
        "amount": 440.00,
        "timestamp": DAY_08,
        "currency": "USD",
        "country": "ID",
        "city": "Jakarta",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": "sinsp-dev-019",
        "device_type": "mobile",
        "ip_address": "203.0.113.64",
    },
    {
        "transaction_id": "SYNTH-INSP-0045",
        "user_id": "sinsp-usr-044",
        "merchant_id": "sinsp-mrc-elec-021",
        "amount": 360.00,
        "timestamp": DAY_09,
        "currency": "USD",
        "country": "MX",
        "city": "Guadalajara",
        "payment_method": "digital_wallet",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": "sinsp-dev-020",
        "device_type": "mobile",
        "ip_address": "203.0.113.65",
    },
    {
        "transaction_id": "SYNTH-INSP-0046",
        "user_id": "sinsp-usr-045",
        "merchant_id": "sinsp-mrc-travel-012",
        "amount": 680.00,
        "timestamp": DAY_10,
        "currency": "USD",
        "country": "TH",
        "city": "Bangkok",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": "sinsp-dev-021",
        "device_type": "desktop",
        "ip_address": "203.0.113.66",
    },
    {
        "transaction_id": "SYNTH-INSP-0047",
        "user_id": "sinsp-usr-046",
        "merchant_id": "sinsp-mrc-gaming-014",
        "amount": 220.00,
        "timestamp": NIGHT_MED_01,
        "currency": "USD",
        "country": "US",
        "city": "San Diego",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": False,
        "device_id": None,
        "device_type": "desktop",
        "ip_address": "203.0.113.67",
    },
    {
        "transaction_id": "SYNTH-INSP-0048",
        "user_id": "sinsp-usr-047",
        "merchant_id": "sinsp-mrc-elec-022",
        "amount": 490.00,
        "timestamp": DAY_01,
        "currency": "USD",
        "country": "PH",
        "city": "Manila",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": True,
        "device_id": "sinsp-dev-022",
        "device_type": "mobile",
        "ip_address": "203.0.113.68",
    },
    {
        "transaction_id": "SYNTH-INSP-0049",
        "user_id": "sinsp-usr-048",
        "merchant_id": "sinsp-mrc-travel-013",
        "amount": 310.00,
        "timestamp": DAY_02,
        "currency": "USD",
        "country": "US",
        "city": "Seattle",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": False,
        "device_id": "sinsp-dev-023",
        "device_type": "mobile",
        "ip_address": "203.0.113.69",
    },
    {
        "transaction_id": "SYNTH-INSP-0050",
        "user_id": "sinsp-usr-049",
        "merchant_id": "sinsp-mrc-gaming-015",
        "amount": 760.00,
        "timestamp": DAY_03,
        "currency": "USD",
        "country": "CO",
        "city": "Bogota",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": "sinsp-dev-024",
        "device_type": "desktop",
        "ip_address": "203.0.113.70",
    },
    {
        "transaction_id": "SYNTH-INSP-0051",
        "user_id": "sinsp-usr-050",
        "merchant_id": "sinsp-mrc-elec-023",
        "amount": 145.00,
        "timestamp": NIGHT_HIGH_02,
        "currency": "USD",
        "country": "US",
        "city": "Denver",
        "payment_method": "credit_card",
        "merchant_category": "electronics",
        "is_international": False,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "203.0.113.71",
    },
    {
        "transaction_id": "SYNTH-INSP-0052",
        "user_id": "sinsp-usr-051",
        "merchant_id": "sinsp-mrc-travel-014",
        "amount": 420.00,
        "timestamp": DAY_04,
        "currency": "USD",
        "country": "VN",
        "city": "Ho Chi Minh City",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": "sinsp-dev-025",
        "device_type": "mobile",
        "ip_address": "203.0.113.72",
    },
    {
        "transaction_id": "SYNTH-INSP-0053",
        "user_id": "sinsp-usr-052",
        "merchant_id": "sinsp-mrc-gaming-016",
        "amount": 570.00,
        "timestamp": DAY_05,
        "currency": "USD",
        "country": "EG",
        "city": "Cairo",
        "payment_method": "credit_card",
        "merchant_category": "gaming",
        "is_international": True,
        "device_id": "sinsp-dev-026",
        "device_type": "desktop",
        "ip_address": "203.0.113.73",
    },
    {
        "transaction_id": "SYNTH-INSP-0054",
        "user_id": "sinsp-usr-053",
        "merchant_id": "sinsp-mrc-elec-024",
        "amount": 320.00,
        "timestamp": NIGHT_MED_02,
        "currency": "USD",
        "country": "US",
        "city": "Minneapolis",
        "payment_method": "digital_wallet",
        "merchant_category": "electronics",
        "is_international": False,
        "device_id": None,
        "device_type": "mobile",
        "ip_address": "203.0.113.74",
    },
    {
        "transaction_id": "SYNTH-INSP-0055",
        "user_id": "sinsp-usr-054",
        "merchant_id": "sinsp-mrc-travel-015",
        "amount": 890.00,
        "timestamp": DAY_06,
        "currency": "USD",
        "country": "AR",
        "city": "Buenos Aires",
        "payment_method": "credit_card",
        "merchant_category": "travel",
        "is_international": True,
        "device_id": "sinsp-dev-027",
        "device_type": "mobile",
        "ip_address": "203.0.113.75",
    },

    # ------------------------------------------------------------------
    # LOW RISK targets (20 transactions)
    # Small amounts, domestic US, day time, low-risk merchant categories
    # Expected: rule_flag=0, model_prediction=0, APPROVE
    # ------------------------------------------------------------------
    {
        "transaction_id": "SYNTH-INSP-0056",
        "user_id": "sinsp-usr-055",
        "merchant_id": "sinsp-mrc-grocery-001",
        "amount": 48.50,
        "timestamp": DAY_01,
        "currency": "USD",
        "country": "US",
        "city": "Boston",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "is_international": False,
        "device_id": "sinsp-dev-028",
        "device_type": "mobile",
        "ip_address": "192.0.2.101",
    },
    {
        "transaction_id": "SYNTH-INSP-0057",
        "user_id": "sinsp-usr-056",
        "merchant_id": "sinsp-mrc-pharmacy-001",
        "amount": 32.75,
        "timestamp": DAY_02,
        "currency": "USD",
        "country": "US",
        "city": "Portland",
        "payment_method": "debit_card",
        "merchant_category": "pharmacy",
        "is_international": False,
        "device_id": "sinsp-dev-029",
        "device_type": "mobile",
        "ip_address": "192.0.2.102",
    },
    {
        "transaction_id": "SYNTH-INSP-0058",
        "user_id": "sinsp-usr-057",
        "merchant_id": "sinsp-mrc-fuel-001",
        "amount": 65.20,
        "timestamp": DAY_03,
        "currency": "USD",
        "country": "US",
        "city": "Atlanta",
        "payment_method": "debit_card",
        "merchant_category": "fuel",
        "is_international": False,
        "device_id": "sinsp-dev-030",
        "device_type": "mobile",
        "ip_address": "192.0.2.103",
    },
    {
        "transaction_id": "SYNTH-INSP-0059",
        "user_id": "sinsp-usr-058",
        "merchant_id": "sinsp-mrc-grocery-002",
        "amount": 125.40,
        "timestamp": DAY_04,
        "currency": "USD",
        "country": "US",
        "city": "Nashville",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "is_international": False,
        "device_id": "sinsp-dev-031",
        "device_type": "mobile",
        "ip_address": "192.0.2.104",
    },
    {
        "transaction_id": "SYNTH-INSP-0060",
        "user_id": "sinsp-usr-059",
        "merchant_id": "sinsp-mrc-pharmacy-002",
        "amount": 18.90,
        "timestamp": DAY_05,
        "currency": "USD",
        "country": "US",
        "city": "Columbus",
        "payment_method": "debit_card",
        "merchant_category": "pharmacy",
        "is_international": False,
        "device_id": "sinsp-dev-032",
        "device_type": "mobile",
        "ip_address": "192.0.2.105",
    },
    {
        "transaction_id": "SYNTH-INSP-0061",
        "user_id": "sinsp-usr-060",
        "merchant_id": "sinsp-mrc-fuel-002",
        "amount": 72.30,
        "timestamp": DAY_06,
        "currency": "USD",
        "country": "US",
        "city": "Charlotte",
        "payment_method": "debit_card",
        "merchant_category": "fuel",
        "is_international": False,
        "device_id": "sinsp-dev-033",
        "device_type": "mobile",
        "ip_address": "192.0.2.106",
    },
    {
        "transaction_id": "SYNTH-INSP-0062",
        "user_id": "sinsp-usr-061",
        "merchant_id": "sinsp-mrc-grocery-003",
        "amount": 55.80,
        "timestamp": DAY_07,
        "currency": "USD",
        "country": "US",
        "city": "Indianapolis",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "is_international": False,
        "device_id": "sinsp-dev-034",
        "device_type": "mobile",
        "ip_address": "192.0.2.107",
    },
    {
        "transaction_id": "SYNTH-INSP-0063",
        "user_id": "sinsp-usr-062",
        "merchant_id": "sinsp-mrc-pharmacy-003",
        "amount": 27.60,
        "timestamp": DAY_08,
        "currency": "USD",
        "country": "US",
        "city": "San Jose",
        "payment_method": "debit_card",
        "merchant_category": "pharmacy",
        "is_international": False,
        "device_id": "sinsp-dev-035",
        "device_type": "mobile",
        "ip_address": "192.0.2.108",
    },
    {
        "transaction_id": "SYNTH-INSP-0064",
        "user_id": "sinsp-usr-063",
        "merchant_id": "sinsp-mrc-grocery-004",
        "amount": 89.15,
        "timestamp": DAY_09,
        "currency": "USD",
        "country": "US",
        "city": "Austin",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "is_international": False,
        "device_id": "sinsp-dev-036",
        "device_type": "mobile",
        "ip_address": "192.0.2.109",
    },
    {
        "transaction_id": "SYNTH-INSP-0065",
        "user_id": "sinsp-usr-064",
        "merchant_id": "sinsp-mrc-fuel-003",
        "amount": 44.80,
        "timestamp": DAY_10,
        "currency": "USD",
        "country": "US",
        "city": "Fort Worth",
        "payment_method": "debit_card",
        "merchant_category": "fuel",
        "is_international": False,
        "device_id": "sinsp-dev-037",
        "device_type": "mobile",
        "ip_address": "192.0.2.110",
    },
    {
        "transaction_id": "SYNTH-INSP-0066",
        "user_id": "sinsp-usr-065",
        "merchant_id": "sinsp-mrc-grocery-005",
        "amount": 62.30,
        "timestamp": DAY_01,
        "currency": "USD",
        "country": "US",
        "city": "Jacksonville",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "is_international": False,
        "device_id": "sinsp-dev-038",
        "device_type": "mobile",
        "ip_address": "192.0.2.111",
    },
    {
        "transaction_id": "SYNTH-INSP-0067",
        "user_id": "sinsp-usr-066",
        "merchant_id": "sinsp-mrc-pharmacy-004",
        "amount": 14.25,
        "timestamp": DAY_02,
        "currency": "USD",
        "country": "US",
        "city": "Memphis",
        "payment_method": "debit_card",
        "merchant_category": "pharmacy",
        "is_international": False,
        "device_id": "sinsp-dev-039",
        "device_type": "mobile",
        "ip_address": "192.0.2.112",
    },
    {
        "transaction_id": "SYNTH-INSP-0068",
        "user_id": "sinsp-usr-067",
        "merchant_id": "sinsp-mrc-fuel-004",
        "amount": 58.60,
        "timestamp": DAY_03,
        "currency": "USD",
        "country": "US",
        "city": "El Paso",
        "payment_method": "debit_card",
        "merchant_category": "fuel",
        "is_international": False,
        "device_id": "sinsp-dev-040",
        "device_type": "mobile",
        "ip_address": "192.0.2.113",
    },
    {
        "transaction_id": "SYNTH-INSP-0069",
        "user_id": "sinsp-usr-068",
        "merchant_id": "sinsp-mrc-grocery-006",
        "amount": 94.70,
        "timestamp": DAY_04,
        "currency": "USD",
        "country": "US",
        "city": "Louisville",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "is_international": False,
        "device_id": "sinsp-dev-041",
        "device_type": "mobile",
        "ip_address": "192.0.2.114",
    },
    {
        "transaction_id": "SYNTH-INSP-0070",
        "user_id": "sinsp-usr-069",
        "merchant_id": "sinsp-mrc-pharmacy-005",
        "amount": 21.40,
        "timestamp": DAY_05,
        "currency": "USD",
        "country": "US",
        "city": "Baltimore",
        "payment_method": "debit_card",
        "merchant_category": "pharmacy",
        "is_international": False,
        "device_id": "sinsp-dev-042",
        "device_type": "mobile",
        "ip_address": "192.0.2.115",
    },
    {
        "transaction_id": "SYNTH-INSP-0071",
        "user_id": "sinsp-usr-070",
        "merchant_id": "sinsp-mrc-grocery-007",
        "amount": 76.90,
        "timestamp": DAY_06,
        "currency": "USD",
        "country": "US",
        "city": "Milwaukee",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "is_international": False,
        "device_id": "sinsp-dev-043",
        "device_type": "mobile",
        "ip_address": "192.0.2.116",
    },
    {
        "transaction_id": "SYNTH-INSP-0072",
        "user_id": "sinsp-usr-071",
        "merchant_id": "sinsp-mrc-fuel-005",
        "amount": 38.50,
        "timestamp": DAY_07,
        "currency": "USD",
        "country": "US",
        "city": "Albuquerque",
        "payment_method": "debit_card",
        "merchant_category": "fuel",
        "is_international": False,
        "device_id": "sinsp-dev-044",
        "device_type": "mobile",
        "ip_address": "192.0.2.117",
    },
    {
        "transaction_id": "SYNTH-INSP-0073",
        "user_id": "sinsp-usr-072",
        "merchant_id": "sinsp-mrc-grocery-008",
        "amount": 112.60,
        "timestamp": DAY_08,
        "currency": "USD",
        "country": "US",
        "city": "Tucson",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "is_international": False,
        "device_id": "sinsp-dev-045",
        "device_type": "mobile",
        "ip_address": "192.0.2.118",
    },
    {
        "transaction_id": "SYNTH-INSP-0074",
        "user_id": "sinsp-usr-073",
        "merchant_id": "sinsp-mrc-pharmacy-006",
        "amount": 9.80,
        "timestamp": DAY_09,
        "currency": "USD",
        "country": "US",
        "city": "Fresno",
        "payment_method": "debit_card",
        "merchant_category": "pharmacy",
        "is_international": False,
        "device_id": "sinsp-dev-046",
        "device_type": "mobile",
        "ip_address": "192.0.2.119",
    },
    {
        "transaction_id": "SYNTH-INSP-0075",
        "user_id": "sinsp-usr-074",
        "merchant_id": "sinsp-mrc-grocery-009",
        "amount": 83.40,
        "timestamp": DAY_10,
        "currency": "USD",
        "country": "US",
        "city": "Sacramento",
        "payment_method": "debit_card",
        "merchant_category": "grocery",
        "is_international": False,
        "device_id": "sinsp-dev-047",
        "device_type": "mobile",
        "ip_address": "192.0.2.120",
    },
]

# ---------------------------------------------------------------------------
# Verdict plan: which transactions receive analyst verdicts and what type.
# Keys are 1-indexed transaction list positions (transaction_id suffix).
# ---------------------------------------------------------------------------

VERDICT_PLAN = {
    # High-risk BLOCK targets: some confirmed fraud, some left unreviewed
    "SYNTH-INSP-0001": ("CONFIRMED_FRAUD",
                        "High-value electronics purchase at 02:14 UTC from Moscow. "
                        "No device identifier. Rule and model both flagged. Confirmed fraud."),
    "SYNTH-INSP-0002": ("CONFIRMED_FRAUD",
                        "Nighttime cross-border transaction from Lagos. High amount. "
                        "No device. Risk signals consistent with account takeover. Confirmed."),
    "SYNTH-INSP-0003": ("CONFIRMED_FRAUD",
                        "High-value electronics purchase at 01:52 UTC. International, elevated-risk region. "
                        "No device identifier. Confirmed fraudulent."),
    "SYNTH-INSP-0006": ("CONFIRMED_FRAUD",
                        "Large gaming purchase at 02:14 UTC from Moscow. No device ID. "
                        "Consistent with mule-network pattern. Confirmed fraud."),
    "SYNTH-INSP-0008": ("CONFIRMED_FRAUD",
                        "High-value electronics from Kyiv at 01:52 UTC. No device identifier. "
                        "Pattern matches coordinated cross-border card use. Confirmed."),
    # REVIEW-tier: some false positives, some confirmed, some unreviewed
    "SYNTH-INSP-0011": ("FALSE_POSITIVE",
                        "Nighttime electronics purchase from Moscow but amount below block threshold. "
                        "Customer verified as travelling. Cleared as false positive."),
    "SYNTH-INSP-0013": ("FALSE_POSITIVE",
                        "Late-night travel purchase from Odessa. Customer confirmed booking legitimate. "
                        "No further fraud signals. False positive."),
    "SYNTH-INSP-0015": ("CONFIRMED_FRAUD",
                        "Gaming purchase at 23:20 UTC from Abuja. Digital wallet used. "
                        "No device ID. Pattern consistent with card testing. Confirmed fraud."),
    "SYNTH-INSP-0018": ("FALSE_POSITIVE",
                        "Nighttime travel booking from Port Harcourt. Customer confirmed trip. "
                        "Fraud signal insufficient for confirmation. Cleared."),
    "SYNTH-INSP-0021": ("FALSE_POSITIVE",
                        "Daytime electronics purchase from London. Device present. "
                        "Customer verified UK residence. Not fraud."),
    "SYNTH-INSP-0022": ("FALSE_POSITIVE",
                        "Gaming purchase from Toronto during business hours. Customer account in good standing. "
                        "Amount within normal range. Cleared."),
    "SYNTH-INSP-0023": ("APPROVED",
                        "Travel booking from Berlin, device present. Customer confirmed business travel. "
                        "Risk score within review threshold only due to amount. Approved."),
    "SYNTH-INSP-0025": ("APPROVED",
                        "Gaming purchase from Paris with known device. Customer account verified. "
                        "Amount elevated but pattern expected. Approved."),
    "SYNTH-INSP-0027": ("APPROVED",
                        "Electronics from Amsterdam, desktop device, business hours. "
                        "Customer account in good standing. Approved."),
    # Medium cases: mix of outcomes
    "SYNTH-INSP-0031": ("FALSE_POSITIVE",
                        "Late-night domestic travel booking with known device. "
                        "Customer confirmed booking. No international risk. False positive."),
    "SYNTH-INSP-0036": ("APPROVED",
                        "Daytime electronics from Sao Paulo with known device. "
                        "Amount within normal range. Customer account active. Approved."),
    "SYNTH-INSP-0040": ("APPROVED",
                        "Travel purchase from Istanbul with device. Customer confirmed trip. Approved."),
    "SYNTH-INSP-0042": ("FALSE_POSITIVE",
                        "Electronics from Johannesburg with desktop device. "
                        "Customer confirmed purchase at known merchant. False positive."),
    # Low-risk: some approved, most unreviewed (APPROVE decisions)
    "SYNTH-INSP-0056": ("APPROVED",
                        "Routine grocery purchase. Domestic, known device, small amount. Approved."),
    "SYNTH-INSP-0059": ("APPROVED",
                        "Grocery purchase with known device. Within normal spending pattern. Approved."),
    "SYNTH-INSP-0062": ("APPROVED",
                        "Routine grocery purchase. Domestic, low amount, known device. Approved."),
    "SYNTH-INSP-0064": ("APPROVED",
                        "Grocery purchase. Domestic US, device present, normal amount. Approved."),
    "SYNTH-INSP-0069": ("APPROVED",
                        "Grocery purchase in Louisville. Low risk, known device. Approved."),
}

# Workflow events to write after verdicts.
# Keyed by transaction_id. Written via POST /workflow/audit-event.
WORKFLOW_EVENT_PLAN = {
    "SYNTH-INSP-0001": ("CASE_ESCALATED",      "SUCCESS",
                        "BLOCK decision confirmed fraud. Case escalated to fraud operations team."),
    "SYNTH-INSP-0002": ("CASE_ESCALATED",      "SUCCESS",
                        "High-value confirmed fraud case escalated for chargeback initiation."),
    "SYNTH-INSP-0003": ("CASE_ESCALATED",      "SUCCESS",
                        "Confirmed fraud case. Escalation sent to card operations."),
    "SYNTH-INSP-0006": ("CASE_ESCALATED",      "SUCCESS",
                        "Mule-pattern confirmed. Escalation dispatched to network fraud team."),
    "SYNTH-INSP-0008": ("CASE_ESCALATED",      "SUCCESS",
                        "Cross-border coordinated fraud confirmed. Escalated for account suspension review."),
    "SYNTH-INSP-0011": ("CASE_CLEARED",        "SUCCESS",
                        "False positive cleared. No further action required."),
    "SYNTH-INSP-0013": ("CASE_CLEARED",        "SUCCESS",
                        "Customer verified. False positive cleared."),
    "SYNTH-INSP-0015": ("CASE_ESCALATED",      "SUCCESS",
                        "Card testing pattern confirmed. Escalated for merchant block review."),
    "SYNTH-INSP-0018": ("CASE_CLEARED",        "SUCCESS",
                        "Travel confirmed by customer. No further action."),
    "SYNTH-INSP-0021": ("CASE_CLEARED",        "SUCCESS",
                        "UK residence confirmed. False positive closed."),
    "SYNTH-INSP-0022": ("CASE_CLEARED",        "SUCCESS",
                        "Canadian account verified. Case cleared."),
    "SYNTH-INSP-0023": ("CASE_APPROVED",       "SUCCESS",
                        "Business travel confirmed. Case approved and closed."),
    "SYNTH-INSP-0025": ("CASE_APPROVED",       "SUCCESS",
                        "Gaming purchase pattern expected. Approved."),
    "SYNTH-INSP-0027": ("CASE_APPROVED",       "SUCCESS",
                        "Netherlands purchase approved. Account in good standing."),
    "SYNTH-INSP-0031": ("CASE_CLEARED",        "SUCCESS",
                        "Domestic travel confirmed. False positive cleared."),
    "SYNTH-INSP-0036": ("CASE_APPROVED",       "SUCCESS",
                        "Brazil purchase approved after customer confirmation."),
    "SYNTH-INSP-0040": ("CASE_APPROVED",       "SUCCESS",
                        "Istanbul travel confirmed. Case approved."),
    "SYNTH-INSP-0042": ("CASE_CLEARED",        "SUCCESS",
                        "South Africa purchase cleared. Customer verified."),
}


# ---------------------------------------------------------------------------
# Main population flow
# ---------------------------------------------------------------------------

def run(base_url: str, max_count: int, dry_run: bool) -> None:
    print()
    print("Fraud Intelligence Console - Inspection Dataset Population Utility")
    print("=" * 68)
    print(f"  Target API:  {base_url}")
    print(f"  Max count:   {max_count}")
    print(f"  Dry run:     {dry_run}")
    print()
    print("  WARNING: All data created is SYNTHETIC. No real transaction data.")
    print("  Transaction IDs are prefixed SYNTH-INSP- to mark synthetic origin.")
    print()

    # Health check
    if not dry_run:
        try:
            resp = _get(base_url, "/health")
            if resp.status_code != 200:
                print(f"  [WARN] Health check returned HTTP {resp.status_code}. Continuing.",
                      file=sys.stderr)
            else:
                print("  API health: OK\n")
        except requests.RequestException as exc:
            print(f"  [WARN] Health check failed: {exc}. Continuing anyway.", file=sys.stderr)

    transactions = SYNTHETIC_TRANSACTIONS[:max_count]
    scored = 0
    skipped = 0
    blocked = 0
    reviewed = 0
    approved_decisions = 0
    verdicts_submitted = 0
    workflow_events_written = 0

    print(f"  Submitting {len(transactions)} synthetic transactions ...\n")

    # Map transaction_id -> case_id for verdict and workflow phases
    case_map: dict[str, int] = {}

    for i, txn in enumerate(transactions, 1):
        txn_id = txn["transaction_id"]
        prediction = submit_transaction(base_url, txn, dry_run)

        if dry_run:
            continue

        if prediction is None:
            skipped += 1
            print(f"  [{i:02d}/{len(transactions)}] SKIP  {txn_id}")
            continue

        decision = prediction.get("decision", "UNKNOWN")
        case_id = prediction.get("id")
        risk_score = prediction.get("risk_score", 0.0)

        case_map[txn_id] = case_id

        if decision == "BLOCK":
            blocked += 1
        elif decision == "REVIEW":
            reviewed += 1
        else:
            approved_decisions += 1

        scored += 1
        print(f"  [{i:02d}/{len(transactions)}] OK    {txn_id} "
              f"decision={decision} score={risk_score:.3f} case_id={case_id}")

    print()

    if not dry_run:
        print(f"  Scored: {scored}  Skipped: {skipped}")
        print(f"  Decisions: BLOCK={blocked}  REVIEW={reviewed}  APPROVE={approved_decisions}")
        print()

    # Verdict submission phase
    print("  Submitting analyst verdicts ...")
    for txn_id, (analyst_status, notes) in VERDICT_PLAN.items():
        if txn_id not in case_map and not dry_run:
            continue
        case_id = case_map.get(txn_id, 0)
        ok = submit_verdict(base_url, case_id, txn_id, analyst_status, notes, dry_run)
        if ok:
            verdicts_submitted += 1
            if not dry_run:
                print(f"    Verdict {analyst_status:18s} -> {txn_id} (case {case_id})")

    print()

    # Workflow audit event phase
    print("  Writing workflow audit events ...")
    for txn_id, (action, status, message) in WORKFLOW_EVENT_PLAN.items():
        if txn_id not in case_map and not dry_run:
            continue
        case_id = case_map.get(txn_id, 0)
        ok = write_workflow_event(base_url, case_id, action, status, message, dry_run)
        if ok:
            workflow_events_written += 1
            if not dry_run:
                print(f"    Event {action:22s} -> {txn_id} (case {case_id})")

    print()
    print("=" * 68)
    print("  Inspection Dataset Population Summary")
    print("=" * 68)
    print(f"  Transactions submitted/found:  {scored}")
    print(f"  Transactions skipped (error):  {skipped}")
    print(f"  BLOCK decisions:               {blocked}")
    print(f"  REVIEW decisions:              {reviewed}")
    print(f"  APPROVE decisions:             {approved_decisions}")
    print(f"  Verdicts submitted:            {verdicts_submitted}")
    print(f"  Workflow events written:       {workflow_events_written}")
    print()
    print("  All data is synthetic. SYNTH-INSP-* prefix marks inspection origin.")
    print("  Population complete.\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Populate the hosted inspection environment with synthetic data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("HOSTED_API_URL", DEFAULT_API_URL),
        help="Base URL of the target API (default: %(default)s)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=75,
        help="Maximum number of transactions to submit (default: 75)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without making any API calls",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(base_url=args.api_url, max_count=args.count, dry_run=args.dry_run)
