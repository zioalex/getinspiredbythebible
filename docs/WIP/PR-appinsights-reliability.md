# PR: Fix App Insights Metrics Outage

**Status:** In Progress
**Branch:** fix/appinsights-reliability

## Summary

App Insights metrics stopped flowing at ~08:30 on 2026-02-21 after a Docker image
rebuild (CI run 07:25–07:36). Root cause: version incompatibility.

- `azure-monitor-opentelemetry==1.6.4` requires `opentelemetry-sdk ~=1.28`
- After the Docker rebuild, `opentelemetry-sdk 1.39.1` was installed (unpinned `>=1.20.0`)
- The 1.39 SDK is incompatible with the 1.6.4 Azure Monitor package, causing silent init failure

## Changes

- `deployment/terraform.tfvars`: `frontend_min_replicas = 0 → 1` (user-requested)
- `api/requirements.txt`: upgrade `azure-monitor-opentelemetry` to `1.8.6` (supports sdk==1.39 exactly)
- `api/main.py`:
  - Track `_appinsights_initialized: bool` flag
  - Log full traceback on init failure (previously only message)
  - Guard FastAPI instrumentation and shutdown flush on `_appinsights_initialized` (not just `_appinsights_conn`)
  - Expose `telemetry.appinsights_initialized` in `/config` response

## Verification

- `/config` endpoint now shows `telemetry.appinsights_initialized: true/false`
- Container logs will show full traceback on any future initialization failure

## Progress Log

### 2026-02-21

- Identified root cause: CI test failure due to guard condition change
- Test expects `if _appinsights_conn:` but code now uses `if _appinsights_initialized:`
- This is the correct, intentional change - test needs updating
- Plan: Update test assertions + add new test for initialization flag + update docs

### 2026-02-21 (Test Fix)

- Updated `test_force_flush_is_guarded_by_connection_string` → `test_force_flush_is_guarded_by_initialized_flag`
- Added new test `test_appinsights_initialized_flag_exists_and_used` to verify flag usage
- Updated test file docstring to reflect _appinsights_initialized flag
- All 911 tests now passing locally

## Tasks

- [x] Identify CI test failure root cause
- [x] Update failing test assertions
- [x] Add new test for _appinsights_initialized flag
- [x] Update test documentation
- [ ] Run `make pre-commit` before pushing
- [ ] Push to PR branch and verify CI passes
- [ ] Verify App Insights metrics flowing after deployment
