# BITB-248: Web Read Aloud Still Stuck on Pause on Snap Firefox (Start Watchdog Trusted `speaking`)

**Status:** 🚧 In Progress
**Priority:** P1
**Size:** S
**Created:** 2026-10-27
**Prompted by:** owner retest 2026-10-27 after BITB-241 shipped — "I just tested the play button on firefox
Linux and still it doesn't work" (stuck on Pause, no notice).

Follow-up to BITB-241.

## Diagnosis (owner's console output, Snap Firefox)

- `getVoices()` → `["en_UK/apope_low|en|false"]`: one Piper voice from the host's speech-dispatcher,
  reported with `localService === false`.
- `speechSynthesis.speak(...)`: no `start`, `end`, `error` or `boundary` event, ever.
- `speaking === true` and `pending === true` at 0 ms, 1 s and 4 s.
- A bare console `speak("hello")` is silent too, so speech-dispatcher hangs outside the app.

## Root cause

BITB-241's second round treated `speechSynthesis.speaking === true` at timeout as proof that audio had
started. That relied on an assumption ("Firefox only sets `speaking` after a real start") that this
engine disproves. The start watchdog therefore never gave up, and the button stayed on Pause.

## Fix

Only events (`onstart`, `onboundary`, a chunk's `onend`) count as a start. A hung engine with
`speaking`/`pending` set now gets one retry, then the button resets and the localized "speech engine
didn't respond" notice shows.

## Acceptance criteria

- [x] Regression test with the exact signature (`speaking` and `pending` true, no events): retry once,
      then idle plus notice. It fails on the BITB-241 code and passes with the fix
- [ ] Owner check on Snap Firefox: the notice shows instead of a stuck Pause

## Out of scope

- Making audio play when the browser's speech engine itself is broken; that is a separate product
  decision (in-page TTS or server TTS)
