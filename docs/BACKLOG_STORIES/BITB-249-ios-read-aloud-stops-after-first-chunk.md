# BITB-249: Read Aloud Stops After the First Chunk on iPhone (Web)

**Status:** 🚧 In Progress
**Priority:** P1
**Size:** S
**Created:** 2026-10-27
**Prompted by:** owner report 2026-10-27 — "on iPhone/Firefox the voice reading starts but stops after the
second sentence. I tried in different languages. Same problem. Only 2 sentences are read."

Follow-up to BITB-205 / BITB-241.

## Root cause

- **How answers are chunked:** `chunkForSpeech` (`frontend/src/lib/speakableText.ts`) packs sentences
  into chunks of up to 200 characters, so the first chunk is usually two sentences.
- **How chunks are queued:** `startQueue` (`frontend/src/lib/speech.ts`) calls
  `speechSynthesis.speak()` for every chunk up front and keeps no reference to the
  `SpeechSynthesisUtterance` objects.
- **What iOS does:** every iPhone browser, Firefox included, runs on WebKit. WebKit drops the queued
  utterances after the first, especially when the page holds no reference to them (they are
  garbage-collected). Only chunk 0, about two sentences, is spoken.
- **Language:** the behaviour does not depend on the UI language, which matches the report.

## Functional requirements

1. **Speak one chunk at a time.** Chunk *i+1* is spoken from chunk *i*'s `onend`, and the current
   call keeps references to its utterances.
2. **Keep existing behaviour unchanged:**
   - BITB-205 native pause/resume and the chunk fallback (resume restarts the current chunk).
   - The BITB-241/248 start watchdog. It arms on the first `speak()` of a call; a later chunk that
     never starts is caught by the same rule.
   - Generation guards against stale callbacks.
   - One voice at a time.
3. Stopping, pausing or switching answers never lets a pending "speak next chunk" fire.

## Acceptance criteria

- [ ] Only one utterance is queued at a time; the next chunk is spoken from the previous chunk's
      `onend`, and all chunks are read in order (Vitest)
- [ ] Utterances are referenced from the current call while it is active
- [ ] Pause/resume (native and fallback), stop, switching answers and the start watchdog tests stay
      green; added tests for stop or pause between two chunks
- [ ] Owner check on iPhone (Firefox and Safari): the whole answer is read

## Out of scope

- Android app (uses the platform TextToSpeech queue, not affected)
