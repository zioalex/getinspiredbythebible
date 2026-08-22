# BITB-079: Web — the Bottom Bar Is Permanently Off Screen on the Chat Page

**Status:** 🎯 Todo
**Priority:** P1
**Size:** S (< 4 hrs)
**Created:** 2026-07-25

## User Story

**As a** web visitor,
**I want** the bottom bar (About / Get the app / Privacy / Terms / Changelog) to be reachable from
the chat page,
**so that** I can actually get to the legal pages and the app link instead of scrolling into a
footer that never arrives.

## Why

On the chat page the footer is rendered but is not reachable in practice. It is not a styling
nitpick: `/privacy` and `/terms` are legally required disclosures, `/app` is the Play Store funnel,
and the About page from **BITB-076** is about to be added to the same bar. A navigation surface
that exists in the DOM and never appears on screen is the same as not having one.

## Current Behaviour — Root Cause

The layout gives the chat page the entire viewport and then places the footer *after* it:

- `frontend/src/app/[locale]/layout.tsx:107-111`

  ```tsx
  <div className="min-h-screen bg-gradient-to-b ... flex flex-col [overflow-x:clip]">
    <div className="flex-1">{children}</div>
    <Footer />
  </div>
  ```

- `frontend/src/app/[locale]/ChatIsland.tsx:938` — `<main className="flex h-dvh">`, i.e. the chat
  occupies a **full dynamic viewport height** on its own.

So the document is `100dvh` of chat **plus** the footer's height. The footer sits exactly one
footer-height below the fold, and the only way to reach it is a document-level scroll that the user
essentially never gets: the chat page's own scrolling happens inside
`ChatIsland.tsx:1033-1035` (`flex-1 overflow-y-auto`), which swallows wheel and touch gestures,
and the input area below it (`:1149`, `sticky bottom-0`) pins the visual bottom of the screen. On
mobile the mismatch is worse — `100dvh` tracks the browser chrome as it hides and shows, so the
footer keeps sliding back out of reach as the user scrolls.

Short pages (`/app`, `/privacy`, `/terms`, `/changelog`) are unaffected — they are not `h-dvh`, so
their footer shows normally. **This is a chat-page-only defect.**

A related crowding problem lives in the same region: the sticky input container at
`ChatIsland.tsx:1149-1231` stacks the session-limit button, the language-switch suggestion, the
textarea, the character counter, the disclaimer, `ChurchFinderBanner` and the whole `ContactForm`
into one block. When several of those are visible at once (and when `ContactForm` is expanded), the
bottom region eats an unreasonable share of a phone screen and pushes the conversation out of view.
Worth fixing in the same pass.

## Proposed Behaviour

The chat page must be self-contained within the viewport **and** expose the footer links. Pick one
of these — recommended first:

1. **Recommended — a compact footer row inside the chat shell.** Stop relying on the page-level
   `<Footer />` for the chat route and render a slim link row inside the sticky bottom container
   (next to, or merged with, the `Chat.disclaimer` line at `ChatIsland.tsx:1220-1222`). Always
   visible, no scrolling required, costs one line of height. The page-level `<Footer />` continues
   to serve every other route unchanged.
2. **Alternative — make the chat page shorter than the viewport.** Replace `h-dvh` on `main` with a
   height that subtracts the footer (`h-[calc(100dvh-var(--footer-h))]` with the footer height
   published as a CSS variable) so the footer is permanently on screen beneath the chat. Costs
   vertical space on every screen and needs care with the mobile keyboard.

Whichever is chosen, it must survive the mobile keyboard: when the on-screen keyboard opens, the
input must stay visible and the bottom chrome must not be pushed under it. `dvh` units plus the
existing `sticky bottom-0` handle most of this; verify on real iOS Safari and Android Chrome, not
only in a desktop responsive emulator.

**Also in scope — decrowd the bottom region:**

- Collapse `ContactForm` to a single-line trigger by default on small screens (it already has an
  `isExpanded` state, `ContactForm.tsx:34`) and consider moving it out of the sticky container so
  it does not compete with the composer.
- Ensure at most one promotional/suggestion element (`ChurchFinderBanner`, language-switch
  suggestion, session-limit button) is shown at a time.

## Acceptance Criteria

- [ ] On the chat page, the footer links (About, Get the app, Privacy, Terms, Changelog) are
      reachable without a document-level scroll, at 360×640, 390×844, 768×1024 and 1440×900.
- [ ] With the mobile keyboard open, the composer remains fully visible and is not overlapped.
- [ ] The conversation area still gets the majority of the vertical space on a 360×640 screen with
      the church-finder banner visible.
- [ ] No horizontal scrolling is introduced at any of the above widths.
- [ ] `/app`, `/privacy`, `/terms`, `/changelog` are visually unchanged.
- [ ] RTL (Arabic) renders correctly.
- [ ] No duplicate footer rendered on the chat page.

## Tests to Add

- Playwright (`frontend/e2e/`): on `/en`, assert a footer link is within the viewport bounding box
  without scrolling, at mobile and desktop viewports — this is the regression that matters and it
  cannot be caught by a unit test.
- Playwright: with the church-finder banner shown, the last message and the composer are both
  within the viewport.
- Component test for whatever new bottom-bar component is introduced.

## Files Likely to Change

| File | Change |
|---|---|
| `frontend/src/app/[locale]/ChatIsland.tsx` | Chat-shell height; bottom link row; decrowd sticky region |
| `frontend/src/app/[locale]/layout.tsx` | Do not double-render the footer on the chat route |
| `frontend/src/components/Footer.tsx` | Extract a compact variant for in-chat use |
| `frontend/src/components/ContactForm.tsx` | Collapsed-by-default trigger on small screens |
| `frontend/e2e/` | Viewport regression tests |

## Related

- **BITB-076** — adds an About link to this bar; the link is worthless until this is fixed.
- **BITB-074** — adds a "Support us" link to the same bar.
- **BITB-028** — Church Finder banner/bottom-sheet cleanup (same crowded region).
- `docs/BACKLOG_STORIES/mobile-fab-reposition.md` — prior art on mobile bottom-region layout.
