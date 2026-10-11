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
  and `:151`), which returns early only when there is no `session_id`. Turn 2 of a multi-turn
  case reuses turn 1's `session_id` (`follow_up_runner.py:288`), so it adds a message to the same
  `sessions` row. Against production a run therefore records one session per case (77) and 88
  messages (77 + 11 second turns, the 11 `multi-turn` cases in `follow_ups.yaml`), all counted by
  `api/reports/weekly_report.py`.
- BITB-181's planned fix skips tracking only for authorized probe requests, so it does not cover
  this runner. The interpretation runner (`api/golden_set/runner.py`) sends no `session_id` and is
  unaffected.
- Multi-turn cases do not strictly need a session: the tapped chip is sent as the next message with
  the history in `conversation_history`. But `session_id` is used for more than tracking:
  - the per-session rate limit: `rate_limit_requests_per_session_minute` (10/min) and the
    `rate_limit_session_max_requests` cap (10, `rate_limit_sessions` table) via
    `api/utils/security.py` (~217-228, reads `session_id` from the body) and
    `api/utils/rate_limiter.py`; the check is skipped for authorized monitor probes;
  - the OTel `chat_sessions_counter` (`api/routes/chat.py:80` and `:134`);
  - `record_blocked_sample(..., session_id=...)` and the safety log (`api/chat/service.py:261-273`).

  Dropping `session_id` would move the runner onto the per-IP limit only and keep it out of the
  OTel session counter, but it changes rate-limit behaviour; the Plan stage should confirm.

## Functional Requirements

- FR1 Either send the monitor-probe header when a probe token is configured (and rely on BITB-181's
  skip), or otherwise mark or exclude these sessions. Pick in Plan.

## Acceptance Criteria

- [ ] A run against a backend creates no `sessions` rows counted by the weekly report (tested with a mocked tracker or DB)
- [ ] The OTel `chat_sessions_counter` is not incremented by the runner
- [ ] Multi-turn cases still work
- [ ] A test pins the runner's request headers and payload

## Out of Scope

- BITB-181 itself.
