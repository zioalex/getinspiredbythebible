# BITB-205: Read Aloud — Pause/Resume and a Sticky Side Rail for Answer Actions (Web + Android)

**Status:** ✅ Done — PR #1188, merged 2026-10-22
**Priority:** P2
**Size:** M
**Created:** 2026-10-21
**Prompted by:** product-owner feedback on v1.57.0 — "the voice reading is working! The play should be
stoppable and start again where it stopped. Instead of having the copy, play and share button at the
bottom of the message it should be a moving pane on the right side that stays always in focus. On the
web side also implement the play/pause."

Follow-up to BITB-119 (read-aloud).

## User story

As a listener, I want to pause the reading of an answer and continue from where I paused, and I want
the Listen / Copy / Share actions next to the text I am reading instead of at the bottom of a long
answer, so I don't have to scroll to control playback.

## Today (v1.57.0)

- Listen is a **Listen ↔ Stop** toggle. Stop throws the position away; the next Listen restarts the
  whole answer (`SpeechEngine.kt`, `frontend/src/lib/speech.ts`).
- Android: backgrounding the app or an audio-focus loss (phone call) **stops** playback.
- Listen, Copy and Share sit in the action row at the **bottom** of the answer
  (`ChatMessageItem.kt` `trailingActions`, `ChatMessage.tsx` `FeedbackControls trailing`), so on a long
  answer they are off-screen while it is being read.

## Decisions (interview 2026-10-21)

| Question | Decision |
|---|---|
| Resume granularity | **Web: native `speechSynthesis.pause()/resume()`** where it works, sentence/chunk-level fallback where it doesn't (Android Chrome, a resume that never restarts). **Android app: chunk-level** — the platform `TextToSpeech` has no pause, so resume restarts the chunk that was playing. |
| How long a paused position is kept | **One paused position at a time, until another answer is played.** Playing a different answer resets it. Backgrounding the app pauses (keeps the position) instead of stopping. |
| Pane layout | **Sticky rail per answer**: a vertical Listen / Copy / Share column on the end side (right in LTR, left in Arabic) of each finished assistant answer. While the answer is partly in view the rail stays visible, pinned near the top of the viewport, clamped to the answer's top and bottom edges. Feedback thumbs stay in the bottom row. |
| Web scope | **Rail on both platforms**, plus play/pause on web. |

## Functional requirements

1. **Three states** for the Listen control of an answer: *idle* (speaker icon, "Listen to this
   answer"), *playing* (pause icon, "Pause reading"), *paused* (play icon, "Resume reading").
2. Tapping while playing **pauses**; tapping while paused **resumes**:
   - Android: from the start of the chunk that was playing when paused.
   - Web: from the exact point via native resume; if the browser can't (Android Chrome UA, or the
     native resume doesn't restart within ~1 s), from the start of the chunk that was playing.
3. Playing a **different** answer discards the paused position of the previous one (one position at a
   time). Finishing an answer clears its state, so the next tap starts from the beginning.
4. Android: app backgrounded (`ON_STOP`) or **transient/permanent audio-focus loss** (call, alarm) →
   **pause** (was: stop). Starting a new conversation, or the paused answer leaving the message
   list → reset.
5. Web: unmounting the playing/paused answer, a locale change, or hiding the control (flag /
   preference off) still stops and clears (existing BITB-119 behaviour).
6. **Side rail**: Listen (when available), Copy, Share move from the bottom action row into a vertical
   rail beside each finished assistant answer, on the end side. The rail sticks within the viewport as
   described above. User-message copy button and the feedback row are unchanged. Streaming / error
   answers show no rail (same visibility rules as today's buttons).
7. The bubble keeps its current max width (Android 85% / 320–840 dp from BITB-174); the rail lives in
   the gutter next to the assistant bubble.

## Non-functional requirements

- **11 languages**: new strings (`Pause reading`, `Resume reading`, a "Paused" state description on
  Android) translated for en, it, de, es, fr, pt, ar, ru, zh, hi, ko on web and Android; Android
  translation-validation CI passes. Strings that become unused are removed everywhere.
- **RTL**: rail on the left in Arabic (end side), icons auto-mirrored where they already are.
- **Accessibility**: 44 px / 48 dp touch targets; accessible name and Android `stateDescription` /
  web `aria-pressed` reflect playing vs paused; rail buttons stay in reading order after the answer
  text.
- **Privacy** unchanged: on-device voices only.
- **Performance**: the rail's sticky offset must not recompose the whole message on every scroll
  frame (Android: apply the offset in the layout/draw phase; web: CSS `position: sticky`).

## Acceptance criteria

- [x] Android: Play → Pause → Play resumes at the paused chunk, not chunk 0 (engine unit test with a
      fake `TextToSpeech` asserting the re-queued chunks)
- [x] Android: playing answer B while A is paused resets A (A shows *idle*)
- [x] Android: `ON_STOP` and audio-focus loss pause instead of stop; resume continues
- [x] Android: ListenButton shows the right icon / label / state description for idle, playing, paused
      (Compose test)
- [x] Android: Listen / Copy / Share render in the side rail, not the bottom row; feedback row still at
      the bottom; pure `stickyRailOffset(...)` function unit-tested (above, inside, below the viewport,
      rail taller than answer)
- [x] Web: `speech.ts` pause/resume — native path, Android-UA chunk fallback, and the watchdog fallback
      tested with the speech mock
- [x] Web: ListenButton three states (Vitest)
- [x] Web: Listen and Share (incl. Copy) render in a sticky rail beside the answer; feedback row stays
- [x] New strings in all 11 locales on both platforms; translation validation passes
- [x] Backend untouched; frontend lint/tsc/vitest/build and Android unit + Compose tests green in CI
- [ ] Owner check on a phone: play a long answer, scroll, pause, background the app, resume

## Out of scope

- Playback with the screen off / foreground service (BITB-176)
- A separate "restart from beginning" control, seek bar, speed control
- Word-level highlighting of the text being read
- New telemetry events (resume does not re-send `tts_started`)

## Open questions

- None blocking. If the web sticky rail crowds the bubble on narrow phones (<360 px), the builder may
  shrink the rail buttons to 40 px wide but keep 44 px height.

## Plan

### Android

1. `tts/SpeechEngine.kt`
   - Interface: add `pausedId: StateFlow<String?>`, `pause()`, `resume(): Boolean`.
   - `AndroidSpeechEngine`: keep the current call's `chunks`, `languageTag`, `id` and the index of the
     chunk that is playing (set in `UtteranceProgressListener.onStart` from the `"$token:$index"`
     utterance id). `pause()`: invalidate token, `tts.stop()`, abandon focus, `speakingId = null`,
     `pausedId = id`, keep the resume index. `resume()`: re-queue `chunks.drop(index)` under the same
     id through the shared speak path (re-requests focus; returns false if denied). `speak()` of any
     id clears paused state; `stop()` clears everything; last `onDone` clears everything.
   - `onAudioFocusChange` LOSS / LOSS_TRANSIENT → `pause()`.
2. `ChatViewModel.kt`: collect `pausedId` into `uiState.pausedMessageId`; `toggleSpeak` → pause if
   speaking this message, resume if paused on it, else speak; add `pauseSpeaking()`; new
   conversation / message list cleared → `stopSpeaking()`.
3. `ChatScreen.kt`: `ON_STOP` → `pauseSpeaking()`; pass `isPaused` to `ChatMessageItem`; provide the
   LazyColumn viewport bounds (window coordinates) to items (CompositionLocal or parameter).
4. `ChatMessageItem.kt`: `ListenButton(isSpeaking, isPaused, ...)` with Pause / PlayArrow / VolumeUp
   icons and labels; move Listen / Copy / Share out of `trailingActions` into a `MessageActionRail`
   (vertical) placed beside the assistant bubble on the end side; its Y offset =
   `stickyRailOffset(itemTop, itemHeight, railHeight, viewportTop, viewportBottom, margin)` applied
   via `Modifier.offset { }` / `layout` so scrolling doesn't recompose. Feedback row keeps the bottom.
5. Strings: add `action_pause_listening`, `action_resume_listening`, `state_paused_listening` to
   `values/` and all 10 `values-<locale>/`; drop `action_stop_listening` if unused.
6. Tests: extend `AndroidSpeechEngine` tests, ViewModel tests, `ListenButtonComposeTest`, add
   `stickyRailOffset` unit test, rail Compose test.

### Web

1. `lib/speech.ts`: add `pausedId`, `getPausedId()`, `pause()`, `resume()`; track the playing chunk
   index via `utterance.onstart`; native pause unless `navigator.userAgent` matches `/Android/i`;
   resume watchdog (~1 s without `onresume`/`onstart`/`onboundary` → cancel and re-speak from the
   chunk); `speak()` clears any paused state; `stop()` clears all. Snapshot for
   `useSyncExternalStore` must stay referentially stable.
2. `components/ListenButton.tsx`: three states, Pause / Play / Volume2 icons; i18n keys
   `pauseListening`, `resumeListening` (remove `stopListening` if unused) in all 11
   `messages/*.json`.
3. `components/ChatMessage.tsx`: assistant answers render a `MessageActionRail` (Listen + ShareMenu)
   as a flex sibling of the bubble with `sticky top-<header offset> self-start`, end side; the bottom
   row keeps FeedbackControls only. Verify no ancestor `overflow: hidden` breaks sticky.
4. Tests: `speech.test.ts`, `ListenButton.test.tsx`, `ChatMessage` rail test; update
   `speechMock.ts` with `pause`/`resume`/`paused`.

### Verification

Backend untouched. Frontend: `npx vitest run`, `npm run lint`, `npx tsc --noEmit`, `npm run build`.
Android: `testDebugUnitTest`, `testDebugCompose`, `lint` (CI is authoritative if Gradle can't fetch
AGP in the sandbox).

## Also fixed in this PR

- **Deploys broken by #1183.** It renamed the Azure resource names in `azure-deploy.yml` and
  `prod-deploy-drift.yml` to `voxquieta-*`. Terraform still creates them from
  `project_name = "bible-app"` / `resource_suffix = "mb0172"`, so every PR preview and main deploy
  failed at `az acr login`. Restored the real names. `api/tests/test_workflow_azure_resource_names.py`
  derives the names from `deployment/terraform.tfvars` and guards against a repeat.

## Follow-ups

- BITB-206 — Android side rail trails one frame behind during a fast fling
- BITB-207 — short answers grow to the side rail's height (Android)
- BITB-208 — rename Azure resources to `voxquieta-*` through Terraform
- BITB-209 — web resume watchdog can replay a chunk when the voice emits no events
