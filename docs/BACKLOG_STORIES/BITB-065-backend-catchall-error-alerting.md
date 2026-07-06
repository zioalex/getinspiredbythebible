# BITB-065: Backend Catch-All Error Alerting — HTTP 5xx, Unhandled & ASGI-Layer Exceptions

**Status:** ✅ Done (delivered on the PR #824 branch)
**Priority:** P1 (High) — a total outage produced no alert because no rule watched the most basic
failure signal: a backend 5xx.
**Size:** S (three Terraform scheduled-query alerts)
**Created:** 2026-07-05
**Incident ref:** the 2026-07-05 `_IncludedRouter` 500 (HTTP 500 on every CORS preflight) — see BITB-064.

## User Story

As the operator, I want an alert to fire whenever the backend returns HTTP 5xx or throws an unhandled
/ ASGI-layer exception, so that a server-side outage pages me on Telegram regardless of which specific
subsystem broke — instead of only the hand-picked failure signatures the existing rules watch.

## Problem / Motivation

An audit of the 17 pre-existing Azure Monitor alerts found **none keyed on backend HTTP 5xx or the
App Insights `requests` / `exceptions` tables.** They watch DB resource metrics, custom counters
(`scripture.*`, `embedding.fallback_total`, …), and specific app `| ERROR |` log strings. The generic
5xx KQL existed only in the **passive** performance workbook
(`deployment/azure-monitor/workbook-performance-dashboard.json`), which visualizes but never fires.

So when the `_IncludedRouter` crash returned HTTP 500 on every CORS preflight, it fell through every
net: it is not a DB metric, not a custom counter, and — because the crash is in the OpenTelemetry ASGI
middleware **above** the app — it never reached a `bible_app` logger, so it produced no
`| ERROR |`-formatted line and the `backend_errors` filter never matched.

**Load-bearing nuance:** the crash happens inside `default_span_details()` **before** the request span
is started (`opentelemetry/instrumentation/asgi/__init__.py`: line 755 runs before the span-start at
line 760), so App Insights records **no `requests` row** for the failing request. A 5xx-on-`requests`
alert therefore cannot see *this* class — but the crash **does** emit a `uvicorn.error`
"Exception in ASGI application" console line. That log line is the reliable in-telemetry signal, which
is why a log-based rule is required alongside the `requests`/`exceptions` rules.

## Acceptance Criteria (all delivered)

- [x] **`backend_5xx_rate`** — App-Insights-scoped scheduled query over `requests`
      (`success == false or toint(resultCode) >= 500`), fires on 3+ in 10 min, Sev 1. Broad catch-all
      for app-layer 5xx. KQL mirrors the workbook "Failed Requests" tile.
- [x] **`backend_unhandled_exceptions`** — App-Insights-scoped over `exceptions`, fires on 3+ in
      10 min, Sev 2. Catches regressions that raise past route handlers.
- [x] **`backend_asgi_exceptions`** — Log-Analytics-scoped over `ContainerAppConsoleLogs_CL`, matches
      `"Exception in ASGI application"` or a bare `Traceback (most recent call last)`, Sev 1. The
      in-telemetry catch for the middleware-layer class that the other two (and the `| ERROR |` filter)
      structurally miss.
- [x] All three reuse the `ops_email` action group and `local.alerts_enabled` gating, so they deliver
      to email + Telegram exactly like the existing alerts. (`deployment/monitoring.tf`.)

## Notes / Reuse

- KQL lifted from the proven workbook queries (`workbook-performance-dashboard.json:58,360,374`) — same
  tables/columns, so no new query invention.
- Rule structure mirrors `scripture_pipeline_errors` / `scripture_grounding_errors` in
  `deployment/monitoring.tf` (App-Insights- and Log-Analytics-scoped variants respectively).
- Thresholds (`>= 3` for the table-based rules) are conservative to avoid single-blip fatigue and are
  tunable once a production baseline is observed; the ASGI-log rule fires on the first occurrence.

## Out of Scope

- The browser-preflight probe and full browser smoke test (BITB-064).
- Frontend client-side error telemetry (BITB-066).
- Fixing the OTel→App Insights exporter drops that can under-count metric-based alerts (BITB-057 Phase 4).

## Verification

- `terraform -chdir=deployment fmt -check` (passes) + `validate` + `plan` (no apply) renders the three
  new rules wired to `ops_email` with no diff to existing resources. *(Local `validate` is blocked by
  the registry being unreachable behind the agent proxy; CI's Terraform job runs the full check.)*
- Dry-run each KQL in the Log Analytics / App Insights query editor over the last 24h to confirm it
  parses and returns sensibly.
- Operationally, confirm `TF_VAR_ALERT_EMAIL` / `TELEGRAM_CHAT_ID` / `enable_application_insights` are
  set in the deploy env so the new alerts actually deliver.
