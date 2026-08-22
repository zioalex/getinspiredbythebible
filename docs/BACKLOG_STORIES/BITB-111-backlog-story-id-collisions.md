# BITB-111: Fifteen Story IDs Refer to More Than One Story

**Status:** 🎯 Todo
**Priority:** P2 — a tracking defect that has already caused one near-miss and costs time on every
dedup pass
**Size:** M (mechanical, but every rename touches cross-references)
**Created:** 2026-08-22
**Prompted by:** the STEP 6 hygiene pass, and the BITB-092 collision caught in PR #969 hours before
it would have merged

## User Story

**As** anyone deciding what to work on, **I want** a `BITB-NNN` to identify exactly one story, **so
that** "is this already done?" is answerable by looking the ID up rather than by reading every file
that shares it.

## Why This Exists

`AGENTS.md` states the rule:

> **Story IDs are sequential.** Before creating a new story, check the highest existing `BITB-NNN`
> number in `docs/BACKLOG_STORIES/` and increment by one.

It is not holding. Fifteen IDs currently name two or three unrelated stories across
`docs/BACKLOG_STORIES/` and `docs/DONE/`:

| ID | files | ID | files |
|---|---|---|---|
| BITB-017 | 3 | BITB-051 | 2 |
| BITB-018 | 4 | BITB-052 | 2 |
| BITB-024 | 2 | BITB-053 | 2 |
| BITB-027 | 2 | BITB-054 | 2 |
| BITB-028 | 2 | BITB-057 | 2 |
| BITB-037 | 3 | BITB-068 | 3 |
| BITB-043 | 3 | BITB-069 | 3 |
| BITB-050 | 2 | | |

### This is not cosmetic

- **PR #969 nearly shipped a sixteenth.** It split BITB-084 Part C out as "BITB-092" while
  `BITB-092-fix-dev-db-initialization.md` was already merged and marked ✅ Done. Caught in review and
  renumbered to BITB-102 — but the only thing standing between the repo and another collision was
  someone noticing.
- **A dedup pass cannot trust an ID.** "Is BITB-051 done?" has no answer: the search-eval harness
  BITB-051 is partly shipped, the Android contact-form BITB-051 merged in June. Every check degrades
  into reading files.
- **Status lies by aliasing.** `docs/BACKLOG.md` marks BITB-009 ✅ Done on the strength of the models
  half, while four `# type: ignore` suppressions the same story requires removing are still on
  `main` and are what PR #984 fixes. An ID that names one thing cannot be half-done under another.

### Two related defects in the same family

- **BITB-059 has no `docs/BACKLOG.md` entry at all.** It exists only as a story file, and PR #983
  does not add one — so after that PR merges, an active story is invisible in the canonical list.
- **Orphaned story files.** `BITB-025-verse-linking-android.md` sits in `docs/BACKLOG_STORIES/` with
  no `BACKLOG.md` section; the BITB-025 entry that *does* exist is the Traditional Chinese story
  (PR #982). At least one such orphan exists per the earlier dedup pass; a sweep should find the
  rest.

## Proposed Fix

1. **Inventory** every duplicated ID and every story file with no `BACKLOG.md` entry. Mechanical and
   scriptable.
2. **Keep the earliest/shipped claimant** on each contested ID and **renumber the others** from the
   current high-water mark. Renaming a *shipped* story's ID is worse than renaming an unstarted
   one — merged PR titles and commit messages reference it and cannot be rewritten.
3. **Update every cross-reference** — `docs/BACKLOG.md`, other story files' Related sections,
   `docs/AUDIT_PLAYBOOK.md`, and any in-code comment naming the ID. Those in-code references are the
   ones most likely to be missed.
4. **Add a CI guard** asserting each `BITB-NNN` maps to exactly one story file and that every story
   file has a `BACKLOG.md` entry. This is the durable part: without it, the next collision is a
   matter of time, and the rule in `AGENTS.md` has already proven insufficient on its own.
5. **Record renumberings** in a short table so anyone following an old ID from a merged PR can find
   where the story went.

## Acceptance Criteria

- [ ] Every `BITB-NNN` maps to exactly one story file across `docs/BACKLOG_STORIES/` and `docs/DONE/`
- [ ] Every story file has a corresponding `docs/BACKLOG.md` entry — including BITB-059
- [ ] Cross-references updated everywhere, in-code comments included
- [ ] A CI check fails on a duplicate ID or a story file with no backlog entry
- [ ] A renumbering table records old → new for anything moved
- [ ] The BITB-009 status is corrected to reflect that its suppression-removal criterion was
      outstanding until PR #984

## Verification

The CI guard is the deliverable that matters — the cleanup without it just resets a counter that
climbs again. Prove it by adding a deliberate duplicate on a scratch branch and confirming CI
rejects it.

## Related

- **PR #969 / BITB-102** — the near-miss that prompted this
- **PR #984 / BITB-009** — the status-aliasing example
- **PR #983 / BITB-059** — the missing-entry example
- `AGENTS.md` (*Backlog Hygiene*), `docs/BACKLOG.md`, `docs/BACKLOG_STORIES/`, `docs/DONE/`
