# Real-Time Transaction Fraud Intelligence Console

A fraud decision intelligence console that transforms raw transactions into prioritised,
explainable, analyst-ready investigations using hybrid ML/rule scoring, behavioural and
graph intelligence, portfolio-scale risk scanning, lifecycle audit trails, and hardened
AI-assisted investigation briefs.

The system operates in a controlled benchmark environment built on a production-style
event-driven architecture. Validation evidence includes a verified 10M-transaction
Portfolio Risk Scan benchmark, adversarial simulation across five fraud pattern families,
11/11 E2E Playwright checks, and a formal governance documentation package.

---

## 1. Executive Summary

The Transaction Fraud Intelligence Console is a decision intelligence platform covering the complete
case lifecycle -- from multi-layer transaction scoring through analyst triage,
AI-assisted investigation, workflow automation, audit trail generation, and
portfolio-scale bulk risk scanning.

The platform runs on a production-style Docker Compose stack with a representative
service topology: FastAPI backend, PostgreSQL persistence, Redpanda event stream, Redis
cache, scoring consumer, investigation consumer, n8n workflow automation, and a Next.js
analyst interface. Twenty-seven API endpoints cover the full operational surface from
transaction intake to governance-ready health monitoring.

The scoring engine implements four independently-computed intelligence layers -- hybrid
ML/rule base, enriched transaction risk signals, behavioural deviation profiling, and
graph mule-network detection -- combined into a single bounded risk score with
analyst-visible reason codes. Each intelligence layer can independently drive a case
to REVIEW or BLOCK tier.

The Portfolio Risk Scan module extends the platform to bulk transaction intelligence:
an async scan engine that processed, persisted, and exported a 10,000,000-row synthetic
transaction dataset through a hardened server-side streaming CSV cursor with zero API
restarts and zero OOM kills.

The engineering story behind the 10M benchmark is not just about throughput. It is a
documented hardening journey: five scale ramps from 500k to 10M, each exposing a
different class of bottleneck, each resolved with a targeted architectural intervention,
each verified before the next scale step was attempted.

---

## 2. Problem Statement

Fraud teams operate under conditions that a raw model output alone cannot address.

A scored transaction produces a probability estimate. The operational work begins where
the model stops: the case must be triaged against the full queue, risk evidence must be
assembled, an investigation context must be formed, a decision must be recorded with
traceability, and the downstream workflow triggered by that decision must be verified
to have executed correctly.

When these steps are handled by separate, unconnected tools, traceability degrades.
Analysts work without a shared audit record. Workflow failures are invisible until
complaints arrive downstream. Reliability problems in the automation layer accumulate
silently.

Static scoring engines miss coordinated fraud patterns. Behavioural deviation from
entity norms, mule-network topology across shared devices and identities, and
adversarial structuring attacks require intelligence layers that profile relationships
and history -- not just individual transaction features.

Portfolio-scale risk scanning introduces a third problem: bulk transaction files cannot
be scored synchronously without exhausting API memory and blocking normal case
operations. Export of large result sets fails if the export path reads the full result
into memory. Deep pagination degrades if queries lack index support at multi-million-row
scale.

These are the operational problems this platform addresses.

---

## 3. Product Vision

A Transaction Fraud Intelligence Console that covers the complete case lifecycle with an audit
record at every step, combines multi-layer ML/rule scoring with behavioural profiling
and graph mule-network intelligence, surfaces hardened AI investigation briefs in
context where they add value, dispatches workflow automation and proves it executed,
monitors its own reliability, and handles portfolio-scale bulk risk scanning through an
async engine hardened for large file ingestion, bounded-memory processing, indexed
pagination, and server-side streaming export.

---

## 4. System Architecture

### Service topology

| Service | Role |
|---|---|
| FastAPI (Python) | REST API -- 27 endpoints covering scoring, case management, investigation, workflow, metrics, risk scan, model attribution, and health monitoring |
| PostgreSQL 16 | Persistence -- cases, predictions, investigations, workflow events, portfolio scans, scan results |
| Redpanda (Kafka-compatible) | Event stream -- transaction events, scored case events, 4 topics |
| Redis | Cache |
| Scoring consumer | Kafka consumer -- 4-layer scoring (base + rich + behavioural + graph), creates case records |
| Investigation consumer | Kafka consumer -- AI investigation reports per case via Ollama local inference |
| n8n | Workflow automation -- fraud case escalation workflow, HTTP callback to FastAPI audit endpoint |
| Next.js 16 | Analyst interface -- 8 routes, TypeScript, TanStack Query, Recharts |

### Data flow (real-time path)

```
Transaction submitted (POST /predict or async Kafka event)
  -> Scoring consumer: 4-layer scoring (base + rich + behavioural + graph)
  -> Risk score + decision (APPROVE / REVIEW / BLOCK) + reason codes persisted
  -> REVIEW and BLOCK cases published to case event topic
  -> Investigation consumer: Ollama generates evidence-grouped investigation report
  -> n8n workflow dispatch triggered via POST /workflow/notify-case/{case_id}
  -> n8n callback writes audit event via POST /workflow/audit-event
  -> Workflow event persisted with case_id, status, source, action
```

### Data flow (Portfolio Risk Scan path)

```
CSV upload (POST /risk-scan)
  -> HTTP 202 response with scan_id
  -> Background task: chunked processing (2,000-row chunks)
  -> Each chunk: validate -> score -> persist to portfolio_scan_results
  -> Running summary counters updated per chunk
  -> GET /risk-scan/{scan_id}/status: real-time progress polling
  -> GET /risk-scan/{scan_id}/results: indexed paginated results
  -> GET /risk-scan/{scan_id}/export: server-side cursor streaming CSV
```

### Scoring architecture

**Base hybrid formula:**

```
base_score = (0.6 x model_output) + (0.4 x rule_flag)
```

**4-layer extended formula:**

```
risk_score = clip(
    base_score
  + rich_boost
  + behavioural_boost
  + graph_boost,
  upper=1.0
)
```

Model: XGBoost classifier, 9-feature vector, synthetic training data.
Rule: deterministic evaluation of 3 high-risk pattern conditions.
Each layer contributes independently; final clipping preserves bounded score semantics.
Each layer maps directly to analyst-visible reason codes in the Case Dossier.

---

## 5. Intelligence Architecture

The fraud scoring engine combines four independently-computed intelligence layers.
Each layer produces a non-negative boost, with the final score clipped at 1.0 to
preserve bounded semantics. A transaction can reach REVIEW or BLOCK tier from any
single layer alone, without other layers firing.

### Behavioural Intelligence (Phase 13)

The behavioural layer profiles entity-level transaction norms and detects deviations
invisible to static rules.

| Signal | Description |
|---|---|
| `BEHAVIOURAL_AMOUNT_DEVIATION` | Transaction significantly exceeds the entity's historical spend baseline |
| `BEHAVIOURAL_VELOCITY_DEVIATION` | Transaction rate exceeds expected frequency norms for the entity |
| `BEHAVIOURAL_PROFILE_SHIFT` | Combined deviation signals a coordinated change in entity behaviour |

Behavioural signals surface as amber chips in the Case Dossier. A transaction that is
individually unremarkable may still be high-risk if it deviates sharply from the
entity's established pattern. Architecture: [docs/BEHAVIOURAL_INTELLIGENCE_DESIGN.md](docs/BEHAVIOURAL_INTELLIGENCE_DESIGN.md).

### Dirty Data and Stream Resilience (Phase 14)

The ingestion and scoring pipeline was validated against realistic input degradation:

- Schema-invalid records handled as poison pills: offset committed, message skipped, error logged
- Null and missing field coverage: all feature extraction paths apply safe defaults without raising
- Consumer restart recovery: message redelivery after unexpected failure handled correctly per consumer type
- Stream resilience verified under controlled dirty-data injection scenarios

Architecture: [docs/DIRTY_DATA_RESILIENCE.md](docs/DIRTY_DATA_RESILIENCE.md).

### Graph / Mule-Network Intelligence (Phase 15)

The graph layer detects coordinated fraud patterns through shared-entity topology.

| Signal | Description |
|---|---|
| `MULE_FAN_IN_PATTERN` | Transactions converging on a common receiving entity -- mule account pattern |
| `MULE_FAN_OUT_PATTERN` | Transactions dispersing from a single originating entity -- distribution pattern |
| Shared device indicator | Multiple user accounts sharing a common device identifier |
| Shared identity indicator | Connected identity clusters across the transaction network |

Nine graph indicators are computed per transaction. `graph_boost` contributes to the
4-layer risk score independently of model and behavioural signals. Graph signals surface
as violet chips in the Case Dossier. Architecture: [docs/GRAPH_INTELLIGENCE_DESIGN.md](docs/GRAPH_INTELLIGENCE_DESIGN.md).

### Adversarial Synthetic Fraud Simulation (Phase 16)

Five coordinated fraud pattern families were simulated to validate detection coverage
across the full intelligence stack.

| Family | Description |
|---|---|
| Velocity manipulation | High transaction frequency designed to evade velocity thresholds |
| Amount structuring | Transaction sizes calibrated below detection thresholds |
| Geographic dispersion | Multi-region coordinated transaction sets |
| Device rotation | Coordinated device-ID switching across a fraud ring |
| Mule-network coordination | Fan-in and fan-out patterns through synthetic mule accounts |

Detection evidence matrices confirm the 4-layer scoring engine identifies adversarial
patterns that evade the base hybrid model alone. Corrected cluster ID isolation ensures
adversarial patterns do not contaminate training-distribution validation.

---

## 6. Core Workflow

### Transaction-to-verdict lifecycle

1. Transaction submitted via Transaction Intake Console or async Kafka event
2. Scoring consumer evaluates 4 intelligence layers: base ML/rule, rich signals, behavioural profiling, graph topology
3. Risk score, decision tier, and reason codes persisted to PostgreSQL
4. REVIEW and BLOCK cases surface in the Review Queue, sorted by descending risk score
5. Analyst opens Case Dossier 2.0: grouped evidence display, lifecycle timeline, AI investigation brief, verdict capture
6. Analyst submits verdict (Confirmed Fraud, False Positive, Approved) with optional notes
7. Workflow automation dispatched from Case Dossier
8. n8n processes case, writes callback audit event to FastAPI
9. Automation Audit Trail records all dispatch events with status and case linkage
10. Reliability Metrics surface aggregate automation health with SLO-style monitoring

### Priority tier assignment

| Tier | Criteria |
|---|---|
| P0 Critical | BLOCK decision, risk_score >= 0.85 |
| P1 High | BLOCK or REVIEW decision, risk_score >= 0.70 |
| P2 Medium | REVIEW decision, risk_score >= 0.50 |
| P3 Low | APPROVE or low-risk REVIEW |

### Guided Investigation Command Panel

The Fraud Intelligence Command Center (Overview page) presents the Guided Investigation
Command Panel as the structured reviewer entry point. Clicking "Launch Guided
Investigation" calls `POST /cases/seed-review`, which idempotently provisions two canonical
review cases covering the showcase (BLOCK decision, evidence inspection) and review
(REVIEW / FALSE_POSITIVE verdict) paths, then navigates directly to the Case Dossier
for the high-priority showcase case.

The panel surfaces six capability dimensions — 4-layer scoring, evidence-led case
dossier, model attribution, AI investigation brief, analyst decision loop, and
reliability and scale — with a nine-step workflow path strip mapping the end-to-end
reviewer journey. Three secondary action links provide direct access to the Review
Queue, the verified 10M Portfolio Risk Scan, and the live API documentation.

---

## 7. Portfolio Risk Scan Module

### Capability overview

The Portfolio Risk Scan module accepts large CSV transaction files and processes them
through the same 4-layer scoring pipeline used for real-time cases, operating
asynchronously with durable progress tracking, indexed paginated results, risk tier
filtering, and hardened server-side streaming export.

### Key capabilities

| Capability | Description |
|---|---|
| Async upload | POST /risk-scan returns HTTP 202 with scan_id immediately |
| Chunked processing | Configurable chunk size (default 2,000 rows); memory bounded by chunk, not file |
| Durable progress | Status written to PostgreSQL after every chunk; polling reflects real incremental state |
| Indexed pagination | Composite ordered indexes support page 1 through deep pages at 10M scale |
| Risk-tier filtering | Server-side P1/P3/All filter queries via indexed scan_id + tier columns |
| Server-side cursor export | Bounded-batch CSV iterator writes directly to HTTP response; no full in-memory load |
| Scan resume | Frontend reloads any completed scan by public scan UUID |
| Recent scans panel | Last N scans surfaced in the UI for quick access |
| Scan Detail Header | Filename, row count, tier distribution, exposure totals, scan UUID, controls |
| Promote to case | Individual scan results can be promoted to full Case Dossiers |
| Frontend scan UUID routing | `/risk-scan?scan_id=<uuid>` loads the named scan directly |

---

## 8. 10M Benchmark Verification

The 10M benchmark is the current verified scale ceiling for the async Portfolio Risk
Scan engine under controlled benchmark conditions.

### Scan identity

| Field | Value |
|---|---|
| scan_id | `aa0971d2-bdb6-49c7-bac3-fa355aa161ad` |
| Input file | risk-scan-12d8u-10m.csv (720 MiB, 10,000,000 rows) |
| Status | COMPLETE |

### Processing results

| Metric | Value |
|---|---|
| Processed rows | 10,000,000 / 10,000,000 |
| Valid / invalid / skipped | 10,000,000 / 0 / 0 |
| Processing time | ~103m 35s |
| Average throughput | ~1,610 rows/sec |
| Chunk size | 2,000 rows |
| P1 count | 8,420,051 |
| P3 count | 1,579,949 |
| Total exposure | $25,095,000,000 |
| High exposure | $24,455,516,419 |

### Pagination and query performance (post-index hardening)

| Query | Response time |
|---|---|
| Page 1 (default sort) | 0.676s |
| Page 2 | 0.247s |
| Deep pagination (page 1,000) | 0.379s |
| P1 filter, page 1 | Sub-second |

### Export performance

| Metric | Value |
|---|---|
| HTTP status | 200 |
| Total export duration | 113.63s |
| Time to first byte | 0.006987s |
| Export file size | 1.64 GiB |
| Export lines | 10,000,001 (header + 10,000,000 rows) |
| API RestartCount after export | 0 |
| OOMKilled | false |

---

## 9. Engineering Hardening Journey

The path from the 10k verified checkpoint to the 10M benchmark was a series of targeted
architectural interventions, each motivated by a real bottleneck exposed at a specific
scale.

### 500k -- O(N squared) summary recomputation

The 500k run exposed a progressive throughput degradation. Each chunk's completion
triggered a full recompute of tier counts across all previously processed rows.
At 500k rows, this recomputation cost grew to dominate processing time.

**Fix:** Running summary counters. Each chunk update increments persistent counter
columns rather than recomputing from scratch. Throughput degradation eliminated.

### 2.5M -- PostgreSQL table bloat and export risk

The 2.5M run exposed Postgres dead-space accumulation from prior benchmark churn.
The table carried ~19 GB of dead rows from previously completed scans.

**Fix:** VACUUM FULL and dead-space reclaim. Export stability improved. This also
motivated a DB archive/cleanup strategy for large benchmark environments.

### 5M -- Large CSV export failure

The first 5M export failed after ~26m55s with an empty server reply and an API restart.
The export path was using the UI pagination helper internally, including count and offset
work on each iteration, which buffered too much state.

**Fix:** Server-side cursor export. A dedicated bounded-batch export iterator replaced
the UI pagination path. The hardened 5M export completed with immediate first byte,
no restart, no OOM. This fix became the foundation for all subsequent scale exports.

### 7.5M -- Sort and query scale on result table

The 7.5M run surfaced DB sort latency: result queries scanned by `scan_id` and sorted
millions of rows without index support. Page 1 queries included expensive sort nodes.

**Fix:** Composite ordered indexes with `NULLS LAST` on
`(scan_id, risk_score DESC, row_number ASC)` and on
`(scan_id, tier, risk_score DESC, row_number ASC)` for filtered queries.
Large sort nodes and disk spill eliminated before the 10M run.

### 10M -- Benchmark passed

After ingestion, export, dedup, and index hardening, the 10M benchmark passed:
10,000,000 rows processed, zero invalid, zero skipped, stable pagination through deep
pages, 1.64 GiB export completed cleanly, API remained stable throughout.

### Summary

| Scale | Issue exposed | Resolution |
|---|---|---|
| 500k | Summary recomputation O(N^2) | Running counter optimization |
| 2.5M | Postgres table bloat | DB cleanup and dead-space reclaim |
| 5M | Large export failure (API restart) | Server-side cursor streaming export |
| 7.5M | Sort/query latency at scale | Composite ordered index hardening |
| 10M | Passed -- all hardening verified |  |

---

## 10. Analyst Workflow and Case Dossier 2.0

### Review Queue

The Review Queue presents the full caseload sorted by descending risk score, with BLOCK
decisions as the tie-breaker for equal scores. Priority tier labels (P0-P3) identify
urgency. Status filters allow isolation of unreviewed cases, confirmed fraud, false
positives, and approved cases.

### Case Dossier 2.0 (Investigation Workspace)

Case Dossier 2.0 organises all risk evidence, investigation context, and analyst actions
into a structured lifecycle view:

**Grouped evidence display:**

| Evidence group | Content |
|---|---|
| Base signals | ML risk score, decision tier, deterministic rule flag, 9-feature signal factors |
| Enriched signals | Rich risk indicators from expanded feature combinations |
| Behavioural indicators | `BEHAVIOURAL_AMOUNT_DEVIATION`, `BEHAVIOURAL_VELOCITY_DEVIATION`, `BEHAVIOURAL_PROFILE_SHIFT` -- amber chips |
| Graph indicators | `MULE_FAN_IN_PATTERN`, `MULE_FAN_OUT_PATTERN`, shared device, shared identity -- violet chips |

**Lifecycle timeline:** creation, investigation, verdict, and workflow dispatch events
with timestamps -- full traceability across the case lifecycle.

**AI investigation brief:** structured recommendation, confidence rating, risk factors,
mitigating factors, triggered rules, referenced playbooks, rationale -- produced by the
hardened AI investigation pipeline.

**Model Attribution panel:** positioned between the grouped evidence and the AI
investigation brief, the Model Attribution panel surfaces per-feature XGBoost
contributions via `GET /cases/{case_id}/explain`, which uses XGBoost's built-in
TreeSHAP (`pred_contribs=True`) — no external library required. All 9 feature
contributions are ranked by magnitude with direction (increases or decreases risk)
and the feature value used at scoring time. This is an explainability surface for the
baseline XGBoost model specifically; it is distinct from the hybrid reason codes in
the grouped evidence, which explain the full 4-layer decision including rules, rich
signals, behavioural profiling, and graph topology.

**Verdict capture:** analyst submits a formal verdict with notes; verdict persists
against the case record and triggers the workflow dispatch path.

**Case-scoped audit trail:** workflow events filtered by case_id refresh immediately
after n8n callback.


### Scan result promotion

Individual portfolio scan result rows can be promoted to full Case Dossiers via the
scan results table. This bridges the bulk risk scan workflow and the individual analyst
review lifecycle.

---

## 11. AI Investigation Pipeline

### Phase 18 -- Investigation Brief Hardening

The AI investigation pipeline delivers per-case briefs with production-grade
reliability controls and a complete AI audit trail.

```
Case promoted to investigation
  -> Evidence extraction: deterministic feature breakdown per case
  -> Evidence grouping: base signals, enriched signals, behavioural indicators,
     graph indicators
  -> RAG retrieval: playbook and policy knowledge base queried for matching guidance
  -> Prompt assembly: evidence groups + playbook context + policy context
  -> Ollama reasoning: structured JSON investigation report generated locally
  -> Schema validation: report validated against structured output contract
  -> Bounded failure handling: Ollama failure, content failure, and unexpected errors
     each produce a specific analyst-readable FAILED report (never a silent failure)
  -> Report persistence: COMPLETE or FAILED report written to PostgreSQL
  -> AGENT_VERSION tagged: investigation row records agent configuration version
  -> Analyst review: brief surfaced in Case Dossier; analyst verdict required
     before any operational decision
```

**AI assists investigation briefing. It does not autonomously enforce decisions.**

### Investigation report structure

| Field | Description |
|---|---|
| Recommendation | CONFIRM_FRAUD / FALSE_POSITIVE / ESCALATE |
| Confidence | HIGH / MEDIUM / LOW |
| Risk Factors | Array of contributing risk signals |
| Mitigating Factors | Evidence against fraud classification |
| Rules Triggered | Which deterministic rules fired |
| Playbooks Referenced | Relevant fraud investigation playbooks |
| Rationale | Full recommendation reasoning |

### Production-grade reliability controls

| Control | Description |
|---|---|
| Evidence-grouped prompting | Evidence delivered to the LLM in the same taxonomy displayed in the Case Dossier |
| `AGENT_VERSION` traceability | Every investigation record tagged with agent configuration version -- immutable AI audit trail |
| Bounded failure messages | Ollama connectivity failure, LLM content failure, and unexpected errors each produce a specific, analyst-readable message |
| Honest no-guidance handling | When no matching playbook document exists, the prompt explicitly states this rather than allowing confabulation |
| FAILED-state persistence | Investigation failures write a durable FAILED record to PostgreSQL; analyst can retry from the Case Dossier UI |

Every investigation record in the database is tagged with `AGENT_VERSION`, creating an
immutable traceability chain between the analyst brief and the specific agent
configuration that produced it.


### Workflow automation and audit

Workflow dispatch uses an n8n webhook pattern with HTTP callback audit:

1. Analyst triggers dispatch from Case Dossier
2. FastAPI calls n8n production webhook
3. n8n evaluates case, constructs escalation or no-escalation response
4. n8n writes structured audit event back via POST /workflow/audit-event
5. Audit event persists with case_id, action, status, source, priority, message
6. Case-scoped workflow events table refreshes immediately in the analyst view

All workflow events are queryable in the Automation Audit Trail with filter support
by status, source, and coverage date range.

---

## 12. Reliability and Observability

### Operational Health Endpoint (Phase 19A)

`GET /health/detailed` returns a structured per-component health status:

```json
{"status": "healthy", "components": {"postgres": "healthy", "kafka": "healthy", "ollama": "healthy"}}
```

Each component is probed independently. Component-level degradation is surfaced
before it affects the analyst workflow. The endpoint is referenced in operational
runbooks and governance documentation.

### Reliability Metrics (Automation Reliability Center)

The Reliability Metrics page computes live health from workflow event records:

| Component | Description |
|---|---|
| Health verdict | Healthy / Degraded / Critical based on success rate and dispatch failure count |
| SLO targets | Success rate target 90%, dispatch failure target 0%, automation coverage target 70% |
| Failure Spotlight | Explicit cards for failed events and dispatch failures with alert states |
| Operational Diagnosis | Three-column contextual card: diagnosis, reliability impact, recommended action |
| Charts | Action breakdown (horizontal bar), source breakdown (vertical bar), reliability outcome (donut) |

### Demo reliability state

The demo seed state preserves 10 dispatch failures, producing a Critical health verdict
(54.5% success rate, below the 70% floor; 10 dispatch failures, exceeding the
3-failure threshold). This is intentional: a system that correctly classifies and
surfaces degraded automation behaviour demonstrates operational maturity.

---

## 13. Validation Scope

Benchmarks were executed on synthetic transaction data in a controlled local product
environment. The scoring engine is an enhanced baseline hybrid model. The 9-feature
XGBoost classifier was trained on synthetic data with a controlled fraud rate and
known feature distributions. Synthetic training accuracy reflects the data generation
distribution, not real-world fraud detection robustness.

The 4-layer intelligence architecture -- behavioural profiling, graph mule-network
detection, and adversarial simulation -- validates the system's capability to detect
fraud patterns beyond static feature scoring. Threshold selection is validated within
the controlled synthetic benchmark and adversarial simulation environment.

The engineering patterns applied -- async processing, server-side pagination and
export, indexed query hardening, event-driven audit architecture, structured AI
investigation with AGENT_VERSION traceability, consumer durability design -- are
applicable to a regulated deployment context with the appropriate institutional
controls in place.

---

## 14. Business Value

### Operational value by capability

| Capability | Operational value |
|---|---|
| 4-Layer Fraud Scoring | Base ML/rule + rich signals + behavioural profiling + graph topology, each contributing independently to a bounded risk score |
| Behavioural Intelligence | Entity-level deviation detection: amount, velocity, and profile shift -- invisible to static rules alone |
| Graph Mule-Network Detection | Fan-in / fan-out pattern detection across shared device and identity clusters -- identifies coordinated fraud rings |
| Adversarial Simulation | Five-family detection validation confirms intelligence layers catch patterns that evade the base model |
| Async Portfolio Risk Scan | Score portfolios of millions of transactions without blocking real-time case operations |
| Indexed pagination at 10M scale | Analysts can review, filter, and export large result sets without system degradation |
| Server-side streaming export | 1.64 GiB CSV exported without API restart or memory pressure |
| Guided Investigation Command Panel | Structured reviewer entry point: `POST /cases/seed-review` provisions canonical review cases; six capability cards and nine-step workflow path orient reviewers to each intelligence surface |
| Case Dossier 2.0 | Grouped evidence, lifecycle timeline, behavioural and graph chips, model attribution, AI brief, verdict capture -- full analyst context in one workspace |
| Model Attribution | `GET /cases/{case_id}/explain` via XGBoost native TreeSHAP (`pred_contribs=True`) -- 9 feature contributions ranked by magnitude; separates base ML model attribution from hybrid reason codes |
| AI Investigation Brief | Evidence-grouped prompting, AGENT_VERSION traceability, bounded failure handling, structured LLM report persisted per case |
| End-to-end audit trail | Every automation dispatch produces a durable, queryable event record |
| Reliability monitoring | The system surfaces its own automation health with SLO-style targets |
| Operational health endpoint | GET /health/detailed -- per-component Postgres, Kafka, Ollama status |
| Governance documentation package | Consumer durability, auth/RBAC design, and security posture documented for institution-specific deployment review |

### Executive value by audience

**Fraud operations teams:**
Prioritised case queue with P0-P3 tier labels, multi-layer risk evidence grouped by
intelligence type, AI-assisted investigation briefs advisory to the analyst, structured
verdict capture with notes, and workflow automation with a full audit trail per case.

**Risk and compliance leadership:**
Portfolio-scale exposure quantification across millions of transactions, immutable
prediction records with idempotency guarantees, append-only workflow event audit trail,
AGENT_VERSION traceability on all AI investigation records, and a formal governance
documentation package covering consumer durability, RBAC design, and security posture.

**Engineering leadership:**
Production-style event-driven architecture with explicit consumer durability design,
per-component operational health monitoring, composite indexed queries validated at
10M row scale, server-side streaming export validated at 1.64 GiB, documented
deployment-readiness boundary with prioritised production hardening controls.

**AI governance reviewers:**
Analyst-in-the-loop enforcement: AI generates investigation briefs, analysts decide
verdicts. Every investigation record tagged with AGENT_VERSION for full traceability.
Bounded failure handling ensures every pipeline failure produces a durable, structured
outcome. Honest RAG fallback prevents confabulation when no playbook guidance exists.
Model Attribution (`GET /cases/{case_id}/explain`, XGBoost native TreeSHAP) provides a
per-case explainability record for the baseline ML model, distinct from the hybrid
reason codes that reflect the full 4-layer decision.

---

## 15. Roadmap

| Phase | Capability | Status |
|---|---|---|
| Phase 12E | Demo packaging, risk scan UX polish, report generator | Complete |
| Phase 12F | Rich synthetic banking dataset generator | Complete |
| Phase 12G | Enhanced fraud decision engine and explainability audit | Complete |
| Phase 13 | Behavioural intelligence layer | Complete |
| Phase 14 | Dirty data and stream resilience | Complete |
| Phase 15 | Graph / mule-network intelligence | Complete |
| Phase 16 | Adversarial synthetic fraud simulation | Complete |
| Phase 17 | Case Dossier 2.0 | Complete |
| Phase 18 | AI investigation brief hardening | Complete |
| Phase 19 | Governance and production readiness documentation | Complete |
| Phase 20 | Deployment, GitHub, portfolio integration | Complete |

---

## 16. Deployment Boundary and Production Readiness

### Current deployment boundary

The Fraud Intelligence Console operates in a controlled local product environment:
a single Docker Compose stack on a development machine, using synthetic transaction
data, with no internet exposure and no external institution integration. The
deployment boundary reflects the current build scope as a local Docker Compose inspection package.

This boundary is a defined engineering constraint, not a capability limit. The
architecture, intelligence layers, audit trail design, and governance documentation
are all designed for the deployment path that follows.

### What the benchmark and validation evidence represents

- 10M-row Portfolio Risk Scan: verified at controlled benchmark scale in the local
  product environment. Throughput, query performance, and export metrics are
  reproducible and sourced from real PostgreSQL state.
- 11/11 E2E Playwright checks: functional validation of the analyst frontend against
  the live stack.
- Adversarial simulation: detection coverage validated across five coordinated fraud
  pattern families in a controlled synthetic benchmark.
- Per-component health endpoint: `GET /health/detailed` confirms Postgres, Kafka,
  and Ollama operational status within the local stack.

### Institution-specific deployment requirements

Deploying this system to a regulated financial services environment requires:

- **Model calibration:** threshold selection and decision tiers require calibration
  against labelled historical fraud outcomes and false-positive cost analysis
- **Auth / RBAC implementation:** the RBAC design in `docs/AUTH_RBAC_DESIGN.md`
  specifies the three-role model (Analyst, Senior Analyst, Admin), permission matrix,
  and JWT architecture; implementation is a deployment prerequisite
- **Secrets management:** `DATABASE_URL` and `N8N_WEBHOOK_URL` require secrets
  manager injection; hardcoded localhost origins require env-variable-driven
  CORS configuration
- **DLQ and retry infrastructure:** the scoring consumer's commit-on-failure path and
  the missing dead-letter topic are documented production gaps in
  `docs/CONSUMER_DURABILITY.md`; DLQ implementation is required before sustained
  high-volume operation
- **Monitoring and alerting:** no Prometheus, OpenTelemetry, or external metrics
  stack is implemented; consumer lag monitoring, FAILED investigation rate alerting,
  and API latency instrumentation are documented as hardening prerequisites
- **Model-risk review and operational approval:** institution-specific governance
  and model-risk management processes apply before regulated deployment

These requirements are not deficiencies -- they are standard deployment prerequisites
for any financial services risk system. They are documented in the governance package
and in the public MLOps readiness and deployment documentation.

### What to claim confidently

- A complete, working fraud decision intelligence platform with a traceable
  engineering history across 20 phases
- Verified benchmark evidence at a scale that required genuine architectural
  problem-solving across five hardening milestones
- A 4-layer intelligence architecture (base ML/rule + rich signals + behavioural
  profiling + graph mule-network) with analyst-visible reason codes
- Adversarial detection coverage validated across five coordinated fraud pattern
  families
- Hardened AI investigation pipeline with AGENT_VERSION traceability, bounded
  failure handling, and FAILED-state persistence
- A governance documentation package covering consumer durability, auth/RBAC design,
  and security posture -- designed for institution-specific deployment review
- End-to-end operational thinking: not just a model, but the complete decision
  intelligence layer around it
