# BITB-254: Follow-Up Chips Stop Appearing After a Few Turns (Web + Android)

**Status:** 🚧 In Progress
**Priority:** P1
**Size:** M (backend + web + Android)
**Created:** 2026-10-28
**Parent:** BITB-080 (suggested follow-up questions), BITB-149 (Android chips)

## Bug Report

> "I merged the suggestion chips feature. It works, but after a few interactions it stops
> suggesting new proposals. Happens on both web and Android 1.57.0."

## Root Cause

Both platforms are affected, so the cause is on the backend / in the prompt, not in either client.

1. **The model copies its own history (main cause).** The model is asked to end each answer
   with `<!-- FOLLOWUPS: q1|q2|q3 -->`. The server strips that trailer
   (`split_follow_ups`) and sends the clean body back as `corrected_message`. Both clients store
   that clean body (`ChatIsland.tsx` `streamedContent = chunk.corrected_message`,
   `ChatViewModel.kt` `chunk.correctedMessage`) and send it back on the next turn as
   `conversation_history`. So from turn 2 on, **every earlier assistant message the model sees
   has no trailer**, and the only instruction to write one sits at the top of a long system
   prompt (`FOLLOW_UP_SUGGESTIONS_GUIDANCE`, `_build_messages` in `api/chat/service.py`).
   The model follows the pattern of its own earlier turns and leaves the trailer out more and
   more often as the conversation grows.
2. **The verse filter is too strict on later turns.** `_filter_fabricated_follow_ups` drops any
   suggestion that names a verse this answer did not cite, even a verse the user discussed
   a turn earlier. If that leaves fewer than 2 suggestions, **all** chips are dropped.
   Follow-up questions in a longer conversation often refer to an earlier verse.
3. **No telemetry.** Nothing records turns where follow-ups were enabled but none were sent,
   so the drop-off is invisible in production.

## Decisions (user, 2026-10-28)

- Fix (1) by having the **clients echo each turn's chips back** in `conversation_history`; the
  server puts the trailer back on earlier assistant turns, so the history shows the model the
  format it is asked to use. (Chosen over a server-only prompt reminder.)
- Also fix (2): allow verses cited in the recent history window.
- Also fix (3): add an OTel counter with the reason.

## Functional Requirements

- **FR1 (API):** `ConversationMessage` gains an optional `follow_ups: list[str] | None = None`.
  Old clients that leave it out keep working (backward compatible); unknown fields are still ignored.
- **FR2 (API):** In `_build_messages`, only when `follow_ups_enabled` is true for this turn, each
  history assistant message with `follow_ups` gets `\n\n<!-- FOLLOWUPS: a|b|c -->` appended to the
  LLM-facing content. Echoed suggestions are untrusted client input: re-sanitize them with the
  same rules as `split_follow_ups` (reuse `_clean_suggestion`, dedupe, cap 3, need ≥2, else skip),
  so a client can never inject `-->` or markup into the prompt. When follow-ups are disabled
  (flag off, compassionate, off-topic or clarification path), history is passed through
  unchanged, with no trailer.
- **FR3 (API):** `_filter_fabricated_follow_ups` accepts verses cited in this answer **or**
  found by `extract_all_references` in the history messages that `_build_messages` actually
  sends (`history[-settings.max_conversation_history:]`, user and assistant). Applies to
  both `chat()` and `chat_stream()`.
- **FR4 (API):** an OTel counter `chat.follow_ups.suppressed` (`chat_follow_ups_suppressed_counter`
  in `api/utils/metrics.py`; App Insights may show it as `chat_follow_ups_suppressed`) is incremented once per turn where follow-ups were enabled but none
  were sent, with attributes `reason` ∈ {`no_trailer`, `too_few_valid`, `fabrication_filter`},
  `language`, and `history_turns` bucket (`0`, `1-2`, `3-5`, `6+`) — counts history *messages*, not
  question/answer pairs, so 3 exchanges land in `6+`. It applies to both
  `chat()` and `chat_stream()`.
- **FR5 (Web):** `Message` (`frontend/src/lib/api.ts`) gains `follow_ups?: string[]`. When a
  completion carries `follow_ups`, they are saved on that assistant message, so they are sent
  in `conversation_history` and persisted in local (IndexedDB) history. Chip display is
  unchanged (latest message only, state `followUps`).
- **FR6 (Android):** domain `Message` gains `followUps: List<String> = emptyList()`;
  `ConversationMessageDto` gains `@SerialName("follow_ups") val followUps: List<String>? = null`
  (sent only when non-empty); the ViewModel saves the completion's `followUps` on the assistant
  message. The message is saved **whatever the rollout flag says** (echoing them back helps
  the model even when chips are hidden), but chips only *render* behind
  `CHAT_FOLLOW_UPS_ENABLED`, as today. Room persistence is optional; if the entity is touched,
  add a migration.

## Non-Functional Requirements

- Multilingual: the echo-back is language-agnostic, but tests must be parametrized across all 11
  languages (en, it, de, es, fr, pt, ar, ru, zh, hi, ko). This covers the fullwidth `｜`
  separator for zh, plus RTL/Devanagari suggestions surviving the round trip unchanged.
  The history-verse filter test must cover localized references (e.g. `Giovanni 3:16`,
  `Johannes 3,16`, `约翰福音3:16`).
- No extra LLM calls and no new latency: string work only.
- Prompt-injection safety: echoed text goes through the same sanitizer as model output.

## Acceptance Criteria

- [ ] A history assistant message with `follow_ups` reaches the LLM with a well-formed trailer when
      follow-ups are enabled, and without one when disabled/compassionate/off-topic.
- [ ] Malicious echoed suggestions (`-->`, `<script>`, >120 chars, 1-item lists) never reach the prompt.
- [ ] A suggestion that names a verse cited only in recent history is kept; one that names a verse
      cited nowhere is still dropped.
- [ ] `chat.follow_ups.suppressed` fires with the right reason in each of the three cases, on both
      `chat()` and `chat_stream()`.
- [ ] Web: after a completion with `follow_ups`, the next request's `conversation_history`
      includes them on that assistant message (vitest).
- [ ] Android: after a completion with `followUps`, the next `ChatRequestDto` serializes
      `follow_ups` on that assistant message, including with the rollout flag off (JVM test).
- [ ] Old-client compatibility: a request with no `follow_ups` anywhere behaves exactly as before.
- [ ] Owner: after deploy, check the `chat_follow_ups_suppressed` rate by `history_turns`
      bucket in App Insights.

## Out of Scope

- A server-only prompt reminder (not chosen; can be added later if the counter shows the
  drop-off persists).
- Android 1.57.0 already in users' hands: it sends no `follow_ups`, so it only benefits from
  FR3 until the next Android release ships FR6.
- Raising `llm_max_tokens` (truncating long answers before the trailer is possible, but
  unconfirmed; the new counter's `no_trailer` reason will show if it matters).

## Plan (per file)

| File | Change |
|------|--------|
| `api/chat/follow_ups.py` | Add `sanitize_follow_ups(list[str]) -> list[str]` (shared cleaning/dedupe/cap/≥2 rule; `split_follow_ups` reuses it) and `format_follow_ups_trailer(list[str]) -> str`. |
| `api/chat/service.py` | `ConversationMessage.follow_ups`; `_build_messages` re-attaches the trailer when enabled; `_filter_fabricated_follow_ups` gets history refs; suppressed counter + reason in `chat()`/`chat_stream()`. |
| `api/tests/test_chat_follow_ups.py` | Unit tests for sanitize/format, prompt build, history-verse filter (11-language param), counter reasons, `chat_stream()` integration. |
| `frontend/src/lib/api.ts` | `Message.follow_ups?`. |
| `frontend/src/app/[locale]/ChatIsland.tsx` | Attach `chunk.follow_ups` to the finished assistant message. |
| `frontend/src/**/*.test.ts(x)` | Test that the next `streamMessage` call's history carries `follow_ups`. |
| Android `domain/models/Message.kt`, `data/remote/models/ConversationMessageDto` + `ChatMapper.kt`, `ChatViewModel.kt` | Field, DTO, mapping, saving on the message. |
| Android `app/src/test/...` | Mapper serialization + ViewModel test (flag on and off). |
| `docs/BACKLOG.md` | Entry + changelog line. |

## Known limitations

- Android keeps `followUps` in memory only (not in Room), so a conversation reloaded after an app
  restart echoes no trailers for its older turns; new turns echo normally.
- Android 1.57.0 sends no `follow_ups` and benefits only from FR3 until the next release.
