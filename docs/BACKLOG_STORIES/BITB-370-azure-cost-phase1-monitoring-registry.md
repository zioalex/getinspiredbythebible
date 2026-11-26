---
id: BITB-370
status: in-progress
priority: P1
size: S
created: 2026-11-26
depends_on: [BITB-224]
---

# BITB-370: Azure cost phase 1 - cut web-test, alert-rule and registry spend

## User story

As the owner paying the Azure invoice, I want the monitoring and registry meters that the
November 2026 bill exposed trimmed to what actually protects production, so that the monthly
spend drops by about $40 without losing any alert that has a 3am action.

## Evidence

Cost Management export for `bible-app-rg`, 1-26 Nov 2026: 96.72 CHF (~$116 USD), about $134/month
projected, against a $50/month budget. Projected to 30 days (USD/month):

| Line | ~USD/month | This story |
| ---- | ---------- | ---------- |
| Postgres B2s compute + 64 GB storage | 57 | Out of scope (DB track BITB-228 -> 230 -> 229 -> 231) |
| App Insights "Standard Web Test Execution" | 29 | 2 tests x 3 geos x every 5 min ~ 52k executions/month. BITB-224 (PR #1232) re-enabled them ~10 Nov and wrongly called the cost negligible |
| Log-search alert rules | 15 | 9 rules still evaluate every 5 min (~$1.38/month each vs ~$0.46 at 15 min) |
| Container Apps | 16 | Out of scope |
| Container Registry | 9 | ~$4.7/month is storage over the 10 GB included in Basic; no image purge existed |
| Log Analytics ingestion | 6.5 | Open PR #1341 / BITB-233 handles Postgres logs; nothing here |

## Owner decisions (2026-11-26)

1. Web tests: keep ONLY the CORS-preflight test, 1 location, every 15 min. Retire the `/health/ready` test.
2. Log alerts: move every PT5M scheduled-query rule to PT15M except `rate_limiter_fail_closed` and `backend_asgi_exceptions`.
3. ACR: add a scheduled purge workflow.
4. DB: untouched.

## What changed

- `deployment/main.tf`: deleted `backend_availability` web test; `backend_preflight` now has one geo
  (West Europe) and `frequency = 900`; stale "$25-40/month" header replaced by a pointer to the README.
- `deployment/monitoring.tf`: deleted the `backend_availability` metric alert; `backend_preflight_availability`
  is `failed_location_count = 1`, `window_size = PT15M`, `frequency = PT5M` (metric alerts bill per time
  series, so frequency barely matters). Moved to PT15M: `backend_probe_failures`, `backend_errors`,
  `scripture_grounding_errors`, `scripture_pipeline_errors` (windows widened PT10M -> PT15M, queries `ago(15m)`),
  `scripture_search_latency_p95`, `backend_5xx_rate`, `content_safety_fallback_burn_fast` (short window 5m -> 15m).
  `backend_5xx_rate` is one PT15M evaluation, 1-of-1; the query bins the last 15 minutes into three fixed
  5-minute bins (`bin_at(timestamp, 5m, ago(15m))`), keeps bins with >= 3 5xx and alerts when all three
  breach (an empty bin has no row, so it cannot count). Same "15 minutes sustained" semantics as the old 3-of-3.
  Header inventory comments updated.
- `.github/workflows/prod-deploy-drift.yml`, `scripts/monitor/check_webtests_enabled.py`: expect only `bible-app-preflight`.
- `.github/workflows/acr-purge.yml` (new): weekly purge, `dry_run` dispatch input (default true).
- Tests: `api/tests/test_monitoring_alert_cadence.py` (new), `test_acr_purge_workflow.py` (new),
  `test_webtests_enabled_guard.py`, `test_monitoring_content_safety_slo.py`.
- Docs: `deployment/README.md`, `docs/CONTRIBUTING.md`, `docs/TROUBLESHOOTING.md`, BITB-224 and BITB-150 amendments.

## Expected effect

About -$40/month (web tests ~ -$29, log alerts ~ -$6 for the six rules moved plus smaller windows, ACR ~ -$4.7),
taking the run rate from ~$134 to about $90-95/month. **This does not reach the $50 budget.** The remaining
gap is the Postgres SKU/storage (~$57/month), tracked as BITB-231, gated on BITB-230.

## Acceptance criteria

- [x] Only the preflight web test exists; 1 location, every 900 s, `enabled`/`retry_enabled` true
- [x] `backend_preflight_availability` valid for one location (`failed_location_count = 1`, `PT15M` window)
- [x] Only `rate_limiter_fail_closed` and `backend_asgi_exceptions` evaluate at PT5M (guard test)
- [x] Every rule's look-back stays <= 48h (existing guard test)
- [x] `backend_5xx_rate` keeps sustained-15-minute semantics in a single evaluation
- [x] Weekly ACR purge workflow with dry-run, deployed-image lock/unlock, usage before/after
- [x] Drift guard expects only `bible-app-preflight`
- [x] Docs state the savings and the remaining gap plainly
- [ ] Owner step: merge PR #1341 (BITB-233)
- [ ] Owner step: after deploy, run the ACR Purge workflow via workflow_dispatch with `dry_run=true`, review the
      listed deletions, then run with `dry_run=false`. If `az acr run` is denied, grant the deploy service
      principal `Contributor` on the registry (covers `registries/scheduleRun/action`,
      `registries/runs/listLogSasUrl/action` and `registries/repositories/metadata/write`); the SPN is normally
      Contributor already via `deployment/scripts/setup-github-spn.sh`
- [ ] Owner step: about 7 days after deploy, re-export Cost Management for `bible-app-rg` and confirm the web-test
      line is about $0.05/day, the log-alert line is about 40% lower, and ACR storage is under the included 10 GB
- [ ] Owner step: decide whether to start the DB track (BITB-228 -> 230 -> 229 -> 231)

## Follow-ups

None. The remaining DB work is already BITB-230 and BITB-231.
