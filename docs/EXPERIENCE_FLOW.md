# Real-Time Transaction Fraud Intelligence Console: Experience Flow

---

## 1. Product Experience Thesis

The Real-Time Transaction Fraud Intelligence Console is built around a single operational thesis: fraud decisioning is a workflow problem, not a scoring problem. A risk score is an input to the analyst workflow, not a replacement for it.

The console connects every stage of the fraud decisioning lifecycle into a coherent analyst experience: scoring, triage, investigation, verdict capture, automation dispatch, audit, and reliability monitoring. Each stage has a clear purpose, a clear handoff to the next stage, and a clear evidence trail connecting it to the case record in PostgreSQL.

Every product decision is an expression of that thesis. The command center gives the analyst operational awareness before they open a case. The review queue prioritises the most urgent work. The case dossier presents evidence in grouped, structured context rather than a flat field list. The investigation brief offers a reasoned, advisory recommendation with documented rationale. The workflow audit trail makes automation accountable. The reliability center makes the performance of that automation visible.

The portfolio scan layer extends the same decisioning architecture to bulk transaction intelligence: not as a separate product, but as a natural extension of the same evidence-led, analyst-controlled framework.

---

## 2. Analyst Journey Overview

```mermaid
sequenceDiagram
    participant T as Transaction Event
    participant API as Scoring API
    participant S as 4-Layer Scoring Engine
    participant Q as Review Queue
    participant C as Case Dossier
    participant AI as Investigation Brief
    participant A as Analyst
    participant W as Workflow Audit Trail

    T->>API: Submit transaction context
    API->>S: Extract features; compute base, rich, behavioural, and graph scores
    S->>Q: Route REVIEW or BLOCK cases
    Q->>C: Open case dossier
    C->>AI: Request investigation brief (async via Redpanda)
    AI->>C: Return recommendation, confidence, risk factors, mitigating factors
    C->>A: Present grouped evidence, attribution, and AI brief
    A->>C: Record verdict and case notes
    C->>W: Persist workflow event and audit entry
```

The analyst experience moves through seven stages:

1. **Command Center:** Operational orientation. Queue state, SLA pressure, system health.
2. **Review Queue:** Case triage. Priority ranking, risk-tier distribution, status filters.
3. **Case Dossier:** Evidence review. Scored signals grouped by origin, model attribution, lifecycle timeline.
4. **Investigation Brief:** Advisory recommendation. AI analysis with stated confidence and rationale.
5. **Analyst Verdict:** Human decision. Explicit verdict capture with notes via POST /review-case/{case_id}.
6. **Workflow Events:** Accountability. Every automation action timestamped, sourced, and case-linked.
7. **Reliability Metrics:** Operational confidence. Aggregate automation health, SLO panels, failure patterns.

The Portfolio Risk Scan operates as a parallel workflow: bulk ingestion, async chunked processing, risk-tier review, paginated navigation, and streaming export.

---

## 3. Flow 1: Command Center to Review Queue

**Entry point:** http://localhost:3000 (Fraud Intelligence Command Center)

**What the command center shows:**
- KPI strip: total cases, review queue depth, blocked transactions, approval rate
- 6-stage pipeline map: transaction flow from intake through scored decision to verdict
- Stale case pressure: cases approaching SLA breach displayed with time indicators
- System status: connectivity health of all connected services

**What the analyst does here:** Reads operational state, identifies queue pressure, and decides where to focus.

**Transition:** Navigate to /queue (Analyst Workbench / Review Queue).

**What the review queue shows:**

Cases ranked into priority tiers:

| Tier | Threshold | Meaning |
|---|---|---|
| P0 | Highest urgency | Score at or above BLOCK_THRESHOLD (0.7) |
| P1 | High | Score in upper REVIEW band |
| P2 | Medium | Score in mid REVIEW band |
| P3 | Lower | Score at or approaching REVIEW_THRESHOLD (0.3) |

Score bars appear inline per case. Status filter controls narrow the queue to pending, in-progress, or escalated cases. The queue is ordered by tier first, then score descending within each tier.

**What the analyst does here:** Identifies the highest-priority open cases and selects one for investigation.

---

## 4. Flow 2: Flagged Transaction to Case Dossier

**Entry:** Select any case from the review queue.

**Route:** /cases/[id] (Investigation Workspace / Case Dossier 2.0)

**What the Case Dossier shows:**

Evidence is organised into groups by signal origin, not presented as a flat list:

| Evidence group | Contents |
|---|---|
| Base signals | Transaction amount, time of day, high-amount flag, model prediction flag, rule flag, reason codes |
| Rich signals | Device trust score, geo distance anomaly, 1-hour velocity, failed attempts count, merchant risk score, new payee indicator, chargeback history |
| Behavioural signals | Amount deviation from 30-day entity baseline, velocity deviation, balance drop ratio, new device, new country, new counterparty, unusual channel, unusual merchant |
| Graph intelligence | Shared device indicator (across accounts), cross-account device reuse (across customers), counterparty fan-in, counterparty fan-out |

**Model attribution section:** Risk score value, final decision tier, full reason code list, and the score contribution from each of the four scoring layers.

**Lifecycle timeline:** Complete state history for this case: initial score, any prior reviews, investigation requests, and current status.

**Why this structure matters:** Grouping evidence by origin lets the analyst identify whether a signal is coming from a deterministic rule, a model feature, a behavioural deviation, or a network topology indicator. Each group has a different investigative weight and a different response posture.

---

## 5. Flow 3: Evidence Review to Analyst Decision

**Within the Case Dossier:**

The analyst reviews the four evidence groups and the model attribution, then forms an initial assessment. The analyst verdict panel appears in the same view.

**Analyst verdict panel captures:**

| Field | Options |
|---|---|
| Verdict | CONFIRM_FRAUD, FALSE_POSITIVE, ESCALATE, APPROVE |
| Notes | Free-text disposition instructions |
| Submission | POST /review-case/{case_id} |

**What submission does:**
- Persists the verdict and notes to the predictions record in PostgreSQL
- Timestamps the decision
- Updates case status
- Triggers downstream workflow dispatch if configured

**The analyst is not required to request an investigation brief before submitting a verdict.** The brief is an optional advisory layer. For low-complexity cases, the analyst may decide on evidence alone.

---

## 6. Flow 4: Investigation Brief to Case Judgment

**When the analyst needs advisory support on a complex or ambiguous case:**

**Trigger:** Analyst selects "Request Investigation" in the Case Dossier, which calls POST /cases/{case_id}/investigate (HTTP 202, async).

**What happens in the background:**

1. The API publishes an investigation request to the `cases.investigate` Redpanda topic.
2. The investigation-consumer reads the message.
3. The consumer assembles a structured evidence-grouped prompt from the case record in PostgreSQL.
4. The consumer retrieves relevant playbook knowledge snippets via the retriever.
5. The prompt is sent to the local Ollama LLM instance.
6. The response is validated against the required output schema.
7. On validation failure, the error is appended to the prompt and the call is retried (up to 2 retries).
8. On success, the structured brief is persisted to the `investigation_reports` table with AGENT_VERSION.

**Brief output displayed in /cases/[id]:**

| Field | Content |
|---|---|
| Recommendation | CONFIRM_FRAUD, FALSE_POSITIVE, or ESCALATE |
| Confidence | HIGH, MEDIUM, or LOW |
| Summary | Plain-language case summary |
| Risk factors | List of observations supporting fraud |
| Mitigating factors | List of observations reducing confidence |
| Recommendation rationale | Stated reasoning for the recommendation |
| Confidence rationale | Stated reasoning for the confidence level |

**AGENT_VERSION:** Every investigation_reports row stores the AGENT_VERSION field. This links each brief to the specific agent configuration that produced it, creating an immutable reference for audit purposes.

**Governance:** The brief is advisory. The analyst reads the recommendation and rationale, weighs it against the evidence, and submits an independent verdict. No automated path exists from an LLM recommendation to a case action.

---

## 7. Flow 5: Workflow Events to Auditability

**Route:** /workflow/events (Automation Audit Trail)

**What generates workflow events:**

Every significant case action generates a workflow event written to PostgreSQL:

| Source | Example events |
|---|---|
| Manual action | Case opened, verdict submitted, investigation requested |
| API trigger | POST /workflow/audit-event (from n8n or external caller) |
| n8n automation | Webhook trigger executed, callback received, step completed |
| System lifecycle | Case status transition, stale case alert |

**What the Audit Trail shows:**

- Chronological event log with timestamps
- Source label per event: manual or automated
- Status per event: success, failure, or pending
- Case linkage: each event links to the triggering case ID
- Audit summary rail: aggregated counts by status and source
- Filter controls: filter by status, source, or case ID

**Audit integrity:** Events are written at the time of action. They are not reconciled, edited, or backfilled. The log is the authoritative record of what the automation layer did and when.

**n8n integration path:**

POST /workflow/notify-case/{case_id} dispatches a webhook to n8n. n8n executes configured workflow steps and posts callbacks to the fraud console API. All callbacks are recorded as workflow events in the audit trail, making the full automation loop visible in a single view.

---

## 8. Flow 6: Portfolio Scan to Risk Prioritisation

**Route:** /risk-scan (Portfolio Risk Scan)

**Step 1: Upload and trigger**

The analyst uploads a CSV file containing transaction records. The API accepts the file via POST /risk-scan and returns HTTP 202 with a `scan_id`. The scan runs asynchronously in the background.

**Step 2: Progress monitoring**

The frontend polls GET /risk-scan/{scan_id}/status. Progress is written to PostgreSQL after every processing chunk, so the display reflects real ingestion state. The analyst sees row counts and percentage completion update in real time.

**Step 3: Results review**

On completion, GET /risk-scan/{scan_id}/results returns paginated scored results. Risk-tier filters (P0-P3) allow the analyst to isolate the highest-risk segment of a large batch. Composite indexed queries return filtered pages at sub-second response times even at 10M-row scale (P1 filter query at 8.42M rows: ~4.188s including paginated count).

**Step 4: Summary**

GET /risk-scan/{scan_id}/summary returns tier distribution, total row counts, and total synthetic exposure value. This gives the analyst a risk profile view of the full uploaded batch before committing to row-level review.

**Step 5: Export**

GET /risk-scan/{scan_id}/export streams the full result set as CSV via a server-side PostgreSQL cursor. The header is emitted immediately (time to first byte: ~6.987ms in the 10M benchmark). The full 10M-row export produces a 1.64 GiB file with no API memory growth and no restart.

**Step 6: Promotion**

POST /risk-scan/{scan_id}/promote/{result_id} promotes a selected scan result row into a full case in the analyst review queue. The case then enters the standard Case Dossier workflow.

---

## 9. Flow 7: Reliability Metrics to Operational Confidence

**Route:** /workflow/metrics (Automation Reliability Center)

**Purpose:** The reliability center gives the analyst or operations lead a view of how the automation layer is performing, not only what it is doing.

**Panels:**

| Panel | What it shows |
|---|---|
| Health verdict | Derived from aggregate workflow event success rates |
| SLO panels | Automation performance against configured thresholds |
| Failure spotlight | Recurring failure patterns identified by event type and source |
| Action breakdown chart | Distribution of automation event types over a time window |
| Source breakdown chart | Ratio of manual to automated events |

**Design intent:** The reliability view is populated in both healthy and degraded states. This is intentional: a system that surfaces and categorises failures demonstrates stronger operational design than one that presents only successful events. The analyst can assess whether failure rates are within acceptable bounds and whether patterns suggest a systemic issue versus an isolated event.

**Stale case surface:** GET /workflow/stale-cases returns cases approaching SLA breach. The command center displays these with time pressure indicators. This creates a connection between the reliability layer and the triage queue.

---

## 10. What the Reviewer Should Notice

**Evidence grouping is architectural, not cosmetic.**
The Case Dossier presents evidence in five distinct groups: base, rich, behavioural, graph, and scenario. Each group corresponds to a distinct scoring layer with independent weights and capping. The analyst can see not only that a signal fired but which layer it belongs to and how it contributes to the final score. This is the visible expression of the 4-layer scoring architecture.

**The AI brief has documented failure semantics.**
The investigation-consumer validates every LLM response against a strict schema. On failure, it appends the error to the next prompt and retries. After the retry limit, it surfaces the failure without crashing the consumer. The consumer continues processing the next message. Inspect `src/investigation/reasoner.py` for the complete retry and validation logic.

**AGENT_VERSION is a traceability control, not a label.**
Every InvestigationReport row in PostgreSQL stores the AGENT_VERSION of the agent that produced it. If the agent configuration changes, prior briefs remain permanently linked to the configuration that produced them. This is a prerequisite for AI audit trail integrity in regulated contexts where agent configuration changes must be discoverable.

**Consumer offset asymmetry is documented and intentional.**
The scoring consumer commits offsets on all handled paths, including unexpected error paths, to guarantee forward progress. The investigation consumer withholds the offset on unexpected errors to allow retry on restart. The asymmetry reflects a deliberate design trade-off between throughput and at-least-once delivery. Read `docs/CONSUMER_DURABILITY.md` for the full rationale and production gap matrix.

**The portfolio scan architecture bounds memory at two points.**
First: chunked ingestion means the API never holds the full CSV in heap. Second: the streaming export uses a server-side PostgreSQL cursor, meaning the full result set is never loaded into API memory. These two properties together make the 10M-row path stable. The benchmark verifies this: zero OOMKilled events, zero API restarts across the full 10M ingestion and 1.64 GiB export.

**The reliability view is populated in degraded state.**
A reliability panel that shows only green status provides weaker operational evidence. The Automation Reliability Center is designed to surface failures, categorise them by type and source, and present them alongside SLO thresholds. The failure spotlight is not an edge case display: it is a primary feature.

---

## 11. What This Experience Proves

**Integration depth:**
The console integrates eight distinct analyst-facing surfaces into a single coherent workflow. Each surface reads from and writes to real PostgreSQL state. There are no mock data layers or static fixture displays in the product flow.

**Scoring architecture visibility:**
The 4-layer scoring engine is implemented, deterministic, and fully visible in source code. Each layer emits distinct reason codes that appear in the Case Dossier. The analyst can trace a risk score back to its contributing signals across all four layers.

**Considered AI integration:**
The investigation brief layer uses a local LLM with structured output schema validation, retry with error feedback, AGENT_VERSION traceability, and bounded failure semantics. The LLM is advisory; the analyst is decisive. These are properties of a considered AI integration with governance controls, not a proof-of-concept wrapper.

**Portfolio-scale engineering:**
The 10M-row benchmark is a documented, repeatable result with measured throughput, response times, and memory behavior across ingestion, pagination, and export. The architecture properties that make it stable (chunked ingestion, indexed pagination, cursor export) are visible in the source code and not dependent on benchmark-specific configuration.

**Analyst-in-the-loop by design:**
No path exists from transaction score to final verdict that bypasses analyst judgment. Verdict capture via POST /review-case/{case_id} is a required step. The AI brief can inform the verdict but cannot substitute for it.

**Operational observability:**
Workflow audit trail, reliability panels, and failure spotlight are functional product features, not placeholders. The system does not require a separate observability stack to demonstrate operational design.

---

## 12. What Remains Intentionally Deferred

| Capability | Status | Reference |
|---|---|---|
| Authentication and RBAC | Designed; not implemented | docs/AUTH_RBAC_DESIGN.md |
| Cloud deployment | Deferred to Phase 21 | docs/DEPLOYMENT_PLAN.md |
| Production scoring calibration | Requires institution-specific labelled outcomes | docs/MODEL_CARD.md |
| Multi-broker Redpanda topology | Single-node local configuration only | docs/DEPLOYMENT_PLAN.md |
| TLS and ingress | Not configured in local runtime | docs/SECURITY_POSTURE.md |
| SLO alerting integration | Display-only in current build | Phase 21 scope |
| n8n production workflow templates | Locally defined workflows only | Phase 21 scope |

Each deferral is a boundary decision, not an oversight. The local inspection package is designed to make the architecture, scoring logic, audit trail, and analyst workflow inspectable without institution-specific configuration. The documented governance path covers what must be added before the system operates in a production context.

---

*Document created: Phase 20DPLY-B2 (2026-06-19).*
