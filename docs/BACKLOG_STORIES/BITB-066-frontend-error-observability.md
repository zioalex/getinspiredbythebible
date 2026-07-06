# BITB-066: Frontend Error Observability

**Status:** 🎯 Todo
**Priority:** P1 (High) — the web frontend has **no** general client-side error telemetry, so
user-facing failures (including the 2026-07-05 outage) are invisible to the operator.
**Size:** M (frontend reporter + backend metric/alert + middleware tweak)
**Created:** 2026-07-05
**Incident ref:** the 2026-07-05 `_IncludedRouter` 500 (browser-only CORS-preflight failure) — see BITB-064.

## User Story

As the operator, I want the web frontend to report client-side errors (JS exceptions, unhandled
promise rejections, and API/network failures) to a telemetry sink, and I want a spike in those to
alert me, so that a browser-only outage is visible from the client side — not just the server — the
way the Android app already reports via Firebase Crashlytics.

## Problem / Motivation

An audit found the web frontend has **essentially zero** client-side error observability:

- No RUM/telemetry dependency at all (no App Insights JS, no Sentry) in `frontend/package.json`.
- The React `ErrorBoundary` (`frontend/src/components/ErrorBoundary.tsx`) only `console.error`s.
- API failures in `frontend/src/lib/api.ts` map to typed errors + `console.error` + an in-chat error
  bubble, but are **reported nowhere**. A CORS-blocked preflight surfaces to JS as a bare `TypeError`
  ("Failed to fetch") and is swallowed apart from console + UI.
- No `error.tsx` / `global-error.tsx` in the App Router; `not-found.tsx` renders only.
- Exactly **one** telemetry path exists — `reportTurnstileError()` POSTs to `/api/v1/client-errors`
  (`frontend/src/lib/turnstile.tsx:68-74`; backend endpoint `api/main.py:359-374`) — and only for
  Turnstile challenge failures, once per session.
- The backend's `AccessAuditMiddleware` **explicitly skips `OPTIONS`**
  (`api/middleware/access_audit.py:143-145`), so a preflight 500 isn't even counted server-side.

Contrast: Android has Firebase Crashlytics fully wired. The web asymmetry is the gap.

## Acceptance Criteria

- [ ] **Generalize the existing reporter.** Extend the `reportTurnstileError` → `/api/v1/client-errors`
      pattern into a small global client-error reporter: a `window.onerror` +
      `window.addEventListener("unhandledrejection", …)` handler and an `api.ts` failure hook, each
      POSTing a structured `{type, detail}` to `/api/v1/client-errors`. Must be **sampled / rate-limited**
      and fire-and-forget (never block the UI, never loop on its own failure), and must scrub PII from
      `detail`.
- [ ] **Make the endpoint alertable.** Have `/api/v1/client-errors` emit a custom metric (e.g.
      `client.errors_total` with a `type` attribute) in addition to the current `logger.warning`, and
      add a scheduled-query alert on a spike (mirror the `scripture_pipeline_errors` rule in
      `deployment/monitoring.tf`). A storm of `Failed to fetch` from real browsers then pages us even
      when backend telemetry is blind (as it was for the preflight crash).
- [ ] **Stop dropping preflight failures server-side.** Make `AccessAuditMiddleware` count (or at least
      not silently skip) `OPTIONS` 5xx, so a preflight failure is observable server-side too.
- [ ] **Wire the App Router error routes.** Add `error.tsx` / `global-error.tsx` that report to the
      same sink (not just render), so render-time crashes are captured.

## Open Decision — mechanism

Reuse the existing `/api/v1/client-errors` endpoint (no new dependency, no third-party data sharing,
privacy-friendly) **vs.** adopt a full RUM SDK (Application Insights JS or Sentry) for richer client
telemetry (stack traces, sessions, source maps). Deferred — pick when this is scheduled. The
acceptance criteria above assume the reuse approach as the low-risk default; adopting a RUM SDK would
replace the first two criteria.

## Notes / Reuse

- Reporter pattern + endpoint already exist: `frontend/src/lib/turnstile.tsx:68-74`, `api/main.py:359-374`.
- Metric + alert scaffolding to mirror: the custom-metric counters in `api/utils/metrics.py` and the
  `azurerm_monitor_scheduled_query_rules_alert_v2` blocks in `deployment/monitoring.tf`.
- Android reference (already solved there): Firebase Crashlytics in
  `android/app/src/main/kotlin/org/voxquieta/app/VoxQuietaApp.kt` and `.../analytics/`.
- Related: BITB-064 (browser smoke test) and BITB-065 (backend catch-all alerts) — this is the
  client-side third of the same "make failures loud" effort.

## Out of Scope

- The backend alert net (BITB-065) and the browser smoke test / Turnstile-in-automation (BITB-064).
- Full session-replay / product analytics.

## Verification

- Force a client error (throw in a component; block the API) and confirm a `/api/v1/client-errors`
  POST is sent, the metric increments, and the spike alert fires in a test window.
- Confirm sampling/rate-limiting caps the POST volume and that the reporter never recurses on its own
  network failure.
- `terraform fmt/validate` for the new alert; frontend unit test for the reporter's sampling + PII scrub.
