# BITB-153: docs/BACKLOG.md Status Drifts From Finished Story Files

**Status:** ✅ Done
**Priority:** P2 — a tracking defect that wastes a full dedup pass every time it fires
**Size:** S (mechanical fix + a CI guard)
**Created:** 2026-09-14
**Prompted by:** the scheduled 2026-09-14 backlog audit, which nearly treated five already-shipped
stories as open work because the index still said 🎯

## User Story

**As** the scheduled session that picks up the next backlog story, **I want** `docs/BACKLOG.md`'s
status for a story to be trustworthy, **so that** "is this already done?" is answerable by reading
the index instead of opening every candidate story's own file to check.

## Why This Exists

`docs/BACKLOG.md` keeps its own copy of each story's heading emoji and `**Status:**` line,
duplicated from the canonical `docs/BACKLOG_STORIES/BITB-NNN-*.md` file. Nothing kept the two in
sync. A story finished and marked `✅ Done` in its own file could sit forever as `🎯 Todo` in the
index, because nothing ever re-visits the index once a story ships.

This is the same *shape* of problem as BITB-111 (which found fifteen `BITB-NNN` ids naming more
than one story) but a different failure mode: BITB-111 is about an id pointing at the wrong
number of files; this is about the index disagreeing with the one correct file it does point at.
Both waste the same kind of pass — someone (or some session) trusting `docs/BACKLOG.md` to decide
what is eligible to start.

Running a first pass of the check this story adds against `docs/BACKLOG_STORIES/` as it stood
before this PR found **five** confirmed cases where a single, unambiguous story file said
`✅ Done` while `docs/BACKLOG.md` still showed the story as open:

| ID | Story | Index said |
|---|---|---|
| BITB-029 | Surface Bible Version Information More Clearly | 🎯 Todo |
| BITB-030 | ChatScreen Top App Bar Cleanup | 🚧 In Progress |
| BITB-047 | One-Tap Copy of the User's Prompt | 🎯 Todo |
| BITB-062 | Index-Friendly Public Semantic Search | 🚧 In Progress |
| BITB-100 | Migration-Safety Rules Enforceable | 🎯 Todo |

A larger raw hit list also surfaced, but every other case shares its `BITB-NNN` with a *second*,
unrelated story file (BITB-018, 025, 028, 037, 050, 051, 052) — an existing collision, BITB-111's
problem, not this one. Attributing a `docs/BACKLOG.md` heading to the wrong file in that situation
would risk marking the wrong story Done, so this story's guard deliberately skips any id that
currently maps to more than one file and leaves those to BITB-111 / PR #1068's renumbering pass.

## What Shipped

- `scripts/check_backlog_status_sync.py`: a guard that reads every
  `docs/BACKLOG_STORIES/BITB-NNN-*.md` file, and for each one whose own `**Status:**` line is
  `✅` (Done), checks that its `docs/BACKLOG.md` section heading is also `✅`. Ids with more than
  one story file are skipped (deferred to BITB-111's guard) to avoid misattributing a heading to
  the wrong file. Exits non-zero with one clearly labeled error per drifted story.
- Wired into CI in `.github/workflows/test_update.yml`, alongside the other repo-hygiene guards,
  so a story marked Done without its index entry updated now fails the PR that does it instead of
  drifting silently.
- Fixed all five confirmed drifted entries in `docs/BACKLOG.md` (heading emoji + `**Status:**`
  line updated to match the canonical story file).

## Acceptance Criteria

- [x] A CI-enforceable check flags a `✅ Done` story file whose `docs/BACKLOG.md` entry is not
      also `✅`
- [x] The check safely skips ids with more than one story file rather than guessing
- [x] All currently-drifted entries found by the check are fixed in the same PR
- [x] Guard wired into `test_update.yml` so this cannot silently recur

## Related

- **BITB-111** — the sibling problem (an id naming more than one story); this guard explicitly
  defers to it rather than duplicating its scope
- `scripts/check_backlog_story_ids.py` — the existing guard this one sits alongside
