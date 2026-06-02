# Behavioural Intelligence Design

---

## Purpose

Phase 13 adds entity-aware behavioural context to the Fraud Intelligence Console so risk
triage can move beyond single-row transaction signals. The design preserves the existing
row-level scan path: legacy benchmark rows, rich synthetic banking rows, and no-history rows
must continue to score safely when behavioural history is absent.

This document defines the behavioural feature contract before implementation. It does not
change scoring weights, reason-code behaviour, frontend rendering, database schema, or scan
execution.

---

## Behavioural Entities

| Entity | Behavioural history meaning |
|---|---|
| Customer | Longitudinal customer activity such as usual amount range, transaction velocity, countries, channels, payment methods, and device usage. |
| Account | Account-level financial and access history such as recent balance profile, failed attempts, spend velocity, and new counterparty exposure. |
| Device | Device familiarity, first-seen age, reuse frequency, and whether the device is established for the customer or account. |
| Merchant | Customer-to-merchant relationship history, recurring merchant frequency, merchant category patterns, and unusual merchant exposure for a customer. |
| Counterparty | Payee or recipient relationship history, first-seen timing, prior transaction frequency, and whether the account has paid the counterparty before. |

---

## Baseline Feature Contract

Behavioural baseline fields should be optional and additive. Field names can be refined during
implementation, but the contract should remain clear, stable, and entity-scoped.

| Proposed field | Entity | Meaning |
|---|---|---|
| `customer_avg_amount_30d` | Customer | Average transaction amount over the last 30 days. |
| `customer_avg_amount_90d` | Customer | Average transaction amount over the last 90 days. |
| `customer_txn_count_24h_baseline` | Customer | Typical 24-hour transaction count baseline. |
| `customer_txn_count_7d_baseline` | Customer | Typical 7-day transaction count baseline. |
| `account_avg_balance_30d` | Account | Average account balance over the last 30 days. |
| `account_failed_attempts_30d` | Account | Failed access or authorization attempts over the last 30 days. |
| `device_seen_count_90d` | Device | Number of times this device was seen in the last 90 days. |
| `device_first_seen_days` | Device | Days since the device was first observed. |
| `merchant_customer_frequency_90d` | Merchant | Customer-to-merchant interaction frequency over the last 90 days. |
| `counterparty_seen_before` | Counterparty | Whether this account has paid the counterparty before. |
| `counterparty_first_seen_days` | Counterparty | Days since this counterparty was first observed for the account. |
| `usual_country` | Customer | Usual transaction country or country set for the customer. |
| `usual_channel` | Customer | Usual transaction channel for the customer. |
| `usual_payment_method` | Customer | Usual payment method for the customer. |

---

## Behavioural Derived Features

Derived features should be computed only when the required current-row value and behavioural
baseline are both present.

| Derived feature | Inputs | Meaning |
|---|---|---|
| `amount_deviation_ratio` | Current amount and customer amount baseline | Current amount relative to usual customer amount. |
| `velocity_deviation_ratio` | Current recent transaction count and velocity baseline | Current velocity relative to usual customer velocity. |
| `balance_drop_ratio` | Current amount, current balance, and account balance baseline | Transaction impact relative to recent account balance profile. |
| `new_device_for_customer` | Device history fields | Device is not established for the customer. |
| `new_country_for_customer` | Current country and usual country | Transaction country is outside usual customer geography. |
| `new_counterparty_for_account` | Counterparty history fields | Payee or recipient is new for this account. |
| `unusual_channel_for_customer` | Current channel and usual channel | Channel differs from usual customer activity. |
| `unusual_merchant_for_customer` | Merchant relationship frequency | Merchant is unusual for this customer. |

---

## Fallback and Compatibility Rules

- If behavioural history is absent, behavioural features are absent or neutral.
- Legacy scans must produce identical scoring behaviour when behavioural fields are absent.
- Rich scenario scans must continue to work without behavioural fields.
- Behavioural boosts must not apply unless the required behavioural fields exist.
- Missing optional behavioural fields must not cause validation, parsing, scoring, export, or
  frontend errors.
- Behavioural signals must remain additive to the existing feature contract until a later
  implementation phase explicitly changes scoring behaviour.
- No-history rows must not receive behavioural reason codes.

---

## Phase 13B Implementation Status

**Status:** Complete

Phase 13B implements optional behavioural feature extraction only. It does not change scoring
weights, reason-code emission, frontend rendering, or database schema.

**Optional baseline fields parsed (when present):**
- `customer_avg_amount_30d`, `customer_avg_amount_90d`
- `customer_txn_count_24h_baseline`, `customer_txn_count_7d_baseline`
- `account_avg_balance_30d`, `account_failed_attempts_30d`
- `device_seen_count_90d`, `device_first_seen_days`
- `merchant_customer_frequency_90d`
- `counterparty_seen_before`, `counterparty_first_seen_days`
- `usual_country`, `usual_channel`, `usual_payment_method`

**Derived behavioural features (neutral when inputs missing):**
- `amount_deviation_ratio`
- `velocity_deviation_ratio`
- `balance_drop_ratio`
- `new_device_for_customer`
- `new_country_for_customer`
- `new_counterparty_for_account`
- `unusual_channel_for_customer`
- `unusual_merchant_for_customer`

**No-history behaviour:**
- Missing or invalid behavioural baselines are treated as absent.
- Derived ratios default to 0.0 when baselines or current values are missing.
- Derived boolean indicators default to false when behavioural history is absent.
- Scoring weights and behavioural reason codes remain unchanged in Phase 13B.

**Phase 13B Validation:**
- Behavioural extraction implemented in feature generation.
- No-history rows remain neutral for derived behavioural features.
- Scoring weights unchanged.
- Behavioural reason-code emission unchanged.
- Local validation script passed: `python scripts/verify_behavioural_features.py`.

---

## Phase 13C - Behavioural Scoring Integration Design

### Purpose

Phase 13C defines how behavioural features may influence scoring before any code changes are
made. This phase is design-only.

### Current Behavioural Inputs

Derived behavioural features available from Phase 13B:
- `amount_deviation_ratio`
- `velocity_deviation_ratio`
- `balance_drop_ratio`
- `new_device_for_customer`
- `new_country_for_customer`
- `new_counterparty_for_account`
- `unusual_channel_for_customer`
- `unusual_merchant_for_customer`

### Activation Conditions

Behavioural scoring can only activate when behavioural baseline fields are present and valid.
No-history rows must produce a behavioural boost of 0.0.

### Proposed Behavioural Boost Design (Design Only)

Behavioural scoring is intended to be bounded and additive, without changing existing model,
rule, or rich signal weights.

Proposed components:
- `amount_deviation_ratio` above a threshold contributes a small boost.
- `velocity_deviation_ratio` above a threshold contributes a small boost.
- `balance_drop_ratio` above a threshold contributes a small boost.
- `new_device_for_customer` contributes a small boost.
- `new_country_for_customer` contributes a small boost.
- `new_counterparty_for_account` contributes a small boost.
- `unusual_channel_for_customer` contributes a small boost.
- `unusual_merchant_for_customer` contributes a small boost.
- Total behavioural boost is capped.

### Score Composition Boundary

Intended future formula (conceptual):

```
risk_score = base_score + rich_signal_boost + behavioural_boost
risk_score = min(risk_score, 1.0)
```

Boundaries:
- The existing 0.6 model / 0.4 rule base remains unchanged.
- Existing rich signal boost remains unchanged.
- Behavioural boost is optional and additive only when behavioural history exists.
- Risk score cap remains 1.0.

### Priority and Decision Compatibility

- P0/P1/P2/P3 thresholds remain unchanged unless explicitly reviewed later.
- APPROVE/REVIEW/BLOCK thresholds remain unchanged.
- Behavioural boost may move a transaction across tiers only when behavioural evidence exists.
- No-history rows remain identical to current scoring.

### Guardrails for Phase 13D Implementation

- No scoring change for rows without behavioural fields.
- No behavioural boost for legacy 10k rows.
- No behavioural boost for rich 10k rows unless behavioural history columns exist.
- No behavioural reason-code emission until Phase 13E.
- No frontend behavioural section until Phase 13F.
- No DB migration in 13D unless explicitly approved.

### Validation Requirements Before/For Phase 13D

- Legacy 10k regression unchanged.
- Rich 10k without behavioural history unchanged.
- No-history row produces behavioural_boost = 0.
- Behavioural row produces bounded boost.
- `risk_score` never exceeds 1.0.
- Priority mapping remains based on final capped score.
- `py_compile` passes.
- No large scans required.

### Calibration Boundary

Behavioural scoring is deterministic synthetic triage logic, not a calibrated probability.
Future real-world deployment would require labelled validation, monitoring, governance, and
model-risk review.

---

## Phase 13D - Behavioural Scoring Integration Implementation

**Status:** In progress

Phase 13D implements a bounded, additive behavioural boost when behavioural history exists.
The base model/rule blend, rich signal boost weights, thresholds, and reason-code emission
remain unchanged in this phase.

**Behavioural boost weights and thresholds:**
- `amount_deviation_ratio >= 3.0`: +0.05
- `velocity_deviation_ratio >= 3.0`: +0.05
- `balance_drop_ratio >= 0.20`: +0.04
- `new_device_for_customer`: +0.03
- `new_country_for_customer`: +0.03
- `new_counterparty_for_account`: +0.03
- `unusual_channel_for_customer`: +0.02
- `unusual_merchant_for_customer`: +0.02
- Behavioural boost cap: 0.20

**No-history behaviour:**
- If behavioural fields are missing or neutral, `behavioural_boost = 0.0`.

**Compatibility boundaries:**
- Base scoring weights (0.6 model / 0.4 rule) unchanged.
- Rich signal boost weights unchanged.
- Priority thresholds unchanged.
- APPROVE/REVIEW/BLOCK thresholds unchanged.
- No behavioural reason-code emission until Phase 13E.

---

## Phase 13E - Behavioural Reason-Code and Validation Lock

**Status:** In progress

Phase 13E locks behavioural reason-code taxonomy and enables evidence-gated emission.
Reason codes are emitted only when behavioural evidence exists; no-history rows emit none.
Scoring weights, boost weights, thresholds, frontend display, and DB schema remain unchanged.

**Locked behavioural reason codes and triggers:**
- `BEHAVIOURAL_AMOUNT_DEVIATION`: `amount_deviation_ratio >= 3.0`
- `BEHAVIOURAL_VELOCITY_DEVIATION`: `velocity_deviation_ratio >= 3.0`
- `BALANCE_DROP_ANOMALY`: `balance_drop_ratio >= 0.20`
- `NEW_DEVICE_FOR_CUSTOMER`: `new_device_for_customer` truthy
- `NEW_COUNTRY_FOR_CUSTOMER`: `new_country_for_customer` truthy
- `NEW_COUNTERPARTY_FOR_ACCOUNT`: `new_counterparty_for_account` truthy
- `UNUSUAL_CHANNEL_FOR_CUSTOMER`: `unusual_channel_for_customer` truthy
- `BEHAVIOURAL_PROFILE_SHIFT`: `unusual_merchant_for_customer` truthy

## Behavioural Reason Codes - Locked

These reason codes are locked for behavioural evidence emission in Phase 13E.

| Proposed code | Meaning |
|---|---|
| `BEHAVIOURAL_AMOUNT_DEVIATION` | Current amount materially exceeds the customer baseline. |
| `BEHAVIOURAL_VELOCITY_DEVIATION` | Current transaction velocity materially exceeds the customer baseline. |
| `NEW_DEVICE_FOR_CUSTOMER` | Device is new or rarely seen for this customer. |
| `NEW_COUNTRY_FOR_CUSTOMER` | Transaction country is outside the customer's usual geography. |
| `NEW_COUNTERPARTY_FOR_ACCOUNT` | Account is paying a new counterparty. |
| `UNUSUAL_CHANNEL_FOR_CUSTOMER` | Channel differs from established customer behaviour. |
| `BALANCE_DROP_ANOMALY` | Transaction creates an unusual account balance drop. |
| `BEHAVIOURAL_PROFILE_SHIFT` | Multiple behavioural dimensions differ from the established profile. |

Future implementation should align these codes with the locked reason-code taxonomy before
surfacing them in backend results or frontend chips.

---

## Intended Scoring Integration - Design Only

Behavioural signals should be additive and optional. Phase 13A does not change model weight,
rule weight, rich signal weights, priority thresholds, or decision thresholds.

Future implementation should:
- Apply behavioural boosts only when source fields and derived features are present.
- Use caps and guards so `risk_score` remains normalized.
- Preserve the existing no-history score path.
- Treat behavioural signals as triage evidence, not calibrated fraud probabilities.
- Validate behavioural weighting against synthetic/local evidence before broader use.

---

## UI / Case Dossier Display - Design Only

No frontend changes are made in Phase 13A. Future UI work may add sections such as:

- Behavioural Context
- Baseline vs Current Transaction
- Entity History Signals
- Behavioural Reason Codes

The frontend should hide behavioural sections when behavioural evidence is absent. Legacy rows
and rich rows without behavioural fields should render exactly as they do today.

**Phase 13F (first slice) note:** Risk Scan drawer displays Behavioural Signals only when
behavioural reason codes are present. Case Dossier display is not modified in this slice.

---

## Validation Matrix

| Check | Expected result |
|---|---|
| Legacy 10k regression | Priority distribution and scoring remain unchanged when behavioural fields are absent. |
| Rich 10k scan | Rich reason codes, scenario labels, and drawer grouping remain unchanged unless behavioural fields exist. |
| No-history rows | Behavioural derived features are absent or neutral; no behavioural reason codes emitted. |
| Behavioural synthetic rows | Expected behavioural derived features and proposed reason codes appear in later implementation phases. |
| Frontend drawer | Behavioural section remains hidden when behavioural evidence is absent. |
| Large scans | No large scans required for the first implementation pass. |

---

## Boundaries

Phase 13 behavioural intelligence should be validated first through local synthetic behavioural
simulation. It is not calibrated against real fraud labels yet.

Institution deployment would require labelled validation, governance, access control, security
review, monitoring, cost planning, and model-risk review.
