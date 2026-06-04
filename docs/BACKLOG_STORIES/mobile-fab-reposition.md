# User Story: Mobile Verse Panel FAB Repositioning

**Status:** ✅ Done — changed `bottom-28 right-4` → `top-20 right-4` on the web frontend FAB in `frontend/src/app/[locale]/ChatIsland.tsx`. (Supersedes the stale PR #664, which edited the pre-refactor `page.tsx` and bundled unrelated dependency bumps.)

> Scope note: this story covers the **web frontend** (Next.js) FAB only. The native Android app renders verses via its own components (`VersesPanel`, `InlineVerseCard`, `VerseChip`) and is unaffected.

**As a** mobile user
**I want** the verse references button to be positioned at the top of the screen
**So that** it doesn't interfere with my typing area and other bottom UI elements

## Functional Requirements

- [x] Verse references floating action button (FAB) appears at top-right of mobile screen
- [x] FAB remains visible and accessible during scrolling
- [x] FAB opens the verse panel when tapped
- [x] FAB displays the count of relevant verses

## Non-Functional Requirements

- **UX:** Button must not overlap with header elements or interfere with page content
- **UX:** Button must remain easily tappable (minimum 44x44px touch target)
- **UX:** Transition should feel natural, not jarring
- **Accessibility:** Button must maintain proper aria-label for screen readers
- **Performance:** No layout shift or reflow issues

## Acceptance Criteria

- [x] FAB is positioned at top-right instead of bottom-right on mobile viewports (< 1024px)
- [x] FAB does not overlap with header, language switcher, or translation selector
- [x] FAB maintains adequate spacing from screen edges (4 units/1rem)
- [x] FAB z-index ensures it stays above page content but doesn't block critical UI
- [x] Clicking FAB still opens the verse slide-over panel correctly
- [x] Verse count badge is still visible and readable

## Tech Constraints

- Mobile-only change (hidden on desktop via `lg:hidden` class)
- Must work on small viewports (375px width minimum)
- Should use Tailwind utility classes for positioning
- Maintain existing z-index layering system

## Out of Scope

- Changing FAB appearance, size, or color
- Changing verse panel behavior
- Desktop/tablet layouts (FAB is hidden on large screens)
- Animation or transition effects (can be added later if needed)

## Current Behavior

FAB was positioned at `bottom-28 right-4` which sat directly above the chat input area on mobile phones.

## Expected Behavior

FAB should be positioned at `top-20 right-4` to stay out of the way while remaining accessible.

---

**Priority:** High
**Effort:** Trivial (CSS positioning change)
**Impact:** Improves mobile UX significantly
