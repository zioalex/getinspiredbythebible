# BITB-245: Pin the Chat Input to the Bottom of the Screen on Mobile

**Status:** 🔄 In Review (PR #1225)
**Priority:** P1
**Size:** M
**Created:** 2026-10-27
**Type:** Enhancement (mobile UX, web frontend)
**GitHub Issue:** #1224 (filed at the owner's request for tester feedback)

**As a** mobile user,
**I want** the message box flush with the bottom of the screen (ChatGPT/Claude style),
**so that** I don't accidentally tap "Get in Touch" or the footer links.

## Problem

On mobile the chat page rendered, below the composer: the disclaimer, the BITB-079 compact footer
link row (Get the app / About / Privacy / Terms / Changelog / Support us), the Church Finder banner
and the collapsible "Get in Touch" contact form. These are small tap targets where the thumb rests,
right above the browser toolbar. On `main` the textarea's bottom edge sat 118–138px above the
bottom of the viewport.

## Fix

- Below `lg` (1024px) the composer is the last element in the sticky input area: the disclaimer and
  Church Finder banner are reordered above it (`order-first`), and the footer links and inline
  contact form are wrapped in `hidden lg:block`. Desktop is unchanged.
- The main menu gains "Get in Touch" (opens a new `ContactModal` wrapping `ContactForm` in an
  `embedded` mode) and Get the app / Privacy / Terms / Changelog links between About and Support us,
  all `lg:hidden`.
- Keyboard handling: `interactiveWidget: "resizes-content"` in the viewport export (Android Chrome
  shrinks `100dvh` with the keyboard), and a `useKeyboardAwareViewport` hook that, on iOS, sizes
  `<main>` to the visual viewport via `--chat-viewport-height` while the keyboard is open and pins
  document scroll to the top, so the message list scrolls instead of the page.
- The existing `100dvh` shell, `viewportFit: "cover"` and the `.sticky.bottom-0` safe-area padding
  (`env(safe-area-inset-bottom)`) are kept. The scripture FAB and the "Scroll to bottom" pill are
  lifted to sit above the now-shorter input area on mobile.

## Acceptance Criteria

- [x] At mobile breakpoints the input bar is the last element on screen and pinned to the bottom
- [x] Footer links and "Get in Touch" are removed from the chat view below lg and are in the menu
      next to About / Support us
- [x] `100dvh` + `env(safe-area-inset-bottom)` + `viewport-fit=cover`
- [x] Keyboard: input stays visible and the message list scrolls, not the page (Playwright viewport
      shrink proxy and hook unit tests)
- [x] Message list scrolls independently; last message is not hidden behind the input
- [x] Desktop (>= 1024px) unchanged
- [ ] Checked on real iOS (Safari, Chrome) and Android (Chrome, Samsung Internet) with the on-screen
      keyboard open (owner/tester step)
