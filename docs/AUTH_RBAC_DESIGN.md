# Authentication and Role-Based Access Control Design

**Project:** Real-Time Fraud Intelligence Console
**Phase:** Phase 19C: Auth / RBAC Architecture
**Status:** Design document. No implementation in this phase.

---

## 1. Purpose

The Real-Time Fraud Intelligence Console is currently operated as a controlled local development
environment. No authentication or authorization is enforced at any API or frontend boundary. This
document defines the production authentication and role-based access control model that must be
implemented before the console is deployed to any shared infrastructure, internet-facing
environment, or regulated financial services context.

This document serves as a production-readiness design artifact: it gives technical reviewers
confidence that the system has a clear, well-considered path to controlled access without
introducing scope risk during the current local development phase. It does not implement any of
the controls described. Implementation is deferred to a future deployment-hardening phase.

---

## 2. Current Authentication Posture

The console's current authentication state reflects a deliberate choice for local development:

| Dimension | Current state |
|---|---|
| API authentication | None. All endpoints accept requests from allowed origins without credentials. |
| CORS policy | Restricted to `http://localhost:3000` and `http://127.0.0.1:3000`. Local Next.js dev server only. |
| `Authorization` header | Permitted by the CORS policy (`allow_headers: ["Content-Type", "Authorization"]`) but never validated by any middleware or route handler. |
| Users table | Does not exist. No user accounts, roles, or credentials are stored. |
| Session / token system | Does not exist. No JWT, no OAuth tokens, no session cookies. |
| Frontend route protection | Does not exist. All pages in `fraud-console/` are accessible to any local browser session. |
| Service accounts | No API keys or machine credentials exist. n8n connects to the API without authentication. |

**Risk assessment for local development:** The CORS restriction to `localhost` origins means
browser-based cross-origin requests from other domains are blocked. Direct API access (e.g., via
`curl` or `httpie` from the same machine) is unrestricted. This posture is appropriate for a
single-developer local environment and unacceptable for any shared or deployed context.

---

## 3. Role Model

Four roles are defined for the production access model.

### 3.1 Analyst

Analysts are the primary daily operators of the console. They monitor the fraud review queue,
examine individual case dossiers, submit verdicts, and trigger AI investigations when automated
investigation has not already completed.

| Dimension | Description |
|---|---|
| Responsibilities | Triage flagged transactions; review AI investigation briefs; submit confirm/false-positive/approve verdicts; escalate to supervisor when warranted |
| Allowed actions | Read dashboard metrics; read and filter the review queue; open case dossiers; submit analyst verdict and notes; trigger AI investigation; read workflow events for their cases |
| Restricted actions | Cannot upload portfolio scans; cannot promote scan results to cases; cannot manage workflow dispatch; cannot read admin configuration; cannot manage users; cannot access audit export |

### 3.2 Supervisor

Supervisors oversee analyst throughput, review escalations, manage queue health, and have full
read access across all operational surfaces including workflow automation and portfolio scan history.

| Dimension | Description |
|---|---|
| Responsibilities | Monitor analyst queue coverage and SLA compliance; review escalated cases; approve or override analyst verdicts; monitor workflow automation health |
| Allowed actions | All Analyst permissions; dispatch workflow notifications; read portfolio scan history and summaries; read stale-case SLA data; read workflow reliability metrics; access daily operational summary |
| Restricted actions | Cannot modify system configuration or thresholds; cannot manage users; cannot perform bulk data export; cannot promote scan rows to cases |

### 3.3 Admin

Admins hold full operational and configuration access. In production this role is assigned to a
small number of named individuals with a documented approval chain.

| Dimension | Description |
|---|---|
| Responsibilities | Manage user accounts and role assignments; review audit logs; manage system configuration; oversee operational health; authorize access changes |
| Allowed actions | All Supervisor permissions; upload portfolio scans; promote scan results to cases; access all admin and configuration endpoints; read all audit logs; manage user accounts and API keys |
| Restricted actions | Admin actions must be audit-logged. Bulk destructive operations (e.g., purging scan data) require a separate elevated approval step. |

### 3.4 Service Account

Service accounts are non-human identities used by automation systems. The primary current
service account consumer is n8n, the workflow automation platform, which calls the workflow
audit event endpoint and the workflow notify endpoint.

| Dimension | Description |
|---|---|
| Responsibilities | Machine-to-machine API integration; workflow automation callbacks; health monitoring probes |
| Allowed actions | POST /workflow/audit-event (n8n audit callback); GET /health/detailed (monitoring probes); GET /workflow/metrics (monitoring dashboards); GET /workflow/daily-summary (scheduled automation) |
| Restricted actions | Cannot access analyst review or verdict endpoints; cannot access case dossier content; cannot access portfolio scans; cannot manage users |

---

## 4. Permission Matrix

The table below maps each operational capability to the four roles. `✓` means the role has full
access; `✗` means the role is denied; `read` and `write` indicate partial access where relevant.

| Capability | Analyst | Supervisor | Admin | Service Account |
|---|---|---|---|---|
| Dashboard / read metrics | ✓ | ✓ | ✓ | read |
| Review queue read | ✓ | ✓ | ✓ | ✗ |
| Case dossier read | ✓ | ✓ | ✓ | ✗ |
| Analyst verdict submit | ✓ | ✓ | ✓ | ✗ |
| Trigger AI investigation | ✓ | ✓ | ✓ | ✗ |
| Workflow notify / dispatch | ✗ | ✓ | ✓ | ✓ |
| Workflow events read | read (own cases) | ✓ | ✓ | ✓ |
| Workflow reliability metrics | ✗ | ✓ | ✓ | ✓ |
| Portfolio scan upload | ✗ | ✗ | ✓ | ✗ |
| Portfolio scan read / results | ✗ | ✓ | ✓ | ✗ |
| Promote scan row to case | ✗ | ✗ | ✓ | ✗ |
| Portfolio scan export (CSV) | ✗ | ✓ | ✓ | ✗ |
| System health endpoints | ✗ | read | ✓ | ✓ |
| Daily operational summary | ✗ | ✓ | ✓ | ✓ |
| Stale-case SLA read | ✗ | ✓ | ✓ | ✓ |
| User / role management | ✗ | ✗ | ✓ | ✗ |
| Configuration / threshold management | ✗ | ✗ | ✓ | ✗ |
| Audit log export | ✗ | ✗ | ✓ | ✗ |

---

## 5. Endpoint-Group Permission Mapping

Permissions apply at the endpoint group level. Within each group, all routes inherit the group's
access control unless an individual route is explicitly more restrictive.

| Endpoint Group | Routes | Minimum Role |
|---|---|---|
| **Health** | `GET /health`, `GET /health/detailed` | Service Account or Admin (monitoring systems) |
| **Dashboard and metrics** | `GET /`, `GET /stats` | Analyst (read) |
| **Queue and case read** | `GET /review-queue`, `GET /case/{case_id}`, `GET /predictions/{transaction_id}` | Analyst |
| **Analyst verdict** | `POST /review-case/{case_id}` | Analyst |
| **Investigation** | `GET /cases/{case_id}/investigation`, `POST /cases/{case_id}/investigate` | Analyst |
| **Workflow read** | `GET /workflow/events`, `GET /workflow/metrics`, `GET /workflow/daily-summary`, `GET /workflow/stale-cases` | Supervisor (metrics/daily-summary/stale-cases); Analyst (events for own cases) |
| **Workflow write / dispatch** | `POST /workflow/notify-case/{case_id}`, `POST /workflow/audit-event` | Supervisor (notify-case); Service Account (audit-event) |
| **Portfolio scan management** | `POST /risk-scan`, `POST /risk-scan/upload`, `GET /risk-scan/recent`, `GET /risk-scan/{scan_id}/status`, `GET /risk-scan/{scan_id}/summary` | Supervisor (read); Admin (upload) |
| **Portfolio scan results** | `GET /risk-scan/{scan_id}/results`, `GET /risk-scan/{scan_id}/export` | Supervisor |
| **Scan promotion** | `POST /risk-scan/{scan_id}/promote/{result_id}` | Admin |
| **Transaction intake** | `POST /predict` | Admin or Service Account (internal pipeline use only) |
| **Admin and config** | Future configuration endpoints | Admin |
| **User management** | Future `/users/*`, `/roles/*` endpoints | Admin |

---

## 6. Recommended FastAPI Implementation Path

The following describes the intended production implementation. Nothing in this section is
implemented in Phase 19C.

### 6.1 Auth dependency

FastAPI's `Depends()` injection pattern provides a clean, per-route auth model without middleware.
A reusable `require_role(*roles)` dependency is defined once and injected at each route:

```python
# Future implementation sketch (not present in the codebase)

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> AuthContext:
    payload = _decode_and_validate_jwt(token)  # raises 401 on invalid/expired
    return AuthContext(user_id=payload["sub"], role=payload["role"])

def require_role(*roles: str):
    async def _guard(ctx: AuthContext = Depends(get_current_user)):
        if ctx.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions.")
        return ctx
    return _guard

# Applied at route level:
@app.post("/review-case/{case_id}")
def review_case(
    case_id: int,
    body: ReviewCaseRequest,
    _: AuthContext = Depends(require_role("analyst", "supervisor", "admin")),
):
    ...
```

This pattern requires zero changes to the existing route bodies. The guard dependency is
injected as an additional parameter. Routes that are unauthenticated in development gain auth by
adding a single `Depends(require_role(...))` argument.

### 6.2 Token format

JSON Web Tokens (JWT) using RS256 (asymmetric, recommended for production) or HS256 (symmetric,
acceptable for single-service deployments). The token payload should include at minimum:

```json
{
  "sub":  "user_id",
  "role": "analyst",
  "iat":  1717200000,
  "exp":  1717203600,
  "jti":  "unique-token-id"
}
```

`jti` (JWT ID) enables token revocation by maintaining a revoked-token cache (Redis, which is
already in the stack).

### 6.3 Token issuance

Two paths:

- **Interactive users:** `POST /auth/token` accepts `username` + `password` (OAuth2
  `PasswordRequestForm`). Returns short-lived access token (15 to 60 min) and long-lived refresh
  token (7 to 30 days). Refresh tokens are stored in the `users` table as a hashed value.
- **Service accounts:** Long-lived API keys (32-byte random tokens, stored as bcrypt hashes in
  a `service_accounts` table). Presented in the `Authorization: Bearer` header. No rotation
  by expiry. Rotation is manual and triggered by key compromise or periodic policy.

### 6.4 Environment-based auth flag

An `AUTH_ENABLED` environment variable controls whether the auth dependency is enforced:

```python
AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
```

When `AUTH_ENABLED=false` (default for local development), `require_role()` returns a
permissive stub that grants all requests. When `true`, full JWT validation is enforced. This
allows the local development workflow to remain unchanged while enabling production hardening
without a code change.

### 6.5 Auth context model

```python
from pydantic import BaseModel

class AuthContext(BaseModel):
    user_id: str
    role: str          # "analyst" | "supervisor" | "admin" | "service_account"
    token_jti: str     # for revocation checks
    is_service_account: bool = False
```

---

## 7. Recommended Database Model

The following tables are required in a production deployment. They are not implemented in any
current Alembic migration. The next Alembic migration file would be `0009_create_auth_tables.py`.

```sql
-- Users (human identities)
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,          -- bcrypt, never plaintext
    role          TEXT NOT NULL,          -- "analyst" | "supervisor" | "admin"
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ
);

-- Service accounts (machine identities)
CREATE TABLE service_accounts (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,   -- e.g. "n8n-automation"
    api_key_hash  TEXT NOT NULL,          -- bcrypt hash of the raw API key, never stored plaintext
    role          TEXT NOT NULL DEFAULT 'service_account',
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    last_used_at  TIMESTAMPTZ
);

-- Refresh token store (supports revocation)
CREATE TABLE refresh_tokens (
    id            SERIAL PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash    TEXT NOT NULL UNIQUE,
    issued_at     TIMESTAMPTZ DEFAULT NOW(),
    expires_at    TIMESTAMPTZ NOT NULL,
    revoked_at    TIMESTAMPTZ              -- NULL = active
);

-- Auth audit log (privileged actions)
CREATE TABLE auth_events (
    id            SERIAL PRIMARY KEY,
    actor_id      TEXT NOT NULL,           -- user_id or service_account name
    actor_role    TEXT NOT NULL,
    action        TEXT NOT NULL,           -- "LOGIN" | "LOGOUT" | "TOKEN_REFRESH" | "PERMISSION_DENIED" | ...
    target        TEXT,                    -- endpoint path or resource identifier
    ip_address    TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

**Password and key storage principles:**
- Passwords are hashed with `bcrypt` (cost factor ≥ 12). The plaintext password is never stored,
  logged, or returned in any response.
- API keys are generated as cryptographically random 32-byte values (base64url-encoded). The
  raw key is shown to the user exactly once at creation and is never stored. Only the bcrypt hash
  is persisted in `service_accounts.api_key_hash`.
- Refresh tokens follow the same pattern: raw token shown once, hash stored.

---

## 8. Frontend Integration Design

The following describes the intended production frontend auth implementation. Nothing in this
section is implemented in Phase 19C.

### 8.1 Login page

A `/login` route in `fraud-console/app/login/page.tsx` presents a username/password form. On
successful `POST /auth/token`, the access token is stored in memory (React context / Zustand
store) and the refresh token is stored in an `httpOnly` cookie via a Next.js API route to prevent
XSS token theft.

### 8.2 Protected routes

Next.js middleware (`fraud-console/middleware.ts`) intercepts all non-public routes. If no valid
token is present in the session, the middleware redirects to `/login`. This is enforced at the
edge; no server component or page renders for unauthenticated requests.

### 8.3 Token storage strategy

| Token | Storage | Rationale |
|---|---|---|
| Access token (short-lived) | React in-memory store (Zustand) | Never persisted to `localStorage` or `sessionStorage`; cleared on page unload; immune to XSS token theft from storage |
| Refresh token (long-lived) | `httpOnly` cookie set by Next.js API route | Not accessible to JavaScript; sent automatically on same-origin requests to the Next.js token-refresh endpoint |

### 8.4 Role-aware navigation

The authenticated user's `role` claim is decoded from the access token payload (the payload is not
sensitive; only the signature is secret) and stored in the auth context. Navigation items and
action buttons are conditionally rendered based on role:

- **Portfolio scan upload:** Visible only to Admin.
- **Workflow dispatch button:** Visible only to Supervisor and Admin.
- **AI investigation trigger:** Visible to all authenticated users.
- **Case verdict form:** Visible to Analyst, Supervisor, and Admin.
- **Admin panel link:** Visible only to Admin.

Role-based rendering is a UI affordance only. The FastAPI backend is the authoritative enforcement
point; the frontend guards are a usability improvement, not a security control.

### 8.5 API client auth header

The frontend API client (`fraud-console/lib/`) injects the `Authorization: Bearer <token>` header
on every request. The CORS policy already includes `Authorization` in `allow_headers`, so no CORS
change is required when auth is enabled.

### 8.6 Session expiry and logout

On access token expiry (detected via 401 from the API), the frontend automatically attempts a
silent refresh using the `httpOnly` refresh token cookie. If the refresh succeeds, the new access
token replaces the in-memory one and the failed request is retried. If the refresh fails (expired,
revoked, or cookie absent), the user is redirected to `/login`.

Logout clears the in-memory access token, calls `POST /auth/logout` (which revokes the refresh
token in the database), and clears the cookie.

---

## 9. Security Considerations

### 9.1 Least privilege

Each role is granted only the permissions required for its defined responsibilities. The Analyst
role (the most common operational identity) has no access to portfolio scans, workflow dispatch,
admin endpoints, or audit exports. Privilege escalation (e.g., an analyst promoting themselves to
admin) is only possible through the `users` table, which is exclusively writable by the Admin role
and audit-logged.

### 9.2 Token expiry and refresh strategy

Access tokens carry a short lifespan (15 to 60 minutes) to limit the exposure window of a leaked
token. Refresh tokens carry a longer lifespan (7 to 30 days) but are stored as hashes and can be
individually revoked. Redis (already in the `docker-compose.yml` stack but currently unused by the
application) is the recommended store for a revoked JTI cache, enabling immediate access token
invalidation if a compromise is detected before natural expiry.

### 9.3 Service account rotation

Service account API keys do not expire by design; automation pipelines (n8n) cannot handle
token refresh flows. Rotation is triggered manually on suspected compromise or as part of a
periodic rotation policy (e.g., annually). The `service_accounts.is_active` flag enables
immediate key invalidation without deleting the account record. A new key is issued and the old
hash is overwritten atomically.

### 9.4 Audit logging for privileged actions

The `auth_events` table records all security-relevant actions: logins, logouts, token refresh,
permission-denied events, and admin operations (user creation, role changes, key rotation). This
provides a non-repudiable audit trail for compliance review. PERMISSION_DENIED events are
particularly valuable as they surface both misconfigured tooling and unauthorized access attempts.

### 9.5 Sensitive data in the frontend

The fraud intelligence console surfaces high-sensitivity data: transaction amounts, risk scores,
investigation findings, and analyst verdicts. No sensitive case data should be stored in
`localStorage`, `sessionStorage`, or browser caches. Next.js server components should not embed
sensitive API responses in the static HTML. Token payloads (JWT claims) should contain only
identity and role. No case data, no PII.

### 9.6 Environment-specific CORS

The current CORS policy is hardcoded to localhost origins. In production, the allowed origins list
should be driven by an environment variable (`CORS_ALLOW_ORIGINS`) and include only the specific
deployed frontend hostname(s). Wildcard origins (`*`) are never acceptable for an authenticated API
that issues bearer tokens.

### 9.7 Signing key management

JWT signing keys (RS256 private keys or HS256 secrets) must never be committed to version control
or embedded in `Dockerfile`/`docker-compose.yml`. They should be injected at runtime from a
secrets manager (HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager, or equivalent). Key
rotation requires a brief dual-verification window where both the old and new keys are accepted,
then the old key is retired.

### 9.8 Auth endpoint rate limiting

The `POST /auth/token` login endpoint is a high-value brute-force target. In production, it must
be protected by rate limiting (e.g., 5 failed attempts per IP per 5 minutes triggering a 15-minute
lockout). FastAPI does not include rate limiting natively; `slowapi` (a FastAPI-compatible rate
limiter backed by Redis) is the recommended integration. The `/auth/token` endpoint is the only
one that requires aggressive rate limiting. Standard API endpoints rely on token validity for
protection.

---

## 10. Explicit Non-Goals for Phase 19C

Phase 19C is a documentation-only phase. The following are explicitly out of scope and will not
be implemented here or as a consequence of this document:

- JWT token issuance or validation (`POST /auth/token`, token middleware)
- OAuth2 or external identity provider integration
- Database migration for `users`, `service_accounts`, `refresh_tokens`, or `auth_events` tables
- Password hashing (`bcrypt` or equivalent)
- Frontend login page, protected routes, or middleware
- Role-aware navigation guards in any UI component
- n8n service account credential management
- `AUTH_ENABLED` environment flag in `config.py`
- CORS policy changes
- `docker-compose.yml` changes
- Any modification to `src/api/main.py` beyond what was completed in Phase 19A
- Any modification to `fraud-console/`
- Rate limiting infrastructure

---

## 11. Conclusion

The Real-Time Fraud Intelligence Console is purpose-built as a local fraud operations platform,
and its current authentication posture (no enforcement, localhost CORS restriction) is a
deliberate and appropriate choice for that context. The system is not deployed to any shared
infrastructure, and all data it processes is synthetic.

This document establishes that the console has a complete, implementation-ready production auth
model: a four-role permission hierarchy, a comprehensive endpoint-group permission matrix, a
concrete FastAPI `Depends()`-based implementation path, a minimal and well-defined database
schema, a frontend session management strategy, and a set of security controls proportionate to
the sensitivity of fraud intelligence data.

The design is intentionally additive. The `AUTH_ENABLED` flag pattern means the local
development workflow remains unchanged when `AUTH_ENABLED=false`, and production hardening is
activated by setting it to `true` and running the `0009_create_auth_tables.py` migration. No
existing endpoint signatures change; role guards are injected as dependencies.

Technical reviewers evaluating this console as a portfolio or institutional system can verify that
production access control is fully designed, clearly scoped, and deferrable without introducing
architectural debt, not missing or unconsidered.

---

*Document version: Phase 19C. References: `src/api/main.py` (CORS configuration, endpoint
inventory), `docs/CONSUMER_DURABILITY.md` (Phase 19B), `alembic/versions/` (current migration
state).*
