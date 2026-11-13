# BITB-181: Keep Probe Sessions (Hourly Browser Smoke) Out of the Weekly Report

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-10
**Prompted by:** BITB-178 open question (rev. 2) — does probe traffic, including the new weekly
`golden-set-live.yml` run, inflate the weekly usage report?

## Findings (2026-10-10, from code)

- `api/reports/weekly_report.py` counts sessions, messages, languages and the web/mobile split from
  the `sessions` table only.
- Rows are written by `utils.session_tracker.track_session`, called from both chat routes
  (`api/routes/chat.py`). It returns early when the request has no `session_id`, and it does not
  check `utils.monitor_probe.is_monitor_probe`.
- **Golden-set live run: not counted.** `api/golden_set/runner.py` sends no `session_id`, so its 81
  weekly requests never reach the `sessions` table. Same for `prod-monitor.yml`'s API probes, which
  send no session id either.
- **Hourly browser smoke: counted.** `prod-browser-smoke.yml` (cron `17 * * * *`) drives the real UI
  with Playwright (`frontend/e2e/prod-chat-smoke.spec.ts`) and the probe header. The frontend sends
  its normal `session_id`, so every run creates a session: about 168 a week, all English and desktop,
  which inflates the totals and skews the language and web/mobile mix.

## Functional Requirements

- FR1 Do not record a session for an authorized probe request: `track_session` (or its callers)
  skips when `is_monitor_probe(request)` is true. A schema flag (`is_probe`) is the alternative if
  probe volume is wanted in a report; default to skipping unless Plan finds a consumer.
- FR2 Keep the golden-set runner sessionless, and assert it in `test_golden_set_runner.py`, so a
  later change cannot start counting it.
- FR3 Optionally print one line in the digest with the number of probe requests excluded, if it can
  be obtained without a schema change.

## Acceptance Criteria

- [ ] A chat request with a valid probe header and a `session_id` creates or updates no `sessions` row
      (both `/chat` and `/chat/stream`)
- [ ] A normal request with a `session_id` is still tracked (regression test)
- [ ] A test pins that the golden-set runner payload carries no `session_id`
- [ ] Weekly-report tests unchanged or extended; no migration needed for the default (skip) design

## Out of Scope

- Removing probe sessions already stored. Old weeks are not re-sent.
