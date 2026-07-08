# Deployment Strategy

**Project:** Real-Time Transaction Fraud Intelligence Console
**Status:** Profile B hosted inspection environment deployed (Vercel, Render, Neon Postgres). Full-stack local Docker Compose package also available. This document describes deployment posture and the path for further expansion.

---

## 1. Deployment Recommendation

**Current status: Profile B hosted inspection environment plus full-stack local package.**

The console runs in two complementary forms. The hosted inspection environment (Vercel, Render, Neon Postgres) provides live scoring, analyst triage, case review, and small portfolio scans without local setup. The full-stack Docker Compose package provides the complete seven-service runtime including Kafka-backed async scoring, local LLM investigation brief generation, and workflow automation.

Kafka, Ollama, and n8n are intentionally excluded from the hosted free-tier profile. The `/health/detailed` endpoint reports these services as unavailable in the hosted profile; this is expected boundary behaviour, not a blocker. Full-stack local deployment remains the verification path for all benchmark results documented in this repository.

---

## 2. Current Release Posture

| Dimension | Current state |
|---|---|
| Hosted profile | Profile B: Vercel (frontend), Render (FastAPI), Neon Postgres; synchronous scoring only |
| Local full-stack | Docker Compose 7 services; Kafka async scoring, Ollama LLM, n8n automation |
| Authentication | None (synchronous scoring; no auth in hosted profile or local dev) |
| TLS | HTTPS on hosted profile (Vercel/Render managed); HTTP on local |
| Hosted inspection URL | https://transaction-fraud-intelligence-cons.vercel.app |
| Data | Synthetic data only. No real transaction records, no real cardholder data, no PII. |
| Repo size | 7.1 MB object store |
| Release readiness | 37/37 automated checks PASS |
| E2E coverage | 11/11 Playwright checks PASS |
| Screenshot evidence | 12 Playwright-captured PNGs in docs/screenshots/ |

---

## 3. Why Local-First Is the Correct Current Strategy

**The architecture is inspectable without a live URL.**

The codebase, Docker Compose configuration, source code, scoring logic, and documentation are all present in the repository. A reviewer who clones the repository and runs `docker compose up -d` sees the same system the developer runs. There is no gap between what the documentation describes and what the code implements.

**Local inspection is reproducible and verifiable.**

A reviewer can run `python scripts/verify_release_readiness.py` (37/37 PASS), run `npm run lint` and `npm run build` (both PASS), and clone the repository to confirm model artifacts, schemas, and scoring logic are exactly as documented. A static hosted page or a screenshot-only portfolio cannot offer that level of verification.

**The deployment prerequisites are not yet complete.**

The following are not implemented and must be in place before any shared or internet-facing deployment:
- Authentication and RBAC (design in docs/AUTH_RBAC_DESIGN.md; implementation deferred for institution-specific deployment)
- TLS and HTTPS
- Production secret management (not flat `.env` files)
- Rate limiting and API gateway controls
- Monitoring, alerting, and log aggregation
- Managed infrastructure for PostgreSQL, Redpanda, and Redis at production scale

Deploying without these controls would undermine the professional credibility of the system. The local-first posture preserves that credibility while the remaining controls are planned.

**The video artifact covers the hosted demo gap.**

The narrated product walkthrough (v9-subtitled, approximately 12 minutes 47 seconds) documents the complete analyst experience, including live scoring, case dossier navigation, AI investigation brief generation, portfolio risk scan execution, workflow audit trail, and reliability metrics. Once uploaded to a hosting platform (LinkedIn, YouTube unlisted, Google Drive), the video provides the demonstrability that a live hosted URL would otherwise provide.

---

## 4. Why Full Free-Tier Cloud Deployment Is Deferred

The following technical and risk factors make full cloud deployment premature at this stage:

| Factor | Detail |
|---|---|
| No authentication | All API endpoints are currently open within the localhost boundary. Exposing them to the internet without authentication would be a security posture failure. |
| No TLS | HTTP-only is acceptable for localhost; it is unacceptable for any internet-facing service. |
| No secrets management | `.env` files with development credentials are appropriate for local Docker Compose; they are not appropriate for cloud environments. Secrets injection via a managed provider is required. |
| Ollama on host machine | The investigation brief layer requires a local Ollama instance. Cloud deployment requires either a hosted Ollama endpoint or an alternative LLM provider integration. GPU hosting adds cost. |
| Redpanda single-node | The current Redpanda configuration is a single-node local cluster. A production event broker requires multi-node configuration, replication, and managed infrastructure. |
| PostgreSQL local volume | The current PostgreSQL instance uses a named Docker volume on the developer machine. Cloud deployment requires a managed database service with backup, replication, and failover. |
| Redis local instance | Same pattern: a managed Redis service is required for any shared cache layer. |
| Cost uncertainty | Managed database, managed message broker, managed cache, hosted backend runtime, API gateway, monitoring, logs, domain, and LLM inference all carry recurring cost. The exact cost profile depends on provider selection and requires provider-specific verification before any public cost planning is made. |
| No DLQ or retry hardening | The current consumer durability design has documented production gaps (see docs/CONSUMER_DURABILITY.md). Dead-letter topics and retry counter infrastructure are deferred. |

---

## 5. Current Local Runtime

**Prerequisites:**
```
git clone <repo>
cp .env.example .env
# Edit .env: set DATABASE_URL to use postgres service name if needed
docker compose up -d
cd fraud-console && npm install && npm run dev
```

**Service access after startup:**

| Service | URL |
|---|---|
| Frontend console | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API documentation (Swagger UI) | http://localhost:8000/docs |
| n8n workflow automation | http://localhost:5678 |
| Health check | http://localhost:8000/health |
| Detailed health check | http://localhost:8000/health/detailed |

**Optional (dev profile only):**
```
docker compose --profile dev up -d
```
Redpanda Console browser UI: http://localhost:8080

**Demonstration entry path for reviewers:**

1. http://localhost:3000 (Fraud Intelligence Command Center)
2. POST a transaction via http://localhost:8000/docs (POST /predict)
3. Navigate to /queue to see the scored case
4. Open /cases/{id} for the Case Dossier
5. http://localhost:3000/risk-scan (Portfolio Risk Scan; use pre-loaded benchmark scan_id `aa0971d2-bdb6-49c7-bac3-fa355aa161ad`)
6. http://localhost:3000/workflow/events and /workflow/metrics

---

## 6. Public Inspection Package

The repository constitutes a complete inspection package:

| Asset | Status | Location |
|---|---|---|
| Source code (backend) | Complete | src/ |
| Source code (frontend) | Complete | fraud-console/ |
| Docker Compose configuration | Complete | docker-compose.yml |
| Environment variable documentation | Complete | .env.example |
| Model artifact | Tracked and checksummed | saved_models/fraud_model.pkl |
| Screenshots (12 PNGs) | Tracked | docs/screenshots/ |
| System snapshot | Complete | docs/SYSTEM_SNAPSHOT.md |
| Experience flow guide | Complete | docs/EXPERIENCE_FLOW.md |
| Integration API blueprint | Complete | docs/INTEGRATION_API_BLUEPRINT.md |
| Portfolio case study | Complete | docs/PORTFOLIO_CASE_STUDY.md |
| Consumer durability design | Complete | docs/CONSUMER_DURABILITY.md |
| Auth and RBAC design | Complete | docs/AUTH_RBAC_DESIGN.md |
| Security posture | Complete | docs/SECURITY_POSTURE.md |
| Model card | Complete | docs/MODEL_CARD.md |
| GitHub repo metadata | Complete | docs/GITHUB_REPO_METADATA.md |
| Video artifact policy | Complete | docs/VIDEO_ARTIFACTS.md |
| Build history and phase log | Complete | docs/PRODUCT_STAGES.md |

---

## 7. External Video Artifact Strategy

The narrated product walkthrough is not tracked in the repository (git history cleaned; object store reduced from 977 MB to 7.1 MB). The final artifact (`v9-subtitled`) is held as a local artifact.

**Recommended external hosting:**

| Platform | Characteristics |
|---|---|
| LinkedIn native video | Portfolio-appropriate; visible to professional network without a URL |
| YouTube (unlisted) | Shareable via direct link; quality-preserving; widely accessible |
| Google Drive (shared link) | No quality transcoding; accessible without sign-in if set to "anyone with link" |
| Portfolio page embed | Embed YouTube or Vimeo player in a personal portfolio page for polished presentation |

**After upload:** Add the external URL to:
- `docs/VIDEO_ARTIFACTS.md` (hosted URL placeholder: `TO_BE_ADDED_AFTER_UPLOAD`)
- `docs/GITHUB_REPO_METADATA.md` (website field)
- `README.md` (Product Walkthrough Video row in the demo table)

The video URL is the primary public demonstrability asset until a cloud-hosted live system is available.

---

## 8. Cost Trade-offs

**Zero-cost now (current state):**
- Local Docker Compose runtime on developer hardware
- Git repository hosting (GitHub free tier)
- External video hosting on LinkedIn or YouTube
- All documentation, screenshots, and source code

**Likely paid later (full cloud deployment):**

| Component | Why paid | Notes |
|---|---|---|
| Managed PostgreSQL | Persistent, reliable, backed up | Provider-specific pricing; requires verification |
| Managed Redis | Shared cache layer; availability SLA | Provider-specific pricing; requires verification |
| Managed Redpanda or Kafka-compatible broker | Multi-node, replicated event backbone | Provider-specific pricing; requires verification |
| Hosted backend runtime | FastAPI container; auto-scaling | Provider-specific pricing; requires verification |
| LLM inference (Ollama replacement or supplement) | GPU-hosted or API-based LLM for investigation briefs | Provider-specific pricing; requires verification |
| API gateway and rate limiting | Required for facade exposure | Provider-specific pricing; requires verification |
| Observability, monitoring, and log aggregation | Operational health; alerting | Provider-specific pricing; requires verification |
| Domain and TLS certificate | HTTPS required for production | Minimal cost; varies by registrar |
| Secret management | Required for credential injection in cloud context | Provider-specific pricing; requires verification |

**Cost planning principle:** Provider pricing and free-tier limits change frequently. Cost estimates in this document are indicative; any deployment decision requires provider-specific verification.

---

## 9. Deployment Option Matrix

| Option | Cost | What runs | Pros | Risks | Verdict |
|---|---|---|---|---|---|
| Local-first flagship package | Zero | Full Docker Compose stack on developer machine | Complete system inspection; full benchmark verifiable; no auth risk; no cloud cost | Not accessible without developer presence or local clone | Recommended for deep inspection and benchmark verification |
| Hosted inspection profile (Profile B) | Free tier | Vercel, Render, Neon Postgres; synchronous scoring only | Live scoring, triage, and case review without local setup | Kafka, Ollama, and n8n excluded from hosted profile | Deployed and available at hosted URL above |
| Full-stack cloud deployment | Requires provider-specific verification | All 7 services on managed cloud infrastructure plus hosted LLM | Maximum demonstrability; fully accessible | Highest cost; requires auth, TLS, and all deferred controls to be complete; Ollama on GPU adds cost | Deferred; requires auth, secrets management, and infrastructure hardening |
| Enterprise deployment blueprint | Documentation only | No live deployment; architecture design and migration plan | Demonstrates deployment-readiness thinking | Cannot be inspected live; requires trust in documentation | Captured in this document as the future architecture target |

---

## 10. Production Hardening Checklist

The following checklist covers the controls required before the system transitions from a local inspection package to any shared or internet-facing deployment. None of these items are currently implemented unless explicitly noted.

**Authentication and Authorization:**
- [ ] Implement JWT bearer token or API key authentication middleware (FastAPI `Depends`)
- [ ] Implement role-based access control as designed in `docs/AUTH_RBAC_DESIGN.md`
- [ ] Add frontend route protection (redirect unauthenticated users to login)
- [ ] Configure n8n service account credentials and restrict n8n-to-API connection to authenticated calls
- [ ] Add `Integration Service` role and issue service account credentials for machine-to-machine callers

**Network and TLS:**
- [ ] Configure TLS termination (ingress controller or managed load balancer)
- [ ] Redirect all HTTP traffic to HTTPS
- [ ] Set `ALLOWED_ORIGINS` to specific trusted domain(s); remove localhost origins
- [ ] Restrict PostgreSQL, Redis, and Redpanda ports to internal network only (no external exposure)

**Secrets Management:**
- [ ] Migrate all credentials from `.env` files to a secrets management system (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault, or equivalent)
- [ ] Add JWT signing key (`JWT_SIGNING_KEY`) to secrets manager; never commit to source
- [ ] Implement secret rotation for database credentials and API keys
- [ ] Apply principle of need-to-know: each service receives only the secrets it requires

**Event Consumer Hardening:**
- [ ] Implement dead-letter topic (`transactions.raw.dlq`, `cases.investigate.dlq`) for poison pill and unrecoverable error routing (see `docs/CONSUMER_DURABILITY.md`)
- [ ] Add retry counter per message to prevent infinite retry loops
- [ ] Add DLQ monitoring and alerting
- [ ] Validate consumer restart behavior under Redpanda rolling restart

**Observability:**
- [ ] Add structured JSON logging to all services
- [ ] Configure log aggregation (CloudWatch, Datadog, Loki, or equivalent)
- [ ] Add latency metrics for scoring, database writes, and facade response time
- [ ] Configure alerting on 5xx rate, database connection failure, consumer lag
- [ ] Add `request_id` correlation to all log lines for incident tracing

**Model Governance:**
- [ ] Document institution-specific labelled outcome dataset (see `docs/MODEL_CARD.md`)
- [ ] Retrain model on institution-specific data before use in any decision context with real consequences
- [ ] Implement model version tracking in the predictions table
- [ ] Define and document threshold review process and approval chain

**Data and Compliance:**
- [ ] Define data retention policy for predictions, scan results, workflow events, and investigation reports
- [ ] Implement data deletion or anonymisation workflow for expired records
- [ ] Assess PII handling requirements for the target deployment context
- [ ] Define audit log export and immutability guarantees

**Scaling and Reliability:**
- [ ] Migrate PostgreSQL to a managed database service with replication and automated backup
- [ ] Migrate Redis to a managed cache service with replication
- [ ] Migrate Redpanda to a multi-node, replicated managed cluster
- [ ] Replace single-container FastAPI with a horizontally scalable deployment (Kubernetes pods or managed container service)
- [ ] Define autoscaling policy for the API service under peak transaction volume

---

## 11. Recommended Future Deployment Architecture

The following architecture is the recommended target for full cloud deployment. It preserves the service boundaries of the current Docker Compose design and maps each service to a cloud-native equivalent.

| Current component | Cloud equivalent |
|---|---|
| FastAPI container (Docker) | Managed container service (Cloud Run, ECS, App Service) with horizontal autoscaling |
| PostgreSQL (Docker volume) | Managed relational database with read replica, automated backup, and point-in-time recovery |
| Redis (Docker) | Managed Redis-compatible cache with replication and failover |
| Redpanda (single-node Docker) | Managed Kafka-compatible service with multi-partition, replicated topics; or Redpanda Cloud |
| n8n (Docker) | Self-hosted n8n on managed container, or n8n Cloud |
| Ollama (host) | Hosted LLM endpoint (GPU instance with Ollama, or API-based LLM with equivalent prompt design) |
| Next.js dev server (host) | Static export deployed to a CDN-backed frontend host (Vercel or equivalent) |
| Secrets (`.env` file) | Cloud-native secrets manager with rotation and per-service access control |
| Monitoring (none) | Managed observability platform with structured logs, metrics, and alerting |

**Integration gateway:** A managed API gateway sits in front of the FastAPI container. The gateway handles TLS termination, authentication token validation, rate limiting, and request logging. The API gateway is the public-facing entry point; the FastAPI service is internal.

**Migration path:** The existing Docker Compose service definitions map cleanly to this architecture. The primary migration work is secrets management, managed infrastructure provisioning, ingress configuration, and authentication implementation. The application code does not require architectural changes for cloud deployment.

---

## 12. Claim-Safe Public Wording

The following phrasings are approved for public-facing descriptions of the system at its current release state:

**Repository description (GitHub "About" field):**
> Production-style transaction fraud intelligence console: hybrid ML/rule scoring, analyst review queues, evidence-led case dossiers, AI investigation briefs, workflow audit trails, reliability monitoring, and a 10M-transaction portfolio risk scan benchmark. Docker Compose runtime.

**Portfolio description:**
> Real-Time Transaction Fraud Intelligence Console. A production-style transaction fraud decision intelligence platform built across a 7-service event-driven architecture. Features a 4-layer hybrid ML/rule scoring engine, analyst-in-the-loop case triage, AI investigation briefs with AGENT_VERSION traceability, portfolio-scale risk scan (10M-row benchmark), workflow automation audit trail, and SLO-style reliability monitoring. Reproducible Docker Compose inspection package.

**When asked about live deployment:**
> The console runs as a local Docker Compose inspection package. Full cloud deployment is deferred until authentication, secret management, monitoring, managed infrastructure, and cost planning are complete. The system is designed for cloud extension: each service boundary maps to a separately scalable deployment unit, and the integration API blueprint documents the proposed external-facing decision endpoint.

**When asked about production readiness:**
> The system is not presented as a live production fraud service. It is a production-style local runtime that demonstrates the architecture, scoring depth, analyst workflow, and operational design of a full fraud intelligence console. The deferred controls (authentication, RBAC, TLS, secrets management, DLQ hardening, model calibration, and managed infrastructure) are documented in dedicated design documents.

**When asked about the AI investigation layer:**
> The investigation brief layer uses a local Ollama instance for LLM inference. The brief is an advisory input; the analyst submits an independent verdict. No automated path exists from an LLM recommendation to a case action. Each brief is linked to the specific agent configuration that produced it via the AGENT_VERSION field.

**Phrases to avoid in all public contexts:**
- live production system
- deployed production fraud model
- bank-grade
- compliance-approved
- enterprise deployed
- fully autonomous fraud detection
- guaranteed fraud detection
- real customer transactions

---

## 13. Reviewer Inspection Notes

**What to confirm about the local runtime:**

1. `docker compose up -d` starts all 7 services cleanly within 30-60 seconds
2. `cd fraud-console && npm run dev` starts the Next.js server at http://localhost:3000
3. GET http://localhost:8000/health/detailed returns all components healthy
4. POST a transaction via http://localhost:8000/docs (Swagger UI) and observe the scored case appear in the review queue at http://localhost:3000/queue

**What to confirm about deployment readiness:**

1. `python scripts/verify_release_readiness.py` passes 37/37 checks
2. `git ls-files | grep -i .mp4` returns nothing (no video binaries tracked)
3. `.env` is excluded from git (confirmed by release readiness check)
4. `docs/AUTH_RBAC_DESIGN.md` documents the designed access control model
5. `docs/SECURITY_POSTURE.md` documents the current posture and hardening path
6. `docs/CONSUMER_DURABILITY.md` documents the current consumer design and production gaps
7. `docs/INTEGRATION_API_BLUEPRINT.md` documents the proposed integration facade

**What the current deployment boundary means for portfolio review:**
The local runtime is a complete and verifiable inspection package. The architecture, scoring logic, audit trail, and AI investigation layer are all inspectable in source code and confirmed by automated validation. The boundary between the current local package and a cloud deployment is documented, not hidden.

---