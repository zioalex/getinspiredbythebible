# BITB-123: Android — Suggested Follow-Up Question Chips

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S (Android-only; the backend contract and the design already exist)
**Created:** 2026-09-11
**Parent ref:** BITB-080 (backend + web shipped that story; this is its deferred Android half)

## User Story

**As** an Android user who has just read an answer, **I want** the same one-tap follow-up question
chips the web app now shows, **so that** I can keep exploring without typing on a phone keyboard.

## Context

BITB-080 shipped the backend (`api/chat/follow_ups.py`, `_wants_follow_ups` gate,
`FOLLOW_UP_SUGGESTIONS_GUIDANCE`) and the web chip UI
(`frontend/src/components/FollowUpSuggestions.tsx`). The streaming `completion` event now carries
an optional `follow_ups: list[str]` field (2-3 suggestions, or absent) whenever
`chat_follow_ups_enabled` is on and the turn is not off-topic/crisis-flagged/an error. This story is
purely the Android consumer of that same contract — no backend or web changes.

**Contract to consume (unchanged by this story):**

- `follow_ups` is a plain string array on the stream's `completion` event, absent when suppressed
  or on an older backend — render nothing, no spinner, no empty row.
- Suggestions are already sanitized server-side (length-bounded, no markup, deduped, fabricated
  scripture references filtered out) — the client does not need to re-validate them.
- Tapping a suggestion should behave exactly like typing it and sending — full conversation history
  goes with it, same as any other message.

## Proposed Behaviour

- Parse `follow_ups` off the stream's completion chunk in `ChatViewModel.kt`, mirroring how
  `resolvedVerses`/`correctedMessage` are already parsed there.
- Render a chip row (`ChatScreen.kt` / `ChatMessageItem.kt`) under the **last** assistant item in
  the `LazyColumn` only — structural via an index/position check against the list, not per-item
  state, matching the web implementation's approach (avoids stale chips reappearing on scroll).
- Tapping a chip calls the same `viewModel.sendMessage(...)` path a typed message uses, and must
  fire on the **first** tap (see BITB-081 — this app has had first-tap-swallowed bugs before).
- Clear chips the instant the next turn starts (new message submitted), on new chat, and on
  session reset — same lifecycle as the web `followUps` state.
- Content-describe the chip row for TalkBack (a group label, e.g. "Suggested follow-up questions"
  — reuse/adapt the existing `R.string` the web `Chat.followUpsLabel` key was added for, or add an
  Android string resource with the same English text for parity).

## Acceptance Criteria

- [ ] After a normal answer (flag on), 2-3 follow-up chips appear under the last assistant message.
- [ ] Tapping one sends it immediately — first tap works, no double-tap-to-send regression.
- [ ] Chips appear only under the latest assistant message and clear when the next turn starts.
- [ ] Absent `follow_ups` (suppressed turn, or flag off) renders nothing — no crash, no empty row.
- [ ] Chip row has a TalkBack-visible group label.
- [ ] Existing Android chat/stream-parsing tests pass; a Compose UI test covers chip rendering
      (position: last message only) and tap-to-send.
- [ ] BITB-024 (10-message session limit) interaction checked once both platforms exist: does
      surfacing more follow-ups measurably push users into the limit sooner, and does that matter.

## Files Likely to Change

| File | Change |
|---|---|
| `android/.../viewmodel/ChatViewModel.kt` | Parse `follow_ups` off the completion chunk into UI state |
| `android/.../ui/ChatScreen.kt` | Render chip row after the last assistant item in the `LazyColumn` |
| `android/.../ui/components/ChatMessageItem.kt` or a new `FollowUpChips.kt` | Chip row composable |
| `android/.../res/values*/strings.xml` | Group content-description string, all locales |

## Related

- **BITB-080** — parent story; backend contract and web reference implementation.
- **BITB-078** — clarifying questions; shares the same "chip row" shape conceptually (web-side the
  two now share one component — consider the same on Android if/when BITB-078 gets an Android leg).
- **BITB-081** — Android send-on-tap correctness, the same first-tap requirement this story needs.
- **BITB-024** — 10-interaction session limit; check interaction before enabling in production.
