# BITB-244: Bible Version / Language Selects Overflow the Mobile Menu

**Status:** 🔄 In Review (PR #1225)
**Priority:** P1
**Size:** S
**Created:** 2026-10-27
**Type:** Bug (mobile, web frontend)
**GitHub Issue:** #1223 (filed at the owner's request for tester feedback)

**As a** mobile user,
**I want** the Bible version selector to fit inside the side menu,
**so that** it doesn't overlap the chat and I can read and change the version easily.

## Problem

A tester reported, on both iOS Safari and Android, that the "Change Bible version" select in the
main menu (`MainMenu.tsx` → `TranslationSwitcher.tsx`) is wider than the menu and spills over the
chat. Root cause: a native `<select>` sizes itself to its **longest option**
("King James Version — KJV, 1611"), and it sat in a non-shrinking flex row (`flex items-center`
with no `min-width: 0`) inside the fixed `w-64` menu panel. Measured with Playwright on `main`:
menu right edge 268px, select right edge 352px at every phone width (320–430px). The selects were
also `text-sm` (14px), which makes iOS Safari zoom the page on focus.

## Fix

- `TranslationSwitcher` and `LanguageSwitcher` render a styled, truncating label (`short_name`,
  e.g. "KJV", or the language name) with a chevron, and stretch a transparent native `<select>`
  (`absolute inset-0 opacity-0 text-base`) over it. This is the same pattern as the header Bible
  chip in `ChatIsland.tsx`. The OS picker, keyboard navigation and accessible name are unchanged,
  and the full descriptive name stays in the option list (plus a `title` tooltip).
- The wrappers use `w-full min-w-0`/`flex-1 min-w-0 max-w-full`; the menu panel is capped at
  `max-w-[calc(100vw-1.5rem)]`, scrolls vertically within `100dvh` and clips horizontally.

## Acceptance Criteria

- [x] The select never exceeds the menu width at 320–430px viewports (Playwright: 320/360/375/430
      portrait, 812×375 landscape)
- [x] The collapsed control shows the short label; the full name appears in the option list only
- [x] Long labels truncate with an ellipsis
- [x] The language select gets the same treatment
- [x] Select font size >= 16px (no iOS focus zoom)
- [ ] Checked on real iOS (Safari, Chrome) and Android (Chrome, Samsung Internet), portrait and
      landscape (owner/tester step)
