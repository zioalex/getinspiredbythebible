# Improvement Tasks

Identified areas for improvement beyond current open PRs (#106-108 golden set testing).
Organized by priority and category. Each item includes effort estimate and impact.

---

## Legend

- **Effort**: S (< 30 min), M (1-3 hours), L (half day+), XL (multi-day)
- **Impact**: Low, Medium, High, Critical
- **Status**: Open, In Progress, Done, Deferred

---

## 1. High Priority

### 1.1 Resource Cleanup - HTTP Clients Never Closed

- **File**: `api/providers/ollama.py:44-49,131-135`
- **Issue**: httpx `AsyncClient` instances are lazily created and cached but `aclose()` is
  never called. Leaks connections in long-running instances.
- **Fix**: Call cleanup in FastAPI lifespan shutdown handler.
- **Effort**: S | **Impact**: High | **Status**: Open

### 1.2 Sequential Batch Embeddings

- **File**: `api/providers/ollama.py:187-195`
- **Issue**: `embed_batch` processes texts one-by-one. 100 embeddings take 100x single-embedding time.
- **Fix**: Use `asyncio.gather()` with a semaphore to parallelize without overwhelming the server.
- **Effort**: M | **Impact**: High | **Status**: Open

### 1.3 Fail-Fast Configuration Validation

- **File**: `api/main.py:40-85`, `api/config.py`
- **Issue**: App starts even with default placeholder
  `DATABASE_URL=postgresql://CONFIGURE_ME:...`. Fails only on first DB access.
- **Fix**: Validate critical config on startup and exit immediately if misconfigured.
- **Effort**: S | **Impact**: High | **Status**: Open

### 1.4 Embedding Dimension Mismatch Risk

- **File**: `api/config.py:48-49`
- **Issue**: `embedding_model` and `embedding_dimensions` are independent settings.
  Changing model without updating dimensions silently breaks semantic search.
- **Fix**: Validate dimensions match model on startup; consider coupling them in config.
- **Effort**: M | **Impact**: High | **Status**: Open

### 1.5 No Database Migration Framework

- **Issue**: No Alembic or similar tool. Schema changes are manual with no version tracking,
  rollback, or zero-downtime migration support.
- **Fix**: Add Alembic with initial migration from current schema.
- **Effort**: L | **Impact**: High | **Status**: Open

---

## 2. Security

### 2.1 PostgreSQL Publicly Accessible (Terraform)

- **File**: `deployment/main.tf:264`
- **Issue**: `public_network_access_enabled = true`. Database is reachable from the internet.
- **Fix**: Use Azure Private Endpoints; restrict firewall to VNet only.
- **Effort**: M | **Impact**: Critical | **Status**: Open

### 2.2 ACR Admin Credentials Enabled

- **File**: `deployment/main.tf:238`
- **Issue**: `admin_enabled = true` on container registry. Admin credentials can be brute-forced.
- **Fix**: Use Azure RBAC with Managed Identities instead.
- **Effort**: M | **Impact**: High | **Status**: Open

### 2.3 Security Checks Ignored in CI

- **File**: `.github/workflows/test_update.yml:432,443`
- **Issue**: `continue-on-error: true` on dependency vulnerability checks. Security failures don't block CI.
- **Fix**: Remove `continue-on-error` or separate into warning-only and blocking checks by severity.
- **Effort**: S | **Impact**: High | **Status**: Open

### 2.4 Profanity Filter Easily Bypassed

- **File**: `api/utils/security.py:79-88`
- **Issue**: Basic regex patterns bypassed with unicode variations (`f​u​c​k`), character substitution (`f*ck`), mixed encodings.
- **Fix**: Add unicode normalization before filtering; consider `better-profanity` library.
- **Effort**: M | **Impact**: Medium | **Status**: Open

### 2.5 No Secret Rotation Mechanism

- **Files**: `deployment/main.tf:114-175`, workflow files
- **Issue**: API keys passed as env vars with no expiration or rotation policy.
- **Fix**: Integrate Azure Key Vault with automatic rotation.
- **Effort**: L | **Impact**: High | **Status**: Open

### 2.6 Missing Rate Limit on Streaming Duration

- **File**: `api/routes/chat.py:59-98`
- **Issue**: `/api/v1/chat/stream` rate limits request count only, not bandwidth or
  duration. A user can consume resources for the full streaming duration.
- **Fix**: Add max-duration timeout for streams or chunk-based rate limiting.
- **Effort**: M | **Impact**: Medium | **Status**: Open

---

## 3. Code Quality

### 3.1 Unused Dependency: aiohttp

- **File**: `api/requirements.txt:15`
- **Issue**: `aiohttp` is listed but never imported. Only `httpx` is used.
- **Fix**: Remove from requirements.txt.
- **Effort**: S | **Impact**: Low | **Status**: Open

### 3.2 Likely Unused: psycopg2-binary

- **File**: `api/requirements.txt:10`
- **Issue**: Both `asyncpg` and `psycopg2-binary` listed. The async app uses asyncpg exclusively.
- **Fix**: Verify no sync DB code exists, then remove.
- **Effort**: S | **Impact**: Low | **Status**: Open

### 3.3 SQLAlchemy Legacy Column() Syntax

- **File**: `api/scripture/models.py`
- **Issue**: Uses `Column()` instead of SQLAlchemy 2.0 `Mapped[]` annotations,
  causing mypy suppressions across `scripture.*` and `routes.*`.
- **Fix**: Migrate to `Mapped[]` annotations.
- **Effort**: L | **Impact**: Medium | **Status**: Open
- **Note**: Already tracked in `docs/TECHNICAL_DEBT.md`.

### 3.4 Magic Number: Similarity Threshold

- **File**: `api/chat/service.py:234`
- **Issue**: Hardcoded `similarity_threshold=0.35` with no explanation or configurability.
- **Fix**: Move to config.py with documentation of what different values mean.
- **Effort**: S | **Impact**: Medium | **Status**: Open

### 3.5 Incomplete Error Handling in Batch Embeddings

- **File**: `api/providers/ollama.py:187-195`
- **Issue**: If embedding fails on text #3 of 10, all work is lost. No partial success handling.
- **Fix**: Return partial results or retry failed items.
- **Effort**: M | **Impact**: Medium | **Status**: Open

---

## 4. Testing

### 4.1 No Coverage Reporting in CI

- **File**: `.github/workflows/test_update.yml`
- **Issue**: Runs pytest without `--cov`. No minimum threshold, no coverage trends.
- **Fix**: Add `--cov` flag, set minimum threshold (e.g., 80%), publish coverage report.
- **Effort**: S | **Impact**: Medium | **Status**: Open

### 4.2 No Frontend Tests

- **Issue**: No Jest/Vitest, React Testing Library, or E2E tests (Playwright/Cypress).
- **Fix**: Add component tests and at least basic E2E tests.
- **Effort**: XL | **Impact**: High | **Status**: Open
- **Note**: Already tracked in `docs/TECHNICAL_DEBT.md`.

### 4.3 Integration Tests Written as Shell Scripts

- **File**: `.github/workflows/test_update.yml:223-395`
- **Issue**: Complex shell scripts for integration testing. Brittle, hard to maintain, poor error reporting.
- **Fix**: Rewrite as pytest-based integration tests with proper fixtures and assertions.
- **Effort**: L | **Impact**: Medium | **Status**: Open

---

## 5. Observability

### 5.1 No Request Tracing / Correlation IDs

- **File**: `api/utils/logging_config.py`
- **Issue**: Logs include session_id but no request_id/trace_id. Cannot trace a single request through the system.
- **Fix**: Add request-id middleware that generates and propagates a unique ID per request.
- **Effort**: S | **Impact**: High | **Status**: Open

### 5.2 No Metrics / APM

- **Issue**: No Prometheus, OpenTelemetry, or Application Insights. Only logs available.
- **Fix**: Add OpenTelemetry instrumentation for latency, error rates, cache hit rates.
- **Effort**: L | **Impact**: High | **Status**: Open

### 5.3 No Alerting Beyond Budget

- **File**: `deployment/main.tf:750-766`
- **Issue**: Only budget alerts configured. No alerts for container restarts, API latency,
  DB connection exhaustion, or error rate spikes.
- **Fix**: Add alert rules for operational metrics.
- **Effort**: M | **Impact**: High | **Status**: Open

---

## 6. Deployment and Infrastructure

### 6.1 No Blue-Green / Canary Deployment

- **File**: `.github/workflows/azure-deploy.yml:305-542`
- **Issue**: Direct deployment to production. No rollback automation or traffic splitting.
- **Fix**: Implement Azure Container Apps revisions with traffic splitting.
- **Effort**: L | **Impact**: High | **Status**: Open

### 6.2 No Staging Environment

- **Issue**: Only dev and prod. No staging to validate before production.
- **Fix**: Add staging environment with terraform workspace or separate config.
- **Effort**: L | **Impact**: High | **Status**: Open

### 6.3 Backup Retention Only 7 Days

- **File**: `deployment/main.tf:259`
- **Issue**: `backup_retention_days = 7`, `geo_redundant_backup_enabled = false`. Insufficient for data recovery.
- **Fix**: Increase retention to 30+ days; enable geo-redundancy.
- **Effort**: S | **Impact**: High | **Status**: Open

### 6.4 Missing Workflow Concurrency Control

- **File**: `.github/workflows/*.yml`
- **Issue**: No `concurrency` configuration. Allows duplicate runs of expensive Terraform/build operations.
- **Fix**: Add `concurrency` groups to all workflow files.
- **Effort**: S | **Impact**: Medium | **Status**: Open

### 6.5 Docker Health Check Uses Python Import

- **File**: `api/Dockerfile:57`
- **Issue**: Health check runs `python -c "import httpx; httpx.get(...)"` - slow and heavy.
- **Fix**: Use `curl` or `wget` for lightweight HTTP check.
- **Effort**: S | **Impact**: Low | **Status**: Open

---

## 7. Frontend

### 7.1 No Error Boundary

- **Issue**: No React ErrorBoundary wrapping the app. A component crash takes down the entire UI.
- **Fix**: Add ErrorBoundary component with fallback UI.
- **Effort**: S | **Impact**: Medium | **Status**: Open

### 7.2 Large Monolithic Page Component

- **File**: `frontend/src/app/page.tsx`
- **Issue**: 500+ lines mixing messaging, verse display, modals, feedback, church finder.
- **Fix**: Extract into composable components and custom hooks.
- **Effort**: L | **Impact**: Medium | **Status**: Open

---

## Quick Wins (recommended first batch)

These can all be done in a single session:

| # | Task | Effort | Impact |
|---|------|--------|--------|
| 3.1 | Remove unused `aiohttp` | S | Low |
| 3.2 | Remove unused `psycopg2-binary` (verify first) | S | Low |
| 3.4 | Make similarity threshold configurable | S | Medium |
| 1.1 | Close HTTP clients in lifespan shutdown | S | High |
| 1.3 | Fail-fast config validation on startup | S | High |
| 5.1 | Add request-id middleware | S | High |
| 4.1 | Add `--cov` to CI pytest | S | Medium |
| 6.4 | Add workflow concurrency groups | S | Medium |
| 6.3 | Increase backup retention to 35 days | S | High |
| 6.5 | Lightweight Docker health check | S | Low |
| 2.3 | Make CI security checks blocking | S | High |
| 7.1 | Add React ErrorBoundary | S | Medium |
