# BITB-245: Count Read-Aloud Start Failures (Web Telemetry)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-27
**Follow-up of:** BITB-241 (PR #1203)

## Problem

When the speech engine never starts, BITB-241 gives up after one retry and shows a notice. Nothing is
reported, so we can't tell how many users hit it, which browsers, or whether a broken speech-dispatcher
on Linux Firefox is common. That number decides whether BITB-215 (voice-install help) is worth building.

## Acceptance criteria

- [ ] A locale-only `tts_start_failed` client event, sent once per page view, added to the backend's
      client-events allowlist (`POST /api/v1/client-events`), the same pattern as `tts_unavailable`
- [ ] Tests on both the frontend and the backend; no message text or voice names sent
