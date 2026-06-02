"""
Rich synthetic banking transaction generator -- Phase 12F-2.

Generates scenario-based CSVs using the schema defined in
docs/RICH_SYNTHETIC_BANKING_SCHEMA.md.

All data is synthetic. No real banking data is used or implied.

Usage:
  python scripts/generate_rich_banking_csv.py --rows 10000 --output C:\\tmp\\rich-10k.csv --seed 42
  python scripts/generate_rich_banking_csv.py --rows 1000  --seed 42
  python scripts/generate_rich_banking_csv.py --rows 100000 --output C:\\tmp\\rich-100k.csv
"""

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Output columns -- 42 total
#   38 rich schema fields (docs/RICH_SYNTHETIC_BANKING_SCHEMA.md)
#   + 4 legacy compatibility aliases required by the existing risk scan
#     validator (timestamp, country, device_type, is_international)
# ---------------------------------------------------------------------------
FIELDNAMES = [
    # Required by current risk scan validator (legacy)
    "transaction_id",
    "amount",
    "timestamp",
    "country",
    "payment_method",
    # Transaction Identity (rich)
    "event_timestamp",
    "account_id",
    "customer_id",
    "merchant_id",
    # Monetary
    "currency",
    "account_balance_before",
    "account_balance_after",
    "daily_spend_to_date",
    "available_limit",
    # Channel / Device
    "channel",
    "device_id",
    "device_type",
    "device_trust_score",
    "ip_country",
    "billing_country",
    "shipping_country",
    "geo_distance_km",
    "is_international",
    # Merchant / Counterparty
    "merchant_category",
    "merchant_risk_score",
    "merchant_country",
    "counterparty_age_days",
    "new_payee_flag",
    # Customer Behaviour
    "customer_tenure_days",
    "avg_transaction_amount_30d",
    "txn_count_1h",
    "txn_count_24h",
    "failed_attempts_1h",
    "chargeback_count_90d",
    # Fraud Scenario
    "scenario_label",
    "scenario_family",
    "synthetic_fraud_label",
    "rule_trigger_count",
    "primary_risk_reason",
    # Operational
    "expected_priority",
    "recommended_action",
    "analyst_queue_hint",
]

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------
LOW_RISK_COUNTRIES  = ["US", "GB", "DE", "FR", "AU", "CA", "NL", "JP", "SE", "CH"]
HIGH_RISK_COUNTRIES = ["RU", "CN", "NG", "PK", "VN", "UA", "KE", "ID", "BY", "IR"]

PAYMENT_METHODS           = ["credit_card", "debit_card", "digital_wallet", "bank_transfer"]
HIGH_RISK_PAYMENT_METHODS = {"credit_card", "digital_wallet"}

CHANNELS      = ["mobile_app", "web", "api", "in_store", "atm", "phone"]
DEVICE_TYPES  = ["desktop", "mobile", "tablet"]

NORMAL_CATEGORIES   = ["grocery", "food", "retail", "healthcare", "utilities"]
HIGH_RISK_CATEGORIES = ["electronics", "gaming", "travel", "gambling", "crypto"]
ALL_CATEGORIES      = NORMAL_CATEGORIES + HIGH_RISK_CATEGORIES

HIGH_RISK_MERCHANT_CATEGORIES = {"electronics", "gaming", "travel", "gambling", "crypto"}

HOME_CURRENCIES = {
    "US": "USD", "GB": "GBP", "DE": "EUR", "FR": "EUR",
    "AU": "AUD", "CA": "CAD", "NL": "EUR", "JP": "JPY",
    "SE": "SEK", "CH": "CHF",
}

HIGH_AMOUNT_THRESHOLD = 1000.0
BASE_DATE = datetime(2024, 1, 1)

# ---------------------------------------------------------------------------
# Default scenario mix -- must sum to 1.0
# ---------------------------------------------------------------------------
DEFAULT_SCENARIO_MIX: dict = {
    "normal":                       0.700,
    "high_velocity_spend":          0.050,
    "account_takeover":             0.040,
    "card_testing":                 0.040,
    "unusual_geography":            0.035,
    "new_payee_transfer":           0.030,
    "merchant_risk_spike":          0.030,
    "mule_account_behaviour":       0.020,
    "refund_chargeback_abuse":      0.020,
    "dormant_account_reactivation": 0.010,
    "cross_border_high_value":      0.010,
    "device_mismatch":              0.010,
    "suspicious_repeated_attempts": 0.005,
}

# ---------------------------------------------------------------------------
# Entity pool helpers
# ---------------------------------------------------------------------------

def _hex8() -> str:
    return format(random.randint(0, 0xFFFFFFFF), "08x")


def build_customer_pool(n: int) -> list:
    pool = []
    for _ in range(n):
        home = random.choice(LOW_RISK_COUNTRIES)
        pool.append({
            "customer_id":      f"cust_{_hex8()}",
            "account_id":       f"acct_{_hex8()}",
            "home_country":     home,
            "home_currency":    HOME_CURRENCIES.get(home, "USD"),
            "customer_tenure_days": random.randint(30, 3000),
            "avg_amount_30d":   round(random.uniform(30, 500), 2),
            "available_limit":  round(random.uniform(2000, 15000), 2),
        })
    return pool


def build_merchant_pool(n: int) -> list:
    pool = []
    for _ in range(n):
        country  = random.choice(LOW_RISK_COUNTRIES + HIGH_RISK_COUNTRIES)
        category = random.choice(ALL_CATEGORIES)
        risk = (
            round(random.uniform(0.6, 0.95), 3)
            if category in HIGH_RISK_MERCHANT_CATEGORIES
            else round(random.uniform(0.0, 0.4), 3)
        )
        pool.append({
            "merchant_id":       f"merch_{_hex8()}",
            "merchant_country":  country,
            "merchant_category": category,
            "merchant_risk_score": risk,
        })
    return pool


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ts(hour_min: int = 0, hour_max: int = 23) -> str:
    hour = random.randint(hour_min, hour_max)
    dt = BASE_DATE + timedelta(
        days=random.randint(0, 364),
        hours=hour,
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _is_night(ts: str) -> bool:
    h = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S").hour
    return h < 6 or h > 22


def _rule_count(row: dict) -> int:
    """Count how many legacy rule conditions are expected to fire for this row."""
    n = 0
    amount   = float(row["amount"])
    is_high  = amount > HIGH_AMOUNT_THRESHOLD
    is_night = _is_night(row["timestamp"])
    is_intl  = str(row.get("is_international", "false")).lower() in ("true", "1")
    is_hr_c  = row.get("country", "US") in HIGH_RISK_COUNTRIES
    is_hr_pm = row.get("payment_method", "") in HIGH_RISK_PAYMENT_METHODS
    if is_high and is_night:
        n += 1
    if is_high and is_intl and is_hr_c:
        n += 1
    if is_hr_pm and is_night and is_high:
        n += 1
    return n


# ---------------------------------------------------------------------------
# Normal transaction
# ---------------------------------------------------------------------------

def gen_normal(idx: int, customer: dict, merchant: dict) -> dict:
    ts      = _ts(8, 20)
    amount  = round(random.uniform(10, 700), 2)
    home    = customer["home_country"]
    bal_bef = round(random.uniform(500, 8000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          random.choices(
            ["debit_card", "credit_card", "digital_wallet", "bank_transfer"],
            weights=[45, 35, 15, 5]
        )[0],
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                customer["home_currency"],
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(0, amount * 0.6), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 random.choices(
            ["web", "mobile_app", "in_store", "atm"], weights=[35, 40, 20, 5]
        )[0],
        "device_id":               f"dev_{random.randint(1000, 9999)}",
        "device_type":             random.choices(
            ["mobile", "desktop", "tablet"], weights=[50, 40, 10]
        )[0],
        "device_trust_score":      round(random.uniform(0.70, 1.0), 3),
        "ip_country":              home,
        "billing_country":         home,
        "shipping_country":        home,
        "geo_distance_km":         round(random.uniform(2, 80), 1),
        "is_international":        "false",
        "merchant_category":       random.choice(NORMAL_CATEGORIES),
        "merchant_risk_score":     round(random.uniform(0.0, 0.30), 3),
        "merchant_country":        random.choice(LOW_RISK_COUNTRIES),
        "counterparty_age_days":   random.randint(30, 730),
        "new_payee_flag":          "false",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": customer["avg_amount_30d"],
        "txn_count_1h":            random.choices([0, 1, 2], weights=[60, 30, 10])[0],
        "txn_count_24h":           random.randint(1, 5),
        "failed_attempts_1h":      0,
        "chargeback_count_90d":    0,
        "scenario_label":          f"normal_{idx:08d}",
        "scenario_family":         "normal",
        "synthetic_fraud_label":   0,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "",
        "expected_priority":       "P3",
        "recommended_action":      "APPROVE",
        "analyst_queue_hint":      "Auto-approve low-risk",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


# ---------------------------------------------------------------------------
# Scenario generators
# ---------------------------------------------------------------------------

def gen_account_takeover(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts      = _ts(0, 4)
    amount  = round(random.uniform(800, 8000), 2)
    home    = customer["home_country"]
    ip_c    = random.choice(HIGH_RISK_COUNTRIES)
    bal_bef = round(random.uniform(1000, 12000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          random.choice(["credit_card", "digital_wallet"]),
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                customer["home_currency"],
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(0, 200), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 random.choice(["mobile_app", "api"]),
        "device_id":               "",
        "device_type":             "mobile",
        "device_trust_score":      round(random.uniform(0.05, 0.25), 3),
        "ip_country":              ip_c,
        "billing_country":         home,
        "shipping_country":        ip_c,
        "geo_distance_km":         round(random.uniform(1200, 8500), 1),
        "is_international":        "true",
        "merchant_category":       random.choice(["electronics", "travel"]),
        "merchant_risk_score":     round(random.uniform(0.40, 0.75), 3),
        "merchant_country":        ip_c,
        "counterparty_age_days":   random.randint(0, 14),
        "new_payee_flag":          "false",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": customer["avg_amount_30d"],
        "txn_count_1h":            random.randint(0, 2),
        "txn_count_24h":           random.randint(0, 3),
        "failed_attempts_1h":      random.randint(2, 7),
        "chargeback_count_90d":    0,
        "scenario_label":          f"ato_{instance:04d}",
        "scenario_family":         "account_takeover",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "ACCOUNT_TAKEOVER_PATTERN",
        "expected_priority":       "P0",
        "recommended_action":      "BLOCK",
        "analyst_queue_hint":      "Freeze account; contact customer via verified channel",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_card_testing(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts      = _ts(0, 23)
    amount  = round(random.uniform(0.50, 4.99), 2)
    home    = customer["home_country"]
    bal_bef = round(random.uniform(500, 5000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          random.choice(["credit_card", "digital_wallet"]),
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                "USD",
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(5, 50), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 "api",
        "device_id":               "",
        "device_type":             "mobile",
        "device_trust_score":      round(random.uniform(0.10, 0.40), 3),
        "ip_country":              random.choice(HIGH_RISK_COUNTRIES),
        "billing_country":         home,
        "shipping_country":        home,
        "geo_distance_km":         round(random.uniform(200, 5000), 1),
        "is_international":        "false",
        "merchant_category":       random.choice(NORMAL_CATEGORIES),
        "merchant_risk_score":     round(random.uniform(0.10, 0.50), 3),
        "merchant_country":        home,
        "counterparty_age_days":   random.randint(0, 60),
        "new_payee_flag":          "false",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": customer["avg_amount_30d"],
        "txn_count_1h":            random.randint(8, 25),
        "txn_count_24h":           random.randint(12, 40),
        "failed_attempts_1h":      random.randint(3, 12),
        "chargeback_count_90d":    0,
        "scenario_label":          f"card_testing_{instance:04d}",
        "scenario_family":         "card_testing",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "CARD_TESTING_VELOCITY",
        "expected_priority":       "P1",
        "recommended_action":      "BLOCK",
        "analyst_queue_hint":      "Block card; velocity pattern indicates enumeration",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_high_velocity_spend(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts      = _ts(8, 23)
    amount  = round(random.uniform(200, 2000), 2)
    home    = customer["home_country"]
    limit   = customer["available_limit"]
    bal_bef = round(random.uniform(500, 8000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          random.choice(["credit_card", "digital_wallet", "debit_card"]),
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                customer["home_currency"],
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(0.80, 0.95) * limit, 2),
        "available_limit":         limit,
        "channel":                 random.choice(["mobile_app", "web"]),
        "device_id":               f"dev_{random.randint(1000, 9999)}",
        "device_type":             "mobile",
        "device_trust_score":      round(random.uniform(0.50, 0.85), 3),
        "ip_country":              home,
        "billing_country":         home,
        "shipping_country":        home,
        "geo_distance_km":         round(random.uniform(2, 120), 1),
        "is_international":        "false",
        "merchant_category":       random.choice(ALL_CATEGORIES),
        "merchant_risk_score":     round(random.uniform(0.10, 0.55), 3),
        "merchant_country":        home,
        "counterparty_age_days":   random.randint(5, 200),
        "new_payee_flag":          "false",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": round(random.uniform(40, 150), 2),
        "txn_count_1h":            random.randint(6, 20),
        "txn_count_24h":           random.randint(15, 50),
        "failed_attempts_1h":      random.randint(0, 2),
        "chargeback_count_90d":    random.randint(0, 1),
        "scenario_label":          f"high_velocity_{instance:04d}",
        "scenario_family":         "high_velocity_spend",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "HIGH_VELOCITY_SPEND_PATTERN",
        "expected_priority":       "P1",
        "recommended_action":      "REVIEW",
        "analyst_queue_hint":      "Verify customer-initiated; consider temporary limit reduction",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_unusual_geography(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts         = _ts(8, 22)
    amount     = round(random.uniform(200, 3000), 2)
    home       = customer["home_country"]
    foreign_c  = random.choice(HIGH_RISK_COUNTRIES)
    bal_bef    = round(random.uniform(500, 6000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 foreign_c,
        "payment_method":          random.choice(["credit_card", "digital_wallet"]),
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                random.choice(["USD", "EUR", "GBP"]),
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(50, 500), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 random.choice(["web", "api"]),
        "device_id":               "",
        "device_type":             "mobile",
        "device_trust_score":      round(random.uniform(0.10, 0.45), 3),
        "ip_country":              foreign_c,
        "billing_country":         home,
        "shipping_country":        foreign_c,
        "geo_distance_km":         round(random.uniform(1500, 9000), 1),
        "is_international":        "true",
        "merchant_category":       random.choice(HIGH_RISK_CATEGORIES),
        "merchant_risk_score":     round(random.uniform(0.40, 0.85), 3),
        "merchant_country":        foreign_c,
        "counterparty_age_days":   random.randint(0, 30),
        "new_payee_flag":          "false",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": customer["avg_amount_30d"],
        "txn_count_1h":            random.randint(0, 3),
        "txn_count_24h":           random.randint(1, 6),
        "failed_attempts_1h":      random.randint(0, 3),
        "chargeback_count_90d":    0,
        "scenario_label":          f"unusual_geo_{instance:04d}",
        "scenario_family":         "unusual_geography",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "UNUSUAL_GEOGRAPHY_PATTERN",
        "expected_priority":       "P1",
        "recommended_action":      "REVIEW",
        "analyst_queue_hint":      "Geo-block or step-up authentication required",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_new_payee_transfer(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts        = _ts(8, 20)
    amount    = round(random.uniform(2000, 25000), 2)
    home      = customer["home_country"]
    is_intl   = random.choice(["true", "false"])
    dest_c    = random.choice(HIGH_RISK_COUNTRIES) if is_intl == "true" else home
    bal_bef   = round(random.uniform(3000, 30000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          "bank_transfer",
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             f"merch_{_hex8()}",
        "currency":                customer["home_currency"],
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(0, 500), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 "web",
        "device_id":               f"dev_{random.randint(1000, 9999)}",
        "device_type":             random.choice(["desktop", "mobile"]),
        "device_trust_score":      round(random.uniform(0.50, 0.90), 3),
        "ip_country":              home,
        "billing_country":         home,
        "shipping_country":        dest_c,
        "geo_distance_km":         round(random.uniform(2, 200), 1),
        "is_international":        is_intl,
        "merchant_category":       "utilities",
        "merchant_risk_score":     round(random.uniform(0.40, 0.80), 3),
        "merchant_country":        dest_c,
        "counterparty_age_days":   0,
        "new_payee_flag":          "true",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": customer["avg_amount_30d"],
        "txn_count_1h":            random.randint(0, 2),
        "txn_count_24h":           random.randint(0, 4),
        "failed_attempts_1h":      0,
        "chargeback_count_90d":    0,
        "scenario_label":          f"new_payee_{instance:04d}",
        "scenario_family":         "new_payee_transfer",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "NEW_PAYEE_HIGH_VALUE_TRANSFER",
        "expected_priority":       "P0",
        "recommended_action":      "BLOCK",
        "analyst_queue_hint":      "Contact customer to confirm payee; APP fraud risk",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_merchant_risk_spike(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts        = _ts(8, 22)
    amount    = round(random.uniform(100, 5000), 2)
    home      = customer["home_country"]
    high_risk = random.random() < 0.60
    category  = random.choice(["gambling", "crypto", "electronics", "gaming"])
    bal_bef   = round(random.uniform(500, 8000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          random.choice(["credit_card", "digital_wallet", "debit_card"]),
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                customer["home_currency"],
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(20, 300), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 "web",
        "device_id":               f"dev_{random.randint(1000, 9999)}",
        "device_type":             random.choice(["desktop", "mobile"]),
        "device_trust_score":      round(random.uniform(0.40, 0.80), 3),
        "ip_country":              home,
        "billing_country":         home,
        "shipping_country":        home,
        "geo_distance_km":         round(random.uniform(2, 100), 1),
        "is_international":        "false",
        "merchant_category":       category,
        "merchant_risk_score":     (
            round(random.uniform(0.70, 0.98), 3) if high_risk
            else round(random.uniform(0.50, 0.69), 3)
        ),
        "merchant_country":        random.choice(HIGH_RISK_COUNTRIES),
        "counterparty_age_days":   random.randint(0, 180),
        "new_payee_flag":          "false",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": customer["avg_amount_30d"],
        "txn_count_1h":            random.randint(0, 3),
        "txn_count_24h":           random.randint(1, 8),
        "failed_attempts_1h":      0,
        "chargeback_count_90d":    random.randint(0, 1),
        "scenario_label":          f"merchant_risk_{instance:04d}",
        "scenario_family":         "merchant_risk_spike",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "HIGH_RISK_MERCHANT_PATTERN",
        "expected_priority":       "P1" if high_risk else "P2",
        "recommended_action":      "REVIEW",
        "analyst_queue_hint":      "Review merchant risk profile before authorising",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_mule_account_behaviour(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts        = _ts(8, 22)
    amount    = round(random.uniform(1000, 10000), 2)
    home      = customer["home_country"]
    bal_bef   = round(random.uniform(1500, 15000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          "bank_transfer",
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                customer["home_currency"],
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(800, 5000), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 "web",
        "device_id":               f"dev_{random.randint(1000, 9999)}",
        "device_type":             "desktop",
        "device_trust_score":      round(random.uniform(0.50, 0.85), 3),
        "ip_country":              home,
        "billing_country":         home,
        "shipping_country":        home,
        "geo_distance_km":         round(random.uniform(2, 80), 1),
        "is_international":        "false",
        "merchant_category":       random.choice(["crypto", "travel", "electronics"]),
        "merchant_risk_score":     round(random.uniform(0.40, 0.80), 3),
        "merchant_country":        home,
        "counterparty_age_days":   random.randint(0, 90),
        "new_payee_flag":          random.choice(["true", "false"]),
        "customer_tenure_days":    random.randint(30, 300),
        "avg_transaction_amount_30d": round(random.uniform(20, 100), 2),
        "txn_count_1h":            random.randint(2, 8),
        "txn_count_24h":           random.randint(12, 40),
        "failed_attempts_1h":      random.randint(0, 2),
        "chargeback_count_90d":    random.randint(3, 8),
        "scenario_label":          f"mule_behaviour_{instance:04d}",
        "scenario_family":         "mule_account_behaviour",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "MULE_ACCOUNT_PATTERN",
        "expected_priority":       "P0",
        "recommended_action":      "BLOCK",
        "analyst_queue_hint":      "Escalate to AML team; coordinated account review required",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_refund_chargeback_abuse(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts      = _ts(8, 20)
    amount  = round(random.uniform(100, 500), 2)
    home    = customer["home_country"]
    bal_bef = round(random.uniform(200, 4000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          random.choice(["credit_card", "debit_card"]),
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                customer["home_currency"],
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(50, 300), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 "web",
        "device_id":               f"dev_{random.randint(1000, 9999)}",
        "device_type":             "desktop",
        "device_trust_score":      round(random.uniform(0.60, 0.90), 3),
        "ip_country":              home,
        "billing_country":         home,
        "shipping_country":        home,
        "geo_distance_km":         round(random.uniform(2, 80), 1),
        "is_international":        "false",
        "merchant_category":       random.choice(["electronics", "travel", "gaming"]),
        "merchant_risk_score":     round(random.uniform(0.10, 0.50), 3),
        "merchant_country":        home,
        "counterparty_age_days":   random.randint(0, 120),
        "new_payee_flag":          "false",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": customer["avg_amount_30d"],
        "txn_count_1h":            random.randint(0, 2),
        "txn_count_24h":           random.randint(1, 6),
        "failed_attempts_1h":      0,
        "chargeback_count_90d":    random.randint(2, 5),
        "scenario_label":          f"chargeback_abuse_{instance:04d}",
        "scenario_family":         "refund_chargeback_abuse",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "CHARGEBACK_ABUSE_PATTERN",
        "expected_priority":       "P2",
        "recommended_action":      "REVIEW",
        "analyst_queue_hint":      "Review chargeback history; first-party fraud risk",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_dormant_account_reactivation(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts      = _ts(8, 20)
    amount  = round(random.uniform(1000, 8000), 2)
    home    = customer["home_country"]
    bal_bef = round(random.uniform(1000, 15000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          random.choice(["credit_card", "bank_transfer"]),
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                customer["home_currency"],
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(0, 50), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 random.choice(["web", "mobile_app"]),
        "device_id":               "",
        "device_type":             random.choice(["desktop", "mobile"]),
        "device_trust_score":      round(random.uniform(0.15, 0.45), 3),
        "ip_country":              home,
        "billing_country":         home,
        "shipping_country":        home,
        "geo_distance_km":         round(random.uniform(2, 200), 1),
        "is_international":        "false",
        "merchant_category":       random.choice(ALL_CATEGORIES),
        "merchant_risk_score":     round(random.uniform(0.10, 0.50), 3),
        "merchant_country":        home,
        "counterparty_age_days":   random.randint(0, 30),
        "new_payee_flag":          "false",
        "customer_tenure_days":    random.randint(365, 3000),
        "avg_transaction_amount_30d": round(random.uniform(0, 15), 2),
        "txn_count_1h":            random.choices([0, 1], weights=[80, 20])[0],
        "txn_count_24h":           random.choices([0, 1], weights=[70, 30])[0],
        "failed_attempts_1h":      0,
        "chargeback_count_90d":    0,
        "scenario_label":          f"dormant_reactivation_{instance:04d}",
        "scenario_family":         "dormant_account_reactivation",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "DORMANT_REACTIVATION_HIGH_VALUE",
        "expected_priority":       "P1",
        "recommended_action":      "REVIEW",
        "analyst_queue_hint":      "Verify customer identity; dormant account credential stuffing risk",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_cross_border_high_value(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts       = _ts(0, 4)
    amount   = round(random.uniform(1100, 15000), 2)
    home     = customer["home_country"]
    dest_c   = random.choice(HIGH_RISK_COUNTRIES)
    bal_bef  = round(random.uniform(2000, 20000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 dest_c,
        "payment_method":          random.choice(["credit_card", "bank_transfer"]),
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                random.choice(["EUR", "GBP", "CHF"]),
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(0, 500), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 "web",
        "device_id":               f"dev_{random.randint(1000, 9999)}",
        "device_type":             random.choice(["desktop", "mobile"]),
        "device_trust_score":      round(random.uniform(0.30, 0.70), 3),
        "ip_country":              dest_c,
        "billing_country":         home,
        "shipping_country":        dest_c,
        "geo_distance_km":         round(random.uniform(2000, 9000), 1),
        "is_international":        "true",
        "merchant_category":       random.choice(["travel", "electronics", "crypto"]),
        "merchant_risk_score":     round(random.uniform(0.40, 0.80), 3),
        "merchant_country":        dest_c,
        "counterparty_age_days":   random.randint(0, 60),
        "new_payee_flag":          "false",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": customer["avg_amount_30d"],
        "txn_count_1h":            random.randint(0, 2),
        "txn_count_24h":           random.randint(0, 5),
        "failed_attempts_1h":      random.randint(0, 2),
        "chargeback_count_90d":    0,
        "scenario_label":          f"cross_border_hv_{instance:04d}",
        "scenario_family":         "cross_border_high_value",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "CROSS_BORDER_HIGH_VALUE_PATTERN",
        "expected_priority":       "P1",
        "recommended_action":      "REVIEW",
        "analyst_queue_hint":      "AML check required; retain records for regulatory reporting",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_device_mismatch(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts      = _ts(6, 22)
    amount  = round(random.uniform(200, 2000), 2)
    home    = customer["home_country"]
    bal_bef = round(random.uniform(500, 6000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          random.choice(["credit_card", "debit_card"]),
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                customer["home_currency"],
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(20, 200), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 random.choice(["mobile_app", "api"]),
        "device_id":               "",
        "device_type":             "mobile",
        "device_trust_score":      round(random.uniform(0.05, 0.35), 3),
        "ip_country":              home,
        "billing_country":         home,
        "shipping_country":        home,
        "geo_distance_km":         round(random.uniform(100, 800), 1),
        "is_international":        "false",
        "merchant_category":       random.choice(ALL_CATEGORIES),
        "merchant_risk_score":     round(random.uniform(0.10, 0.55), 3),
        "merchant_country":        home,
        "counterparty_age_days":   random.randint(0, 60),
        "new_payee_flag":          "false",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": customer["avg_amount_30d"],
        "txn_count_1h":            random.randint(0, 3),
        "txn_count_24h":           random.randint(1, 6),
        "failed_attempts_1h":      random.randint(0, 3),
        "chargeback_count_90d":    0,
        "scenario_label":          f"device_mismatch_{instance:04d}",
        "scenario_family":         "device_mismatch",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "DEVICE_MISMATCH_LOW_TRUST",
        "expected_priority":       "P1",
        "recommended_action":      "REVIEW",
        "analyst_queue_hint":      "Step-up authentication required; possible session hijack",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


def gen_suspicious_repeated_attempts(idx: int, customer: dict, merchant: dict, instance: int) -> dict:
    ts      = _ts(0, 23)
    amount  = round(random.uniform(100, 3000), 2)
    home    = customer["home_country"]
    bal_bef = round(random.uniform(500, 8000), 2)
    row = {
        "transaction_id":          f"rich_{idx:08d}",
        "amount":                  amount,
        "timestamp":               ts,
        "country":                 home,
        "payment_method":          random.choice(["credit_card", "digital_wallet"]),
        "event_timestamp":         ts,
        "account_id":              customer["account_id"],
        "customer_id":             customer["customer_id"],
        "merchant_id":             merchant["merchant_id"],
        "currency":                customer["home_currency"],
        "account_balance_before":  bal_bef,
        "account_balance_after":   round(bal_bef - amount, 2),
        "daily_spend_to_date":     round(random.uniform(20, 300), 2),
        "available_limit":         customer["available_limit"],
        "channel":                 random.choice(["web", "api"]),
        "device_id":               "",
        "device_type":             "mobile",
        "device_trust_score":      round(random.uniform(0.20, 0.50), 3),
        "ip_country":              random.choice(HIGH_RISK_COUNTRIES),
        "billing_country":         home,
        "shipping_country":        home,
        "geo_distance_km":         round(random.uniform(200, 4000), 1),
        "is_international":        "false",
        "merchant_category":       random.choice(ALL_CATEGORIES),
        "merchant_risk_score":     round(random.uniform(0.10, 0.55), 3),
        "merchant_country":        home,
        "counterparty_age_days":   random.randint(0, 30),
        "new_payee_flag":          "false",
        "customer_tenure_days":    customer["customer_tenure_days"],
        "avg_transaction_amount_30d": customer["avg_amount_30d"],
        "txn_count_1h":            random.randint(5, 20),
        "txn_count_24h":           random.randint(8, 25),
        "failed_attempts_1h":      random.randint(4, 15),
        "chargeback_count_90d":    0,
        "scenario_label":          f"repeated_attempts_{instance:04d}",
        "scenario_family":         "suspicious_repeated_attempts",
        "synthetic_fraud_label":   1,
        "rule_trigger_count":      0,
        "primary_risk_reason":     "SUSPICIOUS_REPEATED_ATTEMPTS_PATTERN",
        "expected_priority":       "P1",
        "recommended_action":      "BLOCK",
        "analyst_queue_hint":      "Block session; require full re-authentication",
    }
    row["rule_trigger_count"] = _rule_count(row)
    return row


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------
SCENARIO_GENERATORS = {
    "account_takeover":             gen_account_takeover,
    "card_testing":                 gen_card_testing,
    "high_velocity_spend":          gen_high_velocity_spend,
    "unusual_geography":            gen_unusual_geography,
    "new_payee_transfer":           gen_new_payee_transfer,
    "merchant_risk_spike":          gen_merchant_risk_spike,
    "mule_account_behaviour":       gen_mule_account_behaviour,
    "refund_chargeback_abuse":      gen_refund_chargeback_abuse,
    "dormant_account_reactivation": gen_dormant_account_reactivation,
    "cross_border_high_value":      gen_cross_border_high_value,
    "device_mismatch":              gen_device_mismatch,
    "suspicious_repeated_attempts": gen_suspicious_repeated_attempts,
}

# ---------------------------------------------------------------------------
# Scenario assignment
# ---------------------------------------------------------------------------

def assign_scenarios(n: int, mix: dict) -> list:
    total = sum(mix.values())
    normalised = {k: v / total for k, v in mix.items()}
    assignments = []
    remainders = {}
    for family, frac in normalised.items():
        exact = n * frac
        count = int(exact)
        assignments.extend([family] * count)
        remainders[family] = exact - count
    shortfall = n - len(assignments)
    for family in sorted(remainders, key=remainders.get, reverse=True)[:shortfall]:
        assignments.append(family)
    random.shuffle(assignments)
    return assignments

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(rows: list, output_path: str, seed: int) -> None:
    from collections import Counter
    scenarios  = Counter(r["scenario_family"]       for r in rows)
    priorities = Counter(r["expected_priority"]     for r in rows)
    labels     = Counter(r["synthetic_fraud_label"] for r in rows)
    amounts    = [float(r["amount"]) for r in rows]
    n          = len(rows)

    print(f"\n{'='*62}")
    print(f"  Rich Banking Dataset -- Generation Summary")
    print(f"{'='*62}")
    print(f"  Output   : {output_path}")
    print(f"  Rows     : {n:,}")
    print(f"  Columns  : {len(FIELDNAMES)}")
    print(f"  Seed     : {seed}")
    print()
    print(f"  Scenario distribution:")
    for fam, cnt in sorted(scenarios.items(), key=lambda x: -x[1]):
        print(f"    {fam:<35} {cnt:>6,}  ({cnt/n*100:.1f}%)")
    print()
    print(f"  Expected priority:")
    for tier in ["P0", "P1", "P2", "P3"]:
        cnt = priorities.get(tier, 0)
        print(f"    {tier}  {cnt:>6,}  ({cnt/n*100:.1f}%)")
    print()
    print(f"  Fraud label:")
    for lbl, name in [(0, "Legitimate"), (1, "Fraud     ")]:
        cnt = labels.get(lbl, 0)
        print(f"    {name} ({lbl})  {cnt:>6,}  ({cnt/n*100:.1f}%)")
    print()
    srt = sorted(amounts)
    print(f"  Amount summary:")
    print(f"    Min    : ${min(amounts):>10,.2f}")
    print(f"    Max    : ${max(amounts):>10,.2f}")
    print(f"    Mean   : ${sum(amounts)/n:>10,.2f}")
    print(f"    Median : ${srt[n // 2]:>10,.2f}")
    print(f"{'='*62}\n")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Generate a rich synthetic banking transaction CSV (Phase 12F-2).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python scripts/generate_rich_banking_csv.py --rows 10000 --output C:\\tmp\\rich-10k.csv --seed 42
  python scripts/generate_rich_banking_csv.py --rows 1000  --seed 99
  python scripts/generate_rich_banking_csv.py --rows 100000 --output C:\\tmp\\rich-100k.csv
  python scripts/generate_rich_banking_csv.py --rows 1000 --seed 42 \\
      --scenario-mix '{"account_takeover":0.2,"normal":0.5}'
""",
    )
    p.add_argument("--rows",          type=int, default=10000,
                   help="Rows to generate (default: 10000)")
    p.add_argument("--output",        type=str, default="",
                   help="Output CSV path (default: scripts/test_rich_<rows>.csv)")
    p.add_argument("--seed",          type=int, default=42,
                   help="Random seed (default: 42)")
    p.add_argument("--scenario-mix",  type=str, default="",
                   help='JSON dict of scenario proportions, e.g. \'{"account_takeover":0.1}\'')
    return p.parse_args()


def main() -> None:
    args = parse_args()
    seed = args.seed
    rows = args.rows
    random.seed(seed)

    if args.output:
        output_path = args.output
    else:
        script_dir  = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, f"test_rich_{rows}.csv")

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    mix = dict(DEFAULT_SCENARIO_MIX)
    if args.scenario_mix:
        try:
            overrides = json.loads(args.scenario_mix)
        except json.JSONDecodeError as exc:
            print(f"ERROR: --scenario-mix must be valid JSON: {exc}", file=sys.stderr)
            sys.exit(1)
        for key, val in overrides.items():
            if key not in DEFAULT_SCENARIO_MIX:
                print(f"WARNING: unknown scenario '{key}' ignored.", file=sys.stderr)
            else:
                mix[key] = float(val)

    pool_size = max(50, rows // 20)
    print(f"Building entity pools ({pool_size:,} customers / {pool_size:,} merchants)…",
          flush=True)
    customers = build_customer_pool(pool_size)
    merchants = build_merchant_pool(pool_size)

    scenario_assignments = assign_scenarios(rows, mix)
    scenario_counts: dict = {k: 0 for k in DEFAULT_SCENARIO_MIX}

    print(f"Generating {rows:,} rows…", flush=True)
    generated = []
    for idx, scenario in enumerate(scenario_assignments, start=1):
        customer = random.choice(customers)
        merchant = random.choice(merchants)
        instance = scenario_counts.get(scenario, 0)
        scenario_counts[scenario] = instance + 1

        if scenario == "normal":
            row = gen_normal(idx, customer, merchant)
        else:
            row = SCENARIO_GENERATORS[scenario](idx, customer, merchant, instance)
        generated.append(row)

    print(f"Writing CSV…", flush=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(generated)

    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"Written {rows:,} rows -> {output_path}  ({size_mb:.2f} MB)")
    print_summary(generated, output_path, seed)


if __name__ == "__main__":
    main()
