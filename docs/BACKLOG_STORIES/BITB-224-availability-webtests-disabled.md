# BITB-224: Availability Web Tests Are Silently Disabled in Production — Verify, Decide, Codify

**Status:** 🚧 In Progress (PR pending; production verification is owner-only)
**Priority:** P1
**Size:** S
**Created:** 2026-10-23
**Parent:** BITB-150 (Phase 0 discovery — monitoring-integrity finding, not a cost lever)

## User Story

**As** the operator whose browser-outage protection (BITB-064) depends on the two
availability web tests, **I want** their production state verified and a deliberate
keep-or-retire decision codified, **so that** my synthetic availability monitoring
is either actually running or consciously gone — not silently dead while I believe
I'm covered.

## The finding (evidence, not assumption)

`09a-web-test-bible-app-availability.json` and `09a-web-test-bible-app-preflight.json`
both show `"Enabled": false` for the two `Microsoft.Insights/webtests` resources —
while `deployment/main.tf:288-350` defines both as active tests. Consequences:

1. **The BITB-064 safety net is currently off.** Both tests exist to catch
   browser-facing outages that direct probes miss (the 2026-07-05 `_IncludedRouter`
   CORS-preflight 500 fired *no* monitor). If they were off then, the layer built
   specifically to prevent a repeat is not preventing it.
2. **`backend_probe_failures` (3 firings in 30d) has a dead input** if the tests
   stopped feeding it — those 3 firings may predate the disablement. The rule's
   fate is decided here (see BITB-223).
3. **No alert watches this gap**: `prod-deploy-drift.yml` checks deployment drift,
   not web-test state, and `azurerm_application_insights_standard_web_test` does
   not manage the ARM `Enabled` flag — so Terraform *cannot* see or fix this drift.

## Findings (2026-10-29)

- **Root cause:** `azurerm_application_insights_standard_web_test.enabled` is Optional with
  no default, i.e. `false`. `deployment/main.tf` never set it for `backend_availability` or
  `backend_preflight`, so Terraform actively keeps both tests disabled — a `terraform apply`
  re-disables them. With `enabled = true` pinned, apply restores them.
- **Correction:** `backend_probe_failures` does not depend on the web tests — it reads
  `ContainerAppSystemLogs_CL` `ReplicaUnhealthy`. The alerts that depend on the web tests are
  the metric alerts `backend_availability` (`*-availability-failed`) and
  `backend_preflight_availability` (`*-preflight-failed`), which only fire while the web test
  is Enabled. The original finding #2 and #3 above overstated this; the provider *does*
  manage the flag (by defaulting it to false).
- **Fix in code:** `enabled = true` + `retry_enabled = true` in `main.tf`; new
  `scripts/monitor/check_webtests_enabled.py` run by the `webtests-enabled` job in
  `prod-deploy-drift.yml` (every 15 min, Telegram on failure); tests in
  `api/tests/test_webtests_enabled_guard.py`.

## Investigation questions (answer before deciding)

- [ ] When were the tests disabled (web-test revision history / activity log)?
      Deliberate (who, why) or accident?
- [x] Does a `terraform apply` even restore them, given the provider does not
      manage `Enabled`? **Corrected answer:** the provider does manage it, defaulting to
      `false`; apply was actively re-disabling them. With `enabled = true` pinned, apply
      restores them (or `az resource update --ids <id> --set properties.Enabled=true`).
- [ ] What have the tests been catching historically? (Correlate past
      `availabilityResults` rows / `backend_probe_failures` firings.)
- [ ] Cost reality check: at 3 geos × 2 tests × 5 min the story priced them at
      51,840 executions/month — but the meter shows scheduled-query rules and
      workspace ingestion, with web-test execution cost negligible
      (availabilityResults ingestion ≈ zero while disabled). Re-enable cost is
      immaterial to the bill; the decision is purely operational.

## The decision (record which, with reasoning)

**Option A — Re-enable (expected default):** the tests cost almost nothing, they
are the only independent multi-geo vantage points, and BITB-064 exists because a
single-region false positive / browser-only outage once burned a whole day.

**Option B — Retire deliberately:** if the owner judges the GitHub
`cross-origin-smoke` probe (every 5 min, real CORS preflight + streamed answer)
plus `prod-browser-smoke` (hourly, full browser) sufficient coverage, retire the
tests **and** `backend_probe_failures` **and** update BITB-064's runbook note.

## Decision

**Option A re-enable — confirmed by the owner on 2026-10-29.** Code implements Option A
(tests cost almost nothing; they are the only independent multi-geo vantage points, and the
BITB-064 browser-only-outage safety net depends on them).

## Acceptance Criteria

- [ ] Disablement date and actor identified; intent documented in the story
- [x] Keep-or-retire decision recorded with reasoning (this is deliberately the
      owner's call — re-justify, don't rubber-stamp)
- [ ] If kept: tests show `Enabled: true` in production (after deploy; owner-only)
- [ ] If kept: `*-availability-failed` / `*-preflight-failed` alerts verified to fire on a
      forced failure (owner-only; not `backend_probe_failures`, which reads
      `ContainerAppSystemLogs_CL`)
- [x] If kept: a drift guard so a future silent disablement pages (`webtests-enabled` job in
      `prod-deploy-drift.yml`, `scripts/monitor/check_webtests_enabled.py`)
- [x] If kept: Terraform pins `enabled = true` (and `retry_enabled = true`) on both web tests
- [ ] `webtests-enabled` Telegram path exercised via a `force_alert=true` run (owner-only)
- [ ] Historical correlation of past `availabilityResults` rows / alert firings (owner-only)
- [ ] If retired: tests, `backend_probe_failures`, and the BITB-064 runbook
      note are removed together in one PR
- [x] Either way: the decision and its date land in this story file

## Out of Scope

- Other alert rules (BITB-223)
- Log Analytics / App Insights ingestion changes

## Related

- BITB-064 — why the preflight test exists; the outage it answers
- BITB-150 — the cost analysis whose evidence collection caught the disablement
- BITB-223 — `backend_probe_failures` verdict depends on this decision
