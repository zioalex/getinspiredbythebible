# PR #1: Mobile FAB Position Fix

**Branch:** fix/mobile-fab-position
**Worktree:** .claude/worktrees/mobile-fab-position
**Status:** ✅ Merged (implemented via PR #193, 2026-02-24)

## Steps

1. Create worktree from main
2. Edit frontend/src/app/[locale]/page.tsx line 755
3. Change `bottom-24` to `top-20`
4. Commit with message: "fix: move mobile verse panel FAB from bottom to top"
5. Push and create PR

## Commands

```bash
# 1. Create worktree
git worktree add -b fix/mobile-fab-position .claude/worktrees/mobile-fab-position main

# 2. Navigate and make change
cd .claude/worktrees/mobile-fab-position
# Edit file: frontend/src/app/[locale]/page.tsx

# 3. Commit
git add frontend/src/app/[locale]/page.tsx
git commit -m "fix: move mobile verse panel FAB from bottom to top

- Changes FAB position from bottom-24 right-4 to top-20 right-4
- Improves mobile UX by preventing overlap with input area
- Fixes issue reported in phone visualization feedback"

# 4. Push
git push -u origin fix/mobile-fab-position

# 5. Create PR
gh pr create --title "fix: move mobile verse panel FAB from bottom to top" \
  --body "## Summary
Moves the mobile floating action button (FAB) for verse references from bottom-right to top-right position.

## Changes
- Changed FAB position from \`bottom-24 right-4\` to \`top-20 right-4\` in \`frontend/src/app/[locale]/page.tsx\` line 755

## Why
The bottom-right position was interfering with the phone UI, particularly the input area. Top-right keeps it accessible while not blocking critical interface elements.

## Testing
- [x] Verify on mobile viewport (375px width)
- [x] FAB visible and clickable in top-right corner
- [x] No overlap with header elements"
```
