# MLOps Readiness — Fraud Intelligence Console

---

## 1. Purpose

This document describes the MLOps maturity level of the Fraud Intelligence Console and
defines the controls implemented, the release gates enforced, and the enterprise expansion
path not yet taken. It is written for engineering leads, data science reviewers, and risk
architecture reviewers who want to understand the operationalisation posture of the
platform before assessing it for institution-specific deployment.

The target maturity for this release is **L2+ / L2.5** — release engineering, artifact
governance, and CI validation are implemented. Full enterprise L3 (MLflow experiment
tracking, feature store, automated retraining, canary deployment, production drift
monitoring) is explicitly deferred and documented as a future roadmap — not a hidden gap.

---

## 2. Current Maturity Summary

| Domain | Maturity | Notes |
|---|---|---|
| Product and Application Engineering | L2+ | 4-layer scoring engine, 7-service Docker Compose runtime, 27 API endpoints, 11/11 E2E Playwright checks |
| Release Engineering | L2+ | GitHub Actions CI (compile, release readiness checks, model load, evidence smoke checks, frontend build), local E2E gate |
| Model Artifact Governance | L2+ | Artifact tracked in git, MD5 checksum documented, MODEL_CARD.md, deterministic rebuild path, feature schema validation at CI |
| Model Lifecycle Automation | L2 | Manual retrain path documented and tested (deterministic, seed 42); no automated retraining trigger or drift-detection gate |
| Full Enterprise MLOps (L3) | Future | MLflow, feature store, drift monitoring, A/B deployment, canary rollout — documented as future roadmap |

---

## 3. Implemented Controls

### Release Engineering
- **GitHub Actions CI** (`.github/workflows/ci.yml`): two parallel jobs on every push and
  pull request to `master`/`main`
- **Python compile check**: `python -m compileall src/ -q` — catches syntax errors across
  the full backend package before any test or validator runs
- **Release readiness validator** (`scripts/verify_release_readiness.py`):
  required files, model artifact loadability, MD5 checksum, 12 screenshot checks, old
  filename absence, secret/generated artifact hygiene, required tracked artifact presence,
  and stale phrase scan across public-facing docs
- **Model load verification in CI**: `joblib.load` + type check on every CI run
- **Investigation smoke checks in CI**: `verify_investigation_failure.py` and
  `verify_investigation_evidence.py` — no Ollama, no DB, no network required
- **Frontend production build in CI**: `npm ci` + ESLint + `next build --webpack`
- **Local E2E release gate**: `npm run test:e2e` (11 checks, headless Chromium) against the
  live Docker Compose stack — documented as the required pre-push local gate

### Model Artifact Governance
- **Artifact tracked in git**: `saved_models/fraud_model.pkl` tracked via `.gitignore`
  exception — small (≈106 KB), deterministic, required for fresh-clone Docker runtime
- **Checksum registry**: MD5 `887033d57056c6a22480c0b9cea202ca` documented in
  `docs/MODEL_CARD.md` and verified in CI on every run
- **Feature schema contract**: 9 expected features stored in `model.feature_names_in_`;
  verified against the expected list in the release readiness validator
- **MODEL_CARD.md**: 8-section model card covering model overview, artifact details,
  feature schema, training configuration, data contract, decision system context,
  limitations and deployment boundary, and governance/reproducibility record
- **Deterministic rebuild path**: generator (`seed 42`) + trainer (`random_state=42`)
  produce an identical artifact on any platform with the tracked package versions
- **Generator source tracked**: `data/synthetic/generate_transactions.py` tracked via
  `.gitignore` exception; generated CSV gitignored

### Model Explainability
- **Per-case model attribution**: `GET /cases/{case_id}/explain` returns per-feature
  contribution values using XGBoost's built-in TreeSHAP (`pred_contribs=True`) — no
  external `shap` library required; XGBoost is already a required dependency
- **Attribution scope**: baseline XGBoost model only; contributions are in log-odds space
- **Case Dossier integration**: "Model Attribution" panel displays all 9 feature contributions
  ranked by magnitude, with direction (increases/decreases risk) and the feature value used
- **Governance boundary**: read-only diagnostic surface; does not modify the model, scoring
  formula, risk_score, decision, or any stored record
- **Honest reconstruction disclosure**: features not stored in the prediction table are
  inferred from reason codes or defaulted to 0; the response `inferred_fields` list names
  each such field so reviewers can assess per-case attribution accuracy
- **Separation from hybrid reason codes**: attribution explains the base ML model; the hybrid
  reason codes in the Case Dossier evidence groups explain the full 4-layer decision (rules,
  rich signals, behavioural, graph) — these are distinct explainability surfaces

### Audit and Traceability
- **AGENT_VERSION traceability**: every AI investigation record tagged with the agent
  configuration version — immutable AI audit trail in PostgreSQL
- **Analyst-in-the-loop enforcement**: no autonomous decision enforcement; analyst verdict
  required before any operational action
- **Consumer offset governance**: asymmetric durability design documented in
  `docs/CONSUMER_DURABILITY.md`
- **Workflow audit trail**: every automation dispatch and callback produces a durable,
  queryable audit event with case linkage

### Governance Documentation
- `docs/MODEL_CARD.md` — model artifact contract and feature schema
- Security and access-control hardening — documented as a recommended production expansion path
- `docs/CONSUMER_DURABILITY.md` — consumer offset management and idempotency design
- `docs/AUTH_RBAC_DESIGN.md` — RBAC architecture and implementation prerequisites
- `docs/AI_INVESTIGATION_BRIEF_DESIGN.md` — AI pipeline architecture and evidence contract

---

## 4. Model Lifecycle

The model lifecycle for this release follows a controlled, manual path:

```
1. Synthetic data generation
   data/synthetic/generate_transactions.py  (seed 42, 1,000 rows, 8% fraud)

2. Model training
   python -m src.models.train_model         (random_state=42, 100 estimators, XGBoost)

3. Artifact output
   saved_models/fraud_model.pkl             (≈106 KB, tracked in git)

4. Checksum verification
   MD5 887033d57056c6a22480c0b9cea202ca     (verified in CI on every run)

5. Docker packaging
   docker compose build                     (COPY copies pkl into container image)

6. CI gate
   verify_release_readiness.py              (checks including artifact and checksum)

7. Local E2E gate
   npm run test:e2e                         (11 Playwright checks against live stack)
```

The model is one component of the broader 4-layer hybrid scoring engine. It produces
a base probability estimate; the final `risk_score` combines this with deterministic
rule signals, rich-feature boosts, behavioural intelligence boosts, and graph
intelligence boosts before a decision tier is assigned.

---

## 5. What This Release Is Not Claiming

The following controls are **not** implemented in this release. They are identified as
enterprise expansion controls — appropriate for institution-specific deployment — not as
hidden gaps in the current release.

| Control | Status | Notes |
|---|---|---|
| MLflow experiment tracking | Not implemented | Manual artifact governance via MODEL_CARD.md and git tracking |
| Feature store | Not implemented | Feature engineering in `src/features/transaction_features.py`; no external feature registry |
| Automated retraining | Not implemented | Manual rebuild path documented and deterministic; no trigger or schedule |
| Drift monitoring | Not implemented | No production transaction stream; synthetic benchmark environment |
| Canary deployment | Not implemented | Single-instance Docker Compose; no traffic splitting |
| A/B model comparison | Not implemented | Single baseline artifact; no shadow scoring infrastructure |
| Prometheus / Grafana / OpenTelemetry | Not implemented | Application-layer reliability metrics via PostgreSQL; no metrics server |
| GPU-accelerated training | Not applicable | XGBoost CPU baseline on synthetic 1,000-row dataset |

These are identified enterprise expansion controls. Documenting them explicitly is the
governance-correct approach: a reviewer can assess what is and is not implemented without
inferring gaps from omissions.

---

## 6. Future L3 Roadmap

Institution-specific deployment would expand MLOps controls across:

| Control | Description |
|---|---|
| Model registry | MLflow or equivalent; track experiment runs, parameters, metrics, and artifact versions |
| Feature store | Centralised feature computation and serving for base, behavioural, and graph layers |
| Retraining pipeline | Triggered by drift signal or scheduled cadence; produces versioned artifact |
| Drift monitoring | Statistical distribution tracking against a production transaction baseline |
| Shadow scoring | New model version scores in parallel before promotion; comparison against current model |
| Canary deployment | Graduated traffic promotion with automated rollback on quality degradation |
| Monitoring stack | Prometheus metrics export, Grafana dashboards, OpenTelemetry instrumentation |
| Model-risk review | Formal institution-specific review, threshold calibration, and regulatory approval gate |

None of these are prerequisites for the current release boundary (localhost, synthetic
data, portfolio demonstration). All are required for institution-grade regulated deployment.

---

## 7. Why the Current Release Is Strong at Its Target Maturity

This release operates at a well-defined boundary: a controlled local product environment,
synthetic benchmark data, and a portfolio-grade demonstration of a production-style fraud
intelligence architecture. Within that boundary, the MLOps controls are complete:

- Every CI run validates the model artifact, checksum, feature schema, and full release
  readiness in under 3 minutes — before any code reaches the default branch
- The model artifact is small, deterministic, and reproducible from tracked source in a
  single command sequence — no download step, no external registry dependency
- The governance documentation package is written for the deployment reviewers who will
  expand these controls: engineering leads, compliance teams, and risk architecture teams
- The analyst-in-the-loop enforcement design (no autonomous decision enforcement) is
  the correct architecture for a regulated fraud decisioning context regardless of
  deployment scale

The L2+/L2.5 maturity target is not a limitation — it is an accurate, defensible
description of a release that is production-style in architecture, benchmark-validated
in performance, and governance-ready in documentation.

---

## 8. Release Gates

Before every push to the default branch, all of the following must pass:

| Gate | Command | Scope |
|---|---|---|
| Python compile | `python -m compileall src/ -q` | All backend source files |
| Release readiness | `python scripts/verify_release_readiness.py` | 41 checks: files, model, checksums, screenshots, hygiene, stale phrases |
| Model load | `joblib.load('saved_models/fraud_model.pkl')` | Artifact integrity |
| Investigation smoke | `python scripts/verify_investigation_failure.py` | Failure classification contract |
| Evidence smoke | `python scripts/verify_investigation_evidence.py` | Evidence grouping contract |
| Frontend lint | `cd fraud-console && npm run lint` | ESLint across frontend source |
| Frontend build | `cd fraud-console && npm run build` | Full Next.js production bundle |
| E2E Playwright | `cd fraud-console && npm run test:e2e` | 11 checks against live stack (local gate — requires Docker Compose) |

CI (`.github/workflows/ci.yml`) automates all gates except E2E, which requires the full
Docker Compose stack. E2E is the local pre-push gate.

---

## 9. Conclusion

The Fraud Intelligence Console implements release engineering and artifact governance
controls appropriate for its deployment boundary. CI validates model integrity and
release readiness on every commit. The model artifact is tracked, checksummed, and
documented. The governance path to enterprise L3 MLOps is explicitly mapped.

This is a production-style fraud decision intelligence system, validated at the MLOps
maturity level its current deployment scope requires, with a documented expansion path
for institution-specific regulatory deployment.
