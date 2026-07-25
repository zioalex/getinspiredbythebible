# BITB-057: Upstream Dependency Resilience — Bounded, Self-Healing, Observable DB + Inference Calls

**Status:** 🚧 In progress (Phases 1 & 2 — readiness fix, DB bounding, probe alert, embedding
resilience/cache, generalized DB retry — implemented; infra (Phase 3) + observability-of-the-
observability (Phase 4) = follow-up, need owner sign-off)
**Priority:** P1 (High) — production availability; caused a multi-week readiness incident with real user impact
**Size:** M–L (Phases 1 & 2 done; infra follow-up ~2-3 days incl. sign-off)
**Created:** 2026-06-30

## User Story

As the operator of getinspiredbythebible / Vox Quieta, I want every call to an upstream dependency
(Postgres, the LLM, the embedding provider) to be **bounded** (it can never hang the request or pin
a pooled connection), to **degrade gracefully instead of breaking** the user experience, and to be
**loud** (every timeout / retry / fallback / degradation emits a log + metric and is alertable), so
that a slow or flapping dependency is ridden out and surfaced — not silently swallowed for weeks as
it was during the readiness incident.

## Problem / Motivation

A synthetic-chat monitor failure investigation (2026-06-30) found that the backend readiness probe
had been failing **chronically since before 2026-06-16** (continuous `/health/ready` "context
deadline exceeded" → `ReplicaUnhealthy`, clustering in peak-traffic hours), with real user impact —
yet **nothing alerted** and there were **only 3 ERROR log lines in 2 weeks** despite hundreds of
failures. Root causes:

1. **Readiness did heavy, unbounded-for-the-deadline work.** `/health/ready`
   (`api/routes/health.py`) ran a DB `SELECT 1` **plus a live OpenRouter `health_check()` plus a
   live `embedding.embed()`** on every scrape, each allowed `health_check_timeout = 15s`, while the
   Container Apps readiness probe deadline is **5s** (`deployment/main.tf` readiness_probe.timeout).
   Any slow free-tier upstream → probe timeout → pod flap. The probe also added constant embedding
   load every 10s.
2. **DB queries were unbounded.** `pool_pre_ping` validates at *checkout* but cannot save a
   connection that dies **mid-operation** (`asyncpg ConnectionDoesNotExistError: connection was
   closed in the middle of operation`, seen 2026-06-26). A slow/hung query could hold a pooled
   connection up to `db_pool_timeout` (30s) and cascade toward pool exhaustion — the same saturation
   knee BITB-056 found at concurrency ≈ 32.
3. **Failures were silent.** The health-check timeout branches returned "unhealthy" without logging;
   the chat scripture pipeline's fail-open `except` blocks degrade to verse-less without always
   surfacing. The ERROR-only log-scan (BITB-056) cannot see a timeout that never logs.
4. **No probe-failure alert.** `ReplicaUnhealthy` lives in `ContainerAppSystemLogs_CL`, never
   reaches `ContainerAppConsoleLogs_CL`, and does not increment `RestartCount` (the pod kept failing
   readiness without restarting) — so neither `backend_errors` nor `backend_restarts` covered it.
5. **The telemetry pipeline itself dropped data.** The OTel → App Insights exporter timed out
   (2026-06-29, "Envelopes could not be exported … Read timed out"), so the metric-based alerts
   (`scripture.pipeline.errors`, `chat.responses.verseless`) can have blind spots.

The unifying principle the system was missing: **bound → degrade → make it loud.** A delay must
never break the service, but it must always be visible.

## Acceptance Criteria

### Phase 1 — readiness fix, DB bounding, probe alert — **implemented in this PR**

- [x] **Readiness is cheap and correctly bounded.** `/health/ready` checks only the DB with
      `readiness_check_timeout = 3s` (under the 5s platform deadline); the LLM and embedding providers
      are no longer probed on every scrape (still covered by the comprehensive `/health` and the
      LLM/embedding fallback metric alerts). (`api/routes/health.py`, `api/config.py`)
- [x] **DB queries are bounded at driver and server.** `db_command_timeout` (asyncpg, 10s) +
      server `statement_timeout` (8s) so a stalled query fails fast and frees its pooled connection
      instead of pinning it to `db_pool_timeout`. Sized ~4x above the 2s search-saturation SLO so it
      never cancels a legitimately slow query (`api/scripture/database.py`, `api/config.py`).
- [x] **Scripture search retries once on a transient mid-operation disconnect**
      (`_is_disconnection_error`); non-transient errors still fail open. (`api/chat/service.py`)
- [x] **Stalls are loud.** DB/LLM/embedding health-check timeout branches now log a warning.
- [x] **Probe-failure alert** on `ContainerAppSystemLogs_CL` `ReplicaUnhealthy` (`backend_probe_failures`
      in `deployment/monitoring.tf`) — the missing signal that hid the incident.
- [x] **Synthetic-chat probe sends a real scripture prompt** (not `"hi"`) so the verse-citation
      assertion is meaningful (`.github/workflows/prod-monitor.yml`).

### Phase 2 — harden the embedding/inference path (backend code) — **implemented**

- [x] **Embedding provider resilience parity with the LLM path.** Give the embedding client the same
      treatment OpenRouter/Llama Guard already have (`utils/circuit_breaker.py`): a **circuit
      breaker**, a **request-path timeout** tighter than the current 60s Ollama embed client, and a
      bounded **retry-with-jittered-backoff** on transient 429/5xx. Emit a fallback/circuit-open
      metric and alert on a sustained fallback rate.
      (`api/providers/embedding_resilience.py::ResilientEmbeddingProvider`, `embedding.fallback_total`.)
- [x] **Embedding cache.** Cache embeddings for hot/repeated queries (in-process LRU+TTL — no Redis
      exists anywhere in this stack, see Notes) to cut upstream call volume and smooth latency — the
      embedding call is on the chat critical path and was the load the readiness probe amplified.
      (`api/providers/embedding_cache.py::CachingEmbeddingProvider`, composed as the outermost layer
      over `ResilientEmbeddingProvider` in `providers/factory.py`; `embedding.cache_total` hit/miss
      counter; `embedding_cache_enabled`/`embedding_cache_max_size`/`embedding_cache_ttl_seconds`
      config knobs.)
- [x] **Generalize the bounded-timeout + retry-on-disconnect pattern** beyond `_search_scripture` to
      the other request-path DB users (`_resolve_cited_verses`, feedback/blocked-samples writes) via a
      small shared helper, so no request-path query is unbounded.

### Phase 3 — upstream reliability at the source (infra) — **follow-up, needs owner sign-off**

- [ ] **Enable Azure Postgres built-in PgBouncer (transaction pooling).** Highest-leverage item:
      absorbs connection churn and mid-operation drops at the server edge and supports far more
      clients than raw `max_connections`. App-side `QueuePool` + server PgBouncer is the robust combo.
- [ ] **`min_replicas ≥ 1` on the backend Container App** to avoid scale-to-zero cold starts (the
      brief "connection refused" probe failures at container start) and so one slow readiness can't
      pull the only serving pod. (`deployment/main.tf` scale config.)
- [ ] **DB compute right-sizing.** Readiness timeouts cluster at peak → saturation. Coordinate with
      the BITB-056 open item (burstable `B_Standard_B2s` → `B4ms`/GP) once `db_cpu`/`connections_failed`
      confirm the knee; B-series throttles when CPU credits drain. *Cost decision — owner sign-off.*

### Phase 4 — make the observability itself reliable — **follow-up**

- [ ] **Fix telemetry export drops.** Raise the OTel → App Insights exporter timeout / tune batch
      settings so `scripture.pipeline.errors` / `chat.responses.verseless` alerts have no blind spots.
- [ ] **Wire pool-saturation metrics.** Connect the `db.connections.active` gauge to SQLAlchemy
      `checkout`/`checkin` events and alert at ≥80% of the pool ceiling as a leading indicator.
      *(Shared with BITB-056 Phase 2 — implement once, reference there.)*

## Notes / Reuse

- Circuit-breaker primitive already exists: `api/utils/circuit_breaker.py` (`CircuitBreaker`,
  `CircuitOpenError`), used by `api/providers/openrouter.py` and `api/providers/llama_guard.py` —
  the embedding hardening copies this, it does not invent it.
- OpenRouter already has a fallback-model chain + `openrouter_fallback_total` / `llm_fallback_total`
  counters (`api/providers/openrouter.py`, `api/providers/factory.py`) — the LLM path is the model
  to follow; the embedding path is the gap.
- Latency SLOs to size timeouts against: `slow_query_threshold_ms = 100` (normal), p95 alerts at 1s
  (`scripture_fetch_latency_p95`, BITB-041) and 2s (`scripture_search_latency_p95`, BITB-056).
- `azurerm_monitor_scheduled_query_rules_alert_v2` patterns + action group `ops_email` already exist
  in `deployment/monitoring.tf` — new alerts copy them.
- Related: **BITB-055** (scripture-pipeline observability) and **BITB-056** (actionable backend error
  alert + DB saturation detection / tier-bump) — this story is the availability/resilience layer on
  top of their observability layer; the pool-saturation and DB tier items are shared with BITB-056.

## Out of Scope

- Frontend/Android changes.
- Multi-region / read-replica DB topology (revisit only if PgBouncer + tier right-sizing is
  insufficient).
- Replacing the LLM/embedding provider (a separate product/cost decision); this story hardens the
  client side and the fallback path.

## Verification

- Post-deploy: re-run the readiness onset KQL (`ContainerAppSystemLogs_CL` `ReplicaUnhealthy` for
  `bible-app-backend`) and confirm the hourly timeout count flatlines to ~0; the `synthetic-chat`
  monitor job stays green across several scheduled runs.
- DB bounding: induce a slow query (e.g. `SELECT pg_sleep(30)`) and confirm it is cancelled at ~8s
  with a "canceling statement due to statement timeout" error that is logged + retried/degraded, and
  that the pooled connection is freed (no `pool_timeout` cascade).
- Embedding hardening: with the embedding provider forced slow/erroring, confirm the breaker opens,
  the request degrades (not 500s), the fallback/circuit metric increments, and chat still streams.
- `terraform -chdir=deployment fmt -check` + `validate`; `plan` (no apply) renders the new
  `backend_probe_failures` alert (Phase 1) and, later, the PgBouncer / min_replicas changes.
- Telemetry: confirm exporter no longer logs export timeouts and the metric alerts evaluate over a
  continuous series.
