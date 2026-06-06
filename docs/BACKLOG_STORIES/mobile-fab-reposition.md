# User Story: Mobile Verse Panel FAB Repositioning

**Status:** ❌ Won't Do — verified on the real frontend at 375px; the proposed `top-20` reposition is a **regression** and the existing `bottom-28 right-4` position is correct. PR #664 closed.

> Scope note: this story covers the **web frontend** (Next.js) FAB only. The native Android app renders verses via its own components (`VersesPanel`, `InlineVerseCard`, `VerseChip`) and is unaffected.

**As a** mobile user
**I want** the verse references button to not interfere with the chat
**So that** I can read messages and type without the button covering content

## Verification finding (2026-06-05)

The original premise — "`bottom-28 right-4` sits directly above the chat input" — described the **pre-refactor `page.tsx` layout**. The home page has since been refactored into `ChatIsland.tsx`, which renders a footer below the input. In the current layout the FAB positions behave differently. Captured at a 375px mobile viewport (Playwright, mocked verse response):

| Position | Result |
| --- | --- |
| `top-20 right-4` (proposed) | ❌ Overlaps and clips the message/answer card content |
| `bottom-28 right-4` (current) | ✅ Floats in the footer gutter below the input — clears messages, input, and send button |
| `bottom-44 right-4` (candidate) | ❌ Overlaps the send button and disclaimer text |

Conclusion: the existing `bottom-28 right-4` is the cleanest of the three. The reposition is declined. PR #664 was additionally stale (edited the deleted `page.tsx`) and bundled unrelated dependency bumps.

## Possible future work (not scheduled)

If the FAB is ever felt to compete with content, a non-floating approach — surfacing the verse count as a button inside the sticky header instead of a fixed FAB — would eliminate content overlap entirely. That is a larger change and out of scope here.

---

**Priority:** Low (no action needed)
**Effort:** N/A
**Impact:** None — current position retained
