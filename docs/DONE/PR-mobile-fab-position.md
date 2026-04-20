# PR: Fix Mobile FAB Position

**Status:** ✅ Merged (PR #193, 2026-02-24)
**Started:** 2026-02-24

## Summary

Move the mobile floating action button (FAB) for verse references from bottom-right to top-right position to prevent interference with phone UI elements.

## User Story

As a mobile user, I want the verse references button to be positioned at the top of the screen so that it doesn't interfere with the input area and other bottom UI elements.

## Tasks

- [x] Update FAB position in page.tsx from `bottom-24` to `top-20`
- [ ] Create feature branch
- [ ] Commit changes
- [ ] Push branch
- [ ] Create PR
- [ ] Test on mobile viewport
- [ ] Get human approval and merge

## Changes Made

- `frontend/src/app/[locale]/page.tsx` line 755: Changed FAB className from `bottom-24 right-4` to `top-20 right-4`

## Progress Log

### 2026-02-24

- Identified issue from user feedback: FAB at bottom-right interfering with phone visualization
- Made code change to move FAB to top-right position
- Need to create branch and PR for review

## Notes

- This is part of a series of mobile UX fixes
- Related issues: scroll behavior, verse parsing, and default filter state
