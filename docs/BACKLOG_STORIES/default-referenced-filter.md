# User Story: Default Verse Panel to "Referenced" Filter

**Status:** ✅ Done (PR #521 — useState(true) in page.tsx:87)

**As a** user reviewing verse references
**I want** to see only the verses actually cited in the conversation by default
**So that** I can focus on the most relevant scriptures without visual noise

## Functional Requirements

- [ ] Verse references panel defaults to "Referenced" filter on page load
- [ ] "Referenced" tab is visually active/selected by default
- [ ] Panel shows only verses explicitly cited in AI responses by default
- [ ] User can still toggle to "All Related" to see semantically similar verses
- [ ] Filter state persists during the conversation (doesn't reset on new messages)
- [ ] Filter preference does NOT persist across page reloads (always starts with "Referenced")

## Non-Functional Requirements

- **UX:** Default filter should prioritize signal over noise
- **UX:** Toggle between filters should be smooth and instant
- **Clarity:** User should understand the difference between "Referenced" and "All Related"
- **Performance:** Filter switching should be instant (client-side only)
- **Accessibility:** Active filter tab should have proper ARIA states

## Acceptance Criteria

- [ ] On page load, "Referenced" filter is active by default
- [ ] "Referenced" button has active styling (primary color background)
- [ ] "All Related" button has inactive styling (white background)
- [ ] Verse panel shows only cited verses when "Referenced" is active
- [ ] Clicking "All Related" shows all semantically relevant verses
- [ ] Clicking "Referenced" again filters back to cited verses only
- [ ] Filter state is maintained during conversation (doesn't reset when new messages arrive)
- [ ] Behavior is consistent on both desktop sidebar and mobile slide-over panel
- [ ] If no verses are referenced yet, "Referenced" tab shows appropriate empty state message

## Tech Constraints

- Change applies to both desktop sidebar and mobile verse panel
- Must update initial state value in React component
- Filter logic already exists, just need to change default
- Empty state messages already exist in translations

## Out of Scope

- Persisting filter preference across page reloads (localStorage)
- Changing filter toggle UI design
- Adding additional filter options (e.g., "Most Relevant")
- Animating filter transitions

## Current Behavior

Verse panel defaults to showing "All Related" verses, which includes all semantically similar verses from the search results. This can be noisy and distracting.

## Expected Behavior

Verse panel defaults to showing only "Referenced" verses — those explicitly cited by the AI in its responses. Users can expand to see "All Related" if they want more context.

## Testing Requirements

1. **Page load:** Load app, send message → verify "Referenced" is active by default
2. **No citations:** Send message where AI doesn't cite verses → verify empty state shows correctly
3. **Toggle to All:** Click "All Related" → verify all verses appear
4. **Toggle back:** Click "Referenced" → verify filtering works
5. **New messages:** Send new message → verify filter stays on current selection, doesn't reset
6. **Mobile:** Test on mobile slide-over panel → verify same behavior
7. **Desktop:** Test on desktop sidebar → verify same behavior

---

**Priority:** Medium
**Effort:** Trivial (single boolean default value change)
**Impact:** Moderate UX improvement, reduces cognitive load
