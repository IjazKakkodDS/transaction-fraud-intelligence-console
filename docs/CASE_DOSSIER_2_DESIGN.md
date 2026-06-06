# Case Dossier 2.0 Design Contract - Phase 17A

---

## Purpose

Phase 17 upgrades the Case Dossier into a clearer analyst evidence workspace. The goal is to
help analysts understand why a case exists, what risk signals contributed to the decision, what
lifecycle events happened, and what decision was made by the analyst.

This phase is an evidence presentation and traceability phase. It does not change scoring,
model behavior, thresholds, graph or behavioural boost logic, AI investigation prompting, API
contracts, or database schema in Phase 17A.

---

## Current Case Dossier State

The current `/cases/[id]` route renders the Investigation Workspace. It is composed of:

| Component | Current role |
|---|---|
| `CaseHeader` | Shows case ID, transaction ID, amount, ML risk score, decision badge, analyst status, and transaction timestamp. |
| `CaseMetadataPanel` | Shows deterministic rule status, a flat list of risk signal factors, analyst notes, and verdict recorded timestamp. |
| `InvestigationPanel` | Shows AI investigation state, completed report fields, retry/re-run actions, and deterministic investigation context. |
| `AnalystActionPanel` | Captures analyst verdict, notes, and current reviewed timestamp. |
| `WorkflowNotifyButton` | Dispatches the case notification workflow. |
| `CaseWorkflowEvents` | Shows case-scoped automation audit events from the workflow events endpoint. |

The current page already supports case basics, AI investigation, analyst action, workflow
dispatch, and case-scoped workflow events. It does not yet provide dossier-level evidence
grouping, score breakdown, promotion provenance, or a unified timeline.

---

## Existing Evidence Inventory

The following evidence is already available from the current system.

### Case Core Evidence

The `predictions` table and existing case API provide:

| Field | Meaning |
|---|---|
| `id` / case ID | Durable case identifier. |
| `transaction_id` | Transaction reference. |
| `amount` | Transaction amount. |
| `timestamp` | Transaction timestamp. |
| `rule_flag` | Deterministic rule result. |
| `model_prediction` | Model binary signal. |
| `risk_score` | Final persisted risk score. |
| `decision` | Scoring-time decision: APPROVE, REVIEW, or BLOCK. |
| `reasons` | Pipe-delimited risk reason evidence. |
| `analyst_status` | Current analyst verdict state. |
| `analyst_notes` | Analyst-entered notes. |
| `reviewed_at` | Timestamp for current analyst verdict. |

### AI Investigation Evidence

The existing investigation endpoint provides the latest investigation report for a case,
including status, recommendation, confidence, risk factors, mitigating factors, rules
triggered, playbooks referenced, policies referenced, summary, rationale fields, deterministic
tool outputs, and error state.

### Workflow Evidence

The existing workflow events endpoint provides case-scoped automation events, including action,
status, source, escalation priority, message, payload, and event timestamp.

### Reason-Code Evidence

The `reasons` field already carries risk evidence from legacy/base, rich signal, behavioural,
and graph intelligence layers. Phase 17 should group this evidence more clearly in the dossier
without changing the taxonomy.

### Promotion Evidence

Portfolio scan promotion context may exist in `portfolio_scan_results`, including source scan,
source row, risk tier, promoted case ID, and promotion timestamp. This context is not necessarily
exposed by the current case API and should be audited in Phase 17B.

---

## Intelligence Evidence Groups

Case Dossier 2.0 should group reason-code evidence into clear analyst-facing sections. The
grouping is a display concern only and must not change reason-code generation.

| Group | Description |
|---|---|
| Legacy/base reasons | Original transaction-level model and deterministic rule reason text. |
| Rich signal reasons | Optional rich CSV and scenario-derived risk signal evidence. |
| Behavioural signal reasons | Entity-aware behavioural reason codes produced by the behavioural layer. |
| Graph intelligence reasons | Relationship-level graph and mule-network reason codes. |
| Scenario/contextual labels | Scenario family labels or contextual labels already present in the reasons field. |

Known graph intelligence codes include:

- `SHARED_DEVICE_CLUSTER`
- `DEVICE_ACCOUNT_REUSE`
- `MULE_FAN_IN_PATTERN`
- `MULE_FAN_OUT_PATTERN`

Known behavioural and rich signal groups should be classified using the existing frontend
reason grouping concepts already proven in the risk scan result drawer. Phase 17 must not
rename, replace, or expand the reason-code taxonomy unless a later slice explicitly approves it.

---

## Score Breakdown Design

Case Dossier 2.0 should provide an evidence breakdown based on fields already available from
the case API:

| Display item | Source |
|---|---|
| Final risk score | `risk_score` |
| Model signal | `model_prediction` |
| Deterministic rule signal | `rule_flag` |
| Decision | `decision` |
| Supporting evidence | grouped `reasons` |

Important boundaries:

- Do not recalculate scoring in the frontend.
- Do not claim exact rich, behavioural, or graph contribution values unless the backend exposes
  persisted component values.
- Do not infer exact boost values from reason codes.
- Do not present a fake per-dimension score decomposition.
- If component values are unavailable, show the evidence group as qualitative signal evidence.

---

## Timeline Design

Case Dossier 2.0 should assemble a lightweight timeline from existing evidence:

| Timeline event | Source |
|---|---|
| Transaction occurred | `timestamp` from the case record. |
| Case created / prediction persisted | Available only if exposed later; otherwise show as unavailable. |
| AI investigation created or completed | `investigated_at` from the investigation report when available. |
| Workflow event recorded | `created_at` from case-scoped workflow events. |
| Analyst verdict recorded | `reviewed_at` from the case record. |
| Portfolio scan row promoted | `promoted_at` if promotion provenance is exposed later. |

The first implementation should make missing timestamps explicit rather than inventing lifecycle
events that are not present in the API response.

---

## Analyst Decision Lineage

The first Case Dossier 2.0 lineage slice should show:

- Current `analyst_status`.
- Current `analyst_notes`.
- `reviewed_at`.
- Scoring-time `decision`.
- Supporting evidence groups visible near the verdict panel.

Full multi-verdict history is out of scope for Phase 17A and should be deferred unless a later
schema-backed audit trail is approved.

---

## Promotion Provenance

Promoted portfolio scan rows may provide valuable source context:

- Source `scan_id`.
- Source transaction row number.
- Source risk tier and operational priority.
- Promotion timestamp.
- Whether the result was skipped, valid, invalid, or promoted.
- Promoted case ID.

The current case API may not expose this context directly. Phase 17B should audit whether Case
Dossier 2.0 needs a read-only dossier enrichment endpoint or whether the frontend can safely
assemble the context from existing APIs.

---

## Backend/API Readiness Map

| Evidence needed | Already available? | Current source/API | Gap | Proposed Phase 17 action |
|---|---:|---|---|---|
| Case core fields | Yes | `GET /case/{id}` | No dossier-specific grouping. | Use in frontend dossier layout. |
| Reasons | Yes | `GET /case/{id}` -> `reasons` | Flat pipe-delimited string only. | Group on frontend using locked reason groups. |
| AI investigation | Yes | `GET /cases/{case_id}/investigation` | AI brief hardening remains separate. | Display existing report unchanged. |
| Workflow events | Yes | `GET /workflow/events?case_id=...` | Timeline composition not unified. | Reuse events in timeline/workflow section. |
| Promotion provenance | Partial | `portfolio_scan_results` storage, risk scan APIs | Not exposed directly on case API. | Phase 17B audit; consider read-only enrichment only. |
| Enriched transaction attributes | Partial | Risk scan result rows and intake payloads where persisted | `predictions` table has limited attributes. | Display only available fields; audit read-only options. |
| Score component values | Partial | `risk_score`, `model_prediction`, `rule_flag` | Rich, behavioural, and graph component boosts are not persisted on case rows. | Do not fake values; show qualitative evidence groups unless values are exposed later. |

---

## Frontend Information Architecture

Case Dossier 2.0 should be organized around the analyst's review flow:

1. Case overview
   - Case ID, transaction ID, amount, timestamp, status, and decision.

2. Score and decision summary
   - Final risk score, model signal, deterministic rule signal, scoring-time decision.

3. Intelligence evidence groups
   - Legacy/base, rich, behavioural, graph, and scenario/contextual evidence sections.

4. AI investigation report
   - Existing recommendation, confidence, risk factors, mitigation, rules, playbooks, policies,
     and rationale fields.

5. Timeline and workflow events
   - Transaction, investigation, workflow, verdict, and promotion events when available.

6. Analyst decision panel
   - Verdict capture, notes, reviewed timestamp, and current verdict state.

7. Promotion/source context
   - Source scan and row provenance if available through existing or later approved read-only
     APIs.

---

## Out of Scope

Phase 17A explicitly excludes:

- Scoring changes.
- Model changes.
- Threshold changes.
- Graph boost changes.
- Behavioural boost changes.
- Reason-code taxonomy changes.
- AI investigation prompt or schema hardening.
- Authentication or RBAC.
- Deployment work.
- GitHub push or release packaging.
- Large scans.
- Database schema changes.
- Backend source code changes.
- Frontend source code changes.

---

## Proposed Phase 17 Sub-Slices

| Slice | Name | Scope |
|---|---|---|
| 17A | Case Dossier 2.0 design contract and evidence inventory | Documentation only. Defines evidence model, gaps, and guardrails. |
| 17B | Backend/API readiness audit or read-only dossier enrichment checkpoint | Decide whether existing APIs are enough or whether a read-only enrichment endpoint is needed. |
| 17C | Frontend dossier layout and grouped evidence display | Upgrade `/cases/[id]` to show grouped evidence and score summary using available data. |
| 17D | Timeline/workflow/promotion evidence integration | Add lifecycle timeline and source context where available. |
| 17E | Validation and close-out | Build, visual inspection, route checks, documentation update, and freeze decision. |

---

## Validation Strategy

For Phase 17A:

- Documentation review only.
- `git diff --stat`.
- `git status --short`.

For later implementation slices:

- Frontend build.
- E2E or smoke test for `/cases/[id]`.
- API contract test if a read-only endpoint is added.
- No legacy 10k regression unless backend scoring or source logic changes.
- No scans unless explicitly approved for a later slice.

---

## Guardrails

- Do not create a fake score breakdown.
- Do not invent unavailable evidence.
- Do not hide missing fields; show unavailable evidence honestly.
- Keep AI brief hardening for Phase 18.
- Keep auth, observability, durable workers, and RBAC for Phase 19.
- Keep deployment, GitHub release, and portfolio packaging for Phase 20.
- Do not push to GitHub during Phase 17A.
- GitHub push was not performed.

---
