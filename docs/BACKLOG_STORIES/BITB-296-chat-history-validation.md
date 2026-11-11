# BITB-296: Validate and Bound Client-Supplied Chat History

**Status:** 🎯 Todo
**Priority:** P0
**Size:** S
**Created:** 2026-11-11
**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) rows R4, R5, R6.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), wave 1.
**Commit:** `fix(api): validate and bound client-supplied chat history (BITB-296)`

## Problem

The chat endpoints trust the `conversation_history` the client sends:

- `ConversationMessage.role` is a free `str` (`api/chat/service.py:129`) and is forwarded
  unchanged to the LLM (`api/chat/service.py:2267`). A client can send `role: "system"`
  turns that sit next to the real system prompt.
- `content` has no length limit (`:130`) and the list has no length limit (`:141`). The
  500-character limit on `message` (`api/config.py:193`) is bypassed through history.
- There is no request-body size limit in the backend at all.

Reproduced on 2026-11-11: `ChatRequest` accepted 5,002 entries including a
1,000,000-character entry, and `_build_messages` produced roles
`['system', 'system', 'assistant', 'user']`. Only the last
`max_conversation_history` (10) entries reach the LLM, so one request can carry about
10 MB into a paid model call.

Both shipped clients send the **whole** thread on every turn (`frontend/src/lib/api.ts:557,704,726`;
Android `ChatViewModel.kt:724`), and "Continue this conversation" (BITB-118) lets a thread
outlive the 10-message session cap. Legitimate requests therefore grow without bound too —
the fix must not start rejecting long, honest conversations.

## Decisions already made

1. **Reject unknown roles; trim and truncate sizes.** A role outside `user`/`assistant`
   is never legitimate → `422`. Over-long history or content is legitimate → silently
   keep what the LLM would have seen anyway.
2. **Trim the list before validating entries**, so a 5,000-entry request costs nothing.
3. **Content cap is 8,000 characters per history entry**, configurable. The model's
   output is capped at `llm_max_tokens = 1024` (`api/config.py:26`), so an honest
   assistant turn stays far below it.
4. **Body cap is 1 MiB**, configurable, enforced before JSON parsing, answered with `413`.
5. **History is not run through the content filter or ML safety in this story.** A
   message that was allowed through the crisis bypass (`api/utils/security.py:327-342`)
   would be re-blocked on every later turn and break the conversation exactly when the
   user is in crisis. Recorded as a follow-up decision below.

## Requirements

1. `ConversationMessage.role` becomes `Literal["user", "assistant"]`.
2. `ConversationMessage.content` is truncated to `settings.max_history_message_length`
   (new setting, default `8000`) by a `mode="before"` validator. Non-string content is
   still a validation error.
3. `ConversationMessage.follow_ups` is limited to at most 5 items of at most 200
   characters each (drop extras; do not reject). Check `sanitize_follow_ups` first — if it
   already enforces limits, reuse its constants instead of inventing new ones.
4. `ChatRequest.conversation_history` gets a `mode="before"` validator that keeps only
   the **last** `settings.max_conversation_history` entries when given a list.
5. A body-size guard rejects any request whose body exceeds
   `settings.max_request_body_bytes` (new setting, default `1_048_576`) with `413` and a
   JSON body `{"detail": {"error": "request_too_large"}}`. It must:
   - check `Content-Length` first and reject without reading;
   - also bound chunked bodies that omit `Content-Length` (count bytes while receiving);
   - be a pure ASGI middleware, not `BaseHTTPMiddleware`, so the SSE response of
     `/chat/stream` is not buffered.
6. Both new settings are added to `scripts/env-manifest.yaml` (the env source of truth)
   and documented where the existing limits are documented (`docs/SECURITY.md` if it
   lists them — read it first).
7. Both clients must keep working unchanged. Add a `413` branch to the web error mapping
   only if the existing mapping would show a misleading message; otherwise leave clients
   alone.

## Files

| File | Change |
|---|---|
| `api/chat/service.py` | Requirements 1–4 on `ConversationMessage` / `ChatRequest` |
| `api/config.py` | `max_history_message_length`, `max_request_body_bytes` |
| `api/middleware/` | New `body_size_limit.py` (pure ASGI) |
| `api/main.py` | Register the middleware (outermost, before CORS handling of the body) |
| `scripts/env-manifest.yaml` | Two new variables |
| `api/tests/` | New `test_chat_history_validation.py`, `test_body_size_limit.py` |

## Tests (minimum)

- Role `system`, `tool`, `""`, `"User"` → `422`; `user` and `assistant` accepted.
- 5,000-entry history is accepted and reduced to the last 10; assert **which** 10.
- A 1,000,000-character entry is truncated to exactly the configured cap.
- Truncation is character-safe across scripts: parametrize one over-long entry per
  language (en, it, de, es, fr, pt, ar, ru, zh, hi, ko) and assert the result is valid
  text of the capped length (no exception, no lone surrogate).
- Integration through `chat()` **and** `chat_stream()` with the LLM mocked: a forged
  `system` history entry never reaches the provider; assert on the messages the mock
  received.
- Body guard: `Content-Length` over the cap → `413` without the handler running; chunked
  body over the cap → `413`; body at the cap → passes; a streaming response still streams
  (first chunk arrives before the last is produced).
- Existing suites (`test_chat_follow_ups.py`, `test_chat_coverage.py`,
  `test_chat_crisis_path.py`) stay green.

## Acceptance criteria

- [ ] The local proof in the review §6 raises a validation error for `role: "system"`
- [ ] A request with megabytes of history reaches the LLM with at most
      `max_conversation_history × max_history_message_length` characters of history
- [ ] Requests over 1 MiB are rejected with `413` before parsing
- [ ] Web and Android chats of 30+ turns still work (covered by a test that sends 60
      entries and gets `200`)
- [ ] New settings are in `scripts/env-manifest.yaml`

## Out of scope

- Filtering or ML-checking history content (decision 5).
- Server-side or signed history.

## Follow-up decision for the owner

Forged `assistant` turns ("as I agreed earlier…") remain possible because the server
holds no conversation state. Options: (a) HMAC-sign each assistant turn and verify on
return; (b) store conversations server-side keyed by `conversation_id`. File a story once
chosen.

## Related

BITB-118, BITB-254 (follow-up echo is untrusted input), BITB-298.
