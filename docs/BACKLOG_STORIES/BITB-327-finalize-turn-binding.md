---
id: BITB-327
status: todo
priority: P3
size: S
created: 2026-11-16
depends_on: [BITB-320]
---

# BITB-327: Bind Chat Finalize to a Recently Streamed Turn

**Prompted by:** the independent verification of BITB-320 (PR #1299, 2026-11-16), findings 3 and 5.
Filed in the same PR per *Backlog Hygiene*.

## Problem

`POST /api/v1/chat/finalize` (BITB-320) recovers chips and cited verses for a reply whose
`completion` event never reached the client. It knows only what the client sends.

1. **No-chips turns can get chips.** Off-topic redirects, clarifying questions and
   scripture-unavailable replies have no follow-up chips by design (BITB-080). Each of those
   paths builds its own small `completion` in `api/chat/service.py`. If that `completion` is
   lost, finalize sees no FOLLOWUPS trailer and asks the LLM for chips (`_llm_follow_ups`).
   Blocked and compassionate turns are already protected by the safety re-check.
2. **Finalize is not tied to a real turn.** It is not Turnstile-gated (a second challenge
   would stall recovery). It accepts up to 8000 chars of client text and puts it into a
   bounded LLM prompt, limited only by the 10/min IP rate limit. Output is capped at 3
   filtered chips, so the risk is low, but it is a free (tiny) LLM call.

## Requirements

- When `chat_stream` sends `metadata`, the server records a short-lived entry keyed by
  `message_id`. The entry holds the turn type (normal / off_topic / clarification /
  scripture_unavailable / blocked / compassionate) and a hash of the session id. It lives
  in Postgres or another store shared across replicas, with a TTL of about 10 minutes.
- Finalize generates LLM chips only for a known, unexpired, normal turn from the same
  session. Verses and citations (DB-grounded) are still returned for unknown turns, so
  recovery keeps working after a replica restart.
- Tests for each turn type, an expired or unknown `message_id`, and a session mismatch.

## Acceptance criteria

- [ ] No LLM chips for off-topic, clarification, scripture-unavailable, blocked, compassionate
      or unknown turns.
- [ ] Normal turns are recovered exactly as in BITB-320.
- [ ] No message text is stored. The entry expires by TTL.
