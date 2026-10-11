# BITB-188: Keep Follow-Up Runner Sessions Out of the Weekly Report

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-11
**Prompted by:** BITB-182 follow-up — the runner's traffic was not checked against the weekly report.

## Bug Report

Findings (2026-10-11, from code):

- `api/golden_set/follow_up_runner.py` builds each request body with a `session_id`
  (`_request_body`) and generates a fresh `"fu-eval-" + uuid.uuid4().hex[:12]` per case. The
  script creates its client with `httpx.Client(base_url=..., timeout=...)` and no headers
  (`scripts/run_follow_up_eval.py:91`), so no monitor-probe header is sent.
- Both chat routes call `track_session(db, request.session_id, ...)` (`api/routes/chat.py:85`
  and `:151`), which returns early only when there is no `session_id`. Against production each of
  the 73 cases, plus the second turn of each multi-turn case, is recorded as a normal session and
  counted by `api/reports/weekly_report.py`.
- BITB-181's planned fix skips tracking only for authorized probe requests, so it does not cover
  this runner. The interpretation runner (`api/golden_set/runner.py`) sends no `session_id` and is
  unaffected.
- Multi-turn cases do not strictly need a session: the tapped chip is sent as the next message with
  the history in `conversation_history`, and `session_id` is only used for logging and tracking.
  Dropping it is therefore an option, but the Plan stage should confirm before choosing it.

## Functional Requirements

- FR1 Either send the monitor-probe header when a probe token is configured (and rely on BITB-181's
  skip), or otherwise mark or exclude these sessions. Pick in Plan.

## Acceptance Criteria

- [ ] A run against a backend creates no `sessions` rows counted by the weekly report (tested with a mocked tracker or DB)
- [ ] Multi-turn cases still work
- [ ] A test pins the runner's request headers and payload

## Out of Scope

- BITB-181 itself.
