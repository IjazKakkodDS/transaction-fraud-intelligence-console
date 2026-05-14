# Fraud Intelligence Console - Deployment Plan

---

## Purpose

This document records the deployment readiness audit, environment variable inventory, identified blockers, and recommended first-release deployment strategy for the Fraud Intelligence Console. It is a planning document. No deployment has been completed. Deployment planning is Phase 11P of the product build sequence.

The product currently runs as a 7-service Docker Compose stack verified locally on Windows 11 (Docker Desktop). This document defines the work required to move from that local runtime to a publicly accessible deployment.

---

## Current Local Runtime

The full local stack is defined in `docker-compose.yml`. All seven services start with:

```
docker compose up -d --build
```

| Service | Image / Build | Port | Role |
|---|---|---|---|
| api | Custom Dockerfile (python:3.11-slim) | 8000 | FastAPI - all HTTP endpoints |
| postgres | postgres:16-alpine | 5432 | Primary persistence |
| redis | redis:7-alpine | 6379 | Cache layer |
| redpanda | redpandadata/redpanda:v24.1.1 | 9092, 8082 | Kafka-compatible event broker |
| redpanda-init | redpandadata/redpanda:v24.1.1 | - | One-shot topic bootstrap |
| scoring-consumer | Custom Dockerfile (shared with api) | - | Async scoring worker |
| investigation-consumer | Custom Dockerfile (shared with api) | - | AI investigation worker |
| n8n | n8nio/n8n:latest | 5678 | Workflow automation |

The Next.js frontend runs separately via `npm run dev` on port 3000. It is not containerized in the current stack.

Ollama runs as a host-machine process (not a Docker service). The investigation-consumer connects to it at `host.docker.internal:11434`.

---

## Component Readiness Matrix

| Component | Readiness | Notes |
|---|---|---|
| FastAPI API | Needs environment configuration | Multi-stage Dockerfile is solid. CORS origins are hardcoded to localhost. `allow_origins` must be made configurable before deployment. |
| PostgreSQL | Requires managed service replacement | Credentials are hardcoded in docker-compose.yml. Must move to environment variables and a managed database for any public deployment. |
| Redis | Deployment-ready with configuration | No authentication configured locally. Managed Redis (e.g. Redis Cloud, Upstash) resolves both the service and auth requirements. |
| Redpanda | Requires managed service or significant reconfiguration | Single-node local configuration with `--overprovisioned` and `--smp=1`. Not suitable for deployment as-is. Options: managed Kafka-compatible broker, or keep eventing local for first release. |
| scoring-consumer | Deployment-ready with standard configuration | Reuses the API Dockerfile. Requires Kafka and Postgres to be reachable. No other blockers once those services are resolved. |
| investigation-consumer | Local-only for first release | Connects to Ollama at `host.docker.internal:11434`. This host-specific DNS resolves only within Docker environments with host gateway access. Requires Ollama replacement or hosted LLM endpoint before cloud deployment. |
| n8n | Needs environment configuration | `N8N_HOST` and `WEBHOOK_URL` are set to localhost. Must be updated to the deployed hostname before automation callbacks will succeed in a cloud environment. n8n Cloud is a viable alternative. |
| Next.js frontend | Deployment-ready with standard configuration | Standard Next.js 16. Deployable to Vercel or any Node.js host. Requires `NEXT_PUBLIC_API_BASE_URL` set to the deployed API URL. |
| Ollama/Mistral | Local-only for first release | Not containerized. Runs as a host-machine process. No cloud equivalent configured. Must be replaced with a hosted LLM endpoint (e.g. Anthropic API, OpenAI API, hosted Ollama) before investigation consumer can run in a cloud environment. |

---

## Environment Variables

### API service (`src/api/main.py`, `src/config/config.py`)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `APP_ENV` | No | development | Set to `production` for deployed environments |
| `LOG_LEVEL` | No | INFO | |
| `DATABASE_URL` | Yes | - | Full PostgreSQL connection string, e.g. `postgresql://user:pass@host:5432/dbname` |
| `KAFKA_BOOTSTRAP_SERVERS` | No | (empty) | Broker address, e.g. `redpanda:29092`. If unset, event publishing is disabled and the API scores synchronously. |
| `SYNC_SCORING_ENABLED` | No | true | Set to `false` to use async scoring path (event-driven via consumer). Set to `true` for synchronous scoring fallback. |
| `MODEL_PATH` | No | saved_models/fraud_model.pkl | Path to trained XGBoost model artifact inside the container. |
| `MODEL_WEIGHT` | No | 0.6 | Weight applied to XGBoost model output in the scoring formula. |
| `RULE_WEIGHT` | No | 0.4 | Weight applied to deterministic rule flag in the scoring formula. |
| `REVIEW_THRESHOLD` | No | 0.3 | Minimum risk_score to trigger REVIEW decision. |
| `BLOCK_THRESHOLD` | No | 0.7 | Minimum risk_score to trigger BLOCK decision. |
| `HIGH_AMOUNT_THRESHOLD` | No | 1000 | Transaction amount above which `is_high_amount` = 1. |
| `HIGH_RISK_PAYMENT_METHODS` | No | credit_card,digital_wallet | Comma-separated list. |
| `LOW_RISK_COUNTRIES` | No | US,CA,GB,AU,DE,FR,NL,JP | Comma-separated list. Countries not in this list are flagged as high-risk. |
| `HIGH_RISK_MERCHANT_CATEGORIES` | No | electronics,gaming,travel | Comma-separated list. |
| `OLLAMA_BASE_URL` | No | http://host.docker.internal:11434 | URL of the Ollama instance. Must be replaced with a cloud-accessible endpoint for cloud deployment. |
| `OLLAMA_MODEL` | No | mistral:latest | Ollama model tag. |
| `OLLAMA_TIMEOUT` | No | 300 | Ollama HTTP timeout in seconds. |
| `N8N_WEBHOOK_URL` | No | (empty) | Full n8n webhook URL. If unset, workflow dispatch is disabled. In production, set to the published n8n webhook endpoint. |

### Scoring consumer (`src/events/consumer_scoring.py`)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | Yes | - | Same value as the API. |
| `KAFKA_BOOTSTRAP_SERVERS` | Yes | - | Broker address. Consumer will not start if unset. |
| `SYNC_SCORING_ENABLED` | No | true | Should match the API setting. |
| `MODEL_PATH` | No | saved_models/fraud_model.pkl | Must be present inside the container. |
| `MODEL_WEIGHT` | No | 0.6 | |
| `RULE_WEIGHT` | No | 0.4 | |
| `REVIEW_THRESHOLD` | No | 0.3 | |
| `BLOCK_THRESHOLD` | No | 0.7 | |
| `HIGH_AMOUNT_THRESHOLD` | No | 1000 | |
| `HIGH_RISK_PAYMENT_METHODS` | No | credit_card,digital_wallet | |
| `LOW_RISK_COUNTRIES` | No | US,CA,GB,AU,DE,FR,NL,JP | |
| `HIGH_RISK_MERCHANT_CATEGORIES` | No | electronics,gaming,travel | |

### Investigation consumer (`src/investigation/consumer.py`)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | Yes | - | Same value as the API. |
| `KAFKA_BOOTSTRAP_SERVERS` | Yes | - | Broker address. |
| `OLLAMA_BASE_URL` | Yes | http://host.docker.internal:11434 | Must point to a reachable Ollama instance. This is the primary deployment blocker for the investigation consumer. |
| `OLLAMA_MODEL` | No | mistral:latest | |
| `OLLAMA_TIMEOUT` | No | 300 | |

### PostgreSQL service (docker-compose.yml)

| Variable | Value in current config | Notes for deployment |
|---|---|---|
| `POSTGRES_DB` | fraud_db | Move to secrets manager. |
| `POSTGRES_USER` | fraud_user | Move to secrets manager. |
| `POSTGRES_PASSWORD` | fraud_pass | Hardcoded in docker-compose.yml. Must be replaced with a secret reference before any deployment. |

### Redis service

No application-level environment variables are currently configured for Redis. The API and consumers do not yet read a `REDIS_URL` variable. If Redis is used as a cache in future phases, a `REDIS_URL` variable will need to be added.

### n8n service (docker-compose.yml)

| Variable | Value in current config | Notes for deployment |
|---|---|---|
| `N8N_HOST` | localhost | Must be set to the deployed hostname (e.g. `n8n.yourdomain.com`) |
| `N8N_PORT` | 5678 | Standard n8n port. |
| `N8N_PROTOCOL` | http | Set to `https` for deployed environments. |
| `WEBHOOK_URL` | http://localhost:5678/ | Must be set to the full public-facing URL for webhook callbacks to succeed. |
| `GENERIC_TIMEZONE` | Asia/Kolkata | Update to match deployment region if required. |

### Frontend (fraud-console)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Yes | http://localhost:8000 | Set to the deployed API URL. This is the only frontend environment variable required. Currently defined in `fraud-console/.env.local`. |

---

## CORS Configuration - Deployment Blocker

The FastAPI API currently has CORS origins hardcoded in `src/api/main.py`:

```python
allow_origins=[
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
```

This will reject all requests from a deployed frontend. Before deployment, `allow_origins` must be made configurable via an environment variable (e.g. `ALLOWED_ORIGINS`), and the deployed frontend URL must be included.

This is a code change required in `src/api/main.py` before any deployment can succeed. It should be addressed in Phase 11P or as a pre-deployment step.

---

## Recommended First Release Strategy

The recommended approach for a first public release is a conservative split deployment. This minimises operational complexity while making the product publicly accessible.

### Recommended split

| Component | Deployment target | Rationale |
|---|---|---|
| Next.js frontend | Vercel | Zero-configuration deployment for Next.js. `NEXT_PUBLIC_API_BASE_URL` set to the deployed API URL. |
| FastAPI API | Railway, Render, or Fly.io (containerized) | Accepts the existing Dockerfile directly. Managed container platforms handle image builds and service restarts. |
| PostgreSQL | Managed database (Railway Postgres, Supabase, Render Postgres, Neon) | Replaces the local Docker volume with a durable managed service. Alembic migrations run as a one-time command against the managed database URL. |
| Redis | Managed Redis (Upstash, Redis Cloud, Railway Redis) | Replaces the local Docker container. No code changes required - only `REDIS_URL` if/when Redis is actively used by the application. |
| Redpanda / Kafka | Option A: managed Kafka-compatible broker (Upstash Kafka, Confluent Cloud) | Replace `KAFKA_BOOTSTRAP_SERVERS` with the managed broker endpoint. No consumer code changes required. |
| | Option B: disable eventing for first release (set `SYNC_SCORING_ENABLED=true`, leave `KAFKA_BOOTSTRAP_SERVERS` unset) | The API scores synchronously and returns the result directly. The scoring consumer is not deployed. Reduces operational surface for a first release. |
| scoring-consumer | Deployed alongside API if Option A above is chosen | Reuses the same container image. Requires Kafka and Postgres to be reachable. |
| investigation-consumer | Local-only for first release | Requires Ollama on host. No hosted LLM endpoint is currently configured. |
| Ollama / Mistral | Local-only for first release | Not containerized. Requires GPU or sufficient RAM on the host. No cloud equivalent configured. |
| n8n | n8n Cloud (cloud.n8n.io) or self-hosted on the same container platform | If n8n Cloud: update `N8N_WEBHOOK_URL` in the API environment. If self-hosted: update `N8N_HOST` and `WEBHOOK_URL` variables. |

---

## Deployment Options

### Option A - Minimal public release (frontend + API + managed Postgres, sync scoring)

Deploy only the frontend, API, and managed Postgres. Leave Redpanda, consumers, and n8n local or inactive. Use `SYNC_SCORING_ENABLED=true` and unset `KAFKA_BOOTSTRAP_SERVERS`.

**What is available in this configuration:**
- Transaction Intake (synchronous scoring, no async polling required)
- Review Queue
- Case Dossier (risk evidence only)
- Analyst Verdict Capture
- API endpoints for scoring, queue, and case management

**What is not available:**
- Async event-driven scoring
- AI investigation (no Ollama)
- Workflow automation (n8n not deployed)
- Workflow Events and Reliability Metrics surfaces (no workflow events being generated)

**Operational complexity:** Low. Two services (frontend, API) plus managed Postgres.

---

### Option B - Full backend deployment (all services except Ollama)

Deploy frontend, API, managed Postgres, managed Redis, managed Kafka-compatible broker, scoring-consumer, and n8n. Ollama and the investigation-consumer remain local-only.

**What is available:**
- Full async event-driven scoring
- Review Queue and Case Dossier with risk evidence
- Analyst Verdict Capture
- Workflow Automation (n8n)
- Workflow Events and Reliability Metrics

**What is not available:**
- AI investigation reports (investigation-consumer requires Ollama)

**Operational complexity:** Medium. Six deployed services with four managed cloud dependencies.

---

### Option C - Full deployment including AI investigation

All components deployed. Requires replacing Ollama with a hosted LLM endpoint (e.g. Anthropic API, OpenAI API, or a GPU-backed Ollama instance). Requires code changes to `investigation/reasoner.py` to use a hosted endpoint instead of the local Ollama HTTP API.

**What is available:** Full product surface.

**Operational complexity:** High. Requires LLM provider setup, API key secrets management, and investigation consumer code changes.

---

## Local-Only Components (First Release)

The following components are not recommended for cloud deployment in the first release:

| Component | Reason | Path to deployment |
|---|---|---|
| Ollama / Mistral | Host-machine process, not containerized, `host.docker.internal` dependency | Replace with hosted LLM API endpoint; update `src/investigation/reasoner.py` to use the new endpoint |
| investigation-consumer | Depends on Ollama being reachable | Becomes deployable once Ollama replacement is complete |
| Redpanda (self-hosted) | Single-node local config, not production-grade as configured | Replace with managed Kafka-compatible broker; only `KAFKA_BOOTSTRAP_SERVERS` needs updating |

---

## Cloud-Ready Components (With Configuration)

The following components are ready for deployment with environment variable changes only. No code changes are required except where noted.

| Component | Required configuration changes | Code changes required |
|---|---|---|
| FastAPI API | DATABASE_URL, N8N_WEBHOOK_URL, ALLOWED_ORIGINS (new env var) | Yes - CORS origins must be made configurable |
| scoring-consumer | DATABASE_URL, KAFKA_BOOTSTRAP_SERVERS | No |
| Next.js frontend | NEXT_PUBLIC_API_BASE_URL | No |
| n8n | N8N_HOST, N8N_PROTOCOL, WEBHOOK_URL | No |

---

## Blockers and Risks

| Blocker | Severity | Detail |
|---|---|---|
| CORS origins hardcoded to localhost | High | All cross-origin requests from a deployed frontend will be rejected. Must be resolved before any deployment attempt. |
| Postgres credentials hardcoded in docker-compose.yml | High | `fraud_user` / `fraud_pass` must not be used in any deployed environment. Must move to secrets management before deployment. |
| Ollama requires local host process | High | `host.docker.internal:11434` only resolves in Docker environments with host gateway access. Investigation consumer cannot run in standard cloud container environments without replacing Ollama. |
| No authentication layer | High | The API and frontend have no authentication or authorisation. Any public deployment exposes all endpoints to any caller without restriction. |
| No production secrets management finalised | High | No secrets manager (e.g. AWS Secrets Manager, Doppler, Vault) is configured. Environment variables must be injected securely via the deployment platform before going live. |
| n8n webhook URL is localhost | Medium | `N8N_WEBHOOK_URL` must be updated to the deployed n8n URL. Audit callbacks from n8n will fail until this is set correctly. |
| Redpanda is single-node local dev | Medium | The current `--overprovisioned --smp=1 --memory=512M` configuration is not suitable for production. Requires managed Kafka-compatible broker or a production-grade Redpanda configuration. |
| Redis has no authentication | Medium | Local Redis has no password. Managed Redis services require authentication credentials. If Redis becomes actively used by the application, `REDIS_URL` must be added to the environment configuration. |
| Multi-service orchestration complexity | Medium | The full stack requires seven services plus Ollama on the host. Any deployment that goes beyond Option A (minimal) requires coordination across multiple managed services. |
| Alembic migrations must be run manually | Low | There is no automated migration step in the Docker entrypoint. Migrations must be run as a one-time command against the managed database after first deployment: `alembic upgrade head`. |
| Demo seed depends on full running stack | Low | `scripts/demo_seed.py` requires the API, scoring-consumer, investigation-consumer, and n8n to all be healthy. Investigation seeding will fail if the investigation-consumer is not deployed. |
| Case IDs are not stable across database resets | Low | If the managed Postgres database is reset, all case IDs change. Re-run the seed script and update `docs/DEMO_STATE.md` with the new case IDs. |

---

## Pre-Deployment Checklist

The following items must be completed before any service is deployed to a public environment.

### Required before any deployment

- [ ] Make CORS `allow_origins` configurable via an environment variable in `src/api/main.py`
- [ ] Replace hardcoded Postgres credentials in docker-compose.yml with environment variable references
- [ ] Select and configure a secrets management approach for the deployment platform
- [ ] Select a deployment platform for the API container (Railway, Render, Fly.io, or equivalent)
- [ ] Select a managed Postgres provider and provision a database
- [ ] Run Alembic migrations against the managed database: `alembic upgrade head`
- [ ] Set `NEXT_PUBLIC_API_BASE_URL` in the Vercel (or equivalent) frontend environment to the deployed API URL
- [ ] Set `DATABASE_URL` in the API environment to the managed Postgres connection string
- [ ] Set `N8N_WEBHOOK_URL` in the API environment if n8n is deployed
- [ ] Confirm `APP_ENV=production` and appropriate `LOG_LEVEL` in the deployed API environment

### Required only for Option B or C (full backend)

- [ ] Select a managed Kafka-compatible broker (Upstash Kafka, Confluent Cloud, or equivalent)
- [ ] Set `KAFKA_BOOTSTRAP_SERVERS` to the managed broker endpoint
- [ ] Set `SYNC_SCORING_ENABLED=false` to activate async scoring path
- [ ] Deploy scoring-consumer with DATABASE_URL and KAFKA_BOOTSTRAP_SERVERS set
- [ ] Configure n8n with correct `N8N_HOST`, `N8N_PROTOCOL`, and `WEBHOOK_URL` values
- [ ] Publish the n8n fraud-case webhook workflow and confirm the production webhook URL

### Required only for Option C (full deployment with AI investigation)

- [ ] Select a hosted LLM provider or provision a GPU-backed Ollama instance
- [ ] Update `src/investigation/reasoner.py` to use the hosted endpoint
- [ ] Set `OLLAMA_BASE_URL` (or equivalent) in the investigation-consumer environment
- [ ] Deploy investigation-consumer and confirm it connects to the LLM endpoint
- [ ] Run demo seed script and verify investigation COMPLETE status for both canonical cases

---

## Recommended Decision

For the first public release, **Option A** is recommended. Deploy the frontend to Vercel and the API to a container platform with managed Postgres. Use `SYNC_SCORING_ENABLED=true` and leave `KAFKA_BOOTSTRAP_SERVERS` unset. This makes the product publicly accessible with the minimum number of moving parts.

The Workflow Events and Reliability Metrics surfaces will not display live data in Option A unless workflow events are manually seeded or n8n is additionally deployed. The demo seed data already in the database at the time of deployment will remain visible in the Review Queue and Case Dossier.

The investigation consumer and Ollama remain local-only. AI investigation reports seeded before deployment persist in the database and are visible in the deployed Case Dossier without the consumer needing to run.

Option B can be activated in a second step once the managed Kafka broker is provisioned and n8n is deployed with correct webhook configuration.

---

## Phase 11Q Baseline Decision

**Phase 11Q proceeds against the local Docker Compose stack.**

This decision was confirmed at the close of Phase 11P. The pre-deployment blockers identified in this document (CORS configurability, credential hardening, platform selection, Option A execution) are prerequisites for a future public deployment, not prerequisites for screenshot and demo walkthrough packaging.

The local Docker Compose stack is fully verified, all seven services are confirmed operational, both canonical demo cases are seeded and accessible, and all seven product routes return correct data from the live API. This constitutes a sufficient and reproducible baseline for Phase 11Q.

The following items remain open as pre-deployment tasks for a future public release:

- CORS `allow_origins` made configurable in `src/api/main.py`
- Hardcoded Postgres credentials removed from docker-compose.yml
- Secrets management approach selected and configured
- Deployment platform selected (Railway, Render, Fly.io, or equivalent)
- Managed Postgres provider provisioned and Alembic migrations executed
- Decision on Option A vs Option B finalised and executed

None of the above block Phase 11Q. They will be addressed when a public deployment target is confirmed.

---

*This document was created during Phase 11P. It reflects the state of the product as of 2026-05-14. Update this document when deployment decisions are finalised or environment configurations change.*
