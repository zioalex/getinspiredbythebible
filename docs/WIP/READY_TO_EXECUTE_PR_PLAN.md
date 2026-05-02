# Mobile UX Fixes - Ready-to-Execute PR Plan

**Date:** 2026-02-24
**Total PRs:** 4 (3 high priority, 1 medium)

---

## PR #1: Mobile FAB Position Fix ✅ READY

**Branch:** `fix/mobile-fab-position`
**Priority:** High
**Complexity:** Trivial (1 file, 1 line)
**Files:**

- `frontend/src/app/[locale]/page.tsx` (line 755)

**Change:**

```diff
- className="lg:hidden fixed bottom-24 right-4 z-30 flex items-center gap-2 px-4 py-3 bg-primary-600 text-white rounded-full shadow-lg hover:bg-primary-700 transition-colors"
+ className="lg:hidden fixed top-20 right-4 z-30 flex items-center gap-2 px-4 py-3 bg-primary-600 text-white rounded-full shadow-lg hover:bg-primary-700 transition-colors"
```

**Commit message:**

```
fix: move mobile verse panel FAB from bottom to top

- Changes FAB position from bottom-24 right-4 to top-20 right-4
- Improves mobile UX by preventing overlap with input area
- Fixes issue reported in phone visualization feedback
```

**PR Title:** `fix: move mobile verse panel FAB from bottom to top`

**PR Body:**

```markdown
## Summary
Moves the mobile floating action button (FAB) for verse references from bottom-right to top-right position.

## Changes
- Changed FAB position from `bottom-24 right-4` to `top-20 right-4` in `frontend/src/app/[locale]/page.tsx` line 755

## Why
The bottom-right position was interfering with the phone UI, particularly the input area. Top-right keeps it accessible while not blocking critical interface elements.

## Testing
- [ ] Verify on mobile viewport (375px width)
- [ ] FAB visible and clickable in top-right corner
- [ ] No overlap with header elements
- [ ] Opens verse panel correctly
```

---

## PR #2: Referenced Verses Default ✅ READY

**Branch:** `fix/referenced-verses-default`
**Priority:** Medium
**Complexity:** Trivial (1 file, 1 line)
**Files:**

- `frontend/src/app/[locale]/page.tsx` (line 72)

**Change:**

```diff
- const [showOnlyReferenced, setShowOnlyReferenced] = useState(false); // Default to showing all related verses
+ const [showOnlyReferenced, setShowOnlyReferenced] = useState(true); // Default to showing only referenced verses
```

**Commit message:**

```
fix: default right pane to show referenced verses

- Changes showOnlyReferenced initial state from false to true
- Users now see only cited verses by default
- Reduces noise in verse reference panel
- Users can still toggle to see all related verses
```

**PR Title:** `fix: default right pane to show referenced verses`

**PR Body:**

```markdown
## Summary
Changes the default filter in the verse references panel from "All Related" to "Referenced" verses.

## Changes
- Changed `showOnlyReferenced` initial state from `false` to `true` in `frontend/src/app/[locale]/page.tsx` line 72

## Why
The right pane should focus on verses actually cited in the conversation by default. Users can still toggle to see all semantically related verses if desired.

## Testing
- [ ] Load page and send a message
- [ ] Verify "Referenced" filter is active by default
- [ ] Verify toggle to "All Related" still works
- [ ] Verify filter state persists during conversation
```

---

## PR #3: Smart Auto-Scroll ⏳ NEEDS IMPLEMENTATION

**Branch:** `fix/chat-auto-scroll`
**Priority:** High
**Complexity:** Medium (~20 lines, scroll tracking logic)
**Files:**

- `frontend/src/app/[locale]/page.tsx`

**Requirements:**

1. Track if user has manually scrolled up
2. Only auto-scroll if user is near bottom (within 100px)
3. Reset manual scroll flag when:
   - User scrolls back to bottom
   - User sends a new message
4. Apply during streaming AND when messages complete

**Implementation approach:**

- Add state: `const [userHasScrolled, setUserHasScrolled] = useState(false)`
- Add ref to messages container
- Add scroll event listener to detect manual scrolling
- Modify `scrollToBottom()` to check scroll position before scrolling
- Reset flag on new message submission

**Commit message:**

```
fix: allow manual scrolling during message streaming

- Track user scroll position in chat
- Only auto-scroll if user is near bottom (within 100px)
- Allow users to scroll up and read previous messages while AI types
- Reset to auto-scroll when user sends new message or scrolls to bottom
- Improves UX during long AI responses
```

**PR Title:** `fix: allow manual scrolling during message streaming`

---

## PR #4: Fix Verse Conjunction Parsing ⏳ NEEDS IMPLEMENTATION

**Branch:** `fix/verse-conjunction-parsing`
**Priority:** High
**Complexity:** Medium (2 files, regex updates, needs testing)
**Files:**

- `frontend/src/components/ChatMessage.tsx` (lines 41, 58)
- `frontend/src/lib/verseExtraction.ts` (line 14)

**Problem:**
"Salmi 51:6 e 51:17" → clicking creates invalid link `/chapter/e/51` because "e" (Italian "and") is parsed as a book name.

**Solution:**
Exclude common single-letter and short conjunctions from book name matching:

- e (Italian)
- y (Spanish)
- a (Italian "to")
- et (French)
- o (Spanish "or")

**Regex changes needed:**
Current pattern matches any letter sequence before chapter:verse.
Need to add negative lookbehind or positive lookahead to exclude conjunctions.

**Example fix approach:**

```typescript
// Before
const versePattern = /(\d+\.?\s?[\p{L}]+|[\p{L}]+)\s+(\d+):(\d+)/u;

// After - exclude single letters followed by space and numbers
const versePattern = /(?<!^|[\s])[(\d+\.?\s?[\p{L}]{2,}+|[\p{L}]{2,}+)(?!\s+(?:e|y|a|et|o|and|und)\s+\d)]\s+(\d+):(\d+)/u;
```

**Test cases:**

- ✓ "John 3:16" → matches
- ✓ "1 John 3:16" → matches
- ✓ "Giovanni 3:16" → matches
- ✓ "Salmi 51:6" → matches
- ✗ "e 51:17" → should NOT match
- ✗ "y 8:28" → should NOT match
- ✓ "Salmi 51:6 e 51:17" → should match "Salmi 51:6" and "51:17" separately or not parse "e 51:17"

**Commit message:**

```
fix: exclude conjunctions from verse reference parsing

- Prevent single-letter words (e, y, a) from being parsed as book names
- Fixes issue where "Salmi 51:6 e 51:17" created invalid /chapter/e/51 link
- Updated regex in ChatMessage.tsx and verseExtraction.ts
- Supports Italian, Spanish, German, French conjunctions
- Maintains correct parsing for actual book names
```

**PR Title:** `fix: exclude conjunctions from verse reference parsing`

---

## Execution Order

1. **PR #1** (FAB position) - trivial, can ship immediately
2. **PR #2** (Referenced default) - trivial, can bundle with #1 or separate
3. **PR #3** (Smart scroll) - medium complexity, needs careful testing
4. **PR #4** (Conjunction parsing) - medium complexity, needs regex testing with multiple languages

## Git Worktree Commands

For each PR, follow this pattern:

```bash
# Create worktree
git worktree add -b <branch-name> .claude/worktrees/<worktree-name> main

# Work in worktree
cd .claude/worktrees/<worktree-name>
# Make changes...
git add .
git commit -m "<commit-message>"
git push -u origin <branch-name>

# Create PR
gh pr create --title "<pr-title>" --body "<pr-body>"

# After merge, cleanup
cd /home/asurace/github/getinspiredbythebible
git worktree remove .claude/worktrees/<worktree-name>
git branch -d <branch-name>
```

---

## Next Action Required

**Human decision needed:**

1. Should I create all 4 worktrees and prepare the code changes?
2. Or should I delegate to orchestrator?
3. Or do you want to handle git operations and I provide the diffs?
