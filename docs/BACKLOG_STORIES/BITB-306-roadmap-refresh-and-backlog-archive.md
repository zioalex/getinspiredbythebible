---
id: BITB-306
status: todo
priority: P2
size: S
rank: 30
created: 2026-11-11
---

# BITB-306: Refresh the Roadmap, Archive Completed Backlog Entries, Unstick the Audit Trend

**Prompted by:** [2026-11-11 verified review](../audits/2026-11-11-verified-review.md) rows P1, P2, P3.
**Plan:** [2026-11-11 improvement plan](../audits/2026-11-11-improvement-plan.md), any wave.
**Commit:** `docs: refresh roadmap and archive completed backlog entries (BITB-306)`

**Re-scoped (2026-11-13):** the `docs/BACKLOG.md` archive part is done by BITB-313 (the
index is gone, history archived under `docs/backlog/`). Only the roadmap refresh (and the audit
trend item) remain.

## Problem

- `docs/ROADMAP.md` was last updated on 2026-02-23. Its "Now" section is February's
  stability milestone; its "Next" lists work that shipped months ago. Anyone reading it —
  a contributor, a model, the owner in six months — gets the wrong picture of what the
  project is trying to do.
- `docs/BACKLOG.md` is 7,623 lines. Completed stories stay in the priority sections, so
  the open work is hard to see and the file conflicts on most PRs.
- `docs/audits/metrics/report.md` still shows the 2026-07-05 snapshot although the
  `Audit Metrics` workflow succeeded on 2026-11-02. The trend the audits are meant to
  feed has not moved in four months, and nobody was told.

## Decisions already made

1. **The roadmap is rewritten around users, in the existing Now / Next / Later / Icebox
   shape:**
   - *Now — safe to grow:* BITB-296, 297, 298, 299, 304.
   - *Next — be found and be useful:* BITB-300, 301, 302, 303.
   - *Later:* iOS (BITB-085), single verse grammar (BITB-059), private database
     (BITB-005), the monolith splits from the July audit.
   - Each item: one line on what a user gets, and the story ID. No dates the owner has
     not chosen.
2. **Completed entries move out of the live backlog** into `docs/BACKLOG_DONE.md`,
   verbatim, in their original order. The live file keeps the changelog, the legend and
   only stories that are not `✅ Done` or `❌ Cancelled`.
3. **Nothing is renumbered, reworded or deleted.** This is a move.
4. **The changelog section is not touched** except for this story's own new line.

## Requirements

1. Rewrite `docs/ROADMAP.md` (decision 1). Keep the Vision section; correct anything in
   it that is no longer true (the Android app is published — check
   `frontend/src/app/sitemap.ts`'s comment and the `/app` page before stating it).
2. Before moving anything, read `scripts/check_backlog_story_ids.py` in full. It
   requires every file in `docs/BACKLOG_STORIES/` to have a heading in
   `docs/BACKLOG.md`. A `✅ Done` entry whose story file is still in
   `docs/BACKLOG_STORIES/` must have its file moved to `docs/DONE/` in the same commit
   (that is the documented convention in `AGENTS.md`), or the entry stays. Do not weaken
   the check.
3. Move the entries (decisions 2–3) with a script kept in the PR description, not
   committed, so the move is reproducible and reviewable. Verify by line count: lines
   removed from `BACKLOG.md` = lines added to `BACKLOG_DONE.md`.
4. Repo-wide reference check: `grep -rn "BACKLOG.md#" --exclude-dir=.git .` and fix any
   anchor that pointed at a moved entry. Update `AGENTS.md` *Backlog Hygiene* with one
   sentence: completed entries move to `docs/BACKLOG_DONE.md` when the story is marked
   done.
5. Audit trend: read the log of the latest `Audit Metrics` run and
   `tools/audit-metrics/analyze.py` to find out why no snapshot newer than 2026-07-05 is
   in `docs/audits/metrics/history/`. Likely candidates to check, not conclusions: the
   push to `main` fails and the fallback PR is never merged; or the commit step sees no
   diff. Fix the cause, or if the fix needs a repository setting, document it under
   Owner steps. Run `make audit-metrics` locally and commit the fresh snapshot.
6. Run `python scripts/check_backlog_story_ids.py` and the backend test that wraps it.

## Tests

Documentation-only apart from requirement 5. If the audit-metrics fix touches
`tools/audit-metrics/`, extend `tools/audit-metrics/test_analyze.py`. Per `AGENTS.md`
this is a low-risk mechanical change: builder self-verification, green CI and the
line-count proof are sufficient; no separate verifier session is needed.

## Acceptance criteria

- [ ] `docs/ROADMAP.md` "Last Updated" is current and "Now" lists the wave-1 stories
- [ ] `docs/BACKLOG.md` contains no `✅ Done` or `❌ Cancelled` story entries outside the
      changelog; target under 3,500 lines
- [ ] `docs/BACKLOG_DONE.md` contains every moved entry verbatim
- [ ] `scripts/check_backlog_story_ids.py` passes
- [ ] No broken in-repo links to moved entries
- [ ] `docs/audits/metrics/report.md` shows a snapshot dated on or after the merge, or
      the blocker is documented with an owner step
- [ ] **Owner step:** read the new roadmap and correct the order if it does not match
      your priorities

## Out of scope

- Shortening `AGENTS.md`.
- Changing the story-ID rules.
- Writing the 2026-11 adversarial audit report in the `tools/audit-metrics` format (the
  2026-11-11 review is a narrative file on purpose; a full report is a separate run of
  the `risk-audit` command).

## Related

BITB-111, BITB-235, BITB-287 (BACKLOG union merge driver), `docs/AUDIT_PLAYBOOK.md`.
