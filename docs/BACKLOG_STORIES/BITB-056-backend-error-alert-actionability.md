# BITB-056: Backend Error Alert — Precise, Actionable, and DB-Threshold-Aware

**Status:** 🚧 In progress (Phase 1 implemented; Phase 2 + DB tier bump = follow-up)
**Priority:** P2 (Medium) — alert quality / on-call signal-to-noise
**Size:** M (1-2 days)
**Created:** 2026-06-26

## User Story

As the operator of getinspiredbythebible / Vox Quieta, I want the backend error-log alert to
fire only on genuinely actionable failures and to tell me *what* broke, *how often*, and *for
which request* in the notification itself, so that I can triage from my phone without opening the
Azure portal — and I want the database's threshold-failure mode (the latency knee a load test
found at concurrency ≈ 32) to be both **detected** before users see errors and **hardened** at
the root.

## Problem / Motivation

A Sev2 `bible-app-backend-error-logs` alert (`deployment/monitoring.tf`) fired on a keyword regex:

```kql
Log_s matches regex "(?i)(openrouter error|llm streaming error|anthropic error|internal server error|traceback)"
```

It is too general and too noisy, for a specific reason: **the backend already encodes
signal-vs-noise in the log *level*, and the alert ignores it.** `api/utils/logging_config.py`
formats every line as `… | LEVEL | name:line | [request_id] | message`. The code logs transient,
self-recovered conditions (rate limits, timeouts, server-side routing failures, client-side
fallback churn, query-expansion fallback, verse-grounding skips) at **WARNING**, and genuinely
actionable failures at **ERROR** (verified in `api/providers/openrouter.py`, `api/routes/chat.py`,
`api/chat/service.py`). Concretely:

1. **No level filter.** A `WARNING` that merely *mentions* `internal server error` (an upstream
   500 echoed in a message that was then retried successfully via fallback) pages at Sev2.
2. **`traceback` is the noisiest token.** Each `logger.exception()` dumps a multi-line Python
   traceback; in Container Apps every newline becomes a separate `ContainerAppConsoleLogs_CL`
   row, so one *handled* exception lights up the regex.
3. **Dead tokens + catch-alls.** `openrouter error` / `anthropic error` / `llm streaming error`
   don't match the actual log strings, so only the broad catch-alls fire — and they fire on noise.
4. **Fires on `cnt > 0`, one period, fixed Sev2** — no threshold, no dedup, no severity tiering.
5. **Zero actionability in the email.** `summarize cnt = count() by bin(...)` throws away the log
   text — no sample, no `request_id`, no count, no category. The responder must re-run a query.
6. **Two diverged copies.** The Azure rule and the `prod-monitor.yml` log-scan job maintain
   separate regexes in two languages that were meant to mirror each other and had already drifted.

Separately, a concurrency load test (`search_concurrency_test.py` against
`/api/v1/scripture/search`) found a clean latency knee at **concurrency ≈ 32** (p95 4.3x baseline
at 32, 8.4x at 64; err-rate ~0%). The knee sits *above* the app pool ceiling (`pool_size 10 +
max_overflow 10 = 20`), implicating the **2-vCore burstable `B_Standard_B2s`** as the wall:
pgvector HNSW search is CPU-bound and runs at `hnsw.ef_search = 120`. **None of the Postgres
server's own metrics were alerted**, the `/scripture/search` path had no latency alert, and the
`db.connections.active` gauge is defined but never wired — so this degradation was invisible.

## Acceptance Criteria

### Phase 1 — alert precision, actionability & delivery (no backend code) — **implemented here**

- [x] **Alert on ERROR-level lines, not keywords.** A single checked-in
      `deployment/azure-monitor/queries/backend-error-filter.kql` selects `| ERROR |` lines, excludes
      the known-benign `bypassing rate limit`, and extracts `RequestId` + an `ErrorCategory`
      (`db_pool_timeout`, `llm_all_models_down`, `chat_unhandled`, `chat_stream_unhandled`,
      `verse_context_failed`, `scripture_search_failed`, `llm_provider_error`, `other_error`).
- [x] **Self-contained notification.** The Azure rule projects `cnt` / `ErrorCategory` / `Sample`
      / `RequestIds` so the common-alert-schema email carries them, and a Logic App bridge reposts
      the alert to Telegram so the backup channel matches `prod-monitor.yml`.
- [x] **No secret in Terraform state.** The Telegram bot token is written to a Key Vault
      out-of-band by the deploy workflow (`az keyvault secret set` from the `TELEGRAM_BOT_TOKEN`
      repo secret) and read by the Logic App at run time via its system-assigned managed identity;
      Terraform stores only the vault name and the managed-identity grant. The chat id (a routing
      identifier, useless without the token) remains a TF var that gates the bridge.
- [x] **Severity tiered.** Hard-failure categories page at **Sev2** (`backend_errors`); a Sev3
      companion (`backend_error_rate_other`) covers uncategorised ERROR spikes (≥5 in 10m).
- [x] **Single source of truth.** `prod-monitor.yml`'s log-scan job reads the same shared `.kql`
      file, so the two channels can no longer drift.

### DB threshold-failure — detect + harden

- [x] **Detect (infra-only):** Postgres resource metric alerts (`cpu_percent` Sev2, `memory_percent`
      Sev3, `storage_percent` Sev2, `connections_failed` Sev2) + a `/scripture/search` p95 latency
      alert (`db.search.duration_ms` > 2000ms, Sev2) + a `db_pool_timeout` error category at Sev2.
- [x] **Harden (free):** `auto_grow_enabled = true` on the Postgres server removes the disk-full
      write-failure cliff.
- [ ] **Harden (capacity, cost decision):** bump the burstable `B_Standard_B2s` to more vCores
      (e.g. `B_Standard_B4ms` or GP `D2ds_v5`/`D4ds_v5`) to move the conc-32 knee up, and retune
      `db_pool_size`/`db_max_overflow` alongside it. *Requires owner sign-off on the monthly delta.*
- [ ] **Optional:** evaluate lowering `hnsw.ef_search` (120) — cuts CPU/query and raises the knee
      at some recall cost. Search-quality call; do not change without an eval.

### Phase 2 — structured error metric (backend code) — **follow-up**

- [ ] Add a `backend.errors` counter (with a `category` dimension) in `api/utils/metrics.py`,
      incremented in the genuinely-actionable handlers (`api/routes/chat.py`,
      `api/providers/openrouter.py`, `api/chat/service.py`), mirroring `scripture.pipeline.errors`.
- [ ] Add a metric-based alert on `backend.errors` (split by `category`) as the precise **primary**
      Sev2 signal; keep the log-based rule as a backstop (same defence-in-depth as
      `scripture_pipeline_errors`).
- [ ] Wire the `db.connections.active` gauge to SQLAlchemy pool `checkout`/`checkin` events and add
      a pool-saturation alert (active ≥ 80% of the pool ceiling) as a leading indicator.

## Notes / Reuse

- Log level discipline lives in `api/utils/logging_config.py`; the `| ERROR |` marker is the linchpin.
- `request_id` is already on every line via `middleware/correlation_id.py` — extract, don't add.
- `azurerm_monitor_scheduled_query_rules_alert_v2` + `customMetrics … percentile` patterns already
  exist (`scripture_fetch_latency_p95`, `scripture_pipeline_errors`) — the search-latency alert copies them.
- `db.search.duration_ms` already emits from `api/scripture/repository.py` (`_record_duration`), so
  the search-latency alert needs no backend change.
- Telegram formatting reference: `.github/actions/notify-telegram` + `scripts/monitor/*.py`.
- Related: **BITB-055** (scripture-pipeline observability) is the structural metric work this builds on.

## Out of Scope

- Transaction-cascade hardening (savepoints around cited-verse resolution) — tracked separately.
- Frontend changes; this story is alerting + DB capacity only.

## Verification

- `az monitor log-analytics query` with the shared filter over a 24h window: confirm it returns
  genuine ERRORs with sensible `ErrorCategory`/`RequestId` and excludes WARNING rate-limit/fallback noise.
- `terraform -chdir=deployment fmt -check` + `validate`; `plan` (no apply) renders the rewritten rule,
  Sev3 companion, DB metric alerts, search-latency alert, Logic App + `logic_app_receiver`.
- POST a sample common-alert-schema payload to the Logic App trigger URL → formatted Telegram message.
- `prod-monitor.yml` via `workflow_dispatch force_alert=true` → log-scan still runs against the shared filter.
- Re-run `search_concurrency_test.py --mode both --concurrency 1,2,4,8,16,32,64` after the DB tier
  bump and confirm the knee moves above 32 and the db-cpu-high / search-latency alerts fire when pushed past it.
