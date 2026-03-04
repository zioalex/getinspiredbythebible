# PR B5: Azure Monitor Workbook Performance Dashboard

**Status:** In Progress
**PR URL:** TBD
**Started:** 2026-02-24

## Summary

Deploys a visual Azure Monitor Workbook dashboard that aggregates all telemetry from
PRs B1–B4 into a single, colour-coded view. The workbook has five panels covering
overview error detection, LLM performance, database performance, error analysis, and
infrastructure health.

## Tasks

- [x] Create feature branch `feat/azure-monitor-workbook-dashboard`
- [x] Create `deployment/azure-monitor/` directory
- [x] Write `workbook-performance-dashboard.json` (valid JSON, 5 panels, KQL queries)
- [x] Add `azurerm_application_insights_workbook` resource to `deployment/main.tf`
- [x] Add `workbook_portal_url` output to `deployment/outputs.tf`
- [x] Write `deployment/azure-monitor/README.md` (setup + interpretation guide)
- [x] Create this WIP tracking doc
- [ ] Run `make pre-commit` and fix any issues
- [ ] Create PR

## Files Changed

- `deployment/main.tf` — added `azurerm_application_insights_workbook.performance_dashboard`
- `deployment/outputs.tf` — added `workbook_portal_url` output
- `deployment/azure-monitor/workbook-performance-dashboard.json` — workbook definition
- `deployment/azure-monitor/README.md` — setup and interpretation guide
- `docs/WIP/PR-B5-azure-monitor-workbook.md` — this file

## Infrastructure Changes

- **New resource**: `azurerm_application_insights_workbook.performance_dashboard[0]`
  - Only created when `enable_application_insights = true`
  - Fixed UUID `a1b2c3d4-e5f6-7890-abcd-ef1234567890` for stable re-applies
  - Reads workbook JSON from `deployment/azure-monitor/workbook-performance-dashboard.json`
  - No cost beyond the already-deployed Application Insights workspace

## Workbook Panels

| # | Panel | Visualizations |
|---|-------|----------------|
| 1 | Overview | Error rate tile (colour-coded), response time tile, availability tile, request rate line chart |
| 2 | LLM Performance | TTFT tile, duration tile, fallback rate tile (colour-coded), rate limit hits tile, tokens/sec trend |
| 3 | Database Performance | Search duration tile, query duration tile, slow query trend |
| 4 | Error Analysis | Error type pie chart, top-10 slowest table, failed requests table, exception summary table |
| 5 | Infrastructure | CPU/memory trend, restart events tile |

## Progress Log

### 2026-02-24

- Explored existing `deployment/` structure — Terraform uses `azurerm ~> 3.80`,
  Application Insights at `azurerm_application_insights.main[0]`
- Built full 5-panel workbook JSON with all KQL queries from the task spec
- Validated JSON with `python3 -c "import json; json.load(...)"` — valid
- Added Terraform resource and Portal URL output
- Wrote comprehensive README with interpretation guide, alert thresholds table,
  drill-down scenarios, and ASCII layout diagram

## Manual Steps Required After Merge

1. Ensure `enable_application_insights = true` in `terraform.tfvars`
2. Run `make tf-apply` to deploy the workbook
3. Access via the `workbook_portal_url` output or Azure Portal → App Insights → Workbooks

## Notes

- The workbook JSON uses `{timeRange:start}` (not `{TimeRange}`) for KQL time filters
- The `name` field must be a UUID — using a fixed UUID ensures the resource is stable
- No hardcoded resource IDs in the JSON; the workbook inherits the Application Insights
  component context from the Azure Portal when deployed via Terraform
- Panels 2 (LLM) and 3 (DB) will show "no data" until PRs B3/B4 instrumentation is live
