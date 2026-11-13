# BITB-148: The Backlog-ID Guard Can't Tell Two Same-Numbered Headings Apart

**Status:** 🎯 Todo
**Priority:** P3 — a narrow, disclosed gap in a guard that otherwise works; not blocking
**Size:** S
**Created:** 2026-09-13
**Prompted by:** PR #1068 (BITB-111), during the adversarial verify pass on the new
`scripts/check_backlog_story_ids.py` guard

## User Story

**As** the maintainer of the backlog-ID CI guard, **I want** it to verify that a story
file's `docs/BACKLOG.md` entry is actually *about* that file, **so that** an unrelated
same-numbered heading can't silently satisfy the check.

## Why This Exists

`scripts/check_backlog_story_ids.py`'s `_has_backlog_entry()` (added in BITB-111) requires
a real markdown heading or `**Full Story:**` link containing the `BITB-NNN` token — a real
improvement over a bare substring search. But it still can't fully disambiguate *which*
story a heading is about when two different things have ever shared a number.

Concretely: `docs/BACKLOG_STORIES/BITB-024-10-interaction-session-limit.md` (the live,
correct keeper of ID 024) currently "passes" the guard only because
`docs/BACKLOG.md` happens to also contain an unrelated legacy heading, `### ✅ BITB-024:
Add Phase 2 Language Support`, from a third, file-less story that predates the
`docs/BACKLOG_STORIES/` convention. The heading regex matches on the bare `BITB-024`
token and can't tell that heading isn't about the session-limit story at all. If the
"Add Phase 2 Language Support" heading were ever deleted, the session-limit story would
have *no* real entry and the guard would (correctly, this time) start failing — so the
current green state is accidental, not verified.

This is the same shape of ambiguity that motivated BITB-111 in the first place, just one
layer deeper: BITB-111 fixed "two files, one filename-ID"; this is "two things, one
`BACKLOG.md` heading-ID."

## Proposed Fix

Strengthen `_has_backlog_entry()` to check that the heading's *content* (title text) is
plausibly about the specific story file, not just that the numeric token matches — e.g.
by also requiring the heading line or the paragraph under it to reference the file's own
slug/title words, or by requiring exactly one heading per ID repo-wide (which would in
turn require finding and fixing every other legacy no-file heading like the
"Add Phase 2 Language Support" one — likely more than just BITB-024's case; a repo-wide
sweep of `docs/BACKLOG.md` headings vs. `docs/BACKLOG_STORIES/` filenames would need to
run first to size that separately).

## Acceptance Criteria

- [ ] `_has_backlog_entry()` (or its replacement) cannot be satisfied by a heading that
      shares an ID with the target file but is about a different topic
- [ ] The known BITB-024 case is either resolved (the legacy heading is merged/renamed) or
      explicitly allowlisted with the same documented-exception pattern
      `_MISSING_BACKLOG_ENTRY_EXEMPT` already uses
- [ ] A test proves a same-ID, different-topic heading is rejected

## Related

- **PR #1068 / BITB-111** — introduced the guard this hardens
- `scripts/check_backlog_story_ids.py` (`_has_backlog_entry`, docstring already documents
  this exact gap)
