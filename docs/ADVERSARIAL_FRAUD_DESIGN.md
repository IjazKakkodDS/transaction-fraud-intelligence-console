# Adversarial Fraud Design Contract -- Phase 16

---

## Purpose

Phase 16 validates the Fraud Intelligence Console's current detection stack against evasive
synthetic fraud behaviours. Where Phase 12F produced overt fraud scenarios -- patterns that
trigger obvious thresholds and produce strong signals -- Phase 16 generates adversarial
patterns specifically designed to evade individual or compound detection mechanisms.

The goal is not to improve detection rates within this phase. It is to produce a credible,
documented detection evidence matrix that honestly characterises where the current intelligence
stack succeeds and where it has measurable boundaries. This evidence supports accurate system
positioning, grounds future scoring and investigation hardening work, and provides the kind of
self-aware capability documentation that distinguishes a mature fraud intelligence product from
a benchmark-optimised prototype.

All patterns are synthetically generated. No real banking data is used. Detection rates on
synthetic adversarial datasets must not be presented as production fraud model accuracy.

---

## Current Intelligence Stack Under Test

The following layers are active at the time Phase 16 begins. All are locked and operational.
Phase 16 tests their collective behaviour against adversarial inputs -- it does not modify them.

```
Layer 1 -- Row-Level Scoring (Phase 11F, 12F-3)
  Model   : XGBoost, 9-feature vector, weight 0.6
  Rules   : 3 deterministic conditions, weight 0.4
  Formula : base_score = 0.6 * model_prediction + 0.4 * rule_flag

Layer 2 -- Rich Signal Boost (Phase 12F-3)
  Source  : Optional rich CSV fields (device_trust_score, geo_distance_km,
            txn_count_1h, failed_attempts_1h, merchant_risk_score,
            new_payee_flag, chargeback_count_90d, avg_transaction_amount_30d,
            scenario_family)
  Trigger : Column-existence guards with defined thresholds
  Formula : risk_score = min(1.0, base_score + rich_signal_boost)
  Max     : +1.13 before cap

Layer 3 -- Behavioural Boost (Phase 13D)
  Source  : Customer and account historical baseline columns
  Signals : amount_deviation_ratio, velocity_deviation_ratio, balance_drop_ratio,
            new_device_for_customer, new_country_for_customer,
            new_counterparty_for_account, unusual_channel_for_customer,
            unusual_merchant_for_customer
  Cap     : 0.20

Layer 4 -- Graph Boost (Phase 15D)
  Source  : Entity adjacency computed within the scan batch
  Signals : shared_device_flag, cross_account_device_reuse,
            counterparty_fan_in_flag, counterparty_fan_out_flag
  Cap     : 0.15

Combined formula (all layers):
  risk_score = min(1.0,
      base_score
    + rich_signal_boost
    + behavioural_boost
    + graph_boost
  )

Reason-code explanation layer (Phases 12F-3, 13E, 15E):
  Pipe-delimited reasons field carrying legacy, rich, behavioural, and graph
  reason codes. Surfaced in the Risk Scan result drawer as four visual chip
  groups: red (legacy), amber (rich), blue (behavioural), violet (graph).

Decision and priority thresholds (locked):
  APPROVE : risk_score < 0.30
  REVIEW  : 0.30 <= risk_score < 0.70
  BLOCK   : risk_score >= 0.70

  P0 Critical : risk_score >= 0.80
  P1 High     : 0.60 <= risk_score < 0.80
  P2 Medium   : 0.30 <= risk_score < 0.60
  P3 Low      : risk_score < 0.30
```

---

## Why Adversarial Simulation Matters

The 12 Phase 12F rich scenario families represent overt fraud: patterns that produce signals
clearly above defined thresholds. A high-amount night transaction from a high-risk country with
no device ID activates the legacy rule flag, the model, and multiple rich signal boosts
simultaneously. These patterns are detectable by design.

Real adversarial fraud operates differently:

- **Threshold avoidance.** A fraudster aware of rule thresholds keeps transaction amounts
  just below the high-amount threshold, initiates transactions during business hours, and uses
  a low-risk origin country. None of the legacy rule conditions fire. The model may or may not
  flag the pattern depending on its feature inputs.

- **Profile mirroring.** A compromised account is exploited at an amount close to the customer's
  historical 30-day average, using a recognised device type, in a familiar geography. The
  behavioural boost does not fire because the deviation ratios are small.

- **Compound threshold straddling.** All three detection layers have defined numeric thresholds.
  An adversarial transaction can be engineered to sit just below each threshold simultaneously:
  device trust at 0.42 (threshold < 0.40), geo distance at 490km (threshold > 500km), velocity
  at 4 transactions per hour (threshold > 5). None of the rich signal boosts fire.

- **Graph evasion.** A mule fan-in pattern that stays at exactly the counterparty threshold
  (3 accounts, not > 3) avoids the graph boost entirely while still representing a structurally
  suspicious pattern.

Documenting these boundaries is an honest characterisation of a baseline fraud intelligence
system. The gaps inform future model validation, threshold calibration, and investigation brief
hardening work. They should not be hidden.

---

## Scope

### In Scope

- Design and documentation of adversarial scenario taxonomy (this document)
- Standalone adversarial generator implementation (Phase 16B)
- Structural validation of generated adversarial CSV schema and evasion constraints (Phase 16B)
- In-memory detection evidence matrix per adversarial scenario (Phase 16C)
- Small live scan evidence lock (1,000 rows maximum) (Phase 16D)
- Documented detection gaps per scenario and per detection layer (Phase 16C, 16D)

### Out of Scope

| Item | Why deferred |
|---|---|
| Scoring recalibration | Requires separate owner review and approval; changes belong in a dedicated scoring phase |
| Model retraining | No labelled real-world fraud data; synthetic calibration is not credible for this purpose |
| Frontend changes | Phase 17 (Case Dossier 2.0) is the owner of investigative workspace upgrades |
| Database migrations | Adversarial CSVs use the existing 42-column schema; no new persistence layer required |
| Production fraud accuracy claims | Synthetic adversarial detection rates are not transferable to real institution portfolios |
| Large-scale scans | Adversarial value is in pattern precision, not throughput; no scan above 10,000 rows |
| Deployment hardening | Phase 19 and 20 scope; not addressable before investigation and governance layers are complete |
| Multi-scan entity persistence | The current scoring stack operates within a single scan window; cross-scan correlation requires future architecture work |

---

## Design Decision: Separate Adversarial Generator

Phase 16 creates a new, standalone generator script:

```
scripts/generate_adversarial_csv.py
```

The existing `scripts/generate_rich_banking_csv.py` must not be modified.

**Reasons:**

1. **Reproducibility preservation.** The rich generator produces a verified output at seed=42
   (Phase 12F-5 demo dataset, scan_id `62c601b2-ddf7-487b-ad32-976a71b3bf58`). Modifying
   the generator or its `DEFAULT_SCENARIO_MIX` would break the seed=42 reproducibility
   guarantee and potentially alter documented benchmark outputs.

2. **Verified scenario mix stability.** The rich generator's 12 scenario families and their
   proportions are documented and verified. Adding adversarial families to the default mix
   would change the scenario distribution and require re-verifying all prior evidence.

3. **Inverted design orientation.** Rich scenario families are defined by the signals they
   trigger. Adversarial scenario families are defined by the signals they evade. The generator
   structure and field assignment logic is conceptually different enough to warrant a separate
   file.

4. **Independent verification path.** A dedicated `scripts/verify_adversarial_csv.py` can
   validate adversarial schema and evasion constraints without requiring changes to
   `scripts/verify_rich_banking_csv.py`, which is currently verified and stable.

5. **Documentation clarity.** A standalone adversarial generator is self-documenting: its
   purpose, scope, and output are unambiguous to any future reviewer.

The adversarial generator may share reference data (country lists, payment methods, channel
values) with the rich generator by convention -- using the same constants independently -- but
it does not import from the rich generator. Scripts are self-contained.

---

## Shared Schema Contract

Adversarial CSVs use the same 42-column output schema as the rich generator:

- 5 legacy required columns: `transaction_id`, `amount`, `timestamp`, `country`,
  `payment_method`
- 37 optional rich columns covering Transaction Identity, Monetary, Channel/Device,
  Merchant/Counterparty, Customer Behaviour, Fraud Scenario, and Operational fields

This ensures adversarial CSVs pass the existing portfolio scan validator without modification.
The scenario fields (`scenario_label`, `scenario_family`, `synthetic_fraud_label`,
`expected_priority`, `recommended_action`, `analyst_queue_hint`) are populated with
adversarial-specific values and serve as ground-truth labels and verification anchors.

The `scenario_family` values used by the adversarial generator are distinct from the 12
Phase 12F families (e.g., `low_and_slow`, `victim_mirror`, `threshold_straddle`,
`graph_evasion_fan_in`) and will not match the existing `SCENARIO_LABEL_MAP` in the drawer.
This is intentional: adversarial patterns are investigative research artifacts, not
analyst-facing scenario labels. The drawer will render no scenario section for these rows,
which is the correct behaviour.

---

## First-Slice Adversarial Scenario Families

The following four families are approved for Phase 16B implementation. Each entry documents
the intended evasion target, the specific field engineering required, and the expected
detection outcome under the current scoring stack.

---

### A. Low-and-Slow Amount Splitting

**Intent:**
Simulate a fraudster who avoids the `amount > HIGH_AMOUNT_THRESHOLD` (1,000 USD) rule trigger
by keeping each individual transaction sub-threshold. Transactions are conducted during
business hours to avoid the `is_night_transaction` signal. A low-risk country avoids the
`is_high_risk_country` and `is_international` signals. Multiple repeated transfers to the
same counterparty simulate value accumulation over time.

**Field engineering:**

| Field | Adversarial value |
|---|---|
| `amount` | 750 -- 980 (below 1,000 threshold) |
| `timestamp` hour | 09:00 -- 17:00 (business hours; is_night_transaction = 0) |
| `country` | Low-risk (US, GB, DE) |
| `is_international` | false |
| `payment_method` | bank_transfer (avoids high-risk payment method flag) |
| `device_trust_score` | 0.60 -- 0.90 (well above < 0.40 cutoff) |
| `geo_distance_km` | 10 -- 150 (well below > 500 threshold) |
| `txn_count_1h` | 1 -- 3 (well below > 5 threshold) |
| `failed_attempts_1h` | 0 |
| `chargeback_count_90d` | 0 |
| `new_payee_flag` | false (counterparty seen before) |
| `avg_transaction_amount_30d` | 600 -- 900 (amount is within 1.5x of baseline) |
| `merchant_risk_score` | 0.10 -- 0.30 (below >= 0.70 threshold) |
| `scenario_family` | `low_and_slow` |

**Signals expected to fire:** Potentially `model_prediction` depending on XGBoost feature
weights; no rule flag; no rich signal boosts; no behavioural boost (amount deviation < 3x);
no graph boost (unique entities per batch row).

**Primary evasion target:** `HIGH_AMOUNT_THRESHOLD` rule, night signal, country signal.

**Expected detection outcome:** Low detection probability. Model may score modestly on
`amount` + `is_high_amount` features. Risk score likely P3 or low P2 for individual rows.

---

### B. Victim Profile Mirroring

**Intent:**
Simulate a compromised account where the adversary executes transactions that closely mirror
the legitimate account holder's historical behaviour: amounts near the 30-day average, familiar
device, familiar geography, familiar channel. The behavioural boost does not fire because the
deviation ratios are small. The rich signal boost does not fire because thresholds are not met.

**Field engineering:**

| Field | Adversarial value |
|---|---|
| `amount` | 1.1 -- 2.4 times `avg_transaction_amount_30d` (below 3x anomaly threshold) |
| `avg_transaction_amount_30d` | 80 -- 400 (realistic baseline) |
| `device_trust_score` | 0.42 -- 0.70 (above < 0.40 cutoff) |
| `geo_distance_km` | 50 -- 480 (below > 500 threshold) |
| `txn_count_1h` | 2 -- 4 (below > 5 threshold) |
| `failed_attempts_1h` | 0 |
| `chargeback_count_90d` | 0 |
| `channel` | Same as customer's `usual_channel` baseline |
| `country` | Same as customer's `usual_country` baseline |
| `new_payee_flag` | false |
| `new_payee_flag` (occasional) | true (amount just below $500 to avoid is_new_payee_high_value) |
| `scenario_family` | `victim_mirror` |

**Signals expected to fire:** None or minimal. Model signal may or may not fire depending on
feature combination. Risk score likely P3 for amounts within baseline range.

**Primary evasion target:** `is_amount_anomaly` (3x threshold), `is_low_trust_device`
(< 0.40), `is_geo_anomaly` (> 500km), behavioural boost (requires ratio >= 3.0 for amount
deviation).

**Expected detection outcome:** High evasion. This pattern most directly mimics a skilled
account takeover that studies the victim's transaction profile before executing.

---

### C. Threshold Straddling

**Intent:**
Engineer a transaction that sits just below every defined rich signal threshold simultaneously.
No single threshold is crossed; no single boost fires. The pattern tests whether the XGBoost
model can detect fraud when all engineered feature values are in the "safe" zone by threshold
definition.

**Field engineering:**

| Field | Adversarial value | Threshold it evades |
|---|---|---|
| `device_trust_score` | 0.41 -- 0.44 | `is_low_trust_device`: fires at < 0.40 |
| `geo_distance_km` | 480 -- 498 | `is_geo_anomaly`: fires at > 500 |
| `txn_count_1h` | 4 -- 5 | `is_high_velocity_1h`: fires at > 5 |
| `failed_attempts_1h` | 2 -- 3 | `has_failed_attempts`: fires at >= 4 |
| `merchant_risk_score` | 0.55 -- 0.68 | `is_high_risk_merchant_score`: fires at >= 0.70 |
| `amount` | 850 -- 990 | High-amount rule: fires at > 1,000 |
| `avg_transaction_amount_30d` | 350 -- 400 | `is_amount_anomaly`: fires at amount > 3x avg |
| `chargeback_count_90d` | 1 | `has_chargebacks`: fires at >= 2 |
| `new_payee_flag` | false OR true with amount <= 490 | `is_new_payee_high_value`: fires when flag=true AND amount > 500 |
| `timestamp` hour | 07:00 -- 21:00 | Night signal: fires before 06:00 or after 22:00 |
| `country` | Low-risk | Country risk signal |
| `scenario_family` | `threshold_straddle` |

**Signals expected to fire:** None of the above thresholds. Model signal may or may not fire.
Risk score expected to be P3 or low P2 in most rows.

**Primary evasion target:** All rich signal boost triggers simultaneously.

**Expected detection outcome:** Strong evasion of rich signal and rule layers. This pattern
directly tests whether the XGBoost model can generalise beyond its feature thresholds to detect
compound sub-threshold signals.

---

### D. Graph Evasion -- Fan-In at Threshold

**Intent:**
Simulate a mule fan-in network where the number of distinct accounts sending to a shared
counterparty is engineered to sit exactly at the `counterparty_fan_in_flag` threshold (3
accounts, where the flag fires at > 3). This tests graph boost boundary sensitivity and
verifies that the flag correctly fires only when strictly exceeded.

**Field engineering:**

| Field | Adversarial value |
|---|---|
| Batch structure | Exactly 3 distinct `account_id` values per `merchant_id` (at threshold, not > threshold) |
| `merchant_id` | Shared across the 3 rows |
| `account_id` | 3 distinct values (acct_A, acct_B, acct_C) |
| `customer_id` | 3 distinct customers (cross-customer, so cross_account_device_reuse could also be tested) |
| `device_id` | Unique per account (avoids shared_device_flag) |
| `amount` | 200 -- 800 (sub-threshold amounts) |
| `scenario_family` | `graph_evasion_fan_in` |

**Signals expected to fire:** `counterparty_fan_in_flag` = False (exactly 3, not > 3).
`shared_device_flag` = False (unique devices). `cross_account_device_reuse` = False (unique
devices). Graph boost = 0.0.

**Notes:**
This scenario is a **boundary confirmation**, not purely an evasion scenario. It verifies that
the graph boost correctly withholds at the exact threshold boundary, which is important for
analyst confidence in the system's precision. A companion variant with 4 accounts per
counterparty (> threshold) confirms the flag fires correctly above the boundary.

**Primary evasion target:** `counterparty_fan_in_flag` threshold enforcement.

**Expected detection outcome:** No graph boost at exactly 3 accounts. Correct flag fire at 4
accounts. Documents the effective detection boundary precisely.

---

## Deferred Scenario Families

The following patterns are acknowledged but deferred to later Phase 16 sub-slices or Phase 18.

| Scenario | Reason for deferral |
|---|---|
| **Category hopping** | Requires multi-transaction coordination across scan rows and merchant category diversity that is hard to verify cleanly in a first implementation |
| **Device rotation** | Cycling legitimate device IDs to keep `accounts_per_device` below `shared_device_flag` threshold requires careful batch-level engineering; verify complexity is high |
| **Cross-border laundering chain** | Requires `mule_chain_depth` detection that was deferred in Phase 15 graph design; SQL recursive CTE approach not yet implemented |
| **Dormant activation mimic** | Amount must remain below 3x `avg_transaction_amount_30d`; behavioural signal fires on absolute deviation, not just ratio; threshold sensitivity analysis needed |
| **New-payee warm-up** | Simulates initial small transactions to establish counterparty history before a high-value transfer; requires temporal ordering across rows within a single scan batch to work correctly |
| **Tiny card testing** | Amounts $0.50 -- $2.00 test a different scoring regime (amounts so low the model and rules rarely fire for any reason); more useful as a Phase 18 AI Investigation Brief scenario |
| **Multi-scan entity persistence** | Current scoring stack is single-scan-window scoped; detecting patterns that span multiple upload sessions requires persistent entity graph infrastructure not yet implemented |

---

## Detection Evidence Matrix

Phase 16C must produce a detection evidence matrix for each adversarial scenario family.
The matrix is the primary deliverable of Phase 16 -- it documents the system's honest
detection boundary.

### Evidence Fields (per scenario family)

| Field | Description |
|---|---|
| `scenario_family` | Adversarial scenario identifier |
| `rows` | Number of rows generated for this scenario |
| `avg_risk_score` | Mean risk score across all scenario rows |
| `min_risk_score` | Minimum risk score in the scenario |
| `max_risk_score` | Maximum risk score in the scenario |
| `tier_distribution` | P0 / P1 / P2 / P3 row counts |
| `decision_distribution` | BLOCK / REVIEW / APPROVE row counts |
| `reason_codes_fired` | Set of distinct reason codes emitted across scenario rows |
| `rich_signal_count` | Number of rows with at least one rich signal code |
| `behavioural_signal_count` | Number of rows with at least one behavioural signal code |
| `graph_signal_count` | Number of rows with at least one graph signal code |
| `intended_evasion_target` | Which detection layer(s) the scenario was designed to evade |
| `detection_verdict` | Detected / Partially detected / Missed |
| `notes` | Observations about which signals did or did not fire, and why |

### Detection Verdict Definition

| Verdict | Condition |
|---|---|
| **Detected** | >= 80% of rows score P1 or above (risk_score >= 0.60) |
| **Partially detected** | 20% -- 79% of rows score P1 or above |
| **Missed** | < 20% of rows score P1 or above |

These thresholds are conservative and specific to the adversarial context. They use P1 (not P0)
as the detection bar because the purpose of adversarial simulation is to test whether the system
raises any meaningful alert, not whether it produces a maximum-confidence block decision.

---

## Success Criteria

Phase 16 is considered successful when all of the following conditions are met:

1. **Adversarial scenarios are generated reproducibly.** The adversarial generator produces
   identical output for the same seed. Generated CSVs are gitignored and not committed.

2. **Structural verifier confirms schema and evasion constraints.** `verify_adversarial_csv.py`
   passes and confirms that field values for each scenario family fall within the intended
   evasion range (e.g., amounts are genuinely sub-threshold, device trust is genuinely above
   the low-trust cutoff).

3. **Detection evidence matrix is populated.** `verify_adversarial_detection.py` produces a
   filled detection matrix for all four first-slice scenario families, with honest verdicts.

4. **Small live scan evidence is captured.** A 1,000-row adversarial CSV is uploaded and
   scanned; the scan_id and tier distribution are recorded.

5. **Gaps are documented.** Patterns classified as Missed or Partially detected are documented
   with a clear explanation of which signals were evaded and why.

6. **No scoring change is made without separate approval.** If Phase 16 reveals a detection
   gap that merits a scoring fix, the fix must be proposed as a separately scoped slice with
   explicit owner review before implementation.

---

## Phase 16 Proposed Sub-Slices

| Slice | Description | Primary outputs |
|---|---|---|
| **16A** | Adversarial design contract | `docs/ADVERSARIAL_FRAUD_DESIGN.md` (this document) |
| **16B** | Adversarial generator and structural verifier | `scripts/generate_adversarial_csv.py`, `scripts/verify_adversarial_csv.py` |
| **16C** | In-memory detection evidence | `scripts/verify_adversarial_detection.py`, printed detection matrix |
| **16D** | 1k adversarial scan and evidence lock | Scan_id, tier distribution, evidence lock in documentation |
| **16E** | Phase 16 close-out | `docs/PRODUCT_STAGES.md` Phase 16 completion note |

Owner approval is required before each slice begins, consistent with the established roadmap
convention.

---

## Validation Strategy

| Slice | Validation required |
|---|---|
| 16A | Owner review of this design document; `docs/PRODUCT_STAGES.md` update only; no code |
| 16B | `python -m py_compile scripts/generate_adversarial_csv.py`; `python scripts/verify_adversarial_csv.py <path>` PASS on a seed run; generated CSV gitignored |
| 16C | `python scripts/verify_adversarial_detection.py` PASS with printed detection matrix; all four scenario families covered |
| 16D | 1k adversarial CSV upload to live API; scan_id captured; tier distribution recorded; legacy 10k regression only if any backend source file changed |
| 16E | All prior verification PASS; detection evidence matrix final; `docs/PRODUCT_STAGES.md` updated; Phase 16 marked complete |

**Legacy 10k regression rule:** Required only if any file in `src/` is modified during a
Phase 16 slice. The adversarial generator and verifier do not modify backend source files, so
regression is not expected to be required for 16B through 16D.

**Large scan rule:** No scan above 10,000 rows in any Phase 16 slice. Adversarial evidence
value is in scenario precision and detection boundary documentation, not throughput.

---

## Guardrails

- **No production accuracy claims.** Detection rates on synthetic adversarial datasets are
  not evidence of production fraud model performance. All Phase 16 evidence must be clearly
  labelled as synthetic validation.

- **No scoring changes inside design or generation slices.** If a detection gap is found,
  document it. Do not fix it within Phase 16 unless a dedicated scoring sub-slice is approved
  by the owner.

- **No frontend changes.** Adversarial reason codes and scenario labels are not surfaced in
  any new drawer section in Phase 16. The existing four chip groups handle any reason codes
  that do fire. Phase 17 (Case Dossier 2.0) is the correct phase for investigative workspace
  upgrades.

- **No GitHub push.** GitHub push remains intentionally deferred to Phase 20 or an explicit
  owner-approved release checkpoint.

- **Generated CSVs remain gitignored.** Adversarial generator output must not be committed to
  version control. The `.gitignore` exception pattern for scripts (`!scripts/verify_adversarial_csv.py`,
  `!scripts/verify_adversarial_detection.py`) must be added when those scripts are created.

- **Detection gaps must be documented, not hidden.** A Phase 16 scenario that the current
  stack Misses is a valid, valuable finding. It must appear in the detection evidence matrix
  with a clear verdict and explanation. It is not a failure of Phase 16; it is the point.

- **Existing generator and verifier are not modified.** `scripts/generate_rich_banking_csv.py`
  and `scripts/verify_rich_banking_csv.py` remain untouched throughout all Phase 16 slices.

- **Benchmark reference numbers are not changed.** The legacy 10k reference distribution
  (P0:1546 / P1:913 / P2:0 / P3:7541) and all documented scan_ids remain unchanged.

---

## Operational Boundaries

Phase 16 adversarial simulation extends the product's self-evaluation capability. It is not
a production calibration exercise. The following boundaries apply throughout:

- All adversarial patterns are synthetically generated using controlled random seeds.
- No adversarial dataset represents real customer behaviour, real fraud, or real institution data.
- The detection evidence matrix documents current capability boundaries under controlled
  synthetic stress conditions. It is not predictive of detection rates in a real deployed environment.
- Scoring weights, thresholds, and model parameters remain as locked at the end of Phase 15.
  Any future calibration requires institution-specific labelled outcomes, segment-level analysis,
  and governance review before deployment.

---
