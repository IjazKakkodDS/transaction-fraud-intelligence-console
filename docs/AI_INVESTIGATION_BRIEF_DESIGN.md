# AI Investigation Brief Design Contract - Phase 18A

**Status:** Design contract only. No investigation code, prompts, schemas, APIs, frontend,
scoring, or database changes are included in this document or in Phase 18A.

---

## 1. Purpose

Phase 18 hardens the AI investigation brief so the analyst-facing AI explanation aligns with
the current fraud intelligence stack -- rich signals (Phase 12), behavioural intelligence
(Phase 13), graph / mule-network intelligence (Phase 15), adversarial learnings (Phase 16),
and the Case Dossier 2.0 evidence presentation (Phase 17).

The investigation pipeline was built in Phase 3, before any of these intelligence layers
existed. It still reasons over a narrow, legacy-era evidence slice. Phase 18's job is to close
that gap in what the AI **sees**, **validates**, and **says** -- not to change what the system
**computes**.

**Phase 18 changes:**
- What evidence is gathered and handed to the LLM (deterministic tools, feature breakdown).
- How that evidence is structured, labeled, and explained in the prompt.
- What shape and sections the output report takes.
- How failures, retries, and stale or incomplete evidence are handled and surfaced.

**Phase 18 must not change:**
- Scoring (`base_score`, `rich_signal_boost`, `behavioural_boost`, `graph_boost`, caps).
- Thresholds (decision thresholds APPROVE/REVIEW/BLOCK; tier thresholds P0-P3).
- Model outputs (`model_prediction`, `risk_score`).
- Deterministic fraud rules (`apply_fraud_rules`).
- Graph or behavioural boost computation or weighting.
- Reason-code generation or the locked reason-code taxonomy (`generate_reasons` and the
  `extract_*_reason_codes` family in `src/features/transaction_features.py`).

If an AI investigation slice ever appears to require a scoring, rule, boost, threshold, or
taxonomy change, that is a signal the slice has drifted out of Phase 18 scope and must be
deferred to a separate, explicitly approved checkpoint.

---

## 2. Current Pipeline

The investigation pipeline is a complete, working four-step agentic loop, unchanged since
Phase 3 (`AGENT_VERSION = "0.1.0"`):

```
InvestigationRequest (case_id, investigation_id)
  |
  |-- service.py    Step 1: get_prediction_by_id(case_id)            -> case dict from Postgres
  |-- tools.py      Step 2: get_rule_explanations() + get_feature_breakdown()
  |-- retriever.py  Step 3: build_query() + retrieve_knowledge()      -> top-k playbook docs (TF-IDF RAG)
  |-- reasoner.py   Step 4: generate_summary()                        -> LLM structured JSON (Ollama)
  |
  +-- InvestigationReport (status = COMPLETE | FAILED) -> log_investigation() -> investigations table
```

**`service.py` (orchestration):** `process_case()` is the single entry point invoked by the
Kafka consumer (`consumer.py`, topic `cases.investigate`, group `investigation-service`). It
fetches the base case, calls the deterministic tools, runs RAG retrieval, calls the LLM
reasoner, and assembles the final `InvestigationReport`. Returns a `FAILED` report immediately
if the case does not exist, and a `FAILED` report with deterministic fields preserved if LLM
reasoning raises.

**`tools.py` (deterministic evidence extraction):** Two fully working tools --
`get_rule_explanations(rule_flag, reasons)` (maps short reason tokens to human-readable
explanations via a fixed `_reason_explanation` lookup table) and `get_feature_breakdown(case)`
(derives `hour_of_day`, `is_night_transaction`, `amount`, `high_amount_threshold`,
`amount_vs_threshold`, `risk_score`). Three DB-backed tools --
`get_transaction_history`, `get_user_profile`, `get_merchant_profile` -- are honest
schema-limited placeholders: the `predictions` table has no `user_id`/`merchant_id` columns,
so they detect the limitation, log a warning, and return a structured `available: False`
response rather than raising or fabricating data.

**`retriever.py` (local TF-IDF RAG):** Loads `.txt` playbooks from `data/knowledge/` (6 files
covering account takeover, CNP fraud, false-positive indicators, high-amount fraud, night
transactions, velocity), builds a TF-IDF + cosine-similarity vector store lazily and caches it
for the process lifetime, and returns the top-ranked snippets with `{source, content, score}`.
No external embeddings API.

**`reasoner.py` (local Ollama call):** `generate_summary()` builds a compact prompt (`## CASE`,
`## RULES TRIGGERED`, `## FEATURES`, `## PLAYBOOK KNOWLEDGE`) and POSTs it to a local Ollama
instance (`OLLAMA_BASE_URL`, default `mistral:latest`, temperature 0, `num_ctx=2048`,
`num_predict=300`, `OLLAMA_TIMEOUT=300`). The response must be a JSON object with seven required
keys; `_validate()` checks key presence, enum membership (`recommendation`,
`confidence`), and list types. On parse/validation failure the prompt is retried up to
`MAX_RETRIES = 2` additional times with the previous error appended so the model can
self-correct; connection errors (`URLError`/`OSError`) propagate immediately (not retried at
this layer -- the consumer's offset-management policy handles redelivery).

**Persisted `InvestigationReport`:** Written to the `investigations` table via
`log_investigation()` (see `alembic/versions/0003_create_investigations_table.py`). Every field
in `schemas.py::InvestigationReport` is populated on success.

**API endpoints (`src/api/main.py`):**
- `POST /cases/{case_id}/investigate` (202) -- validates the case exists, assigns a UUID
  `investigation_id`, and publishes an `InvestigationRequest` to `cases.investigate`. Returns
  404 if the case does not exist, 503 if Kafka is unreachable.
- `GET /cases/{case_id}/investigation` -- returns the latest report: 200 with the full row when
  `COMPLETE`, `{"status": "FAILED", "error_message": ...}` when `FAILED`, `{"status":
  "IN_PROGRESS"}` (HTTP 202) when in progress, 404 when no investigation has ever been
  triggered for the case.

**`InvestigationPanel.tsx` (frontend rendering):** Polls `useInvestigation` (3s interval while
`IN_PROGRESS`, plus a client-side post-trigger polling window since the backend rarely persists
an `IN_PROGRESS` row). Renders four states: empty/no-report (with a "Run AI Investigation"
button), in-progress (spinner), `FAILED` (red banner with `error_message` if present, plus a
"Retry Investigation" button), and `COMPLETE` (`CompleteReport`: recommendation/confidence
badges, `DeterministicContext` grid for `transaction_count_30d`/`amount_percentile`/
`merchant_seen_before`, summary, then `Risk Factors` / `Mitigating Factors` / `Rules Triggered`
/ `Playbooks` / `Policies` / `Rationale` / `Confidence Rationale` rows, each rendered with
`TagList` + `normalizeStringList` and `toTitleCase`).

**Current agent version:** `AGENT_VERSION = "0.1.0"` (`src/investigation/service.py`), stored on
every persisted report. The module docstring states it should be incremented "whenever a change
affects the meaning of report output (prompt revision, tool change, model version change)."

---

## 3. Current Evidence Inputs

What the LLM prompt and the persisted report currently contain, sourced from the `predictions`
row and the deterministic tools:

| Evidence | Source | Notes |
|---|---|---|
| `transaction_id` | case row | Raw passthrough |
| `amount` | case row | Raw passthrough |
| `risk_score` | case row | Raw passthrough |
| `decision` | case row | Raw passthrough |
| `rules_triggered` | `get_rule_explanations(rule_flag, reasons.split("|"))` | Maps known legacy tokens via a fixed ~10-entry lookup table; unknown tokens pass through unchanged (see Section 4) |
| `feature_breakdown` | `get_feature_breakdown(case)` | `hour_of_day`, `is_night_transaction`, `amount`, `high_amount_threshold`, `amount_vs_threshold`, `risk_score` only |
| RAG snippets | `retrieve_knowledge(query)` | Top-2 playbook excerpts (truncated to 500 chars) injected into the prompt; `playbooks_referenced` records the source file stems |
| `policies_referenced` | schema field | **Structurally always empty** -- no policy corpus exists in `data/knowledge/` or elsewhere; nothing populates this list anywhere in the pipeline |
| `transaction_count_30d`, `amount_percentile`, `merchant_seen_before` | schema fields | Always `None` -- populated only if `get_transaction_history`/`get_user_profile`/`get_merchant_profile` ever return real data, which requires a schema migration that has not happened |

The `case` dict fetched from Postgres contains only the `predictions` table's columns:
`transaction_id`, `amount`, `timestamp`, `rule_flag`, `model_prediction`, `risk_score`,
`decision`, `reasons`, `analyst_status`, `analyst_notes`, `reviewed_at` (plus identity columns).
It does **not** carry persisted `rich_signal_boost`, `behavioural_boost`, `graph_boost`, or
`scenario_family` values -- those are computed at scoring time and folded into `risk_score`,
not stored as separate columns (confirmed in the Phase 17C dossier audit: "No exact rich,
behavioural, or graph contribution values are claimed because component boosts are not
persisted on case rows").

---

## 4. Current Gaps

1. **Legacy-only `_reason_explanation` mapping.** The lookup table in `tools.py` recognizes
   roughly ten Phase-3-era reason strings (`"High transaction amount"`, `"Velocity spike"`,
   `"New merchant"`, etc.). Any token not in the table is returned unchanged -- which is the
   honest fallback, but means the LLM sees raw codes with no explanation for everything added
   since.
2. **Rich-signal reason codes not explained clearly.** Phase 12's rich-signal phrases (e.g.
   "Unrecognised device with low trust score", "Geographic location inconsistent with
   registered address") pass through `_reason_explanation` unchanged -- they are already
   human-readable strings, but the AI brief does not group or label them as "Rich Signal
   evidence" the way the Case Dossier UI now does.
3. **Behavioural reason codes not explained clearly.** Phase 13's `BEHAVIOURAL_*` /
   `BALANCE_DROP_ANOMALY` / `NEW_DEVICE_FOR_CUSTOMER` / etc. ALL_CAPS codes reach the LLM as raw
   tokens with no plain-language mapping or grouping.
4. **Graph reason codes not explained clearly.** Phase 15's `SHARED_DEVICE_CLUSTER`,
   `DEVICE_ACCOUNT_REUSE`, `MULE_FAN_IN_PATTERN`, `MULE_FAN_OUT_PATTERN` codes reach the LLM as
   raw tokens with no explanation of what a mule-network or shared-device pattern means for an
   analyst's recommendation.
5. **Scenario / context codes not explained clearly.** `scenario_family` values (rich, dirty,
   adversarial, graph-evasion, etc.) and the `is_rich_fraud_scenario` synthetic-data marker are
   not surfaced to the LLM at all, even though they materially affect `risk_score` for
   synthetic/benchmark rows and could mislead an AI narrative that doesn't know it's looking at
   a labeled scenario row.
6. **Boost blindness.** `rich_signal_boost`, `behavioural_boost`, and `graph_boost` -- the very
   signals that the Case Dossier UI now groups and color-codes for analysts (Phase 17C) -- are
   not persisted on case rows and therefore cannot be handed to the LLM as structured evidence.
   The AI brief is reasoning with strictly less structure than the analyst sees on the same
   screen.
7. **`policies_referenced` is structurally empty.** The schema field and prompt section exist,
   but no policy corpus is loaded anywhere -- the field will be `[]` on every report until a
   policy knowledge base is created (out of scope for Phase 18 unless separately approved).
8. **Schema-limited placeholder tools.** `get_transaction_history`, `get_user_profile`, and
   `get_merchant_profile` correctly detect that `user_id`/`merchant_id` columns don't exist and
   return honest `available: False` stubs. This is good behavior, but it means
   `transaction_count_30d`, `amount_percentile`, and `merchant_seen_before` are always `None`,
   and `DeterministicContext` in the frontend never renders.
9. **Failure path gives limited analyst context.** A `FAILED` report carries
   `error_message` (a raw exception string) plus whatever deterministic fields were gathered
   before the failure. There is no structured distinction between "LLM unreachable", "LLM
   returned malformed JSON after all retries", "case not found", etc. -- the analyst sees one
   undifferentiated red banner.
10. **Connection-error handling needs a clearer policy.** `_call_ollama` raises
    `URLError`/`OSError` directly out of `generate_summary`; `service.py` catches `Exception`
    broadly and returns a `FAILED` report. This works, but conflates "Ollama is down" (an
    infrastructure condition the consumer should perhaps redeliver) with "the model produced
    garbage three times in a row" (a content condition that should not be retried at the broker
    level). The two are not currently distinguished in the persisted report or surfaced
    differently to the analyst.
11. **Stale or incomplete evidence handling is not formalized.** There is no defined policy for
    what should happen when an analyst views an investigation report that was generated before
    a case was re-scored, re-reviewed, or re-promoted, or when deterministic evidence was
    partially gathered before a failure. The UI currently shows whatever was persisted with no
    "this may be stale" signal.

---

## 5. Locked Evidence Taxonomy Alignment

The Case Dossier 2.0 (`CaseEvidenceGroups`, Phase 17C) and the Risk Scan drawer
(`ScanResultDrawer`, Phase 15F) already group and color-code reason codes into a locked
taxonomy that analysts see on screen:

- **Base / Transaction Signals** (legacy red-chip group + ungrouped/unknown reasons)
- **Rich Signals** (amber)
- **Behavioural Signals** (blue/teal, `#93C5FD`)
- **Graph Intelligence** (violet, `#A78BFA`)
- **Scenario Context** (`scenario_family` / synthetic-data labels)

Phase 18 should map the AI brief's evidence presentation onto these *same* group names and
plain-language descriptions, so an analyst reading the AI summary recognizes the same evidence
groups they see in the dossier evidence chips -- creating one coherent vocabulary across the
product rather than two parallel ones.

**This is a presentation-layer alignment only:**
- Do **not** redefine, rename, reorder, or re-color the reason-code taxonomy itself.
- Do **not** modify `generate_reasons()`, `extract_*_reason_codes()`, or any function that
  produces or classifies reason codes.
- Only add a mapping layer (in the AI evidence-gathering / prompt-assembly code, in a later
  slice) that takes the *existing* codes and groups/labels them the same way the frontend
  already does, for the LLM's and analyst's benefit -- e.g. reusing the same group names as
  `classifyCaseEvidence` / `GRAPH_REASON_SET` / `BEHAVIOURAL_CODES` already establish on the
  frontend, mirrored in Python for the prompt.

---

## 6. Desired Investigation Brief Structure

A hardened brief should have clearly delineated, consistently ordered sections so analysts can
scan it the same way every time. Proposed structure (for a later implementation slice --
**not implemented in 18A**):

1. **Executive summary** -- 2-4 sentence narrative (existing `summary` field, retained).
2. **Key risk drivers** -- the strongest signals behind the score, ranked (refines
   `risk_factors`).
3. **Evidence groups observed** -- reason codes grouped and labeled per Section 5 (Base /
   Rich / Behavioural / Graph / Scenario), each with a plain-language one-line explanation,
   replacing the current flat `rules_triggered` list with something that mirrors the dossier's
   own grouping.
4. **Behavioural / graph / contextual findings** -- a dedicated narrative passage (or
   structured sub-list) specifically calling out behavioural-profile, mule-network/graph, and
   scenario-context findings when present, since these are exactly the signal types the legacy
   prompt cannot currently explain.
5. **Recommended analyst actions** -- a short, constrained action list distinct from the
   existing `recommendation` enum (e.g. "verify device fingerprint", "cross-check counterparty
   cluster") -- optional, evaluated in 18B against whether it adds analyst value beyond the
   existing recommendation/rationale fields.
6. **Missing or unavailable evidence** -- an explicit, honest list of evidence the brief wanted
   but could not obtain (e.g. "transaction history unavailable -- schema does not persist
   user_id"), turning today's silent `None` fields into a stated limitation.
7. **Confidence / limitations** -- existing `confidence` + `confidence_rationale`, extended to
   reference any "missing evidence" items that bound the confidence level.
8. **Playbooks (and policies, if ever populated) referenced** -- existing
   `playbooks_referenced` / `policies_referenced`, retained, with an honest empty-state label
   when `policies_referenced` is `[]` (see Gap 7).
9. **Generated metadata** -- `investigation_id`, `investigated_at`, `agent_version`, `status`,
   surfaced consistently so analysts can tell which pipeline version produced a given report
   (important once `agent_version` starts incrementing again under Phase 18).

No implementation, schema change, or prompt change is made in 18A. This section exists so 18B
has an agreed target shape to design the concrete schema/prompt delta against.

---

## 7. Failure / Retry / Stale Evidence Policy

Desired policy directions for a later implementation slice (**not implemented in 18A**):

- **LLM unavailable (connection error):** Treated as an infrastructure condition. The
  `FAILED` report (or a new distinguishing status/sub-state) should make clear this is a
  *connectivity* failure, not a *content* failure, so analysts and operators read it
  differently from "the model couldn't produce valid output."
- **Malformed JSON / schema validation failure:** Treated as a content condition. Continue
  retrying within `generate_summary` (current `MAX_RETRIES = 2` behavior is sound) but make the
  final persisted `FAILED` report state clearly that this was a *model output* problem, not an
  infrastructure problem, and preserve the last raw response (or a bounded excerpt) for
  diagnosis if not already captured.
- **Partial deterministic evidence:** When some tools succeed and others fail or return
  `available: False`, the report should say so explicitly rather than silently presenting
  `None`/`[]` -- this is largely a presentation change building on the existing honest
  placeholder-tool behavior (Gap 8), not a new tool capability.
- **Empty RAG context:** When `retrieve_knowledge` returns no relevant playbook snippets, the
  brief should say "no matching playbook guidance found" rather than silently omitting the
  section -- distinguishing "we looked and found nothing relevant" from "we have nothing to
  look in."
- **Stale persisted investigation vs. case update:** If a case has been re-scored, re-reviewed,
  or its `reasons`/`risk_score`/`analyst_status` has changed since `investigated_at`, the
  brief/UI should be able to signal "this report may be stale relative to the current case
  state" -- *if and only if* this is detectable from already-persisted, comparable timestamps
  (e.g. comparing `investigated_at` against the case's own update markers). No new "case
  updated_at" column should be added to make this detectable; the policy should be scoped to
  what is honestly comparable today, and explicitly marked deferred if nothing comparable
  exists.
- **`FAILED` report behavior:** Continue persisting deterministic fields gathered before
  failure (current behavior is good and should be preserved/extended, not replaced).
- **Analyst-visible failure message boundaries:** `error_message` should remain a bounded,
  non-sensitive, analyst-readable string -- never a raw stack trace or internal exception
  repr beyond what's useful for triage. The current `str(exc)` passthrough should be reviewed
  in 18C for whether it ever leaks internal detail that should be summarized instead.

---

## 8. Database and Schema Boundaries

- **No database migrations in Phase 18** unless a future sub-slice is separately scoped,
  proposed, and approved through its own checkpoint.
- **Do not add columns just to support the placeholder tools.** `get_transaction_history`,
  `get_user_profile`, and `get_merchant_profile` remain honest, schema-limited stubs through
  Phase 18. Their `available: False` responses are the correct behavior for the current schema
  and should continue to be surfaced honestly (per Section 7), not worked around.
- **Use existing persisted fields wherever possible.** Any evidence-expansion work in 18B
  should draw from columns and reason codes that already exist in `predictions` /
  `investigations` (e.g. the full `reasons` string, which already encodes rich/behavioural/
  graph/scenario information as text) rather than proposing new storage.
- **Any future schema change request is its own checkpoint**, separate from and subsequent to
  Phase 18, requiring explicit owner approval before any migration file is written.

---

## 9. Frontend Boundaries

- `InvestigationPanel.tsx` may be aligned **later, only if** new report fields are added in
  18B/18C that warrant display (Section 10, slice 18D) -- no frontend change occurs in 18A or
  is assumed to occur automatically alongside backend work.
- The existing Case Dossier 2.0 layout (Phase 17A-17E: `CaseHeader`, `CaseScoreSummary`,
  `CaseEvidenceGroups`, `CaseTimeline`, `InvestigationPanel`, `AnalystActionPanel`,
  `WorkflowNotifyButton`, `CaseWorkflowEvents`) must be preserved as-is; Phase 18 does not
  rearrange or duplicate dossier sections.
- **Do not duplicate score/evidence sections already handled by Phase 17.** `CaseEvidenceGroups`
  already groups and color-codes reason codes for the analyst; the AI brief's evidence grouping
  (Section 5/6) is for the *AI's narrative text*, not a second on-screen evidence-chip display.
  If 18D ever renders structured evidence groups inside `InvestigationPanel`, it must visually
  and semantically complement -- not duplicate -- `CaseEvidenceGroups`.
- **Display missing evidence honestly.** Any new "missing or unavailable evidence" content
  (Section 6, item 6) must follow the same honesty convention already established across the
  dossier (e.g. `DeterministicContext`'s `hasContext` guard, `CaseTimeline`'s hidden-event
  behavior) -- show clearly that something is unavailable rather than rendering blank space or
  fabricated values.

---

## 10. Proposed Phase 18 Sub-slices

| Slice | Purpose | Likely files | Validation | Guardrails |
|---|---|---|---|---|
| **18A** | AI Investigation Brief Hardening Design Contract (this document) | `docs/AI_INVESTIGATION_BRIEF_DESIGN.md`, `docs/PRODUCT_STAGES.md` | Doc review; `git diff --check`/`--stat`/`status` | Documentation only; no code, prompt, schema, API, frontend, scoring, or DB changes; no Ollama calls; no scans |
| **18B** | Evidence / Prompt / Schema Contract Update -- expand `tools.py` evidence gathering to surface rich/behavioural/graph/scenario reason groups (via a Python-side mirror of the frontend's grouping, per Section 5); restructure the `reasoner.py` prompt and `InvestigationReport` schema toward the Section 6 structure; bump `AGENT_VERSION` | `src/investigation/{tools.py, reasoner.py, schemas.py}`, possibly `service.py` | Python compile checks; in-process smoke test of `process_case`/`generate_summary` against known cases (mocked or live-Ollama-if-available); no live-Ollama dependency required to pass | No scoring/rule/boost/threshold/taxonomy changes; reuse existing `reasons` string and persisted columns only; no DB migration |
| **18C** | Failure, Retry, and Stale Evidence Handling -- implement the Section 7 policy: distinguish infrastructure vs. content failures, honest partial-evidence/empty-RAG messaging, stale-report signaling if honestly detectable | `src/investigation/{service.py, reasoner.py, consumer.py}`, possibly `schemas.py` | Python compile checks; targeted failure-path smoke tests (simulated connection error, malformed JSON, case-not-found, partial tools); no live-Ollama dependency required | No new "stale" detection requiring schema changes; preserve current offset-commit/redelivery semantics in `consumer.py` unless explicitly re-scoped |
| **18D** | Frontend Investigation Panel Alignment -- display any new 18B/18C report fields honestly in `InvestigationPanel.tsx` (and `types/investigation.ts`), preserving existing layout and Phase 17 dossier structure | `fraud-console/components/cases/InvestigationPanel.tsx`, `fraud-console/types/investigation.ts`, possibly `fraud-console/tests/case-dossier.spec.ts` | `npm run build`, `npm run test:e2e` (expect existing pass count plus any new assertions); mobile/no-overflow check if layout changes | No duplication of `CaseEvidenceGroups`/`CaseTimeline`; no risk-scan drawer changes; no dossier rearrangement |
| **18E** | Validation and Close-Out -- compile checks, in-pipeline smoke verification, full frontend build/E2E if 18D touched the frontend, `docs/PRODUCT_STAGES.md` close-out, mark Phase 18 Complete | `docs/PRODUCT_STAGES.md` (and any close-out evidence script under `scripts/` if one was added in 18B/18C) | Full re-run of whichever validations 18B-18D introduced; `git diff --check`/`--stat`/`status` | Documentation/verification only; no new functional changes; no scans; no Phase 19 start |

---

## 11. Validation Strategy

For Phase 18A (this slice): documentation review only --
`git diff --check`, `git diff --stat`, `git status --short`. No code, build, test, or scan
commands apply.

For later implementation slices (18B-18D):
- **Python compile checks** (`python -m py_compile ...`) for every touched investigation module.
- **A targeted investigation smoke script or in-process verification** that exercises
  `process_case()` / the deterministic tools / the prompt-assembly path against known case rows
  -- mirroring the in-memory verification pattern already proven in
  `scripts/verify_adversarial_detection.py` (import production functions directly, no API/DB
  network dependency beyond Postgres read access).
- **Avoid a live-Ollama dependency** wherever possible -- prefer mocking/stubbing
  `generate_summary`'s LLM call boundary so validation can run without a local Ollama instance;
  if a live call is exercised, it must be explicitly called out as optional, environment-
  dependent evidence.
- **Frontend build/E2E only when frontend or `types/investigation.ts` change** (18D) --
  `npm run build` + `npm run test:e2e`, expecting the existing 11/11 pass count to remain green
  plus any new investigation-specific assertions.
- **No legacy 10k regression** unless a slice changes scoring or `src/features/` /
  `src/rules/` / `src/triage/` source logic -- which Phase 18 must not do. The investigation
  pipeline runs after and independently of scoring; it does not feed back into `risk_score`,
  `decision`, or reason codes.

---

## 12. Explicit Out-of-Scope

The following are explicitly out of scope for all of Phase 18 (18A-18E) and remain owned by
their respective phases or require a separate, explicitly approved checkpoint:

- Scoring changes (model weights, `base_score`, boost formulas, score caps).
- Model changes (XGBoost model artifact, feature engineering for scoring).
- Threshold changes (decision thresholds APPROVE/REVIEW/BLOCK; tier thresholds P0-P3).
- `graph_boost` changes (computation, weighting, cap).
- Behavioural boost changes (computation, weighting, cap).
- Reason-code generation or taxonomy changes (`generate_reasons`, `extract_*_reason_codes`,
  reason-code colors/grouping definitions).
- Adversarial generator/verifier changes (`scripts/generate_adversarial_csv.py`,
  `scripts/verify_adversarial_*.py`).
- Risk-scan drawer changes (`fraud-console/components/risk-scan/ScanResultDrawer.tsx`).
- Database migrations / schema changes (owned by a separate, explicitly approved checkpoint;
  see Section 8).
- Deployment work (Phase 20).
- Auth/RBAC/observability work (Phase 19).
- GitHub push (remains deferred indefinitely per project convention; not performed in any
  Phase 18 slice).
