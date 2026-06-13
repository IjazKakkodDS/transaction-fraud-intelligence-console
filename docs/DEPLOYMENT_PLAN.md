# Fraud Intelligence Console — Deployment Plan

---

## Purpose

This document defines the deployment profiles, environment variable reference, reviewer
run path, and deployment boundary for the Fraud Intelligence Console. It is a planning
and packaging document. No cloud deployment has been performed.

The primary release package for this product is the local full-stack Docker Compose
runtime. Cloud deployment profiles are documented as implementation-ready specifications,
not provisioned environments.

---

## Phase 20I Deployment Packaging Status

| Item | Status |
|---|---|
| GitHub Actions CI | Implemented — `.github/workflows/ci.yml` |
| Release readiness validator | Implemented — `scripts/verify_release_readiness.py` (41 checks) |
| Model artifact governance | Implemented — `docs/MODEL_CARD.md`, MD5 tracked |
| MLOps readiness documentation | Implemented — `docs/MLOPS_READINESS.md` |
| Guided demo endpoint | Implemented — `POST /demo/seed` |
| Model attribution endpoint | Implemented — `GET /cases/{case_id}/explain` |
| CORS environment-configurable | Implemented — `ALLOWED_ORIGINS` env var (Phase 20I) |
| `NEXT_PUBLIC_API_BASE_URL` | Implemented — frontend reads from environment |
| Docker Compose full-stack runtime | Primary local product package |
| Cloud demo profile | Documented below — not provisioned |
| Enterprise / AWS blueprint | Documented below — future roadmap |

**CORS blocker resolved.** `ALLOWED_ORIGINS` is now read from the environment. The
local full-stack default (`http://localhost:3000,http://127.0.0.1:3000`) applies when
the variable is unset. Set it to the deployed frontend URL for cloud deployment.

---

## Local Full-Stack Runtime

The full local stack is defined in `docker-compose.yml`. All services start with:

```bash
cp .env.example .env
docker compose up -d --build
docker compose run --rm api alembic upgrade head   # first run only
```

| Service | Image | Port | Role |
|---|---|---|---|
| `api` | Custom Dockerfile (python:3.11-slim) | 8000 | FastAPI — all HTTP endpoints |
| `postgres` | postgres:16-alpine | 5432 | Primary persistence |
| `redis` | redis:7-alpine | 6379 | Cache layer |
| `redpanda` | redpandadata/redpanda:v24.1.1 | 9092, 8082 | Kafka-compatible event broker |
| `redpanda-init` | redpandadata/redpanda:v24.1.1 | — | One-shot topic bootstrap |
| `scoring-consumer` | Custom Dockerfile (shared with api) | — | Async scoring worker |
| `investigation-consumer` | Custom Dockerfile (shared with api) | — | AI investigation worker |
| `n8n` | n8nio/n8n:latest | 5678 | Workflow automation |

The Next.js frontend runs separately:

```bash
cd fraud-console
npm install
npm run dev        # http://localhost:3000
```

Ollama runs as a host-machine process (not a Docker service). The
`investigation-consumer` connects at `OLLAMA_BASE_URL` (default:
`http://host.docker.internal:11434`). Ollama is required only for AI investigation
brief generation; all other product surfaces function without it.

---

## Deployment Profiles

### Profile A — Full Local Product Mode

The primary product package. All capabilities available when the full stack is running.

| Component | Deployment |
|---|---|
| FastAPI backend | Docker Compose service (`api`) on port 8000 |
| Next.js frontend | `npm run dev` on port 3000 |
| PostgreSQL | Docker Compose service (`postgres`) |
| Redpanda / Kafka | Docker Compose services (`redpanda`, `redpanda-init`) |
| Scoring consumer | Docker Compose service (`scoring-consumer`) |
| Investigation consumer | Docker Compose service (`investigation-consumer`) |
| Ollama / LLM | Host-machine process at `host.docker.internal:11434` |
| n8n | Docker Compose service (`n8n`) on port 5678 |

**Capabilities available:** all 27 API endpoints, guided demo (`POST /demo/seed`), model
attribution (`GET /cases/{case_id}/explain`), AI investigation briefs, workflow automation
audit trail, reliability metrics, portfolio risk scan.

**Model artifact:** `saved_models/fraud_model.pkl` is tracked in git (≈106 KB,
deterministic, required for the Docker image at build time — `docker compose build`
copies it into the container).

**Recommended for:** technical review, full product evaluation, E2E Playwright testing,
demo walkthrough, stakeholder deep-dive.

---

### Profile B — Cloud Demo Mode

Lightweight cloud-accessible review surface. Kafka/Redpanda and Ollama investigation are
treated as local-only for the first cloud demo; the sync scoring path eliminates the
consumer dependency.

| Component | Cloud Target |
|---|---|
| Next.js frontend | Vercel (zero-configuration Next.js deployment) |
| FastAPI backend | Render, Railway, or AWS (containerized via existing Dockerfile) |
| PostgreSQL | Managed Postgres (Render Postgres, Supabase, Neon, Railway Postgres) |
| Redis | Managed Redis (Upstash, Redis Cloud) — optional for first cloud demo |
| Kafka / Redpanda | Disabled for first cloud demo — `KAFKA_BOOTSTRAP_SERVERS` unset |
| Scoring | Synchronous inline — `SYNC_SCORING_ENABLED=true` |
| Ollama / investigation | Local-only; investigation briefs from local DB persist in cloud DB |
| n8n | Optional — set `N8N_WEBHOOK_URL` to n8n Cloud or self-hosted webhook URL |

**Required environment variables for cloud demo:**

| Variable | Value |
|---|---|
| `DATABASE_URL` | Managed Postgres connection string |
| `ALLOWED_ORIGINS` | Deployed frontend URL, e.g. `https://your-app.vercel.app` |
| `NEXT_PUBLIC_API_BASE_URL` | Deployed API URL, e.g. `https://your-api.onrender.com` |
| `SYNC_SCORING_ENABLED` | `true` |
| `KAFKA_BOOTSTRAP_SERVERS` | Unset (disables event publishing; API scores synchronously) |

**Capabilities available in Profile B:** transaction intake, review queue, case dossier,
model attribution, analyst verdict capture, guided demo endpoint. Workflow events and
reliability metrics surfaces will not populate without n8n.

**Not available in Profile B (first cloud demo):** async event-driven scoring, AI
investigation generation, workflow automation events.

**Alembic migration:** run once against the managed database after first deployment:
```bash
docker run --env DATABASE_URL=<managed-url> <image> alembic upgrade head
```

---

### Profile C — Enterprise / AWS Blueprint

Full production-grade deployment. Documented as an implementation-ready blueprint for
institution-specific deployment. Not currently provisioned.

| Component | AWS / Enterprise Target |
|---|---|
| Next.js frontend | AWS Amplify or S3 + CloudFront |
| FastAPI backend | ECS / Fargate or EC2 (containerized) |
| PostgreSQL | Amazon RDS (PostgreSQL 16) |
| Kafka / Redpanda | Amazon MSK, Redpanda Cloud, or self-managed Redpanda on EC2 |
| Scoring consumer | ECS service (shared Dockerfile with API) |
| Investigation consumer | ECS service — requires hosted LLM endpoint (see below) |
| LLM / Ollama | Hosted LLM API (Anthropic Claude API, OpenAI API, or GPU-backed Ollama on EC2) |
| n8n | n8n Cloud or self-hosted n8n on EC2 / ECS |
| Secrets management | AWS Secrets Manager or Parameter Store |
| Auth / RBAC | Implementation deferred — see `docs/AUTH_RBAC_DESIGN.md` |
| Monitoring | CloudWatch, or Prometheus/Grafana stack — see `docs/MLOPS_READINESS.md` |
| CORS | `ALLOWED_ORIGINS` set to production frontend URL |

**Hosted LLM requirement:** the investigation consumer connects to `OLLAMA_BASE_URL`.
For enterprise deployment, replace with a hosted endpoint (Anthropic API, OpenAI API,
or a GPU-backed Ollama instance on EC2). Update `OLLAMA_BASE_URL` accordingly — no
consumer code change required if the endpoint is Ollama-compatible; update
`src/investigation/reasoner.py` if using a different API contract.

**This profile is documented as a future deployment blueprint.** It reflects the correct
enterprise architecture for institution-specific regulated deployment. Auth/RBAC
hardening, drift monitoring, canary deployment, and model-risk governance review are
prerequisites for regulated production use — documented in `docs/AUTH_RBAC_DESIGN.md`,
`docs/SECURITY_POSTURE.md`, and `docs/MLOPS_READINESS.md`.

---

## Environment Variable Reference

### API service (`src/api/main.py`, `src/config/config.py`)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Full PostgreSQL connection string |
| `ALLOWED_ORIGINS` | No | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated frontend origins for CORS middleware. Set to deployed frontend URL for cloud deployment. |
| `APP_ENV` | No | development | Set to `production` for deployed environments |
| `LOG_LEVEL` | No | INFO | |
| `KAFKA_BOOTSTRAP_SERVERS` | No | (empty) | Broker address, e.g. `redpanda:29092`. Unset to disable event publishing (API scores synchronously). |
| `SYNC_SCORING_ENABLED` | No | true | `true` = synchronous inline scoring; `false` = async consumer-only path |
| `MODEL_PATH` | No | `saved_models/fraud_model.pkl` | Path to XGBoost artifact inside the container |
| `MODEL_WEIGHT` | No | 0.6 | Weight for XGBoost model output in hybrid scoring formula |
| `RULE_WEIGHT` | No | 0.4 | Weight for deterministic rule flag |
| `REVIEW_THRESHOLD` | No | 0.3 | Minimum risk_score for REVIEW decision |
| `BLOCK_THRESHOLD` | No | 0.7 | Minimum risk_score for BLOCK decision |
| `HIGH_AMOUNT_THRESHOLD` | No | 1000 | Transaction amount above which `is_high_amount` = 1 |
| `HIGH_RISK_PAYMENT_METHODS` | No | `credit_card,digital_wallet` | Comma-separated |
| `LOW_RISK_COUNTRIES` | No | `US,CA,GB,AU,DE,FR,NL,JP` | Comma-separated; countries absent from list are flagged high-risk |
| `HIGH_RISK_MERCHANT_CATEGORIES` | No | `electronics,gaming,travel` | Comma-separated |
| `OLLAMA_BASE_URL` | No | `http://host.docker.internal:11434` | Ollama endpoint; replace with hosted LLM URL for cloud deployment |
| `OLLAMA_MODEL` | No | `mistral:latest` | Ollama model tag |
| `OLLAMA_TIMEOUT` | No | 300 | Ollama HTTP timeout in seconds |
| `N8N_WEBHOOK_URL` | No | (empty) | n8n webhook URL; unset disables workflow dispatch |

### Scoring consumer

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Same as API |
| `KAFKA_BOOTSTRAP_SERVERS` | Yes | — | Consumer will not start if unset |
| `SYNC_SCORING_ENABLED` | No | true | Should match API setting |
| `MODEL_PATH` | No | `saved_models/fraud_model.pkl` | Must be present inside the container |
| Scoring threshold vars | No | Same defaults as API | `MODEL_WEIGHT`, `RULE_WEIGHT`, `REVIEW_THRESHOLD`, `BLOCK_THRESHOLD`, etc. |

### Investigation consumer

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | Same as API |
| `KAFKA_BOOTSTRAP_SERVERS` | Yes | — | Broker address |
| `OLLAMA_BASE_URL` | Yes | `http://host.docker.internal:11434` | Primary deployment blocker for cloud; replace with hosted LLM endpoint |
| `OLLAMA_MODEL` | No | `mistral:latest` | |
| `OLLAMA_TIMEOUT` | No | 300 | |

### Frontend (fraud-console)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | No | `http://localhost:8000` | Deployed API URL for cloud mode; set in `fraud-console/.env.local` |

### Portfolio Risk Scan tuning

| Variable | Default | Notes |
|---|---|---|
| `RISK_SCAN_MAX_ROWS` | 50000 | Row cap; raise deliberately for benchmark mode |
| `RISK_SCAN_CHUNK_SIZE` | 2000 | Rows per scoring/persistence batch |
| `RISK_SCAN_EXPORT_BATCH_SIZE` | 10000 | Cursor fetch size for CSV export |
| `RISK_SCAN_ENABLE_IN_MEMORY_DEDUP` | true | Cross-chunk dedup; set false for guaranteed-unique benchmark data |

---

## Reviewer Run Path

For a local full product evaluation from a clean clone:

```bash
# 1. Clone and configure
git clone <repo>
cd real-time-fraud-triage-system
cp .env.example .env

# 2. Start full Docker Compose stack
docker compose up -d --build
docker compose ps          # confirm all 7 services healthy

# 3. Run database migrations (first run only)
docker compose run --rm api alembic upgrade head

# 4. Start the Next.js frontend
cd fraud-console
npm install
npm run dev                # http://localhost:3000

# 5. Confirm API connectivity
curl http://localhost:8000/health
curl http://localhost:8000/health/detailed

# 6. Open browser
#    http://localhost:3000                    - Fraud Intelligence Command Center
#    http://localhost:3000 → Run Demo         - seed canonical demo cases
#    http://localhost:3000/cases/<id>         - Case Dossier (model attribution panel)
#    http://localhost:8000/docs               - FastAPI Swagger API documentation

# 7. Run release readiness gate
python scripts/verify_release_readiness.py   # 41 checks; all must pass

# 8. Run E2E Playwright suite (requires live stack)
cd fraud-console
npm run test:e2e                             # 11 checks
```

---

## Deployment Boundary

The Fraud Intelligence Console is a deployment-ready product package validated in a
controlled benchmark environment on synthetic fraud scenarios.

**What this release is:**

- A full-stack fraud decision intelligence platform: 4-layer scoring engine, analyst
  triage queue, AI investigation pipeline, workflow automation audit trail, portfolio
  risk scan, and case dossier with model attribution
- Environment-driven runtime configuration: `ALLOWED_ORIGINS`, `NEXT_PUBLIC_API_BASE_URL`,
  `DATABASE_URL`, `KAFKA_BOOTSTRAP_SERVERS`, `OLLAMA_BASE_URL`, and all scoring thresholds
  are configurable without code changes
- A production-style architecture validated at 10M-transaction scan scale with documented
  MLOps maturity, governance documentation, and CI release gates

**What this release is not:**

- No live institution data; controlled synthetic benchmark environment
- No provisioned cloud deployment; cloud demo profile is a documented specification
- No authentication or RBAC layer (see `docs/AUTH_RBAC_DESIGN.md` for design)
- No production drift monitoring, DLQ, or automated retraining (see `docs/MLOPS_READINESS.md`)
- No institution-specific model-risk review or regulatory calibration

**Governance documentation package:**

| Document | Scope |
|---|---|
| `docs/SECURITY_POSTURE.md` | Deployment boundary, CORS posture, 18 production hardening controls |
| `docs/AUTH_RBAC_DESIGN.md` | RBAC architecture and implementation prerequisites |
| `docs/CONSUMER_DURABILITY.md` | Consumer offset management and idempotency design |
| `docs/MODEL_CARD.md` | Model artifact contract, feature schema, explainability |
| `docs/MLOPS_READINESS.md` | MLOps maturity (L2+), implemented controls, L3 roadmap |

---

## Production Hardening Prerequisites

The following controls are required before institution-grade regulated deployment. They
are documented as known prerequisites, not hidden gaps.

| Control | Status | Notes |
|---|---|---|
| Authentication / RBAC | Not implemented | Design documented in `docs/AUTH_RBAC_DESIGN.md` |
| CORS `ALLOWED_ORIGINS` | **Implemented** | Phase 20I; environment-configurable |
| Postgres credential hardening | Required | Hardcoded in `docker-compose.yml`; move to secrets manager before deployment |
| Managed Kafka broker | Required for async path | Replace local Redpanda with MSK, Redpanda Cloud, or Confluent Cloud |
| Hosted LLM endpoint | Required for cloud investigation | Replace `host.docker.internal:11434` with cloud-accessible LLM API |
| n8n hostname configuration | Required | `N8N_HOST`, `WEBHOOK_URL` must be updated to deployed hostname |
| Secrets management | Required | AWS Secrets Manager, Doppler, or platform-native secrets |
| Production monitoring | Future L3 | Prometheus, Grafana, OpenTelemetry — see `docs/MLOPS_READINESS.md` |
| Drift monitoring | Future L3 | Statistical distribution tracking against production baseline |
| Auth enforcement at API layer | Required | JWT middleware, per-endpoint RBAC — see `docs/AUTH_RBAC_DESIGN.md` |

---

*Document refreshed: Phase 20I (2026-06-13). Previous revision: Phase 11P (2026-05-14).*
