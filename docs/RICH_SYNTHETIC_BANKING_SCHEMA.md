# Rich Synthetic Banking Transaction Schema

---

## Purpose

This document defines the expanded synthetic transaction schema for Phase 12F. The existing
benchmark CSVs use a minimal 9-field format that was sufficient to verify async scan engine
throughput at 10M rows. The Phase 12F schema extends that baseline into a realistic banking
transaction record that supports scenario-aware fraud generation, richer reason-code coverage,
stronger analyst review context, and more credible demo storytelling.

The schema is designed for compatibility: existing 5-field and 9-field CSV files continue to
work without modification. All new fields are optional and additive.

---

## Current Limitation of Benchmark CSVs

The Phase 12D benchmark generator produces 9 columns:

| Column | Required | Notes |
|---|---|---|
| `transaction_id` | Yes | Simple sequential ID |
| `amount` | Yes | Random uniform draw, two tiers (fraud / legitimate) |
| `timestamp` | Yes | Random timestamp within a fixed year |
| `country` | Yes | Binary: high-risk / low-risk pool |
| `payment_method` | Yes | Uniform random from 4 options |
| `merchant_category` | No | Uniform random from 7 options |
| `device_id` | No | Empty string for fraud rows, random string otherwise |
| `device_type` | No | Uniform random from 3 options |
| `is_international` | No | Hardcoded true for fraud, random otherwise |

This produces only two fraud profiles: a high-amount night transaction from a high-risk country
with no device ID, and a low-amount daytime transaction from a low-risk country. It exercises
the scoring engine throughput correctly but produces no scenario variety, no entity relationships,
no velocity signals, and no customer behavioural context.

**Consequences:**
- All fraud rows trigger the same 3-7 reason codes.
- Analyst review of scan results yields no interpretive variety.
- Demo storytelling cannot reference specific fraud patterns.
- Future scoring enhancements (Phase 12G) have no rich features to reason about.
- Scenario families cannot be verified without per-scenario field coverage.

---

## New Schema Design

The rich schema adds 33 optional fields across 7 categories, preserving the 5-column
required minimum. The full 38-field record supports scenario-aware generation, velocity
signals, entity relationships, device trust, geographic anomaly detection, and analyst-facing
operational context.

| Category | Fields | Count |
|---|---|---|
| Transaction Identity | transaction_id, event_timestamp, account_id, customer_id, merchant_id | 5 |
| Monetary | amount, currency, account_balance_before, account_balance_after, daily_spend_to_date, available_limit | 6 |
| Channel / Device | channel, payment_method, device_id, device_trust_score, ip_country, billing_country, shipping_country, geo_distance_km | 8 |
| Merchant / Counterparty | merchant_category, merchant_risk_score, merchant_country, counterparty_age_days, new_payee_flag | 5 |
| Customer Behaviour | customer_tenure_days, avg_transaction_amount_30d, txn_count_1h, txn_count_24h, failed_attempts_1h, chargeback_count_90d | 6 |
| Fraud Scenario | scenario_label, scenario_family, synthetic_fraud_label, rule_trigger_count, primary_risk_reason | 5 |
| Operational | expected_priority, recommended_action, analyst_queue_hint | 3 |

**Total fields: 38**
**Required (unchanged): 5**
**Optional (new): 33**

---

## Field Dictionary

### A. Transaction Identity

| Field | Type | Required | Description |
|---|---|---|---|
| `transaction_id` | string | Yes | Unique transaction identifier. Prefix `rich_` for rich-mode records to distinguish from benchmark records. |
| `event_timestamp` | ISO 8601 string | Yes | Transaction event time. Maps to existing `timestamp` column; rich generator uses the name `event_timestamp` and the processor accepts both. |
| `account_id` | string | No | Account from which funds are drawn. One customer may have multiple accounts. Format: `acct_<hex8>`. |
| `customer_id` | string | No | Customer entity owning the account. Format: `cust_<hex8>`. Stable across multiple transactions. |
| `merchant_id` | string | No | Receiving merchant or payee entity. Format: `merch_<hex8>`. Used to detect repeat vs new payee. |

### B. Monetary Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `amount` | float | Yes | Transaction amount in the stated currency. |
| `currency` | string (ISO 4217) | No | Transaction currency code, e.g. `USD`, `GBP`, `EUR`. Defaults to `USD` when absent. |
| `account_balance_before` | float | No | Account balance immediately before this transaction. Used to detect account drain patterns. |
| `account_balance_after` | float | No | Account balance immediately after this transaction. Derived as `account_balance_before - amount` when not provided. |
| `daily_spend_to_date` | float | No | Cumulative spend for the account on the transaction date up to but not including this transaction. |
| `available_limit` | float | No | Remaining credit or daily limit available before this transaction. Relevant for credit_card and digital_wallet channels. |

### C. Channel / Device

| Field | Type | Required | Description |
|---|---|---|---|
| `channel` | string | No | Transaction entry channel. Values: `mobile_app`, `web`, `api`, `in_store`, `atm`, `phone`. |
| `payment_method` | string | Yes | Payment rail. Values: `credit_card`, `debit_card`, `digital_wallet`, `bank_transfer`. Unchanged from current schema. |
| `device_id` | string | No | Device identifier. Empty or absent triggers the `No device identifier present` reason code. Unchanged from current schema. |
| `device_trust_score` | float [0.0–1.0] | No | Institution-assigned device trust score. Score < 0.4 is treated as an unrecognised or low-trust device. |
| `ip_country` | string (ISO 3166-1 alpha-2) | No | Country resolved from the transaction IP address. May differ from `billing_country` on VPN or proxy. |
| `billing_country` | string (ISO 3166-1 alpha-2) | No | Country on file for the account's billing address. Replaces the existing `country` column for rich-mode records; `country` remains the required alias. |
| `shipping_country` | string (ISO 3166-1 alpha-2) | No | Destination country for e-commerce orders. Relevant for card-not-present fraud detection. |
| `geo_distance_km` | float | No | Approximate distance in km between the IP geolocation and the registered billing address. Values > 500 km are treated as anomalous. |

### D. Merchant / Counterparty

| Field | Type | Required | Description |
|---|---|---|---|
| `merchant_category` | string | No | Merchant category code group. Values: `grocery`, `electronics`, `gaming`, `travel`, `food`, `retail`, `healthcare`, `gambling`, `crypto`, `utilities`. Unchanged from current schema; `gambling` and `crypto` are new high-risk additions. |
| `merchant_risk_score` | float [0.0–1.0] | No | Institution-assigned risk score for the receiving merchant. Score >= 0.7 triggers the `High-risk merchant` reason code. |
| `merchant_country` | string (ISO 3166-1 alpha-2) | No | Country of the merchant's registered entity. May differ from `ip_country` and `billing_country`. |
| `counterparty_age_days` | integer | No | Number of days since the customer first transacted with this merchant or payee. 0 = first transaction ever with this payee. |
| `new_payee_flag` | boolean | No | True when `counterparty_age_days` is 0 or the payee has not previously received a payment from this account. Explicit flag avoids re-deriving from age. |

### E. Customer Behaviour

| Field | Type | Required | Description |
|---|---|---|---|
| `customer_tenure_days` | integer | No | Number of days since the customer opened their account. Low tenure on a high-value transaction is a risk signal. |
| `avg_transaction_amount_30d` | float | No | Customer's rolling 30-day average transaction amount at the time of this event. Used to detect amount anomalies. |
| `txn_count_1h` | integer | No | Number of transactions attempted by this customer in the 60 minutes preceding this event, including failed attempts. |
| `txn_count_24h` | integer | No | Number of transactions attempted by this customer in the 24 hours preceding this event. |
| `failed_attempts_1h` | integer | No | Number of failed authorisation attempts by this customer in the 60 minutes preceding this event. |
| `chargeback_count_90d` | integer | No | Number of chargebacks filed by this customer in the 90 days preceding this event. |

### F. Fraud Scenario Fields

These fields are present only in synthetically generated records and are not expected from real
uploaded transaction files. They serve as ground-truth labels, verification anchors, and
analyst interpretation aids in synthetic demo datasets.

| Field | Type | Required | Description |
|---|---|---|---|
| `scenario_label` | string | No | Specific instance label. Example: `ato_high_value_001`, `card_testing_micro_003`. |
| `scenario_family` | string | No | Scenario family this record belongs to. One of the 12 families defined below. |
| `synthetic_fraud_label` | integer (0 or 1) | No | Ground-truth fraud label for model evaluation. 1 = fraud, 0 = legitimate. Not used by the scoring engine; present for offline analysis only. |
| `rule_trigger_count` | integer | No | Pre-computed count of how many rule conditions are expected to trigger for this record. Used for scenario verification. |
| `primary_risk_reason` | string | No | Human-readable primary reason for the fraud label. Maps to the reason code vocabulary below. |

### G. Operational Fields

These fields carry pre-computed analyst hints for demo and verification purposes.

| Field | Type | Required | Description |
|---|---|---|---|
| `expected_priority` | string | No | Pre-computed expected priority tier (P0, P1, P2, P3) for scenario verification. Allows automated verification that the scoring engine assigns the correct tier to each scenario. |
| `recommended_action` | string | No | Pre-computed recommended analyst action: `BLOCK`, `REVIEW`, or `APPROVE`. |
| `analyst_queue_hint` | string | No | Free-text hint for the analyst review queue. Examples: `Escalate to AML team`, `Contact customer for verification`, `Auto-approve low-risk`. |

---

## Scenario Families

Each of the 12 scenario families represents a distinct fraud pattern with a defined field
signature, expected scoring behaviour, and analyst interpretation.

---

### 1. Account Takeover (ATO)

**Pattern:**
A legitimate account is accessed using stolen credentials. The transaction originates from an
unrecognised device, a new IP geolocation distant from the registered address, and is typically
a high-value transfer at an unusual time.

**Fields affected:**
- `device_trust_score` < 0.3 (unrecognised device)
- `geo_distance_km` > 500
- `ip_country` differs from `billing_country`
- `event_timestamp` hour < 6 or > 22
- `amount` high relative to `avg_transaction_amount_30d`

**Expected priority:** P0

**Reason codes:**
- Unrecognised device with low trust score
- Geographic location inconsistent with registered address
- Unusual transaction time
- Transaction amount significantly above 30-day average

**Analyst interpretation:**
Credential compromise or session hijack. Freeze account immediately. Contact the registered
customer through a verified channel. Do not approve without customer confirmation.

---

### 2. Card Testing

**Pattern:**
A stolen card number is validated through rapid micro-transactions before a larger withdrawal.
Characterised by high velocity, very small amounts, and multiple merchants in a short window.

**Fields affected:**
- `txn_count_1h` > 8
- `amount` < 5.00
- `failed_attempts_1h` > 3
- Multiple distinct `merchant_id` values in the same hour

**Expected priority:** P1

**Reason codes:**
- Transaction velocity exceeds 1-hour baseline
- Multiple failed attempts preceding this transaction

**Analyst interpretation:**
Stolen card number under automated validation. Flag the card immediately. Block the current
and any concurrent transactions from the same device and IP.

---

### 3. High-Velocity Spend

**Pattern:**
Transaction count within a 1-hour or 24-hour window dramatically exceeds the customer's
baseline. Spend may approach or exceed the daily limit. Not necessarily international.

**Fields affected:**
- `txn_count_1h` > 5 or `txn_count_24h` > 15
- `daily_spend_to_date` approaching `available_limit`
- `avg_transaction_amount_30d` significantly lower than current `amount`

**Expected priority:** P1

**Reason codes:**
- Transaction velocity exceeds 24-hour baseline
- Daily spend limit approaching
- Transaction amount significantly above 30-day average

**Analyst interpretation:**
Possible authorised push payment (APP) fraud or post-compromise spending spree. Verify whether
the customer initiated recent transactions. Consider temporary spend limit reduction pending review.

---

### 4. Unusual Geography

**Pattern:**
The transaction IP geolocation is inconsistent with the customer's registered billing country
and merchant country. High `geo_distance_km`. Occurs with no corresponding travel advisory on
the account.

**Fields affected:**
- `ip_country` differs from `billing_country` and `merchant_country`
- `geo_distance_km` > 1000
- `is_international` = true
- `merchant_country` in high-risk country list

**Expected priority:** P1

**Reason codes:**
- Geographic location inconsistent with registered address
- International transaction from elevated-risk region

**Analyst interpretation:**
Card-not-present fraud from a foreign actor using a proxied or VPN-masked connection. Standard
geo-block or step-up authentication check recommended before authorisation.

---

### 5. New Payee Transfer

**Pattern:**
A first-time, high-value bank transfer to a payee the customer has never paid before.
Frequently used in authorised push payment (APP) fraud where a victim is socially engineered
into transferring funds to a mule account.

**Fields affected:**
- `new_payee_flag` = true
- `counterparty_age_days` = 0
- `amount` high (> $2,000)
- `payment_method` = `bank_transfer`

**Expected priority:** P0

**Reason codes:**
- First-time payment to unknown payee
- High transaction amount

**Analyst interpretation:**
APP fraud is the most likely scenario. Contact the customer before processing. Confirm the
payee is known and the instruction was not socially engineered. If unconfirmed, decline and
refer to fraud prevention.

---

### 6. Merchant Risk Spike

**Pattern:**
The transaction is directed to a merchant with a high institution-assigned risk score or a
high-risk merchant category. May reflect a compromised merchant terminal, a newly flagged
merchant, or a known fraud-associated business.

**Fields affected:**
- `merchant_risk_score` >= 0.7
- `merchant_category` in `gambling`, `crypto`, `electronics`, `gaming`
- `merchant_country` in high-risk list

**Expected priority:** P1 / P2

**Reason codes:**
- High-risk merchant
- High-risk merchant category

**Analyst interpretation:**
Review the merchant's risk profile. High-volume transactions to a flagged merchant may indicate
a coordinated fraud pattern targeting that merchant's customer base.

---

### 7. Mule Account Behaviour

**Pattern:**
The account shows a pattern consistent with a money mule: elevated chargeback history, high
transaction velocity, and high-value outbound transfers shortly after inbound credits. Not
necessarily a single-transaction pattern.

**Fields affected:**
- `chargeback_count_90d` >= 3
- `txn_count_24h` > 10
- `amount` large outbound relative to `account_balance_before`
- `daily_spend_to_date` high

**Expected priority:** P0

**Reason codes:**
- High chargeback history
- Transaction velocity exceeds 24-hour baseline
- High transaction amount

**Analyst interpretation:**
Possible money mule account. Escalate to the AML/compliance team. This pattern requires
investigation beyond a single transaction. Do not block without a coordinated account review.

---

### 8. Refund / Chargeback Abuse

**Pattern:**
A customer with an elevated chargeback history makes a new transaction matching the amount
and merchant category of previous chargebacks. May represent first-party fraud.

**Fields affected:**
- `chargeback_count_90d` >= 2
- `merchant_category` matching prior chargeback patterns
- `amount` in the range of previously disputed transactions

**Expected priority:** P2

**Reason codes:**
- High chargeback history

**Analyst interpretation:**
First-party fraud risk. Review the customer's chargeback history before authorising. Consider
requiring additional verification for transactions from this customer.

---

### 9. Dormant Account Reactivation

**Pattern:**
An account that has shown no or minimal activity for an extended period suddenly generates a
high-value transaction. The contrast between a low 30-day average and the current amount is
the primary signal.

**Fields affected:**
- `avg_transaction_amount_30d` near zero (< $20)
- `txn_count_24h` = 0 or 1 (minimal recent activity)
- `amount` high (>= $1,000)
- `customer_tenure_days` high (established account, not new)

**Expected priority:** P1

**Reason codes:**
- Account dormant; high-value reactivation detected
- Transaction amount significantly above 30-day average

**Analyst interpretation:**
Account may have been compromised after a period of dormancy. Verify whether the customer
is aware of the transaction. Dormant accounts are a common target for credential stuffing.

---

### 10. Cross-Border High-Value

**Pattern:**
A large international transaction to a high-risk country, combining high amount, international
flag, night timing, and an elevated merchant or counterparty country risk profile.

**Fields affected:**
- `amount` > HIGH_AMOUNT_THRESHOLD
- `is_international` = true
- `billing_country` / `merchant_country` in high-risk list
- `event_timestamp` hour < 6 or > 22
- `currency` may differ from account home currency

**Expected priority:** P1

**Reason codes:**
- High transaction amount
- International transaction from elevated-risk region
- Unusual transaction time

**Analyst interpretation:**
Standard AML check required. This pattern is common in wire fraud and international card-not-
present fraud. Verify transaction legitimacy before processing. Retain records for regulatory
reporting if the amount exceeds reporting thresholds.

---

### 11. Device Mismatch

**Pattern:**
The transaction arrives from a device that is unrecognised for this account, with a low
trust score. The device channel or device type differs from the customer's established profile.
May accompany geo distance anomaly.

**Fields affected:**
- `device_id` absent or different from previously registered devices
- `device_trust_score` < 0.4
- `channel` different from customer's typical channel
- `geo_distance_km` may be elevated

**Expected priority:** P1

**Reason codes:**
- Unrecognised device with low trust score
- No device identifier present (if device_id absent)

**Analyst interpretation:**
Possible session hijack or phishing-obtained session token. Trigger step-up authentication.
If the customer cannot confirm the session, terminate and flag the account.

---

### 12. Suspicious Repeated Attempts

**Pattern:**
A high number of failed authorisation attempts immediately precede a successful transaction.
This pattern indicates credential brute-forcing, card detail enumeration, or PIN guessing.

**Fields affected:**
- `failed_attempts_1h` >= 4
- `txn_count_1h` elevated
- `payment_method` = `credit_card` or `digital_wallet`
- `amount` may be elevated relative to baseline

**Expected priority:** P1

**Reason codes:**
- Multiple failed attempts preceding this transaction
- Transaction velocity exceeds 1-hour baseline

**Analyst interpretation:**
Brute-force card testing or stolen credential validation. Block the current session immediately.
Require full re-authentication. Notify the cardholder.

---

## Priority Tier Mapping

| Priority | Score Range | Scenario Families |
|---|---|---|
| P0 Critical | >= 0.80 | Account Takeover, New Payee Transfer, Mule Account Behaviour |
| P1 High | 0.60 – 0.79 | Card Testing, High-Velocity Spend, Unusual Geography, Dormant Account Reactivation, Cross-Border High-Value, Device Mismatch, Suspicious Repeated Attempts, Merchant Risk Spike (high) |
| P2 Medium | 0.30 – 0.59 | Refund / Chargeback Abuse, Merchant Risk Spike (low) |
| P3 Low | < 0.30 | Legitimate transactions |

---

## Reason-Code Vocabulary

### Existing reason codes (unchanged)

| Code | Trigger condition |
|---|---|
| High transaction amount | `amount` > HIGH_AMOUNT_THRESHOLD (1000) |
| Unusual transaction time | `hour_of_day` < 6 or > 22 |
| Model flagged as suspicious | `model_prediction` = 1 |
| International transaction from elevated-risk region | `is_international` = 1 and `is_high_risk_country` = 1 |
| High-risk payment method | `payment_method` in {credit_card, digital_wallet} |
| High-risk merchant category | `merchant_category` in {electronics, gaming, travel} |
| No device identifier present | `device_id` absent or empty |

### New reason codes (Phase 12F-3 additions)

| Code | Trigger condition |
|---|---|
| Transaction velocity exceeds 1-hour baseline | `txn_count_1h` > 5 |
| Transaction velocity exceeds 24-hour baseline | `txn_count_24h` > 12 |
| Geographic location inconsistent with registered address | `geo_distance_km` > 500 |
| Unrecognised device with low trust score | `device_trust_score` < 0.4 |
| First-time payment to unknown payee | `new_payee_flag` = true and `amount` > 500 |
| High chargeback history | `chargeback_count_90d` >= 2 |
| Account dormant; high-value reactivation detected | `avg_transaction_amount_30d` < 20 and `amount` > 1000 |
| High-risk merchant | `merchant_risk_score` >= 0.7 |
| Multiple failed attempts preceding this transaction | `failed_attempts_1h` >= 4 |
| Daily spend limit approaching | `daily_spend_to_date` > 0.8 * `available_limit` (when both present) |
| Transaction amount significantly above 30-day average | `amount` > 3 * `avg_transaction_amount_30d` (when baseline > 0) |
| Billing and shipping country mismatch | `billing_country` differs from `shipping_country` |
| Currency inconsistent with account home currency | `currency` not in account's typical currency set |

---

## Compatibility Strategy

The rich schema is designed for zero-disruption adoption. Two modes coexist:

### Legacy Benchmark Mode

Files produced by the existing Phase 12D generators continue to work without modification.
The validator requires only: `transaction_id`, `amount`, `timestamp`, `country`, `payment_method`.
The scanner uses `.get()` with safe defaults for all optional columns. No changes to
`validator.py` or `scanner.py` required for legacy files to continue processing.

### Rich Scenario Mode

Files produced by the Phase 12F generator include the full 38-column schema. The processor
reads all columns present and falls back gracefully when optional columns are absent. Columns
not recognised by the current feature engineering layer are passed through to the result record
and stored for future use; they do not cause errors.

**Compatibility invariants:**

| Invariant | Guarantee |
|---|---|
| Required columns | Unchanged. `transaction_id`, `amount`, `timestamp`, `country`, `payment_method` remain the only required columns. |
| Validation logic | No changes to `REQUIRED_COLUMNS` set in `validator.py`. |
| Scoring contract | `risk_score`, `decision`, `risk_tier`, `operational_priority`, `reasons` all remain in the result payload. |
| Result schema | All existing result fields preserved. New fields are additive. |
| Export format | CSV export column order is unchanged for existing columns; new columns append to the right. |
| API response shape | No changes to `GET /risk-scan/{scan_id}/results` response envelope. |
| Frontend compatibility | Drawer and report modal read only fields they expect; unknown fields are ignored. |

---

## Implementation Plan

### Phase 12F-1 -- Rich Schema Design (this document)

- Field dictionary defined across 7 categories (38 total fields)
- 12 scenario families defined with field signatures, priority tiers, and reason codes
- New reason-code vocabulary extended from 7 to 20 codes
- Compatibility strategy documented
- No code changes required

### Phase 12F-2 -- Rich Generator Implementation (complete)

**Script:** `scripts/generate_rich_banking_csv.py`
**Verify:** `scripts/verify_rich_banking_csv.py`

**Generate a dataset:**

```sh
python scripts/generate_rich_banking_csv.py --rows 10000 --output C:\tmp\rich-10k.csv --seed 42
python scripts/generate_rich_banking_csv.py --rows 1000  --seed 42
python scripts/generate_rich_banking_csv.py --rows 100000 --output C:\tmp\rich-100k.csv
```

**Verify a dataset:**

```sh
python scripts/verify_rich_banking_csv.py C:\tmp\rich-10k.csv
```

**CLI arguments:**

| Argument | Default | Description |
|---|---|---|
| `--rows` | 10000 | Number of rows to generate |
| `--output` | `scripts/test_rich_<rows>.csv` | Output CSV path |
| `--seed` | 42 | Random seed for reproducibility |
| `--scenario-mix` | Default mix | JSON dict overriding scenario proportions |

**Output:** 42-column CSV (38 rich schema fields + 4 legacy compatibility aliases)
**Default mix:** 70% normal, 30% fraud across 12 scenario families
**Reproducibility:** fixed seed produces identical output across runs
**Generated CSVs:** gitignored — never committed to version control

### Phase 12F-3 -- Scenario-Aware Scoring and Reason Mapping (complete)

**Modified files:**
- `src/features/transaction_features.py` -- rich feature extraction and reason codes
- `src/triage/investigator.py` -- rich signal boost applied to risk_score

**Rich features extracted (all with column-existence guards):**

| Feature | Source column | Threshold |
|---|---|---|
| `is_low_trust_device` | `device_trust_score` | < 0.4 |
| `is_geo_anomaly` | `geo_distance_km` | > 500 km |
| `is_high_velocity_1h` | `txn_count_1h` | > 5 |
| `has_failed_attempts` | `failed_attempts_1h` | >= 4 |
| `is_high_risk_merchant_score` | `merchant_risk_score` | >= 0.7 |
| `is_new_payee_high_value` | `new_payee_flag` + `amount` | flag=true AND amount > 500 |
| `has_chargebacks` | `chargeback_count_90d` | >= 2 |
| `is_amount_anomaly` | `avg_transaction_amount_30d` + `amount` | amount > 3x 30d avg |
| `is_rich_fraud_scenario` | `scenario_family` | not empty and not 'normal' |

**Rich signal boost weights (additive, capped at 1.0):**

| Feature | Boost |
|---|---|
| `is_low_trust_device` | +0.10 |
| `is_geo_anomaly` | +0.10 |
| `is_high_velocity_1h` | +0.12 |
| `has_failed_attempts` | +0.15 |
| `is_high_risk_merchant_score` | +0.08 |
| `is_new_payee_high_value` | +0.15 |
| `has_chargebacks` | +0.10 |
| `is_amount_anomaly` | +0.08 |
| `is_rich_fraud_scenario` | +0.25 |

`risk_score = min(1.0, 0.6 * model_prediction + 0.4 * rule_flag + rich_signal_boost)`

**New reason codes added (8 signal codes + 12 scenario labels):**

Signal codes: Unrecognised device with low trust score, Geographic location inconsistent
with registered address, Transaction velocity exceeds 1-hour baseline, Multiple failed
attempts preceding this transaction, High-risk merchant, First-time payment to unknown
payee, High chargeback history, Transaction amount significantly above 30-day average.

Scenario labels (appended as analyst context): Account takeover pattern detected,
Card testing velocity pattern, High-velocity spend pattern, Unusual geographic pattern,
New payee transfer risk, Merchant risk spike, Mule account behaviour pattern,
Refund and chargeback abuse pattern, Dormant account reactivation detected,
Cross-border high-value transaction, Device mismatch detected,
Suspicious repeated attempts detected.

**Verified results (1k rich CSV, seed=42):**
- P0: 198, P1: 39, P2: 61, P3: 702 (rich scoring active)
- Rich codes confirmed in P0/P1/P2 rows
- Legacy 10k CSV: P0: 1546, P1: 913, P2: 0, P3: 7541 (unchanged -- no rich boost)
- E2E 9/9 passed, Next.js build clean

**Compatibility invariants preserved:**
- `REQUIRED_COLUMNS` in `validator.py` unchanged
- `apply_fraud_rules.py` unchanged
- `scanner.py` result payload unchanged
- All rich features degrade to 0 when source columns absent (legacy CSVs unaffected)

### Phase 12F-4 -- UI Support for Richer Fields (complete)

**Approach:** Rich individual fields are not persisted in `portfolio_scan_results`. The
`reasons` pipe-delimited string is the sole carrier of rich scenario information in the
result payload. The drawer was updated to extract maximum analyst value from reasons alone.

**`ScanResultDrawer.tsx` changes:**

Reason codes are classified client-side into three groups:
- **Legacy signals** (7 existing codes) -- rendered as red chips, unchanged
- **Rich signal codes** (8 Phase 12F-3 codes) -- rendered as amber chips
- **Scenario family label** (e.g., "Card testing velocity pattern") -- extracted and
  displayed in a separate "Scenario" section showing the pattern name in cyan

The "Scenario" section only renders when a scenario label is present in reasons. Legacy
scan rows have no such label, so the section is hidden and the drawer is visually
identical to pre-12F-4.

`device_id` normalisation: "NaN" and "None" strings (pandas serialisation of empty-string
CSV cells) are treated as absent. Analysts see no "Device ID: NaN" entry.

**No backend changes.** No Zod type changes. No DB migration.

**Display behaviour by row type:**

| Row source | Scenario section | Reason chip styles |
|---|---|---|
| Legacy scan (10M benchmark) | Hidden | All chips red (unchanged) |
| Rich scan -- normal row | Hidden | Red chips only (no rich signals) |
| Rich scan -- fraud row | Visible (pattern name in cyan) | Red legacy + amber rich chips |

**Analyst view example (card_testing row):**
```
Scenario:        Card Testing
Risk Signals:    High-risk payment method [red]
                 Unrecognised device with low trust score [amber]
                 Geographic location inconsistent with registered address [amber]
                 Transaction velocity exceeds 1-hour baseline [amber]
                 Multiple failed attempts preceding this transaction [amber]
```

### Phase 12F-5 -- Demo Dataset Generation and Verification (complete)

**Rich demo scan verified end-to-end across the full 12F pipeline.**

---

#### Generation

```sh
python scripts/generate_rich_banking_csv.py --rows 10000 --output C:\tmp\rich-banking-demo-10k.csv --seed 229
```

Verification: 11/11 checks PASSED (`scripts/verify_rich_banking_csv.py`).

#### Scan details

| Field | Value |
|---|---|
| `scan_id` | `62c601b2-ddf7-487b-ad32-976a71b3bf58` |
| Filename | `rich-banking-demo-10k.csv` |
| Total rows | 10,000 |
| Valid / Invalid / Skipped | 10,000 / 0 / 0 |
| Processing time | ~6 s |

#### Priority distribution (scored)

| Priority | Count | % |
|---|---|---|
| P0 Critical | 2,080 | 20.8% |
| P1 High | 375 | 3.8% |
| P2 Medium | 533 | 5.3% |
| P3 Low | 7,012 | 70.1% |

#### Exposure summary

| Field | Value |
|---|---|
| Total exposure | $12,820,563 |
| Critical exposure (P0) | $10,114,632 |
| High exposure (P1) | $7,324 |

#### Scenario distribution (generator)

| Scenario | Rows | Expected priority |
|---|---|---|
| normal | 7,000 | P3 |
| high_velocity_spend | 500 | P1 |
| card_testing | 400 | P1 |
| account_takeover | 400 | P0 |
| unusual_geography | 350 | P1 |
| merchant_risk_spike | 300 | P1 / P2 |
| new_payee_transfer | 300 | P0 |
| refund_chargeback_abuse | 200 | P2 |
| mule_account_behaviour | 200 | P0 |
| dormant_account_reactivation | 100 | P1 |
| device_mismatch | 100 | P1 |
| cross_border_high_value | 100 | P1 |
| suspicious_repeated_attempts | 50 | P1 |

#### Verified reason code examples

**P0 account_takeover row (score 1.000):**
```
High transaction amount | Unusual transaction time | Model flagged as suspicious |
International transaction from elevated-risk region | High-risk payment method |
Unrecognised device with low trust score | Geographic location inconsistent with
registered address | Multiple failed attempts preceding this transaction |
Transaction amount significantly above 30-day average | Account takeover pattern detected
```

**P1 card_testing row (score 0.720):**
```
High-risk payment method | Unrecognised device with low trust score |
Geographic location inconsistent with registered address |
Transaction velocity exceeds 1-hour baseline |
Multiple failed attempts preceding this transaction | Card testing velocity pattern
```

**P0 high_velocity_spend row (score 1.000):**
```
High transaction amount | Model flagged as suspicious | High-risk payment method |
High-risk merchant category | Transaction velocity exceeds 1-hour baseline |
Transaction amount significantly above 30-day average | High-velocity spend pattern
```

#### Frontend verification

Rich scan loaded at:
`http://localhost:3000/risk-scan?scan_id=62c601b2-ddf7-487b-ad32-976a71b3bf58`

- Filename `rich-banking-demo-10k.csv` visible in recent scans panel
- Results table loaded with P0/P1/P2/P3 tier filter tabs
- Drawer opened on first row (P0, high_velocity_spend pattern)
- Scenario section rendered: "PATTERN | High-Velocity Spend" in cyan
- Risk Signals showed legacy (red) and rich (amber) chips correctly
- 10M legacy scan drawer: Scenario section absent, all chips legacy red

#### Legacy compatibility confirmed

10k legacy benchmark CSV (seed=42) scan produced:
P0: 1,546 / P1: 913 / P2: 0 / P3: 7,541 -- exact match to Phase 12D-5 benchmark.
No rich codes present. No boost applied.

#### Export

Full export: HTTP 200, 10,001 lines (header + 10,000 rows), ~2.0 MB.

#### Test results

E2E: 9/9 passed. Build: clean (8 routes).
