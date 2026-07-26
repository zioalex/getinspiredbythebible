# BITB-080: Suggested Follow-Up Questions as One-Tap Buttons Under Each Answer

**Status:** 🎯 Todo
**Priority:** P2
**Size:** M (1–2 days, backend + web + Android)
**Created:** 2026-07-25

## User Story

**As a** user who has just read an answer,
**I want** two or three suggested next questions offered as buttons under it,
**so that** I can keep exploring without having to work out what to ask next — or type it on a
phone.

## Why

The welcome screen already does this and it works: four randomized starter prompts, and tapping one
submits it immediately (`ChatIsland.tsx:1061-1070` → `submitMessage(prompt)`; Android
`WelcomeBanner.kt` → `ChatScreen.kt:370-382`). That scaffolding disappears the moment the first
answer arrives, exactly when the user has the most to explore and the least idea how to phrase it.

Conversations here end after one turn far more often than they should. Someone who asked about
anxiety may want the passage in context, or a prayer, or what to do when the feeling comes back
tonight — but they have to invent the question themselves, in their own words, into a small
keyboard, while emotionally spent. A concrete, tappable next step removes all of that friction, and
each suggestion also teaches what this companion can do.

There is a design pairing with **BITB-078**: that story asks a clarifying question *before*
answering; this one offers next questions *after*. Both need the same thing on the client — a row
of tappable, send-on-tap chips. **Build the chip component once and use it for both.**

## Current Behaviour

- No follow-up affordance exists after an assistant message. `ChatMessage.tsx` renders content,
  verse chips and feedback controls; nothing else.
- The streaming contract already has a clean place to carry this. The `completion` event
  (`api/chat/service.py:1375-1386`) is a dict that grew `resolved_verses`, `corrected_message` and
  `corrections` over time, with the explicit note that *"older clients ignore unknown fields, so
  this is backward compatible"*. `StreamChunk` on the web side
  (`frontend/src/lib/api.ts:563-589`) mirrors it with optional fields.
- Conversation history is already sent back on the next turn
  (`ChatRequest.conversation_history`, `service.py:96`), so a tapped follow-up behaves like any
  other user message with full context — no new plumbing needed.

## Proposed Behaviour

**Backend — generate the follow-ups.** Add an optional `follow_ups: list[str]` to the `completion`
event (and to `ChatResponse` for the non-streaming path). Two viable approaches:

1. **In-prompt (recommended for v1).** Extend the system prompt so the model appends its suggested
   follow-ups in a machine-readable trailer, exactly like the existing verse-citation mechanism
   (`<!-- VERSES: ... -->` in `SYSTEM_PROMPT_TEMPLATE`), e.g. `<!-- FOLLOWUPS: ...|...|... -->`.
   Strip it from the visible text in the same place the verse comment is stripped, and emit it in
   `completion`. Zero extra latency, zero extra cost, and the suggestions are grounded in what was
   actually said.
2. **Separate fast call.** A second cheap LLM call after generation. Cleaner separation, but adds
   latency to the end of every turn and a second failure mode.

Constraints on the generated suggestions:

- **2–3** suggestions, never more (a wall of buttons is its own kind of pressure).
- Written **in the user's language**, in the user's voice — they are things the *user* would say
  ("What does Psalm 34 say in context?"), not menu labels.
- Short enough to render on one or two lines on a phone (~60 characters).
- Genuinely different from each other and from what was just asked.
- **Suppressed entirely** when the turn was off-topic, when the safety pipeline flagged
  `compassionate_response_needed` (someone in crisis is not offered a menu), and on any error turn.
- Never fabricate scripture references in a suggestion.

**Clients — render as send-on-tap chips.**

- **Web:** a chip row under the last assistant message only (not under every message in the
  scrollback), wired to the existing `submitMessage` path so a tap sends immediately. Chips clear as
  soon as a new turn starts. Reuse the visual language of the welcome-screen prompt buttons.
- **Android:** the same, under the last assistant item in the chat `LazyColumn`
  (`ChatScreen.kt`), calling `viewModel.sendMessage(...)` — and it must send on the first tap
  (see **BITB-081**).

**Degrade silently.** If `follow_ups` is absent (older backend, or suppressed), the client renders
nothing. No spinner, no empty row.

## Acceptance Criteria

- [ ] After a normal answer, 2–3 follow-up buttons appear under the last assistant message on web
      and Android.
- [ ] Tapping one sends it immediately as a user message — no second tap, no manual send.
- [ ] Suggestions are in the conversation's language.
- [ ] Chips appear only under the **latest** assistant message and disappear when the next turn
      starts.
- [ ] No follow-ups on off-topic replies, crisis-flagged turns, or errors.
- [ ] A client on an older backend (no `follow_ups` field) is unaffected.
- [ ] The follow-up trailer never leaks into the visible answer text.
- [ ] Perceived end-of-turn latency does not regress measurably (check the stage timings).
- [ ] The suggestion row is keyboard accessible on web and screen-reader labelled on both platforms.

## Tests to Add

- API: the trailer is parsed into `follow_ups` and stripped from the message body; malformed or
  missing trailer yields an empty list without erroring.
- API: follow-ups suppressed for off-topic and crisis-flagged turns.
- `frontend/src/lib/api.test.ts` — `completion` chunk carrying `follow_ups` is surfaced; absent
  field is handled.
- Web component test: chips render under the last message only; tap submits.
- Android: Compose UI test (the `testDebugCompose` tier, **BITB-034**) — chips render and a tap
  triggers `sendMessage`.

## Files Likely to Change

| File | Change |
|---|---|
| `api/chat/prompts.py` | Follow-up trailer instruction + constraints |
| `api/chat/service.py` | Parse/strip trailer; add `follow_ups` to `completion` and `ChatResponse` |
| `frontend/src/lib/api.ts` | `follow_ups?: string[]` on `StreamChunk` / `ChatResponse` |
| `frontend/src/app/[locale]/ChatIsland.tsx`, `ChatMessage.tsx` | Chip row under the last answer |
| `android/.../ChatViewModel.kt`, `ChatScreen.kt`, `ChatMessageItem.kt` | Parse + render + send on tap |
| `frontend/messages/*.json`, `android/.../strings.xml` | Accessibility label for the row |

## Risks

- **Generic suggestions are worse than none.** "Tell me more" adds nothing. Review real output
  before enabling by default; consider a config flag and a manual read of a sample of turns.
- **Steering people away from what they actually wanted to say.** Chips should sit *under* the
  answer as an option, never replace or crowd the composer.

## Related

- **BITB-078** — clarifying questions; shares the chip component.
- **BITB-081** — Android send-on-tap; the same first-tap requirement.
- **BITB-024** — 10-interaction session limit: more follow-ups means hitting that ceiling sooner.
  Check the interaction between the two before rollout.
