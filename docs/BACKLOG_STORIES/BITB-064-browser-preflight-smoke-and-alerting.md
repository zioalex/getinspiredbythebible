# BITB-064: Catch Browser-Only Outages — CORS-Preflight Smoke Test + Instrumented-Request Alerting

**Status:** 🎯 Todo (follow-up carved out of the 2026-07-05 `_IncludedRouter` 500 incident)
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

| Request                                              | Broken pin (0.61b0) | Fixed pin (0.64b0) |
| ---------------------------------------------------- | ------------------- | ------------------ |
| `OPTIONS /api/v1/chat/stream` (browser preflight)    | **500**             | 200                |
| `POST /api/v1/chat/stream` (native app / curl)       | 200                 | 200                |
| `GET /health/ready`                                  | 200                 | 200                |

Every existing safety net sends requests the *non-browser* way, so all of them stayed green:

1. **Azure availability test** pings `GET /health/ready` (`deployment/main.tf:267-286`) → 200 → green.
2. **`synthetic-chat` probe** (`scripts/monitor/synthetic_chat.py`, run by
   `.github/workflows/prod-monitor.yml` every 5 min) POSTs directly via `httpx` with the
   `MONITOR_PROBE_SECRET` bypass → 200 → green. `httpx`/curl never send a CORS preflight; that is
   browser-only behavior.
3. **`verse-search` probe** — same, a direct `GET`/`POST`.

Net: the browser is the *only* client that broke, and **no probe ever behaves like a browser**, so
`prod-monitor.yml` never failed, the `notify-telegram` action never fired, and Azure Monitor never
alerted. The `android works good` observation during triage was the tell — native Android sends no
preflight, so it was unaffected, exactly like every monitor.

A second, deeper gap: the crashing layer (`FastAPIInstrumentor.instrument_app`) runs **only in
production**, gated on `APPLICATIONINSIGHTS_CONNECTION_STRING` (`api/main.py:266-273`). No unit or
integration test sets that var, so the instrumented request path — the exact thing that failed —
had zero automated coverage before this incident. (Closing the unit/CI half is tracked in the code
fix; this story covers the *production* smoke + alert half.)

## Acceptance Criteria

- [ ] **Browser-preflight synthetic probe.** New probe (e.g. `scripts/monitor/synthetic_preflight.py`)
      sends a real cross-origin CORS preflight to a representative included-router route — at minimum
      `OPTIONS /api/v1/chat/stream` with `Origin: https://voxquieta.org`,
      `Access-Control-Request-Method: POST`, `Access-Control-Request-Headers: content-type,x-turnstile-token`
      (mirror the failing request from the incident) — and **asserts 2xx/204 AND the presence of the
      expected `Access-Control-Allow-Origin` / `Access-Control-Allow-Methods` headers**. It fails on
      the 500 this incident produced.
- [ ] **Wired into `prod-monitor.yml`** as its own job on the existing `*/5 * * * *` schedule, using
      the shared `./.github/actions/notify-telegram` action so a failure pages the same Telegram chat
      as the other probes. Reuse the existing state-branch / de-dup mechanism the other jobs use.
- [ ] **(Recommended) Azure availability test parity.** Add a second `azurerm_application_insights_web_test`
      (or upgrade the existing one) that issues the CORS preflight, so the always-on Azure-native path
      also alerts — not just the 5-min GitHub cron. *If cost/complexity is a concern, the GitHub probe
      alone satisfies the story; note the decision.*
- [ ] **Runbook note** in `docs/TROUBLESHOOTING.md`: "browser 500 but native app / curl fine" ⇒ suspect
      the CORS-preflight / OTel-instrumentation path and a FastAPI-vs-instrumentation version skew.

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
  new signal here is *browser-shaped* traffic, which none of those covered.

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
