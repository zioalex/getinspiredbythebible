# User Story: Smart Auto-Scroll During AI Streaming

**Status:** ✅ Done (PR merged 2026-05-09)
**Priority:** High
**Effort:** Medium
**Impact:** Significant UX improvement for power users and long conversations

**As a** user reading previous messages
**I want** to be able to scroll up and read past messages while the AI is typing
**So that** I can review context without being forced back to the bottom of the conversation

## Functional Requirements

- [x] Chat window allows manual scrolling at all times, including during AI response streaming
- [x] Chat auto-scrolls to show new content ONLY if user is already at the bottom
- [x] "At bottom" is defined as within ~100 pixels of the scrollable area's end
- [x] When user sends a new message, reset scroll behavior to auto-scroll
- [x] When user manually scrolls back to bottom, resume auto-scrolling

## Non-Functional Requirements

- **UX:** Scroll behavior should feel natural and predictable
- **UX:** Users should never lose their reading position unexpectedly
- **UX:** Auto-scroll should be smooth, not jarring
- **Performance:** Scroll position detection should not cause performance degradation
- **Accessibility:** Keyboard navigation (Page Up/Down, arrow keys) should work during streaming

## Acceptance Criteria

- [x] User can scroll up in chat history while AI is streaming a response
- [x] Chat does NOT auto-scroll to bottom if user has scrolled up (>100px from bottom)
- [x] Chat DOES auto-scroll to bottom if user is already near bottom (within 100px)
- [x] Sending a new message resets behavior to auto-scroll for the new response
- [x] Scrolling back to bottom manually re-enables auto-scroll
- [x] Behavior works consistently across different viewport sizes (mobile, tablet, desktop)
- [x] No performance issues or scroll jank during streaming

## Implementation Notes

- `isUserNearBottom` state tracks scroll position via `SCROLL_THRESHOLD = 100px`
- Scroll event listener on `messagesContainerRef` updates position state
- `useEffect` on `messages` change only calls `scrollToBottom()` when `isUserNearBottom`
- Key fix: `setIsUserNearBottom(true)` added to `submitMessage()` to reset on new message
- "Scroll to bottom" button shown when `!isUserNearBottom && messages.length > 0`
- Button text fully i18n-ified across 11 locales
- 4 new tests added covering: scrollIntoView on submit, button visibility, reset on send, resume on manual scroll

## Files Changed

- `frontend/src/app/[locale]/page.tsx` — reset fix, dead code removal, i18n button
- `frontend/messages/{en,it,de,es,fr,hi,pt,ru,ko,ar,zh}.json` — `Chat.scrollToBottom` key
- `frontend/src/app/[locale]/page.test.tsx` — 4 new scroll behavior tests
