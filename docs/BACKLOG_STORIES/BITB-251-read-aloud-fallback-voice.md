# BITB-251: Read-Aloud Fallback Voice When the Browser's Speech Engine Is Missing or Broken (Web)

**Status:** 🎯 Todo (decision pending data)
**Priority:** P2
**Size:** M
**Created:** 2026-10-28
**Follow-up of:** BITB-247, BITB-248 (PR #1226)

## Problem

Read aloud uses the browser's own speech engine (`speechSynthesis`). Where that engine is broken or empty,
the app can only explain it:

- Snap Firefox on Linux: the host's speech-dispatcher accepts `speak()` and plays nothing. Since BITB-248
  the button shows "Your browser's speech engine didn't respond" instead of a stuck Pause, but no audio plays.
- Browsers with no voices: the Listen button is hidden, and the menu note explains why (BITB-210).

BITB-247 and BITB-248 both left the audio fix out of scope: it is a product decision.

## Options gathered so far (2026-10-27)

1. **Server TTS (Azure Speech):** about $15–16 per 1M characters, with 0.5M characters a month free on the
   F0 tier. Needs an endpoint, caching and the cost guardrails the owner asked for.
2. **In-page TTS (Piper, WASM):** the owner rated the sample quality good. The model loads once per session
   (5–7 s measured natively), then each sentence takes about 0.1 s. The owner's concern is the wait before
   the first sentence.

## Decision input

The BITB-247 telemetry (`tts_event_daily`, weekly report "Read aloud" section, workbook tile) shows how many
Listen attempts end in `tts_start_failed` or `tts_unavailable`, per browser and OS family. Decide once it has
a few weeks of data.

## Acceptance criteria

- [ ] Owner decision (Azure, Piper, or neither) recorded here, with the telemetry numbers behind it
- [ ] If built: the fallback is used only after the start watchdog gives up or when no voice exists, works in
      all 11 languages, and ships with tests
