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
