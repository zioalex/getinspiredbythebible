---
id: BITB-265
status: in-review
priority: P1
size: S
rank: 220
created: 2026-11-03
---

# BITB-265: Query Expansion Logs the User's Message and the Expanded Query

**Found by:** BITB-256 verification

## Problem (verified in code, 2026-11-03)

`ChatService._expand_query` (`api/chat/service.py`, the "Query expansion completed" log) writes
`original_query` (the first 100 characters of the user's message) and `expanded_query` (the
first 200 characters of the LLM expansion) into a structured log record on every chat turn with
query expansion enabled. Similar `message_preview` fields exist in other info logs (for example
"Language detection and translation resolution").

This contradicts the privacy posture the policy states ("Chat messages: not retained on our
servers") and the BITB-256 design, where neither the prompt nor the expanded sentence may appear
in a table, log or counter. Application Insights retains these records.

## Requirements

1. Remove user text and expansion text from info-level logs; log lengths, language, timing and
   booleans only. If a debugging aid is needed, gate it behind an explicit `DEBUG` flag that is
   off in production.
2. Audit `api/` for other log calls that include message content (`message_preview`,
   `original_query`, `expanded_query`) and fix or justify each.
3. Add a sentinel test through `chat()` / `chat_stream()` asserting no log record contains the
   user message or expansion text.

## Acceptance criteria

- [x] No info/warning log record from a normal chat turn contains the message or expansion text.
- [x] Sentinel test passes on both chat paths.
- [ ] Privacy policy wording reviewed against actual log contents.

## Implementation notes (2026-11-03)

- `_expand_query` logs `original_query_chars` / `expanded_query_chars`; the two "Language detection"
  logs carry `message_chars`; `log_security_violation` takes `message_length` instead of a preview.
- Audit of `api/` found no other log call carrying message content. `details` on security violations
  holds only the filter's reason string.
- Tests: `api/tests/test_log_privacy.py` (44 cases, 11 languages; all fail on the old code).
- Open: privacy-policy wording review (last AC) stays with the owner. Logs now match the stated
  "chat messages: not retained" posture, so no wording change is proposed.
