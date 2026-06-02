# Graph Intelligence Design Contract -- Phase 15

---

## Purpose

Phase 15 adds relationship-level fraud intelligence to the Fraud Intelligence Console. Where
Phase 13 introduced entity-aware behavioural context -- detecting anomalies in one customer's
or account's own history -- Phase 15 detects patterns that span multiple entities: shared
devices across unrelated accounts, counterparties receiving funds from many sources, accounts
linked through common payment instruments, and coordinated mule-network movement patterns.

These relationship signals are invisible at the single-row level and only emerge when
transactions are evaluated in the context of an entity neighborhood. They represent the third
detection layer in the intelligence stack.

This document defines the graph intelligence contract before implementation. It does not
change scoring weights, reason-code behaviour, frontend rendering, database schema, or scan
execution. It serves the same role as BEHAVIOURAL_INTELLIGENCE_DESIGN.md did for Phase 13.

---

## Intelligence-Layer Stack

The Fraud Intelligence Console operates at three detection levels:

```
Layer 1 -- Transaction-Level Detection
  Model: XGBoost on 9 features (amount, time, payment method, country, ...)
  Rules: deterministic high-risk pattern conditions
  Rich signals: Phase 12F scenario and velocity signals
  Formula: base_score = 0.6 * model_prediction + 0.4 * rule_flag + rich_signal_boost
  Scope: single transaction row, no cross-row context

Layer 2 -- Entity-Level Detection (Phase 13)
  Behavioural: velocity deviation, amount deviation, device familiarity, ...
  Formula: base_score + behavioural_boost (cap 0.20)
  Scope: one entity's longitudinal history across time

Layer 3 -- Relationship-Level Detection (Phase 15)
  Graph: shared device clusters, mule fan-in/fan-out, counterparty linkage, ...
  Formula: base_score + behavioural_boost + graph_boost (proposed cap 0.15-0.20)
  Scope: relationships across entities within a portfolio scan window
```

Each layer is additive and evidence-gated. A transaction without graph context receives a
graph boost of 0.0 and scores identically to a Phase 13 transaction. Legacy scans, rich scans,
and no-history scans must continue to produce unchanged results.

---

## Graph Entities (Nodes)

| Node type | Entity identifier | Source field(s) |
|---|---|---|
| Customer | Stable customer entity | `customer_id` |
| Account | Account from which funds are drawn | `account_id` |
| Device | Access device or terminal | `device_id` |
| Merchant | Receiving merchant or payee | `merchant_id` |
| Counterparty / Payee | External recipient of funds | `merchant_id` or `counterparty_id` |
| Payment instrument | Card or wallet identifier | `payment_method` + `device_id` combination |
| Geography cluster | IP country / billing country / merchant country | `ip_country`, `billing_country`, `merchant_country` |
| Transaction (event node) | Optional anchor for temporal graph traversal | `transaction_id` with `timestamp` |

Nodes exist only when the corresponding identifier is present in the uploaded CSV. Missing or
empty entity identifiers produce no graph nodes and no graph signals for that row.

---

## Graph Edges

| Edge | Meaning | Source fields |
|---|---|---|
| `customer -- account` | A customer owns or operates an account | `customer_id`, `account_id` |
| `customer -- device` | A customer has used a device | `customer_id`, `device_id` |
| `account -- counterparty` | An account has sent funds to a counterparty | `account_id`, `merchant_id` |
| `account -- account` | Two accounts share a device or counterparty | `account_id` via shared `device_id` |
| `device -- account` | A device has been used on an account | `device_id`, `account_id` |
| `transaction -- merchant` | A transaction targeted a merchant | `transaction_id`, `merchant_id` |
| `transaction -- device` | A transaction used a device | `transaction_id`, `device_id` |
| `account -- geo_cluster` | An account transacts from a geography | `account_id`, `ip_country` or `billing_country` |
| `customer -- payment_method` | A customer uses a payment type | `customer_id`, `payment_method` |

Edge weight can reflect frequency (number of shared transactions) or recency. For the first
implementation slice, edge existence (binary) is sufficient. Weighted edges can be added in
a later slice.

---

## Network Indicators

The following graph indicators are defined for design purposes. Thresholds and implementation
order are to be determined during the implementation slice.

| Indicator | Meaning | Likely source query |
|---|---|---|
| `shared_device_count` | Number of distinct accounts that have used the same device | GROUP BY device_id, COUNT(DISTINCT account_id) |
| `accounts_per_device` | Same as above, from the device's perspective | Inverse of device-account edge |
| `counterparties_per_account` | Number of distinct counterparties an account has paid | GROUP BY account_id, COUNT(DISTINCT merchant_id) |
| `accounts_per_counterparty` | Number of distinct accounts that have paid the same counterparty | GROUP BY merchant_id, COUNT(DISTINCT account_id) -- fan-in |
| `merchant_cluster_risk` | Average or maximum merchant_risk_score among merchants linked to the same device or account cluster | Aggregate over linked merchant_id values |
| `counterparty_fan_in` | A counterparty is receiving from many distinct unrelated accounts | High accounts_per_counterparty relative to a threshold |
| `counterparty_fan_out` | A source account is distributing to many distinct counterparties | High counterparties_per_account relative to a threshold |
| `device_cluster_size` | Number of entities (customers + accounts) in the device's neighborhood | Neighborhood count from device-centric adjacency |
| `cross_account_device_reuse` | A device is shared across accounts that belong to different customers | Accounts with same device_id but different customer_id |
| `mule_chain_depth` | Length of the longest account-to-account transfer chain observable in the scan | Graph path length; approximate in SQL via recursive CTE |
| `rapid_fund_flow_pattern` | Multiple account-to-account transfers within a short time window | Temporal filter on shared counterparty edges |
| `neighborhood_risk_score` | Aggregate risk signal from the entity neighborhood (linked accounts, devices, counterparties) | Weighted sum of neighbor risk scores |
| `linked_high_risk_entity_count` | Number of directly linked entities that individually carry a high risk score | Join on neighbor entity risk score |

Not all indicators need to be implemented in the first slice. The recommended starting set is:
`shared_device_count`, `accounts_per_device`, `accounts_per_counterparty`, `counterparty_fan_in`,
and `cross_account_device_reuse`. These cover the most common mule and account-takeover patterns
and can be computed with simple grouped aggregations on existing CSV fields.

---

## Mule-Network Scenarios

The following controlled network scenarios define the expected signal families for Phase 15
validation. Each scenario maps to one or more graph indicators.

| Scenario | Description | Indicators triggered |
|---|---|---|
| **Device cluster** | Multiple unrelated accounts transact from a single device identifier | `shared_device_count`, `accounts_per_device`, `cross_account_device_reuse` |
| **Fan-in counterparty** | One counterparty receives funds from many unrelated accounts in a short window | `counterparty_fan_in`, `accounts_per_counterparty` |
| **Fan-out distribution** | One account distributes funds rapidly to many distinct counterparties | `counterparty_fan_out`, `counterparties_per_account`, `rapid_fund_flow_pattern` |
| **Mule chain** | Funds move through a chain of accounts (A -> B -> C -> ...) via sequential transfers | `mule_chain_depth`, `rapid_fund_flow_pattern` |
| **Merchant cluster** | Multiple accounts route transactions through a concentrated set of high-risk merchants | `merchant_cluster_risk`, `neighborhood_risk_score` |
| **Shared payment instrument** | Multiple accounts use the same device + payment method combination | `shared_device_count`, `cross_account_device_reuse` |
| **Device / country mismatch cluster** | A device is used across accounts in multiple countries inconsistent with the device's origin | `device_cluster_size`, `cross_account_device_reuse`, `neighborhood_risk_score` |
| **Dormant-account activation cluster** | Multiple dormant accounts activate simultaneously, linked by shared device or counterparty | `shared_device_count`, `linked_high_risk_entity_count` |

Synthetic controlled scenarios for verification must be generated with fixed seeds and bounded
row counts. They must not be committed as large generated files.

---

## Neutral / No-Graph-Context Behaviour

The following invariants must hold throughout Phase 15 implementation:

- If no graph entity fields (`device_id`, `account_id`, `customer_id`, `merchant_id`) are
  present in the uploaded CSV, the graph boost is 0.0 for all rows.
- Missing or empty entity identifiers must not cause crashes, silent errors, or incorrect
  indicator values.
- No synthetic graph relationship may be inferred from absent fields. A null `device_id` is
  not an implied shared device.
- The graph boost of 0.0 must produce scoring results identical to current Phase 14 scoring
  for the same row.
- Legacy benchmark CSVs (9-field format) and rich scenario CSVs without graph entity fields
  must not receive any graph boost.
- Rows with partial entity fields (e.g., `device_id` present but `account_id` absent) may
  receive graph signals for the fields that are present, but only when the available adjacency
  evidence meets the minimum threshold for that indicator.

---

## Proposed Graph Reason-Code Taxonomy

The following reason codes are proposed for Phase 15. They are not yet implemented. Codes
must be additive to the existing reason-code vocabulary and must not replace or rename any
locked legacy, rich-signal, or behavioural codes.

| Proposed code | Meaning |
|---|---|
| `SHARED_DEVICE_CLUSTER` | Transaction device is shared across multiple distinct accounts, indicating potential credential reuse or coordinated activity. |
| `HIGH_RISK_COUNTERPARTY_CLUSTER` | The receiving counterparty is linked to a high-concentration of risk signals across its transaction neighborhood. |
| `MULE_FAN_IN_PATTERN` | A counterparty is receiving funds from an unusually high number of distinct source accounts. |
| `MULE_FAN_OUT_PATTERN` | A source account is distributing funds to an unusually high number of distinct counterparties in a short window. |
| `LINKED_HIGH_RISK_ENTITY` | The transaction is directly linked to one or more entities carrying independently elevated risk scores. |
| `DEVICE_ACCOUNT_REUSE` | The transaction device is associated with accounts belonging to different customers, indicating cross-account device sharing. |
| `RAPID_FUNDS_CHAIN` | Multiple sequential account-to-account transfers are observed in a compressed time window, consistent with layering activity. |
| `MERCHANT_CLUSTER_RISK` | The receiving merchant belongs to a cluster of merchants with elevated aggregate risk scores linked through shared device or account neighborhoods. |
| `GRAPH_NEIGHBORHOOD_RISK` | The transaction entity neighborhood carries an elevated aggregate risk signal, even if the individual transaction row does not independently trigger other signals. |
| `CROSS_ACCOUNT_LINKAGE` | Two or more accounts in the scan are linked through a common device, counterparty, or payment instrument, suggesting coordinated account activity. |

Reason codes are emitted only when the corresponding indicator meets its defined threshold.
Rows with no graph context must not receive any graph reason code.

---

## Proposed Scoring Contract

This scoring contract is proposed, not yet implemented. Weights and caps are subject to review
and calibration before any implementation commit.

### Formula (Conceptual)

```
base_score           = 0.6 * model_prediction + 0.4 * rule_flag
rich_signal_boost    = sum of Phase 12F rich signal boosts (existing, unchanged)
behavioural_boost    = sum of Phase 13 behavioural signal boosts, cap 0.20 (existing, unchanged)
graph_boost          = sum of Phase 15 graph signal boosts, proposed cap 0.15-0.20

risk_score = min(base_score + rich_signal_boost + behavioural_boost + graph_boost, 1.0)
```

### Graph Boost Design Principles

- **Additive.** The graph boost adds to the existing score without replacing model, rule, rich,
  or behavioural contributions.
- **Evidence-gated.** A graph boost component fires only when the corresponding indicator
  exceeds its defined threshold. No indicator = no contribution.
- **Capped.** The total graph boost is bounded. Proposed cap: 0.15. Final value to be
  determined during implementation and verified against controlled scenarios.
- **Neutral when no context.** Rows without graph entity fields or with insufficient adjacency
  evidence receive a graph boost of exactly 0.0.
- **Score-capped.** The final `risk_score` remains bounded at 1.0 regardless of graph boost
  magnitude.
- **Threshold-reviewed.** Per-indicator thresholds (e.g., minimum accounts per device to
  trigger `SHARED_DEVICE_CLUSTER`) must be defined and reviewed before implementation.

### Existing Boundaries Unchanged

- Model weight (0.6) and rule weight (0.4): unchanged.
- Rich signal boost weights: unchanged.
- Behavioural boost weights and 0.20 cap: unchanged.
- APPROVE / REVIEW / BLOCK thresholds: unchanged unless separately reviewed and approved.
- P0 / P1 / P2 / P3 priority tier thresholds: unchanged.

---

## Storage and Implementation Approach

Four approaches are evaluated for computing graph indicators.

| Option | Approach | Suitability for this stage |
|---|---|---|
| **A. In-memory validation** | Load uploaded CSV into a Pandas DataFrame; compute shared-entity counts using groupby/agg; no broker or database required | Suitable for controlled scenario verification and unit-level testing. Not suitable for production-scale scans without chunking. |
| **B. PostgreSQL adjacency queries** | Query existing `portfolio_scan_results` rows within a scan_id using GROUP BY and HAVING; compute shared-entity counts at the DB layer | Recommended for the first implementation slice. No new tables or schema changes required. Works at the scan scope with the data already in Postgres after a scan completes. |
| **C. NetworkX in-memory analytics** | Build a full graph object from scan results using the NetworkX library; enables path-length and community-detection algorithms | Suitable for small to medium scans; adds a new dependency. Recommended only if path-length metrics (e.g., mule_chain_depth) are required and SQL recursive CTEs are insufficient. Not recommended for the first slice. |
| **D. Dedicated graph database** | Introduce Neo4j, Amazon Neptune, or equivalent; persist entity relationships outside Postgres | Adds significant operational complexity and a new persistent service. Not recommended for this product stage. Should only be considered after the adjacency-query approach proves insufficient at scale. |

**Recommendation:** Begin with Option B (PostgreSQL adjacency queries) within the existing
scan result table scope. This adds no new dependencies, no schema migrations, and aligns with
the existing chunked scan architecture. Option A (in-memory validation) is used for unit-level
verification scripts.

Option C (NetworkX) may be evaluated during implementation if mule chain depth or graph
community detection requires path traversal that SQL cannot express efficiently. This decision
belongs to the Phase 15B implementation slice, not this design contract.

---

## Validation Plan

The following validation cases must be verified before any Phase 15 implementation commit.

| Case | Expected result |
|---|---|
| No graph context (legacy 9-field CSV) | graph_boost = 0.0; scoring identical to Phase 14 output |
| No graph entity fields present | graph_boost = 0.0; no graph reason codes emitted |
| Shared device cluster (controlled scenario) | `SHARED_DEVICE_CLUSTER` emitted; graph_boost > 0.0 |
| Fan-in counterparty (controlled scenario) | `MULE_FAN_IN_PATTERN` emitted; graph_boost > 0.0 |
| Fan-out distribution (controlled scenario) | `MULE_FAN_OUT_PATTERN` emitted; graph_boost > 0.0 |
| Linked high-risk entity (controlled scenario) | `LINKED_HIGH_RISK_ENTITY` emitted; graph_boost > 0.0 |
| Graph boost cap enforced | graph_boost never exceeds proposed cap regardless of indicator count |
| Score cap enforced | risk_score never exceeds 1.0 |
| Legacy 10k regression | P0:1546 / P1:913 / P2:0 / P3:7541 -- exact match to Phase 13G reference |
| Rich 10k scan | Rich reason codes, scenario labels, and drawer grouping unchanged |
| Behavioural regression | verify_behavioural_features.py and verify_behavioural_fraud_quality.py both PASS |
| Stream resilience | verify_stream_resilience.py PASS |
| Dirty-data resilience | verify_dirty_data_handling.py PASS |
| Frontend build | All 8 routes compile cleanly; no TypeScript errors |
| No DB migration | graph signals are derived from existing scan result data; no new schema required for first slice |
| No frontend display until reason codes verified | ScanResultDrawer graph section added only after graph reason codes are confirmed in verified scan output |

---

## Operational Boundaries

Phase 15 graph intelligence extends the system's relationship-level risk evidence layer.
It provides controlled graph-intelligence validation against defined network scenarios and
serves as the foundation for mule network detection in the analyst workflow.

Graph signals are computed from entity relationships observed within uploaded portfolio scan
data. The indicators quantify structural adjacency patterns -- shared device clusters, fund
flow concentration, counterparty fan-in -- that correspond to known coordinated fraud
indicators.

The deployment hardening path for graph intelligence includes:

- **Institution-specific graph calibration using labelled outcomes.** Graph indicator thresholds
  are proposed values derived from controlled synthetic scenarios. Deployment-ready calibration
  requires labelled transaction data, outcome-linked fraud labels, and a review process specific
  to the institution's portfolio.

- **Temporal graph persistence.** The current design computes graph signals within a single
  scan window. A persistent entity graph that accumulates adjacency evidence across multiple
  scans and time windows would provide stronger long-term mule network detection.

- **Network intelligence extension layer.** The graph layer is designed as an additive extension
  to the existing scoring pipeline. It does not replace the model, rule, rich, or behavioural
  layers. Each layer contributes independently and the combination is evaluated at decision time.

- **Regulatory and governance alignment.** Relationship-level risk evidence that links
  customers, accounts, and devices involves considerations around data use, consent, regulatory
  risk classification, and explainability. Institution deployment of graph intelligence requires
  governance review covering these dimensions.

---

## Phase 15 Implementation Sequence (Recommended)

The following implementation slices are recommended. None are official sub-phases and none are
marked as started or complete. Each slice requires owner approval before implementation begins.

| Slice | Description | Scope |
|---|---|---|
| 15A | **Design contract** (this document) | Docs only |
| 15B | **In-memory graph feature validation** | New `scripts/verify_graph_signals.py`; no source changes |
| 15C | **Graph feature extraction** | `src/features/transaction_features.py`; adjacency helpers |
| 15D | **Graph boost and scoring integration** | `src/triage/investigator.py`; capped additive boost |
| 15E | **Graph reason-code validation lock** | Verify codes against controlled scenarios; lock taxonomy |
| 15F | **Graph UI and drawer display** | `ScanResultDrawer.tsx`; graph signal chip section |
| 15G | **Graph regression close-out** | Legacy 10k regression; full verification matrix; E2E |

Slices 15B and 15C are the natural first implementation candidates after this design contract
is approved. 15B (in-memory validation) can proceed without any source code changes and
provides a clear signal that the graph indicator logic is sound before 15C integrates it.

---

## Compatibility with Existing Layers

| Layer | Impact from graph additions |
|---|---|
| Legacy 9-field CSVs | No impact. No entity fields present; graph_boost = 0.0 always. |
| Rich synthetic banking CSVs (Phase 12F) | Partial impact. `customer_id`, `account_id`, `merchant_id` fields present; graph signals enabled when thresholds met. |
| Behavioural layer (Phase 13) | No impact. Behavioural boost is independent of graph boost. Both are additive. |
| Risk scan processor (Phase 12D) | Reviewed but not modified. Graph indicators operate on data already written to `portfolio_scan_results`; no change to the scan ingestion path. |
| CSV validator (Phase 14) | No impact. Graph entity fields (`account_id`, `customer_id`, `merchant_id`) are optional columns handled by `extra="ignore"` in the current validator. |
| Frozen frontend routes | No impact until 15F. |
