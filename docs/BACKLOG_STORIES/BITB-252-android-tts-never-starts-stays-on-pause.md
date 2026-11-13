# BITB-252: Android Read Aloud Stays on Pause When the TTS Engine Never Starts

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-10-28
**Follow-up of:** BITB-247 (PR #1226)

## Problem

BITB-247 added a start watchdog to the Android `SpeechEngine`
(`android/app/src/main/kotlin/org/voxquieta/app/tts/SpeechEngine.kt`, `armWatchdog`). If no utterance
callback (`onStart`, `onBeginSynthesis`, `onRangeStart`, `onDone`) arrives within `START_TIMEOUT_MS`, it emits
`SpeechEvent.StartFailed`. By design it then leaves the reading running, because telemetry must not change
playback. `ChatViewModel` only maps that event to the `tts_start_failed` analytics event.

So on a device whose TextToSpeech engine accepts `speak()` and never plays, `speakingId` stays set and the
message keeps showing the Pause/stop control indefinitely, with no message to the user. This is the Android
counterpart of the web bug fixed in BITB-241/248, where the web button now resets and shows a notice.

## Acceptance criteria

- [ ] After the start watchdog fires and a short grace period passes with still no callback, the reading
      stops, the control returns to Listen, and a localized "speech engine didn't respond" message shows
      (strings in all 11 locales)
- [ ] A late start (a callback arriving within the grace period) keeps playing normally
- [ ] `tts_start_failed` is still reported exactly once per Listen
- [ ] Unit tests in `AndroidSpeechEngineTest` / `ChatViewModelTest` with the fake scheduler
