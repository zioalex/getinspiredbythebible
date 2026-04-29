# User Story: Smart Auto-Scroll During AI Streaming

**As a** user reading previous messages
**I want** to be able to scroll up and read past messages while the AI is typing
**So that** I can review context without being forced back to the bottom of the conversation

## Functional Requirements

- [ ] Chat window allows manual scrolling at all times, including during AI response streaming
- [ ] Chat auto-scrolls to show new content ONLY if user is already at the bottom
- [ ] "At bottom" is defined as within ~100 pixels of the scrollable area's end
- [ ] When user sends a new message, reset scroll behavior to auto-scroll
- [ ] When user manually scrolls back to bottom, resume auto-scrolling

## Non-Functional Requirements

- **UX:** Scroll behavior should feel natural and predictable
- **UX:** Users should never lose their reading position unexpectedly
- **UX:** Auto-scroll should be smooth, not jarring
- **Performance:** Scroll position detection should not cause performance degradation
- **Accessibility:** Keyboard navigation (Page Up/Down, arrow keys) should work during streaming

## Acceptance Criteria

- [ ] User can scroll up in chat history while AI is streaming a response
- [ ] Chat does NOT auto-scroll to bottom if user has scrolled up (>100px from bottom)
- [ ] Chat DOES auto-scroll to bottom if user is already near bottom (within 100px)
- [ ] Sending a new message resets behavior to auto-scroll for the new response
- [ ] Scrolling back to bottom manually re-enables auto-scroll
- [ ] Behavior works consistently across different viewport sizes (mobile, tablet, desktop)
- [ ] No performance issues or scroll jank during streaming

## Tech Constraints

- Must work with React 18+ and Next.js App Router
- Must integrate with existing streaming message display logic
- Must handle both SSE streaming and message completion states
- Should use React refs and event listeners for scroll detection
- Must clean up event listeners properly to avoid memory leaks

## Out of Scope

- Smooth scrolling animations (can use CSS for this)
- "Jump to bottom" button when scrolled up (nice-to-have for future)
- Scroll position persistence across page reloads
- Virtual scrolling for very long conversations

## Current Behavior

Chat automatically scrolls to bottom on every content update during streaming, making it impossible to read previous messages while AI is typing.

## Expected Behavior

Chat only scrolls to bottom automatically if user hasn't manually scrolled up. If user scrolls up to read history, stay there until they scroll back down or send a new message.

## Testing Requirements

1. **Manual scroll while streaming:** Start a conversation, scroll up while AI types — verify you stay at scroll position
2. **Auto-scroll when at bottom:** Don't scroll, let AI type — verify it auto-scrolls to show new content
3. **Reset on new message:** Scroll up, send new message — verify auto-scroll resumes for new response
4. **Manual scroll to bottom:** Scroll up, then manually scroll back to bottom — verify auto-scroll resumes
5. **Mobile behavior:** Test on 375px viewport — verify scroll behavior identical to desktop
6. **Long messages:** Test with very long AI responses to ensure consistent behavior

---

**Priority:** High
**Effort:** Medium (requires scroll position tracking and conditional logic)
**Impact:** Significant UX improvement for power users and long conversations
