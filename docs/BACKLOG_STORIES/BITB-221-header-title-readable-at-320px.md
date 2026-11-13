# BITB-221: Header Brand Title Unreadable at 320px

**Status:** 🎯 Todo
**Priority:** P3
**Size:** XS
**Created:** 2026-10-23
**Type:** Bug (cosmetic)
**Follow-up of:** BITB-219 (PR #1191)

## Problem

BITB-219 keeps the Bible chip and New chat on screen on phones by letting the brand title
truncate (`truncate` on the `h1` in `frontend/src/app/[locale]/ChatIsland.tsx`). The verifier
measured the result with Playwright: at 320px the `h1` gets 22–33px and renders as "V…" (en/pt/hi),
at 360px "Vox …", and only at 412px the full "Vox Quieta". On the smallest phones the header
shows no recognisable brand.

The right-hand group (`shrink-0`) holds the icon-only Get-the-app pill (`px-3`), the Bible chip
(label up to `max-w-[5rem]`) and New chat, and takes nearly all of a 320px row.

## Options

- Hide the icon-only Get-the-app pill below ~360px (it is also reachable from the footer's
  "Get the app" link), or tighten its padding below `sm`.
- Cap the Bible chip label narrower below ~360px (short names like KJV/WEB/CEI still fit).
- Show a compact brand mark instead of truncated text when the title has no room.

## Acceptance Criteria

- [ ] At 320px the header shows a readable brand ("Vox Quieta" or an agreed compact mark), and the
      Bible chip and New chat stay fully inside the viewport
- [ ] No change from `sm` (640px) up
- [ ] Layout checked in a real browser at 320/360/412px for en, ar (RTL), ko, hi; Vitest asserts
      the responsive classes
