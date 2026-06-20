# BITB-055: Scripture/Chat Pipeline Observability — Fail Loud, Not Silent

**Status:** 🎯 Todo
**Priority:** P2 (Medium) — reliability/observability hardening after a silent 2-week outage
**Size:** M (1-2 days)
**Created:** 2026-06-20

## User Story

As the operator, I want the scripture/chat pipeline to **emit explicit failure and
degradation signals** (metrics, alerts, synthetic checks) instead of swallowing errors and
serving a verse-less answer, so that a broken search/grounding path is detected in minutes —
not discovered two weeks later by reading raw logs.

## Problem / Motivation

A one-character SQL bug (a misplaced `# nosec` comment that put `#` at the start of every
search query — fixed in PR #764) broke **all** DB-backed verse retrieval in production for
**~2 weeks** with zero alerts. The root reason it stayed invisible is systemic, not specific
to that bug:

1. **The pipeline fails open.** Three nested `except Exception` blocks each degrade silently to
   "answer with no verses" (no 5xx, no user-visible error):
   - `_search_scripture` (`api/chat/service.py`) → `logger.error(..., exc_info=True)`, `return None, ""`
   - `_resolve_cited_verses` (`api/chat/service.py`) → `logger.warning` per verse, returns empty set
   - `_apply_verse_grounding` (`api/chat/service.py`) → `logger.warning`, returns text unchanged
2. **Monitoring is reactive log-scraping that this bug slipped through twice.** The Terraform
   `backend_errors` rule and the `prod-monitor.yml` Telegram scan both rely on a hand-maintained
   keyword regex; the scan additionally AND-requires a `| ERROR |` level marker *and* a keyword on
   the **same** line, which multi-line tracebacks split. The failure signatures matched neither net.
3. **No metric distinguished "served with verses" from "served empty."** A 100% silent-degradation
   rate looked identical to healthy traffic on every dashboard.
4. **CI never executes the real SQL.** `search_verses_*` are mocked in tests, so a SQL-level
   regression cannot be caught before merge.
5. **The alert layer can be entirely disabled and nobody is told.** All `monitoring.tf` alerts are
   gated on `alerts_enabled = var.alert_email != "" && var.enable_application_insights`, both of
   which default off.

PR #764 fixed the specific bug and added a signature-matched alert + a regression test as a
stopgap. This story addresses the **class** of problem so the next silent failure can't hide.

## Acceptance Criteria

- [ ] **Metrics from the fail-open paths, not inferred from logs.** Increment explicit counters in
      the three `except` blocks — e.g. `chat.scripture.search_errors`, `chat.cited_verse.resolve_errors`,
      `chat.grounding.errors` (dimensioned by error type / language) — via the existing
      `api/utils/metrics.py` helper (same pattern as `scripture.fetch.errors`, BITB-041). Alert on the
      metric in `deployment/monitoring.tf`, not on log text.
- [ ] **Business-level SLI for silent degradation.** Emit a counter/ratio for chat responses served
      with **zero DB verses and zero resolved citations** (degradation that has no exception at all),
      and add a threshold alert (e.g. degraded-rate over a rolling window).
- [ ] **End-to-end synthetic check.** Extend the `prod-monitor.yml` `verse-search` job (or add a
      chat probe) to assert the chat path actually returns cited/grounded verses, so a
      transaction-abort-class regression is caught regardless of log content.
- [ ] **Log-scan robustness.** Decouple the Telegram scan's level-marker and keyword conditions and
      move toward alerting on structured `| ERROR |` / `| CRITICAL |` lines with a small
      benign-allowlist, rather than a growing keyword denylist that must be maintained by hand.
- [ ] **Fail loud when alerting is disabled.** Add a prod guard / CI check that flags when production
      has `alerts_enabled = false` (no `alert_email` or App Insights), so the alert layer can't be
      silently off.
- [ ] **Close the CI gap.** Add a lightweight integration test that runs the real search/grounding
      SQL against the Postgres service container already used in `test_update.yml`, so SQL-level
      regressions are caught pre-merge.

## Notes / Reuse

- Custom-metric emission + `azurerm_monitor_scheduled_query_rules_alert_v2`: existing
  `scripture.fetch.errors` / `scripture_fetch_errors` (BITB-041) in `api/utils/metrics.py` and
  `deployment/monitoring.tf` are the templates to copy.
- Synthetic probes already exist in `.github/workflows/prod-monitor.yml` (`verse-search`, health).
- Related but distinct: **BITB-054** covers per-translation *data* observability (missing
  translations / embeddings); this story covers *pipeline failure* observability. Keep them separate.

## Out of Scope

- Transaction-cascade hardening (resolving cited verses on a savepoint so one search failure can't
  poison the request) — worth doing, but tracked separately as a resilience change.
