# BITB-209: Web Resume Watchdog Can Replay a Chunk When the Voice Emits No Events

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-22
**Follow-up of:** BITB-205 (PR #1188)

## Problem

After a native `speechSynthesis.resume()`, `frontend/src/lib/speech.ts` waits `RESUME_WATCHDOG_MS`
(1 s) for `onresume` / `onstart` / `onboundary`. If none arrives it assumes the resume silently failed
(a known Chrome bug), cancels, and re-speaks from the start of the current chunk. A voice that resumes
correctly but fires no boundary events within 1 s on a long chunk would hear that chunk restarted.
Never two voices at once, but audible repetition.

The fallback also only un-pauses when `synth.paused` (or the native-paused flag) reads true. A browser
that reports `paused=false` while stuck would stay silent.

## Acceptance criteria

- [ ] Measure on Chrome desktop, Edge, Safari macOS/iOS and Firefox which events fire after resume
- [ ] Watchdog uses a signal that doesn't false-positive (e.g. also check `synth.speaking && !synth.paused`)
- [ ] Tests in `speech.test.ts` for a voice with no boundary events and for a stuck engine reporting `paused=false`
