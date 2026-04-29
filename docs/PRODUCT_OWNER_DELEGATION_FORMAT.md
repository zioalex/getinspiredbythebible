# Product Owner Directive: User Story Delegation Format

**Updated:** 2026-02-24

## Problem

Subagents get blocked when:

- They try to read user story files from `docs/BACKLOG_STORIES/`
- They try to write to directories outside project scope (e.g., `/home/asurace/.npm`)

## Solution

**Embed full requirements in task delegation** instead of referencing external files.

### Before (Causes Blocking)

```
User Story: See docs/BACKLOG_STORIES/mobile-fab-reposition.md
```

### After (Works)

```
User Story:

As a mobile user,
I want the verse references button at the top of the screen,
So that it doesn't interfere with my typing area.

Functional Requirements:
- [ ] FAB appears at top-right instead of bottom-right
- [ ] FAB remains clickable and opens verse panel
...

Acceptance Criteria:
- [ ] FAB positioned at top-20 right-4 on mobile
- [ ] No overlap with header
...
```

## Delegation Template

When delegating to orchestrator, include:

1. **User Story** (As a... I want... So that...)
2. **Functional Requirements** (full list from story file)
3. **Non-Functional Requirements** (UX, performance, accessibility)
4. **Acceptance Criteria** (full list from story file)
5. **Tech Constraints** (what must/must not be done)
6. **Out of Scope** (what NOT to include)
7. **Testing Requirements** (how to verify)
8. **Expected Deliverable** (PR URL, CI status, summary)

## Benefits

- No file access issues
- Subagent has all context in one place
- No need to navigate docs/ while in worktree
- Task is self-contained and clear

## File Organization

- Continue writing detailed user stories in `docs/BACKLOG_STORIES/` for documentation
- When delegating, copy the relevant sections into the task prompt
- User story files remain source of truth, but delegation includes full text
