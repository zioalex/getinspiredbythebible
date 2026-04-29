# Mobile UX Fixes - Summary

**Date:** 2026-02-24
**Reporter:** User feedback on phone visualization
**Status:** In Progress

## Issues Identified

### 1. ✅ Mobile FAB Position (FIXED - Ready for PR)

**Problem:** Floating action button at bottom-right interferes with phone UI
**Solution:** Move FAB from `bottom-24 right-4` to `top-20 right-4`
**File:** `frontend/src/app/[locale]/page.tsx` line 755
**Change:** One-line CSS class change
**Status:** Code changed, ready to commit

### 2. ⏳ Auto-scroll During Streaming (Ready to implement)

**Problem:** Cannot scroll up manually while AI is typing
**Solution:** Only auto-scroll if user hasn't manually scrolled up
**Approach:**

- Add state to track if user is near bottom of chat
- Only call `scrollToBottom()` if user is within ~100px of bottom
- Reset on new message sent
**Files to change:** `frontend/src/app/[locale]/page.tsx`
**Complexity:** Medium (requires scroll position tracking)

### 3. 🔍 Language Detection Mid-Response (Investigation needed)

**Problem:** User reported: "I was in Spanish locale, wrote in Italian, got first sentence in English...then Italian"
**Example:** User wrote "Dimmi qualcosa riguardo il cuore a lo spirito da i salmi"
**Response:** "Questo è tratto dalla Bibbia, precisamente Salmi 51:6 e 51:17..." (all Italian)
**Status:** Could not reproduce - response appears to be entirely in correct language
**Action:** Monitor for future occurrences, request text dump if it happens again

### 4. ⏳ Verse Reference Parsing (Ready to implement)

**Problem:** "Salmi 51:6 e 51:17" creates invalid link `/chapter/e/51` because "e" (Italian "and") is parsed as book name
**Solution:** Exclude common conjunctions from book name matching
**Conjunctions to exclude:** e (IT), and (EN), und (DE), y (ES), et (FR), a (IT)
**Files to change:**

- `frontend/src/components/ChatMessage.tsx` (versePattern regex line 41, 58)
- `frontend/src/lib/verseExtraction.ts` (versePattern regex line 14)
**Approach:** Add negative lookbehind for single-letter words followed by space+numbers

### 5. ⏳ Right Pane Default Filter (Ready to implement)

**Problem:** Right panel defaults to "All Related" but should show "Referenced" by default
**Solution:** Change initial state from `false` to `true`
**File:** `frontend/src/app/[locale]/page.tsx` line 72
**Change:** One-line state initialization change
**Status:** Not yet implemented

## PR Plan

### PR #1: Mobile FAB Position ✅

- Branch: `fix/mobile-fab-position`
- Files: 1 file, 1 line change
- Complexity: Trivial
- Testing: Visual check on mobile viewport
- **Status:** Code ready, awaiting branch creation

### PR #2: Smart Auto-scroll

- Branch: `fix/chat-auto-scroll`
- Files: 1 file, ~15 lines
- Complexity: Medium
- Testing: Manual scroll behavior during streaming

### PR #3: Verse Reference Parsing

- Branch: `fix/verse-conjunction-parsing`
- Files: 2 files, regex updates
- Complexity: Medium
- Testing: Italian/Spanish/German verse references with conjunctions

### PR #4: Referenced Verses Default

- Branch: `fix/referenced-verses-default`
- Files: 1 file, 1 line change
- Complexity: Trivial
- Testing: Check default filter state on page load

## Next Steps

1. Create branch and PR for Fix #1 (trivial, ready now)
2. Implement Fix #5 (trivial, can bundle with #1 or separate PR)
3. Implement Fix #2 (medium complexity)
4. Implement Fix #4 (medium complexity, needs careful regex testing)
5. Monitor for Issue #3 recurrence
