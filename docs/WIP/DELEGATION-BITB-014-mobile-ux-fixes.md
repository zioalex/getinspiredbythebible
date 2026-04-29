# Delegation Request to Orchestrator: BITB-014 Mobile UX Fixes

**From:** Product Owner
**To:** Orchestrator
**Date:** 2026-02-24
**Priority:** P0 (Critical)

## Summary

User reported 4 mobile UX issues during phone visualization testing. I've written detailed user stories for each. Please delegate to fullstack-engineer to implement as 4 separate PRs using git worktrees.

## User Stories (Detailed Requirements)

1. **BITB-014a:** Mobile FAB Repositioning → `docs/BACKLOG_STORIES/mobile-fab-reposition.md`
2. **BITB-014b:** Smart Auto-Scroll → `docs/BACKLOG_STORIES/smart-auto-scroll.md`
3. **BITB-014c:** Verse Conjunction Parsing → `docs/BACKLOG_STORIES/fix-verse-conjunction-parsing.md`
4. **BITB-014d:** Referenced Filter Default → `docs/BACKLOG_STORIES/default-referenced-filter.md`

Each story includes:

- Functional requirements
- Non-functional requirements (UX, performance, accessibility)
- Acceptance criteria
- Testing requirements
- Tech constraints
- Out of scope items

## Implementation Requirements

### Git Workflow

- Create each PR in a separate git worktree
- Worktree locations: `.claude/worktrees/<branch-name>/`
- Branch naming: `fix/mobile-fab-position`, `fix/chat-auto-scroll`, `fix/verse-conjunction-parsing`, `fix/referenced-verses-default`
- Each PR should be independently mergeable

### PR Structure

- One PR per story (4 total PRs)
- Keep PRs simple and focused
- Include tests as specified in each story
- Run `make pre-commit` before pushing
- Create PR with title matching commit message (conventional commits)

### Execution Order (Suggested)

1. **PR #1:** BITB-014a (FAB position) — trivial, ship immediately
2. **PR #2:** BITB-014d (Referenced default) — trivial, can ship immediately
3. **PR #3:** BITB-014b (Smart scroll) — medium complexity, requires testing
4. **PR #4:** BITB-014c (Conjunction parsing) — medium complexity, requires multi-language testing

## Definition of Done

For each PR:

- [ ] Code matches functional requirements in story
- [ ] All acceptance criteria met
- [ ] Tests written and passing (as specified in story)
- [ ] `make pre-commit` passes
- [ ] PR created with clear title and description
- [ ] CI green

## Expected Deliverables

When complete, please report back with:

1. PR numbers and URLs for all 4 PRs
2. CI status for each PR
3. Summary of what was built
4. Any deviations from requirements (with justification)

## Questions?

If any requirements are unclear or technically infeasible, please ask clarifying questions before implementation.

---

**Awaiting your delegation to fullstack-engineer. Please confirm before proceeding.**
