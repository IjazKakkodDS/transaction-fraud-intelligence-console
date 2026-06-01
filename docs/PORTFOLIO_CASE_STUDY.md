# Real-Time Fraud Intelligence Console

A local production-style fraud operations platform covering the full case lifecycle from
real-time transaction scoring to analyst verdict capture, AI-assisted investigation,
workflow automation, audit trail generation, and portfolio-scale bulk risk scanning.

---

## 1. Executive Summary

The Fraud Intelligence Console is a decision intelligence layer built to demonstrate the
full operational surface of a real-time fraud operations system -- from transaction scoring
through analyst review, investigation, workflow automation, audit trail, and reliability
monitoring.

The system runs on a local Docker Compose stack with a production-representative service
topology: FastAPI backend, PostgreSQL persistence, Redpanda event stream, Redis cache,
scoring consumer, investigation consumer, n8n workflow automation, and a Next.js analyst
interface.

The Portfolio Risk Scan module extends the system to bulk transaction intelligence: an
async scan engine that processed, persisted, and exported a 10,000,000-row synthetic
transaction dataset through a hardened server-side streaming CSV cursor with zero API
restarts and zero out-of-memory kills.

The engineering story behind the 10 M benchmark is not just about throughput. It is a
documented hardening journey: five scale ramps from 500k to 10 M, each exposing a
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

Portfolio-scale risk scanning introduces a second problem: bulk transaction files cannot
be scored synchronously without exhausting API memory and blocking normal case operations.
Export of large result sets fails if the export path reads the full result into memory.
Deep pagination degrades if queries lack index support at multi-million-row scale.

These are the problems this system was built to address.

---

## 3. Product Vision

A Fraud Intelligence Console that covers the complete case lifecycle with an audit record
at every step, surfaces AI investigation in context where it adds value, dispatches
workflow automation and proves it executed, monitors its own reliability, and handles
portfolio-scale bulk risk scanning through an async engine hardened for large file ingestion,
bounded-memory processing, indexed pagination, and server-side streaming export.

---

## 4. System Architecture

### Service topology

| Service | Role |
|---|---|
| FastAPI (Python) | REST API -- 15+ endpoints covering scoring, case management, investigation, workflow, metrics, risk scan |
| PostgreSQL 16 | Persistence -- cases, predictions, investigations, workflow events, portfolio scans, scan results |
| Redpanda (Kafka-compatible) | Event stream -- transaction events, scored case events, 4 topics |
| Redis | Cache |
| Scoring consumer | Kafka consumer -- scores raw transaction events, creates case records |
| Investigation consumer | Kafka consumer -- generates AI investigation reports per case via Ollama/Mistral |
| n8n | Workflow automation -- fraud case escalation workflow, HTTP callback to FastAPI audit endpoint |
| Next.js 16 | Analyst interface -- 8 routes, TypeScript, TanStack Query, Recharts |

### Data flow (real-time path)

```
Transaction submitted (POST /predict or async Kafka event)
  -> Scoring consumer: XGBoost model + deterministic rule evaluation
  -> Risk score + decision (APPROVE / REVIEW / BLOCK) persisted
  -> REVIEW and BLOCK cases published to case event topic
  -> Investigation consumer: Ollama/Mistral generates structured investigation report
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

### Scoring formula

```
risk_score = (0.6 x model_output) + (0.4 x rule_flag)
```

Model: XGBoost classifier, 9-feature vector, synthetic training data.
Rule: deterministic evaluation of 3 high-risk pattern conditions.

---

## 5. Core Workflow

### Transaction-to-verdict lifecycle

1. Transaction submitted via Transaction Intake Console or async Kafka event
2. Scoring consumer evaluates 9 risk features; applies deterministic rule layer
3. Risk score, decision tier, and reason codes persisted to PostgreSQL
4. REVIEW and BLOCK cases surface in the Review Queue, sorted by descending risk score
5. Analyst opens Case Dossier: risk evidence, AI investigation report, verdict capture
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

---

## 6. Portfolio Risk Scan Module

### Capability overview

The Portfolio Risk Scan module accepts large CSV transaction files and processes them
through the same XGBoost + rule scoring pipeline used for real-time cases, operating
asynchronously with durable progress tracking, indexed paginated results, risk tier
filtering, and hardened server-side streaming export.

### Key capabilities

| Capability | Description |
|---|---|
| Async upload | POST /risk-scan returns HTTP 202 with scan_id immediately |
| Chunked processing | Configurable chunk size (default 2,000 rows); memory bounded by chunk, not file |
| Durable progress | Status written to PostgreSQL after every chunk; polling reflects real incremental state |
| Indexed pagination | Composite ordered indexes support page 1 through deep pages at 10 M scale |
| Risk-tier filtering | Server-side P1/P3/All filter queries via indexed scan_id + tier columns |
| Server-side cursor export | Bounded-batch CSV iterator writes directly to HTTP response; no full in-memory load |
| Scan resume | Frontend reloads any completed scan by public scan UUID |
| Recent scans panel | Last N scans surfaced in the UI for quick access |
| Scan Detail Header | Filename, row count, tier distribution, exposure totals, scan UUID, controls |
| Promote to case | Individual scan results can be promoted to full Case Dossiers |
| Frontend scan UUID routing | `/risk-scan?scan_id=<uuid>` loads the named scan directly |

---

## 7. 10 M Benchmark Verification

The 10 M benchmark is the current verified scale ceiling for the async Portfolio Risk
Scan engine under local production-style conditions.

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

## 8. Engineering Hardening Journey

The path from the 10k verified checkpoint to the 10 M benchmark was a series of targeted
architectural interventions, each motivated by a real bottleneck exposed at a specific scale.

### 500k -- O(N squared) summary recomputation

The 500k run exposed a progressive throughput degradation. Each chunk's completion
triggered a full recompute of tier counts across all previously processed rows.
At 500k rows, this recomputation cost grew to dominate processing time.

**Fix:** Running summary counters. Each chunk update increments persistent counter columns
rather than recomputing from scratch. Throughput degradation eliminated.

### 2.5 M -- PostgreSQL table bloat and export risk

The 2.5 M run exposed Postgres dead-space accumulation from prior benchmark churn.
The table carried ~19 GB of dead rows from previously completed scans.

**Fix:** VACUUM FULL and dead-space reclaim. Export stability improved. This also
motivated a DB archive/cleanup strategy for large benchmark environments.

### 5 M -- Large CSV export failure

The first 5 M export failed after ~26m55s with an empty server reply and an API restart.
The export path was using the UI pagination helper internally, including count and offset
work on each iteration, which buffered too much state.

**Fix:** Server-side cursor export. A dedicated bounded-batch export iterator replaced
the UI pagination path. The hardened 5 M export completed with immediate first byte,
no restart, no OOM. This fix became the foundation for all subsequent scale exports.

### 7.5 M -- Sort and query scale on result table

The 7.5 M run surfaced DB sort latency: result queries scanned by `scan_id` and sorted
millions of rows without index support. Page 1 queries included expensive sort nodes.

**Fix:** Composite ordered indexes with `NULLS LAST` on `(scan_id, risk_score DESC, row_number ASC)` and on `(scan_id, tier, risk_score DESC, row_number ASC)` for filtered queries.
Large sort nodes and disk spill eliminated before the 10 M run.

### 10 M -- Benchmark passed

After ingestion, export, dedup, and index hardening, the 10 M benchmark passed:
10,000,000 rows processed, zero invalid, zero skipped, stable pagination through deep
pages, 1.64 GiB export completed cleanly, API remained stable throughout.

### Summary

| Scale | Issue exposed | Resolution |
|---|---|---|
| 500k | Summary recomputation O(N^2) | Running counter optimization |
| 2.5 M | Postgres table bloat | DB cleanup and dead-space reclaim |
| 5 M | Large export failure (API restart) | Server-side cursor streaming export |
| 7.5 M | Sort/query latency at scale | Composite ordered index hardening |
| 10 M | Passed -- all hardening verified |  |

---

## 9. Analyst Workflow and Case Promotion

### Review Queue

The Review Queue presents the full caseload sorted by descending risk score, with BLOCK
decisions as the tie-breaker for equal scores. Priority tier labels (P0-P3) identify
urgency. Status filters allow isolation of unreviewed cases, confirmed fraud, false
positives, and approved cases.

### Case Dossier (Investigation Workspace)

Each case has a structured dossier containing:

- Risk evidence: ML risk score, decision tier, deterministic rule flag, signal factors, analyst notes
- AI Investigation report: recommendation (CONFIRM_FRAUD / FALSE_POSITIVE / ESCALATE), confidence rating, risk factors, mitigating factors, triggered rules, referenced playbooks, rationale
- Verdict capture: analyst submits a formal verdict with notes; verdict persists against the case record
- Workflow automation panel: dispatch to n8n workflow; case-scoped audit trail refreshes on callback

### Scan result promotion

Individual portfolio scan result rows can be promoted to full Case Dossiers via the
scan results table. This bridges the bulk risk scan workflow and the individual analyst
review lifecycle.

---

## 10. AI Investigation and Workflow Audit Layer

### AI investigation

Each case generates a structured AI investigation report via Ollama/Mistral (local
LLM inference). The report is structured with schema enforcement and retry logic:

| Field | Description |
|---|---|
| Recommendation | CONFIRM_FRAUD / FALSE_POSITIVE / ESCALATE |
| Confidence | HIGH / MEDIUM / LOW |
| Risk Factors | Array of contributing risk signals |
| Mitigating Factors | Evidence against fraud classification |
| Rules Triggered | Which deterministic rules fired |
| Playbooks Referenced | Relevant fraud investigation playbooks |
| Rationale | Full recommendation reasoning |

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

## 11. Reliability and Observability Surface

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
(54.5% success rate, below the 70% floor; 10 dispatch failures, exceeding the 3-failure
threshold). This is intentional: a system that correctly classifies and surfaces degraded
automation behavior demonstrates operational maturity.

---

## 12. Validation Scope

Benchmarks were executed on synthetic transaction data in a local production-style
environment. Institution deployment would require security review, access control,
governance, monitoring, and model validation against real fraud labels.

The scoring engine is an enhanced baseline hybrid model. The 9-feature XGBoost
classifier was trained on synthetic data with a controlled fraud rate and known
feature distributions. Synthetic training accuracy reflects the data generation
distribution, not real-world fraud detection robustness.

The engineering patterns demonstrated -- async processing, server-side pagination and
export, indexed query hardening, event-driven audit architecture, structured AI
investigation -- are applicable to a regulated deployment context with the appropriate
institutional controls in place.

---

## 13. Business Value

| Capability | Operational value |
|---|---|
| Async Portfolio Risk Scan | Score portfolios of millions of transactions without blocking real-time case operations |
| Indexed pagination at 10 M scale | Analysts can review, filter, and export large result sets without system degradation |
| Server-side streaming export | 1.64 GiB CSV exported without API restart or memory pressure |
| End-to-end audit trail | Every automation dispatch produces a durable, queryable event record |
| AI investigation per case | Structured recommendation and rationale available in the analyst workflow |
| Reliability monitoring | The system surfaces its own automation health with SLO-style targets |
| Case promotion from scan | Bulk scan results connect directly into the single-case analyst review lifecycle |
| Promote-to-case from scan results | Bridges portfolio-level risk scanning and transaction-level case review |

---

## 14. Roadmap

### Phase 12E -- Schema Mapping and Data Quality Layer (Planned)

- Column mapping: user maps uploaded file column names to expected schema fields
- Auto-mapping with confidence scoring
- Schema template persistence for recurring file sources
- Per-row data quality scoring and rejected-row reporting
- Quality summary panel before scoring begins

### Phase 12F -- Rich Synthetic Banking Dataset Generator (Planned)

- User entity baselines: home country, typical amounts, merchant categories, device type
- Structured fraud pattern injection library
- 10k / 100k / 1M scale output targets

### Phase 12G -- Enhanced Fraud Decision Engine (Planned)

- Per-dimension risk score breakdown: model, rules, velocity, behavioral deviation, device, merchant, country, amount anomaly
- Reason code per contributing dimension
- Score breakdown panel in Case Dossier

### Phase 13 -- Behavioral Intelligence Layer (Planned)

- Entity-aware risk scoring based on user transaction history
- Velocity signals: transaction count per 1h and 24h windows
- Behavioral deviation: amount vs user average, unusual merchant or device

### Phase 15 -- Graph / Mule Network Intelligence (Planned)

- Shared device and merchant network analysis
- Mule-ring detection indicators
- Network evidence surfaced in Case Dossier

---

## 15. Resume-Safe Positioning

### What this system demonstrates

- Full-stack system design: async event-driven pipeline, REST API, PostgreSQL persistence,
  Redis cache, Kafka-compatible eventing, Next.js analyst interface
- Production-style engineering patterns applied to a complex, multi-service architecture
- Documented, reproducible benchmark evidence at 10 M rows with a clear hardening narrative
- End-to-end traceability: transaction to score to case to verdict to workflow event to audit trail
- Operational observability: reliability monitoring with SLO-style health verdicts
- AI integration: structured LLM investigation reports with schema enforcement and retry logic

### How to describe the scoring model

Enhanced baseline hybrid fraud scoring engine: 9-feature XGBoost classifier trained on
synthetic transaction data, combined with a 3-condition deterministic rule layer via a
weighted formula (risk_score = 0.6 x model_output + 0.4 x rule_flag). Feature importances
reflect the training distribution. Validation against real fraud labels and institution-specific
model governance are deployment prerequisites.

### How to describe the scale benchmark

Verified 10,000,000-transaction async Portfolio Risk Scan in a local production-style Docker
Compose environment: 103m 35s processing time (~1,610 rows/sec average), indexed pagination
(deep page at 0.379s), hardened server-side streaming export (1.64 GiB in 113.63s, sub-7ms
time to first byte, zero API restarts, zero OOM kills).

### What not to claim

- Do not claim production-certified fraud detection. The model baseline requires real-data
  validation before regulated use.
- Do not claim public deployment. The system runs locally via Docker Compose.
- Do not claim real-world throughput at production scale. Benchmark conditions are local,
  single-machine, synthetic data.

### What to claim confidently

- A complete, working, production-style fraud operations platform with a traceable
  engineering history
- Verified benchmark evidence at a scale that required genuine architectural problem-solving
- A system that demonstrates end-to-end operational thinking: not just a model, but the
  full decision intelligence layer around it
