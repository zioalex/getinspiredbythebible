---
id: BITB-320
status: todo
priority: P1
size: L
created: 2026-11-15
follow_ups: [BITB-321]
---

# BITB-320: Reliable Chat Completion: Server Always Completes, Clients Auto-Recover Missing Chips and Verses

## Bug report

On Android, a reply *sometimes* arrives without suggestion chips and without the cited-verse
references at the end. There is no error message. Reported 2026-11-15, after deploying `e401385`.

**Root cause (code-verified).** Chips (`follow_ups`) and cited verses (`verses_cited`,
`resolved_verses`, `citations`, `corrected_message`) are delivered only in the final
`completion` SSE event. When `chat_stream` raises after content has started streaming,
`api/routes/chat.py` (`generate()`) sends `{"type":"error",...}` instead. Android's
`EventSourceParser.kt` drops unknown event types (the `else ->` branch), so the flow ends
"normally". `ChatViewModel` then saves the partial reply with no chips and no verses, and shows
no error. A connection that closes before `[DONE]` has the same effect (the reader hits EOF and
completes normally). The web client throws on `type: "error"` (`ChatIsland.tsx:579`), so it
surfaces the failure instead of hiding it. That is why it "works on web".

The failure is intermittent because it depends on a server-side failure partway through the stream.
That cause is investigated in BITB-321.

## User story

As a user of the Android (or web) app, when the server or network fails partway through a reply,
I keep the text I already received. The app fetches the suggestion chips and verse references
automatically. If the reply was cut off, I see a short note and can tap **Continue**.

## Functional requirements

1. **Server always completes when it can (backend).** A failure in post-generation processing
   (grounding, citation extraction, citation spans, follow-up filtering, retrieval-miss hook)
   must not replace `completion` with `error`. Each step degrades on its own, for example
   regex-only `verses_cited`, unresolved verses omitted, follow-ups from the trailer only.
   A best-effort `completion` is always sent. A degraded completion is marked with
   `"degraded": true`.
2. **Recoverable error event (backend).** When the stream fails after content was sent (for
   example the AI provider drops mid-reply), the error event carries `"partial": true` and the
   `message_id`, so a client can tell "reply cut off" apart from "nothing produced".
3. **Finalize endpoint (backend).** New `POST /chat/finalize` returns the same fields as a
   `completion` event (`verses_cited`, `resolved_verses`, `citations`, `corrected_message?`,
   `follow_ups?`) for a reply the client already holds. Inputs: the assistant text it received,
   the user message, a short conversation tail, `preferred_translation`, `language`,
   `session_id`, `message_id`.
   - Verses are resolved from the DB in the user's selected translation, never from text the
     client sent.
   - Chips come from the `FOLLOWUPS` trailer if the received text has one. Otherwise one small,
     bounded LLM call generates them. They pass the existing sanitizer and the
     fabricated-reference filter.
   - The response says whether the text looked complete (`truncated: true` when there was no
     trailer and the stream had reported `partial`).
4. **Android auto-recovery.**
   - The parser surfaces `error` events, and the ViewModel tracks whether `completion` arrived.
   - On `error`, a dropped connection, or EOF without `completion`, with content already
     received: keep the text, call `/chat/finalize` automatically (one silent retry with
     backoff), and merge the result exactly as if `completion` had arrived (chips, Cited tab,
     verse links, trailer stripped from the text). Then persist the message.
   - If the reply was cut off (`partial`/`truncated`), show an inline "This response was
     interrupted" note with a **Continue** button. Continue sends a localized "please continue"
     turn.
   - If finalize also fails: keep the text, strip a visible trailer locally, show the
     interrupted note, and show no error dialog.
   - With no content received: unchanged (the existing error path).
5. **Web parity.** The web client applies the same recovery. It keeps the partial text instead
   of discarding it on `type: "error"`, calls `/chat/finalize`, and shows the same note and
   Continue button.
6. **Observability.** Counters for: completion sent degraded, stream ended with partial error,
   client finalize calls (by outcome).

## Non-functional requirements

- **Languages:** the note, the Continue button and the "please continue" text in all 11 locales
  (en, it, de, es, fr, pt, ar, ru, zh, hi, ko) on web and Android. Recovered verse
  extraction is tested across all 11 languages, including CJK/fullwidth, RTL and Devanagari
  citations, through the finalize endpoint.
- **Version-faithful:** resolved verses use the user's selected translation (test KJV vs WEB).
- **Security / abuse:** `/chat/finalize` has the same Turnstile gate, rate limiting
  (scope-namespaced IP limit) and content filter as chat. It enforces body and length bounds
  (BITB-296), uses no history beyond the bounded tail, and does not count toward the per-session
  message limit. The LLM call only happens when chips are missing, and is capped (short prompt,
  low max tokens).
- **Accessibility:** the note is announced (TalkBack live region / ARIA `status`). Continue has a
  48dp / 44px touch target.
- **Performance:** recovery adds ≤ 1 extra request in the common case. Finalize p95 is under 3 s
  without the LLM step.
- **Backward compatible:** older Android builds ignore the new fields. `degraded` and `partial`
  are additive.

## Acceptance criteria

- [ ] Backend: a post-processing exception (grounding, citation spans, follow-ups) still emits a
      `completion` (`degraded: true`). Tested through `chat_stream()`.
- [ ] Backend: a mid-content provider failure emits `error` with `partial: true` + `message_id`.
- [ ] Backend: `/chat/finalize` returns verses and citations for the received text in all 11
      languages and is version-faithful. Chips come from the trailer or the bounded LLM step.
      Gated by Turnstile, the rate limit and the content filter.
- [ ] Android: unit tests for the parser (`error` surfaced) and for the ViewModel (error event,
      EOF without completion and IOException after content each trigger finalize; the merge
      restores chips and verses; finalize failure keeps the text and shows the note). Compose
      test for the note and Continue.
- [ ] Web: Vitest coverage for the same scenarios.
- [ ] Strings present in all 11 locales (Android translation-validation and web messages).
- [ ] Docs: the API endpoint is documented. Capability parity registry (BITB-262) updated.

## Out of scope

- Finding and fixing the server-side cause of the mid-stream failures (BITB-321).
- Auto-continuing a truncated reply without the user tapping Continue.
- Re-running the whole request automatically.

## Open questions

- None blocking. Plan stage decides: whether the finalize LLM step uses the main chat provider
  or a cheaper model, and the exact client heuristic for `truncated`.

## Follow-ups

- BITB-321: investigate and fix the intermittent server-side mid-stream failure.
