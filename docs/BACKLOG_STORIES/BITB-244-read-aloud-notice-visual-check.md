# BITB-244: Visually Check the "Speech Engine Didn't Respond" Notice Beside the Action Rail (Web)

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-10-27
**Follow-up of:** BITB-241 (PR #1203)

## Problem

BITB-241 positions the notice absolutely next to the sticky action rail in `ListenButton.tsx`
(`absolute top-0 end-full me-1 w-28 z-10`), over the start of the answer text, so the rail doesn't widen.
The placement was only covered by jsdom tests. Nobody has looked at it in a browser in LTR, in Arabic
(RTL), on a 320–360 px phone, or with the long German or Russian strings.

## Acceptance criteria

- [ ] Screenshots on desktop and phone widths in en, de, ru and ar: readable, not clipped, not covering
      the Listen button
- [ ] Fix the placement if needed; optionally add a Playwright visual check
