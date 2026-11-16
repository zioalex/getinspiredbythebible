---
id: BITB-320
status: in-progress
priority: P1
size: L
created: 2026-11-15
follow_ups: [BITB-321]
---

# BITB-320: Reliable Chat Completion: Clients Recover Chips and Verses When a Stream Ends Early

## Bug report

On Android, a reply *sometimes* arrives without suggestion chips and without the cited-verse
references at the end. There is no error message. Reported 2026-11-15.

## Root cause (code-verified, narrowed with prod logs 2026-11-16)

Chips (`follow_ups`) and cited verses (`verses_cited`, `resolved_verses`, `citations`,
`corrected_message`) are delivered only in the final `completion` SSE event. When a reply ends
without it, nothing tells the user.

- **Android.** A clean EOF without `completion`, or an `{"type":"error"}` event, ends the flow
  "normally". `EventSourceParser.kt` drops unknown types in its `else ->` branch.
  `ChatViewModel` then saves the partial text with no chips and no verses, and shows no error.
  An `IOException` after content *replaces* the received text with an error message.
- **Web** (`ChatIsland.tsx`). On EOF without `completion` it extracts verse refs client-side
  but shows no chips. An `error` event after content appends an error bubble.
- **Backend logs (7 days, `make az-chat-stream-errors`).** Zero `Chat stream failed` /
  `runtime error` / `all LLM models exhausted`. Every logged request reached
  `Verse extraction completed` + `chat_stage_timings … total`. The `content_safety_block`
  signals are the prod-monitor probe ("build a bomb"), not users.
  **So the server sends `completion`. It is lost between server and device** (mobile network
  switch, app backgrounded, proxy/connection reset). The backend does not log client
  disconnects, so this has been invisible.

## User story

As a user, when a reply's connection drops partway through, I keep the text I received. The
app fetches the suggestion chips and verse references automatically. If the reply itself was
cut off, I see a short "interrupted" note and can tap **Continue**.

## Functional requirements

1. **Finalize endpoint (backend).** New `POST /api/v1/chat/finalize`: given the text the
   client received, return the same fields as a `completion` event. Contract below.
2. **Client recovery (Android + web).** When a stream ends without `completion` and some
   content was received (EOF, `error` event, network error or timeout after content), keep the
   text and call finalize automatically: one attempt plus one silent retry after ~1.5 s. Merge
   the result exactly as if `completion` had arrived. Never on a user Stop/abort.
3. **Interrupted note.** Show an inline note "This response was interrupted" with a
   **Continue** button when finalize says `truncated: true` or finalize fails. Continue sends a
   localized "Please continue" user turn. If finalize fails, strip any `<!-- FOLLOWUPS/VERSES -->`
   trailer locally so it never shows. Android persists the flag (Room), so it survives the
   live re-emission and reloads.
4. **Server degrades instead of erroring.** In `chat_stream`, a failure in post-generation
   processing still yields a `completion` (`"degraded": true`). An exception after content was
   sent yields `{"type":"error", …, "partial": true, "message_id": …}`.
5. **Observability.**
   - Backend logs `Chat stream client disconnected before completion` (WARNING) with
     `content_chars` and `completion_sent`, plus a counter.
   - Finalize logs `Chat finalize requested` (WARNING) with `reason`, `platform` and outcome,
     plus a counter.
   - `make az-chat-stream-errors` shows both signals.

## Finalize API contract (shared by all three builders)

`POST /api/v1/chat/finalize`. Dependencies: `require_ip_rate_limit("chat_finalize",
lambda: settings.chat_finalize_rate_limit_per_minute)` (new setting, default 10) and
`check_content_filter` (it reads the body's `message`). **No Turnstile**: the turn already
passed it, and a second challenge would stall recovery. Does not count toward the session
message limit.

Request (JSON, `extra="forbid"`):

| field | type | notes |
|---|---|---|
| `message` | str, 1..`max_message_length` | the user's message for this turn |
| `assistant_text` | str, 1..`max_history_message_length` (8000) | exactly what the client received |
| `conversation_history` | list[ConversationMessage], default [] | same model and trim validator as `ChatRequest` (BITB-296) |
| `preferred_translation` | str \| null | same semantics as `ChatRequest` |
| `language` | str \| null | UI locale |
| `session_id` | str | same as chat |
| `message_id` | str \| null | from the stream's `metadata` event (UUID; ignored if malformed) |
| `reason` | `"eof" \| "error_event" \| "network_error" \| "timeout"` | telemetry |
| `platform` | `"web" \| "android"`, default `"web"` | telemetry |

Response 200:

```json
{"verses_cited": ["John 3:16"], "resolved_verses": [VerseResult...], "citations": [...],
 "corrected_message": "…", "corrections": [...], "follow_ups": ["…"], "truncated": false}
```

- `corrected_message` is present only when it differs from `assistant_text`: a trailer was
  stripped or grounding rewrote a quote. `corrections` and `follow_ups` are present only when
  non-empty.
- `truncated` is true when the text has no `<!-- VERSES:` / `<!-- FOLLOWUPS:` marker **and**
  does not end with sentence-final punctuation (`. ! ? … 。 ！ ？ ؟ ।` optionally followed by
  closing quotes/brackets).
- **Chips:** from the trailer if present. Otherwise one bounded LLM call (`max_tokens` ≤ 200,
  temperature 0.3) asking for the FOLLOWUPS trailer in the user's language, parsed with the
  existing `split_follow_ups`, then the same sanitizer and fabricated-reference filter
  (`_filter_fabricated_follow_ups`). Skipped entirely when `settings.chat_follow_ups_enabled`
  is off. An LLM failure means no chips, never a 5xx.
- **Verses:** resolved from the DB in the user's translation via the same grounding path
  (`_ground_streamed_answer`) with `scripture_context=None`. Never text from the client.
- Errors: 422 validation, 429 rate limit, 400 content filter (as chat). Everything else
  degrades to a 200 with what could be computed.

## Implementation plan

### Backend (`api/`)

- `chat/service.py`:
  - Extract the post-generation block of `chat_stream` (from `split_follow_ups` through
    building `completion` incl. `citations` and `follow_ups`; today ≈ lines 2071–2219) into
    `async def _build_completion(self, raw_text, *, request_history, scripture_context,
    translation, language, compassionate, crisis_suffix) -> tuple[dict, bool]` (payload,
    trailer_present). Keep the metrics/log calls that belong to the stream in `chat_stream`.
  - `chat_stream` calls it inside `try`. On exception, `logger.exception` and yield a degraded
    completion built defensively, each part in its own `try`: `verses_cited` from
    `extract_all_references(clean)`, `follow_ups` from the trailer via the existing sanitizer,
    `corrected_message` = clean text if a trailer was stripped, `"degraded": True`.
  - New `async def finalize(self, req: FinalizeRequest) -> dict`. It resolves translation and
    language the same way `chat_stream` does, calls `_build_completion`, adds LLM chips when
    there is no trailer, and computes `truncated`.
- `chat/` (models next to `ChatRequest`): `FinalizeRequest`, `FinalizeResponse`.
- `chat/prompts.py`: `get_follow_ups_only_prompt(language_code)`, English instructions plus
  "answer in <language>", output exactly the existing FOLLOWUPS trailer format.
- `routes/chat.py`:
  - New `POST /finalize` route (the router prefix gives `/api/v1/chat/finalize`).
  - In `generate()`: remember `message_id` from the metadata chunk, count content chars, track
    `completion_sent`.
  - On `asyncio.CancelledError` / `GeneratorExit`, log the WARNING above, increment the counter
    and re-raise.
  - Error events after content add `"partial": true, "message_id": …`.
- `config.py` + `scripts/env-manifest.yaml`: `CHAT_FINALIZE_RATE_LIMIT_PER_MINUTE` (default 10,
  `required_in: none`).
- `utils/metrics.py`: `chat.stream.client_disconnected`, `chat.finalize.requests`
  (attrs: `reason`, `platform`, `outcome` ∈ ok/llm_chips/no_chips/error).
- `scripts/az-logs.sh` `chat-stream-errors`: add signals `client_disconnected`
  ("Chat stream client disconnected") and `client_finalize` ("Chat finalize requested").
  Extend `scripts/test_az_logs.py`.
- Capability parity registry (BITB-262): register the capability for web and android (find it
  with `grep -rn parity docs scripts`).

### Android (`android/`)

- `data/remote/models`: `FinalizeRequestDto` / `FinalizeResponseDto` (`@SerialName` snake_case).
  `StreamChunkDto` gets `errorMessage`, `partial` and `messageId` for `type="error"`.
- `data/streaming/EventSourceParser.kt`: emit `type="error"` chunks instead of dropping them.
- `data/remote/api/BibleApiService.kt`: `@POST("api/v1/chat/finalize")`.
  Repository: `suspend fun finalize(...)`.
- `presentation/viewmodels/ChatViewModel.kt` `sendMessage`:
  - Track `receivedCompletion`, `streamEndReason`, and `userCancelled` (Stop).
  - After the stream, if `!receivedCompletion && !userCancelled && accumulatedContent.isNotBlank()`,
    run recovery (finalize + 1 retry) and merge into the same final-message path as a completion.
  - An `IOException`/timeout *after content* goes to recovery instead of replacing the text.
    With no content, keep today's error path.
  - No snackbar or error state on recovery.
- `domain/models/Message.kt`: `isInterrupted: Boolean = false`. Room: column `interrupted`
  (INTEGER NOT NULL DEFAULT 0), `MIGRATION_2_3` in `data/local/Migrations.kt`, DB version 3,
  exported schema JSON, entity mapper.
- UI (`ChatMessageItem` / `ChatScreen`): note + **Continue** under an interrupted assistant
  message (only the latest one shows Continue). TalkBack live region, 48dp target. Continue
  calls `sendMessage(stringResource(chat_continue_prompt))`.
- Strings in `values/` and all 10 `values-<locale>/`: `chat_interrupted_note`,
  `chat_continue_button`, `chat_continue_prompt`.

### Web (`frontend/`)

- `src/lib/api.ts`: `finalizeMessage(...)` + types. `StreamChunk` gets `partial` / `message_id`.
- `src/app/[locale]/ChatIsland.tsx`: same recovery rules (replaces today's client-only
  fallback):
  - `error` event after content, stream end without completion, or a network/timeout error
    after content → finalize → merge.
  - Abort never recovers. No content → existing error path.
- Message type gets `interrupted?: boolean`. Render the note + Continue (`role="status"`,
  ≥44px target). Continue sends `t("chat.continuePrompt")`.
- `messages/*.json` (11 locales): `chat.interruptedNote`, `chat.continueButton`,
  `chat.continuePrompt`.

## Non-functional requirements

- **11 languages** (en, it, de, es, fr, pt, ar, ru, zh, hi, ko): new strings on both clients.
  Finalize verse extraction is tested with a parametrized test across all 11, including CJK
  fullwidth, RTL, Devanagari, German comma, parenthesized citations and ranges. `truncated` is
  tested with each language's sentence-final punctuation.
- **Version-faithful:** `resolved_verses` uses the request's translation (test KJV vs WEB).
- **Privacy:** finalize logs never include message or assistant text.
- **Backward compatible:** new fields are additive. Old Android builds are unaffected.

## Acceptance criteria

- [ ] Backend: finalize contract tests (happy path, trailer chips, LLM chips, LLM failure →
      no chips, `truncated` cases, 11-language verse extraction, KJV vs WEB, rate limit,
      content filter, 422s). An integration test through `chat_stream()` shows a
      post-processing exception yields `completion` with `degraded: true`. Route tests: the
      disconnect is logged and counted, and the error event after content carries `partial`.
- [ ] Android: parser test (`error` surfaced). ViewModel tests: EOF without completion, error
      event, and IOException after content each trigger finalize and merge chips and verses;
      finalize failure keeps the text, marks it interrupted and strips the trailer; Stop does
      not finalize; no content means the old error path. Migration 2→3 test. Compose test for
      the note and Continue.
- [ ] Web: Vitest for the same scenarios. `npm run lint`, `tsc --noEmit` and the build pass.
- [ ] Strings present in all 11 locales (Android translation validation, web messages).
- [ ] `make az-chat-stream-errors` shows `client_disconnected` / `client_finalize`.
- [ ] Owner step: after deploy, `make az-chat-stream-errors DAYS=3` shows how often streams
      end early, and on which platform.

## Out of scope

- Llama Guard primary model failing on every request (BITB-321).
- Blocked-sample capture switch in Terraform (BITB-326).
- Auto-continuing without the user tapping Continue. Re-running the whole request.

## Follow-ups

- BITB-321: Llama Guard primary (`llama-guard-4-12b`) returns `content: null` on every call.
