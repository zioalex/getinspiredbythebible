# BITB-064: Catch Browser-Only Outages — CORS-Preflight Smoke Test + Instrumented-Request Alerting

**Status:** ✅ Done — scripted cross-origin probe, Azure preflight web test, runbook, AND the full
production **browser** smoke test all delivered on the PR #824 branch.
**Priority:** P1 (High) — a total browser-facing chat outage shipped to production and **no monitor,
alert, or Telegram notification fired**; only a user report surfaced it.
**Size:** M (1-2 days — one new synthetic probe + wiring; optional Azure availability test)
**Created:** 2026-07-05
**Incident ref:** FastAPI 0.137 / starlette 1.3.1 put an `_IncludedRouter` in `app.routes`; the pinned
OpenTelemetry FastAPI instrumentation (`azure-monitor-opentelemetry==1.8.8` → `opentelemetry-instrumentation-fastapi==0.61b0`)
did `route.path` on it and raised `'_IncludedRouter' object has no attribute 'path'` on **every CORS
preflight**, returning HTTP 500 for `OPTIONS /api/v1/*`. Code fix tracked separately (requirements bump
to `azure-monitor-opentelemetry==1.8.9` + an instrumented-routing regression test).

## User Story

As the operator of Vox Quieta, I want a synthetic monitor that hits the API **the way a browser does**
— a cross-origin CORS preflight — and I want the production request path exercised **with
OpenTelemetry instrumentation on**, so that an outage which only affects browser traffic pages me on
Telegram within minutes instead of waiting for a user to report a broken site.

## Problem / Motivation

The `_IncludedRouter` 500 broke **only the browser CORS preflight** (`OPTIONS` with `Origin` +
`Access-Control-Request-Method`). The actual `GET`/`POST` requests returned 200. Reproduced locally
under the exact production pins:

| Request                                           | Broken pin (0.61b0) | Fixed pin (0.64b0) |
| ------------------------------------------------- | ------------------- | ------------------ |
| `OPTIONS /api/v1/chat/stream` (browser preflight) | **500**             | 200                |
| `POST /api/v1/chat/stream` (native app / curl)    | 200                 | 200                |
| `GET /health/ready`                               | 200                 | 200                |

Every existing safety net sends requests the _non-browser_ way, so all of them stayed green:

1. **Azure availability test** pings `GET /health/ready` (`deployment/main.tf:267-286`) → 200 → green.
2. **`synthetic-chat` probe** (`scripts/monitor/synthetic_chat.py`, run by
   `.github/workflows/prod-monitor.yml` every 5 min) POSTs directly via `httpx` with the
   `MONITOR_PROBE_SECRET` bypass → 200 → green. `httpx`/curl never send a CORS preflight; that is
   browser-only behavior.
3. **`verse-search` probe** — same, a direct `GET`/`POST`.

Net: the browser is the _only_ client that broke, and **no probe ever behaves like a browser**, so
`prod-monitor.yml` never failed, the `notify-telegram` action never fired, and Azure Monitor never
alerted. The `android works good` observation during triage was the tell — native Android sends no
preflight, so it was unaffected, exactly like every monitor.

A second, deeper gap: the crashing layer (`FastAPIInstrumentor.instrument_app`) runs **only in
production**, gated on `APPLICATIONINSIGHTS_CONNECTION_STRING` (`api/main.py:266-273`). No unit or
integration test sets that var, so the instrumented request path — the exact thing that failed —
had zero automated coverage before this incident. (Closing the unit/CI half is tracked in the code
fix; this story covers the _production_ smoke + alert half.)

## Acceptance Criteria

- [x] **Browser-preflight synthetic probe.** `scripts/monitor/synthetic_preflight.py` sends a real
      cross-origin CORS preflight to `OPTIONS /api/v1/chat/stream` with `Origin: https://voxquieta.org`,
      `Access-Control-Request-Method: POST`, `Access-Control-Request-Headers: content-type,x-turnstile-token`
      and **asserts 2xx/204 AND the `Access-Control-Allow-Origin` / `Access-Control-Allow-Methods`
      headers**, then a cross-origin POST (Origin + probe secret) asserting a streamed answer. It fails
      on the 500 this incident produced (verified against the broken vs fixed OTel pins).
- [x] **Wired into `prod-monitor.yml`** as the `cross-origin-smoke` job on the `*/5 * * * *` schedule,
      using the shared `./.github/actions/notify-telegram` action.
- [x] **Full production browser smoke test.** `frontend/e2e/prod-chat-smoke.spec.ts` loads the deployed
      site in real Chromium, submits a chat, and asserts a **streamed assistant reply** renders (via a
      new `data-testid="assistant-message"`) — the full real journey: rendered frontend → real CORS
      preflight → instrumented API → streamed answer. Runs hourly via `.github/workflows/prod-browser-smoke.yml`,
      wired to `notify-telegram`. **Turnstile decision resolved — smoke-scoped bypass header:** a
      _separate_, rotatable `smoke_probe_secret` (distinct from `monitor_probe_secret`) is injected into
      the CI browser at test time via `addInitScript` (never shipped in the bundle — verified); the
      deployed bundle only reads `window.__VOXQUIETA_SMOKE_SECRET__` (inert for real users) via
      `frontend/src/lib/smoke.ts`, and `getHeaders()` attaches `X-Monitor-Probe-Secret` +
      `ChatIsland` relaxes the send gate only when it's present.
- [x] **Azure availability test parity.** `backend_preflight` standard web test (`deployment/main.tf`)
      issues the `OPTIONS` preflight with the CORS request headers and expects 200, wired to the
      `backend_preflight_availability` metric alert (`deployment/monitoring.tf`) → `ops_email` →
      Telegram. Second, always-on channel independent of the GitHub cron.
- [x] **Runbook note** in `docs/TROUBLESHOOTING.md`: "browser 500 but native app / curl fine" ⇒ suspect
      the CORS-preflight / OTel-instrumentation path and a FastAPI-vs-instrumentation version skew.

**Delivered in PR #824 branch (all AC complete):** the scripted `cross-origin-smoke` probe
(`scripts/monitor/synthetic_preflight.py` + `prod-monitor.yml` job), the `backend_preflight` Azure
availability web test + alert, the troubleshooting runbook note, and the full production **browser**
smoke test (`frontend/e2e/prod-chat-smoke.spec.ts` + `.github/workflows/prod-browser-smoke.yml`, with
the `smoke_probe_secret` bypass wired through the backend + deploy).

## Setup — arming the browser smoke test (one-time)

The browser smoke test is inert until `SMOKE_PROBE_SECRET` exists as a repo secret. Until then,
`prod-chat-smoke.spec.ts` skips itself (`test.skip(!SMOKE_SECRET, ...)`) — the scheduled job still
runs and reports "passed" (0 tests skipped, not a failure), it just doesn't exercise anything yet.

1. **Generate a value** (any high-entropy random string works; this is a bearer-style shared secret,
   not a signing key, so a plain random hex string is fine):

   ```bash
   openssl rand -hex 32
   ```

2. **Set it as a GitHub repo secret** (Settings → Secrets and variables → Actions → New repository
   secret, or via the CLI):

   ```bash
   openssl rand -hex 32 | gh secret set SMOKE_PROBE_SECRET
   ```

3. **Redeploy** (or re-run `azure-deploy.yml`) so `TF_VAR_smoke_probe_secret` (already wired in
   `azure-deploy.yml` from this same repo secret) reaches the backend container as
   `SMOKE_PROBE_SECRET` and `settings.smoke_probe_secret` picks it up
   (`api/config.py` / `api/utils/monitor_probe.py`). No Azure Key Vault step is needed — unlike the
   Telegram bot token, this flows straight through a Container App secret (`deployment/main.tf`),
   the same way `MONITOR_PROBE_SECRET` already does.
4. **Verify:** trigger `.github/workflows/prod-browser-smoke.yml` manually (Actions → Prod Browser
   Smoke → Run workflow). The job should now actually run the Chromium test (not skip) and report a
   streamed assistant reply.

Deliberately kept **separate** from `MONITOR_PROBE_SECRET` (used by the server-to-server probes in
`prod-monitor.yml`) — this secret transits an ephemeral CI browser (injected via Playwright
`addInitScript`, never present in the deployed bundle — verified), so it should be independently
rotatable if it ever needs to be revoked without touching the other probes.

## Notes / Reuse

- Notification plumbing already exists and is the model to copy: `.github/actions/notify-telegram/action.yml`,
  the per-job `Notify Telegram` steps, and the `STATE_BRANCH` de-dup in `.github/workflows/prod-monitor.yml`.
- Probe scaffolding to mirror: `scripts/monitor/synthetic_chat.py` and `scripts/monitor/synthetic_search.py`
  (arg parsing, `--detail-out`, `httpx`, `MONITOR_PROBE_SECRET`). The preflight probe is simpler — no auth,
  no body; it only needs to send the `OPTIONS` with the three CORS request headers and assert the response.
- Azure availability test to mirror/extend: `deployment/main.tf:267-286` (`/health/ready` web test) and the
  alert wiring in `deployment/monitoring.tf`. The Telegram bridge (`ops_email` action group +
  `logic_app_workflow.telegram_alert`, BITB-056) already reposts Azure alerts to Telegram.
- Related: **BITB-055 / BITB-056 / BITB-057** — this is the same "make it loud" observability thread; the
  new signal here is _browser-shaped_ traffic, which none of those covered.

## Out of Scope

- The code fix for the `_IncludedRouter` 500 itself (requirements bump + instrumented-routing regression
  test) — shipped separately alongside this story's creation.
- Full browser-automation / Playwright synthetic against the deployed frontend (heavier; a raw CORS
  preflight is enough to catch this class of failure).
- Rate-limiter / content-safety observability (tracked under BITB-061).

## Verification

- Point the new probe at a backend still running the broken `1.8.8` pin (or the local repro) and confirm it
  **fails** (500 / missing CORS headers) and produces a Telegram alert; point it at the fixed `1.8.9` build
  and confirm it **passes** (2xx + `Access-Control-Allow-*` headers present).
- Trigger `prod-monitor.yml` via `workflow_dispatch` with `force_alert` and confirm the preflight job's
  Telegram message renders through `notify-telegram`.
- If the Azure web test is added: `terraform -chdir=deployment fmt -check` + `validate`, and `plan` (no
  apply) renders the new availability test + its alert.
