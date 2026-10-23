# BITB-224: Availability Web Tests Are Silently Disabled in Production — Verify, Decide, Codify

**Status:** 🎯 Todo
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

## Investigation questions (answer before deciding)

- [ ] When were the tests disabled (web-test revision history / activity log)?
      Deliberate (who, why) or accident?
- [ ] Does a `terraform apply` even restore them, given the provider does not
      manage `Enabled`? (Expected: **no** — manual portal re-enable or
      `az resource update` is required; that's the drift-class gap to close.)
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

## Acceptance Criteria

- [ ] Disablement date and actor identified; intent documented in the story
- [ ] Keep-or-retire decision recorded with reasoning (this is deliberately the
      owner's call — re-justify, don't rubber-stamp)
- [ ] If kept: tests show `Enabled: true` in production, `backend_probe_failures`
      verified to fire on a forced failure, **and** a drift guard added so a
      future silent disablement pages (scheduled check on the webtests'
      `Enabled` property — the same evidence query this analysis used)
- [ ] If retired: tests, `backend_probe_failures`, and the BITB-064 runbook
      note are removed together in one PR
- [ ] Either way: the decision and its date land in this story file

## Out of Scope

- Other alert rules (BITB-223)
- Log Analytics / App Insights ingestion changes

## Related

- BITB-064 — why the preflight test exists; the outage it answers
- BITB-150 — the cost analysis whose evidence collection caught the disablement
- BITB-223 — `backend_probe_failures` verdict depends on this decision
