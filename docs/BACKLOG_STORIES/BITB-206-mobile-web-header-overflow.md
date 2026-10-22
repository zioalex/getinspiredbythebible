# BITB-206: Mobile Web Header Overflows — Bible Selector and New Chat Pushed Off-Screen

**Status:** 🚧 In Progress
**Priority:** P1 (user-visible, every mobile web session)
**Size:** S
**Created:** 2026-10-22
**Type:** Bug

## Bug Report

On voxquieta.org in a mobile browser on Android (~412 CSS px wide), the sticky chat header is
wider than the screen. The Bible version chip and the New chat button sit past the right edge, so
they can't be seen or tapped. The screenshot shows the header ending at the language `<select>`
("English"), and the title "Vox Quieta" wraps onto two lines.

## Root Cause

`frontend/src/app/[locale]/ChatIsland.tsx` (header, ~L1016–1096) is a single
`flex justify-between` row that never wraps or shrinks. Below `sm` it renders:

- left group: hamburger `MainMenu` + decorative `Book` icon + `h1` title
- right group: Get-the-app pill (icon only) + `LanguageSwitcher` (globe + full locale name
  select) + Bible version chip + New chat button

Neither group has `min-w-0`/`shrink-0`, the title can wrap, and the language select shows the full
native locale name ("English", "Português", "Français"…). Together these are wider than a phone
viewport, so the last controls overflow. The hamburger menu (`MainMenu.tsx`) **already** includes
both a language switcher and a Bible version switcher, so the header's language switcher is a
duplicate on mobile.

## Decision (product owner, 2026-10-22)

Below the `sm` breakpoint (640px), **hide the header language switcher** (it is still in the
hamburger menu) and the decorative book icon, and keep the title on one line. The Bible chip, New
chat and app icon stay visible. Considered and rejected: compacting every control (still tight at
360px), and a two-row header (takes chat space).

## Functional Requirements

1. Below `sm`: the header `LanguageSwitcher` and the decorative `Book` logo icon are not rendered
   (`hidden sm:flex` / `hidden sm:block`). From `sm` up, nothing changes.
2. The right-hand control group never shrinks (`shrink-0`). The left group can shrink (`min-w-0`)
   and the title stays on one line, truncating if needed (`truncate`, `text-lg sm:text-xl`). Verified
   at 320, 360 and 412px that this keeps the Bible chip and New chat inside the viewport; widths
   below 320px are not targeted. The outer row has `gap-2` so the truncated title never touches the
   controls, and the `h1` is `dir="ltr"` so the Latin brand truncates from its end in Arabic too.
3. The New chat button has an accessible name at every width (`aria-label`), because its text
   label is `hidden md:inline`, which also removes it from the accessibility tree.
4. Language switching on mobile stays available through the hamburger menu (no change there).

## Non-Functional Requirements

- **Platforms:** web only (the Android app has a native toolbar and is out of scope).
- **Languages:** layout must hold for all 11 locales. The title is the same in every locale, and
  the switcher that is hidden on mobile is the one with the long locale names; the New chat
  `aria-label` uses the existing `Header.newChat` key, which is already translated in all 11
  locales, so no new strings are needed.
- **RTL (ar):** flex order mirrors automatically; nothing direction-specific.
- **Accessibility:** tap targets stay unchanged; the New chat button is named at every width.

## Acceptance Criteria

- [x] At 360px and 412px viewport widths, the Bible chip and New chat button are fully visible
- [x] The header language switcher is `hidden` below `sm` and visible from `sm` up; the hamburger
      menu still offers language switching
- [x] The title does not wrap; it truncates instead of pushing controls off-screen
- [x] The New chat button has an accessible name (`aria-label`) at all widths
- [x] Vitest coverage asserts the responsive classes and the accessible name for all 11 locales

## Out of Scope

- Redesigning the header for tablets or desktops
- The Android native app toolbar

## Plan

- `frontend/src/app/[locale]/ChatIsland.tsx` header:
  - left group: add `min-w-0`; `Book` icon gets `hidden sm:block shrink-0`; title wrapper `min-w-0`;
    `h1` → `text-lg sm:text-xl ... truncate`; `MainMenu` stays.
  - right group: add `shrink-0`; wrap `<LanguageSwitcher />` in `<div className="hidden sm:flex"
    data-testid="header-language-switcher">`.
  - New chat button: `aria-label={tHeader("newChat")}`, and `px-2 sm:px-3` to save width.
- Tests: a Vitest test rendering the header (`ChatIsland`), parametrized across the 11 locales'
  `Header` messages, asserting the wrapper's `hidden sm:flex` classes, the `aria-label` on New
  chat, the Bible version select being rendered, and the right group having `shrink-0`.

## Verification (2026-10-22)

Playwright on `next dev`, mobile contexts at 320/360/412px and desktop 1280px, locales en/pt/ar/ko/hi,
with the backend down and with mocked translations: 40/40 combinations keep the Bible select and New
chat inside the viewport. Before the fix the header content was 524–530px wide at 360/412 and both
controls sat past the right edge, with the title wrapping to two lines. The header language switcher is
hidden below `sm` and shown at 1280; the hamburger menu still offers the 11-locale switcher. Vitest:
73 files / 1335 tests pass; lint, `tsc --noEmit` and Prettier are clean. Note: the overflow was
clipped, so `documentElement.scrollWidth` did not reveal it — the header's own `scrollWidth` did.
