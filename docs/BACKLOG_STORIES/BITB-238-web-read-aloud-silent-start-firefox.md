# BITB-238: Web Read Aloud Shows "Pause" but Plays Nothing on Linux Firefox

**Status:** 🚧 In Progress
**Priority:** P1
**Size:** S
**Created:** 2026-10-24
**Prompted by:** bug report 2026-10-24 — "The voice over doesn't work on web/linux/firefox. The play button is
displayed and if I press it, it shows me the pause one but no audio is produced. … Nothing is played and no
network activity."

Follow-up to BITB-205 / BITB-210.

## Root cause

- **No online voices on Linux Firefox.** Firefox's voices all come from the local speech-dispatcher
  service and report `localService === true`, so BITB-210's online opt-in never applies and no network
  traffic is expected. The Listen button shows because Firefox does list voices.
- **Silent hang.** `startQueue` in `frontend/src/lib/speech.ts` marks the answer as playing as soon as
  it queues the utterances. When the engine never starts, the browser fires neither `onstart` nor
  `onerror`, so the button stays on "Pause" forever. Nothing detects that audio never began.
- **Likely trigger.** `startQueue` always calls `speechSynthesis.cancel()` just before `speak()`, even
  when nothing is playing. On Linux Firefox, cancel is forwarded to speech-dispatcher asynchronously and
  can swallow the utterance queued right after it. A missing or blocked speech-dispatcher (common with
  the Snap/Flatpak builds) gives the same symptom.

## Functional requirements

1. Call `cancel()` before `speak()` only when something is speaking, pending or paused.
2. **Start watchdog:** if no `onstart` (or `onboundary`) arrives within a few seconds of `speak()`:
   - Retry once (cancel only if needed, then speak again).
   - If it still doesn't start, give up: return the button to idle, and show a short localized message
     next to Listen, e.g. "Your browser's speech engine didn't respond." A first-chunk `onerror` gives
     up the same way.
3. **The message:** visible and announced (`role="status"`), it disappears on the next Listen tap or
   after a few seconds, and it is in all 11 locales.
4. The resume watchdog from BITB-205 and the online-voice consent from BITB-210 are unchanged.

## Acceptance criteria

- [ ] No `cancel()` call when the engine is idle (test)
- [ ] An engine that never fires `onstart`: one retry, then the button returns to idle and the
      message shows (fake timers)
- [ ] An engine that starts on the retry plays normally
- [ ] A first-chunk `onerror` gives up the same way
- [ ] Message strings in 11 `messages/*.json`; lint, tsc, vitest and build green
- [ ] Owner check on Linux Firefox: audio plays, or the message shows instead of a stuck "Pause"

## Out of scope

- Fixing speech-dispatcher on the user's machine (BITB-215 covers help for installing a voice)
