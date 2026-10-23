# BITB-215: Help for Installing an Offline Voice When the Browser Has None (Web)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-22
**Follow-up of:** BITB-210 (PR #1190), which left the "help" link optional and didn't build it

## Problem

When a browser has no voice for the UI language, the menu now says "This browser has no voice for
{language}", but not how to fix it. Common fixes:

- Linux Firefox: install speech-dispatcher and an espeak-ng voice. The Snap/Flatpak builds may be
  sandboxed away from it.
- Windows: add the language's speech pack.
- macOS/iOS: download a system voice.

## Acceptance criteria

- [ ] A short help section (on the About/help page, or a small dialog) linked from the note
- [ ] Per-OS steps, in 11 locales
- [ ] Linked only when availability is "none"
