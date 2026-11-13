# BITB-213: `tts_unavailable` Over-Counted When the Browser Loads Voices Slowly (Web)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-22
**Follow-up of:** BITB-210 (PR #1190); the behaviour predates it (BITB-119)

## Problem

`loadVoices()` (`frontend/src/lib/speech.ts`) gives up after 1.5 s. If Chrome fills its voice list
later, availability is briefly "none". In that window `ListenButton.tsx` reports `tts_unavailable`, and
the menu's "no voice" note can flash before availability becomes "online". The telemetry over-counts
unavailable devices.

## Acceptance criteria

- [ ] `tts_unavailable` is sent only once availability has been "none" for a settle period, or still
      is after a `voiceschanged` grace window
- [ ] The menu note doesn't flash for browsers that load voices late
- [ ] Vitest coverage with a voice list that is filled late
