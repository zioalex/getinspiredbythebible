# PR: Application Insights Metrics & Initialization Fix

**Status:** Ready for Commit
**PR URL:** TBD
**Started:** 2025-02-20

## Summary

Improved Application Insights telemetry by fixing initialization order, adding flushing logic for serverless environments,
and expanding custom metrics coverage.

## Changes

- **Initialization**: Moved `configure_azure_monitor` to the top of `api/main.py` to ensure all meters are correctly bound
to the Azure provider.
- **Reliability**: Added `force_flush()` for both traces and metrics in the `lifespan` shutdown handler to prevent data
loss during scale-to-zero.
- **New Metrics**:
  - Added `chat_stream_counter` (streaming requests).
  - Added `church_search_counter` (church finder usage).
  - Added `feedback_counter` (positive/negative ratings).
  - Added `contact_form_counter` (contact submissions).
- **Dependencies**: Added `opentelemetry-instrumentation-fastapi` to `api/requirements.txt` for automatic request tracing.
- **Tests**: Created `api/tests/test_metrics.py` to verify metric definitions and recording logic.

## Tasks

- [x] Fix initialization order in `api/main.py`
- [x] Implement telemetry flushing on shutdown
- [x] Add metrics to chat streaming
- [x] Add metrics to church search
- [x] Add metrics to feedback and contact endpoints
- [x] Update requirements.txt
- [x] Create unit tests for metrics

## Notes

The sandbox environment had git worktree issues due to missing mounts, so these changes need to be committed from the
host or a healthy environment.
