# BITB-222: Header Layout Below 320px Is Unguarded

**Status:** 🎯 Todo
**Priority:** P3
**Size:** XS
**Created:** 2026-10-23
**Type:** Bug (edge case)
**Follow-up of:** BITB-219 (PR #1191)

## Problem

BITB-219 was verified at 320, 360 and 412px only. Below 320px (old/small Android devices, split
screen, large system font scaling that narrows the CSS viewport) nothing bounds the header row in
`frontend/src/app/[locale]/ChatIsland.tsx`:

- the right control group is `shrink-0`, so it never gives up width;
- the left group is `min-w-0` and the title truncates to zero, but the hamburger button wrapper in
  `frontend/src/components/MainMenu.tsx` (`relative inline-block`) is not `shrink-0`, so whether it
  keeps its full tap target is left to flexbox's implicit minimum size;
- once the left group reaches its minimum, the row overflows and the end controls are clipped again
  by the container's `overflow-x-clip` — the original BITB-219 symptom.

## Acceptance Criteria

- [ ] Decide the minimum supported width (e.g. 280px) and record it
- [ ] At that width the hamburger, Bible chip and New chat are fully visible with ≥40px tap targets
      (e.g. `shrink-0` on the menu wrapper, dropping the app pill first)
- [ ] Browser check at the minimum width, plus a Vitest assertion on the menu wrapper's `shrink-0`
