---
id: BITB-313
status: todo
priority: P1
size: L
created: 2026-11-13
prs: []
follow_ups: []
supersedes: BITB-287 requirement 1 (BACKLOG.md union merge driver)
---

# BITB-313: Conflict-Free, Agent-Friendly Backlog — Story Files Are the Single Source of Truth

> This story's own header is written in the **proposed** front-matter format, as a worked
> example. Until the migration lands, the BITB-111/153 checks still read the bold
> `**Status:**` lines of every other story.

## User story

As the **owner**, I want parallel PRs to stop conflicting on the backlog, **without** a
bot token that can write to `main`.

As a **coding agent** (paid remote models and free/local models with 32k–128k context),
I want to find the stories I need with one cheap command and edit only one small file.
I should never have to read or edit a 424 KB monolith.

## Problem (evidence)

1. **Every merge breaks every open PR.** Each PR prepends a line at the same position of
   the `docs/BACKLOG.md` changelog. 2026-11-12: #1279/#1281/#1282/#1283 all conflicted.
   They were resolved by hand, then on 2026-11-13 a single merge (#1280) re-broke all **7**
   open PRs (#1279, #1281, #1282, #1283, #1289, #1290, #1291). #1282 also hit a structural
   conflict: two new story sections were inserted at the same spot, and their identical
   `**Status:**/**Priority:**` lines interleaved.
2. **A merge driver cannot fix it.** BITB-287 req. 1 planned a union merge driver. GitHub
   computes PR mergeability and performs squash merges server-side, and both ignore
   `.gitattributes` merge drivers. A merge driver only helps local merges.
3. **Context saturation.** `docs/BACKLOG.md` is 7,922 lines / 424 KB (≈110k tokens). Read
   whole, it overflows a 32k/64k free or local model and fills most of a 128k window.
   Weak models also fail exact-match `str_replace` edits in a 7.9k-line file (non-unique
   anchors).
4. **Two copies of every status drift apart.** Each story's status lives in both
   `BACKLOG.md` and its story file. BITB-153 added a CI guard for one drift direction
   only. A status-only change can update one copy and miss the other (see the BITB-238/239
   "status drift fixed" changelog lines of 2026-11-11).

## Decision (owner, 2026-11-13)

Option **B** from the comparison done in session on 2026-11-12/13, ranked on 14 criteria
(no-main-write token, conflicts, context cost, local/remote LLM compatibility, targeted
retrieval, edit reliability, prompt-injection exposure, …):

- **Rejected — A, GitHub Issues + Projects.** Every agent read becomes an authenticated
  API call. Small models handle JSON tool calls poorly. Public issue comments inject
  untrusted text into agent context. The backlog edits are not reviewed in the PR.
- **Rejected — B with a bot that commits a regenerated `BACKLOG.md`.** It needs a token
  that can write `main`, which the owner refuses.
- **Rejected — C, changelog fragments only.** It keeps the 110k-token file and the
  double status.

## Functional requirements

1. **Story file = single source of truth.** Every story file carries a YAML front-matter
   block with these fields:
   - `id`
   - no `title` key: the title is the file's single `# BITB-NNN: …` H1 (one copy; a
     front-matter `title` would also trip markdownlint MD025)
   - `status`: enum `todo | in-progress | in-review | blocked | done | cancelled`
   - `priority`: `P0..P3` or `icebox`
   - `size`: `XS..XL`
   - `created`: ISO date
   - `prs`: list of ints
   - `follow_ups`: list of IDs
   - optional: `rank`, `depends_on`, `supersedes`

   The front matter **replaces** the bold `**Status:**/**Priority:**/**Size:**/**Created:**`
   lines, so no second copy remains in the file.
2. **`docs/BACKLOG.md` stops being hand-edited.** It becomes a short, stable stub
   (≈50 lines). The stub explains how to query the backlog, links the legend,
   retrospectives and changelog archive, and is **never changed by feature PRs**.
3. **`scripts/backlog.py`** (stdlib only, offline, deterministic output):
   - `list [--status …] [--priority …] [--size …] [--grep TEXT] [--format compact|md|json]`
     prints one line per story: `BITB-NNN  P1  S  in-review  #1234  Title`. Sort order is
     priority, then `rank`, then id.
   - `show BITB-NNN` prints the story's path and front matter (`--full` for the body).
   - `changelog [--since DATE] [--limit N]` derives entries from first-parent
     `git log origin/main` subjects containing `BITB-NNN` and `(#PR)`. No hand-written
     changelog lines.
   - `check` validates every story's front matter: schema, enums, `id` matching the
     filename, no duplicate ids, `follow_ups`/`depends_on` pointing at existing ids. The
     error output gives a fix hint.
   - `render` prints the full markdown index (P0→P3, icebox, done) to stdout, for humans.
4. **Make targets:**
   - `make backlog` (args passed through)
   - `make backlog-changelog`
   - `make backlog-check`, wired into `make test`/pre-commit
5. **CI** (GITHUB_TOKEN read-only; no write to any branch):
   - `backlog-check` job on PRs touching `docs/BACKLOG_STORIES/**` or `docs/DONE/**` runs
     `backlog.py check`.
   - Guard: a PR whose diff modifies `docs/BACKLOG.md` fails, with a message pointing to
     the story front matter. Exemption: PRs whose title contains `BITB-313` (the cutover).
   - On push to `main`: the job writes `backlog.py render` to the **Actions job summary**
     (human-readable index), with no commit.
6. **One-off migration script** (committed, with tests). It reads every story file's bold
   header lines, plus the `BACKLOG.md` index entry where the story file disagrees or is
   missing a field, and writes front matter. It normalizes the ~20 free-text status
   variants (`✅ Merged`, `🔄 In progress — PR #1272`, `📋 Backlog`, `Todo`, …) to the
   enum. PR numbers found in a free-text status move into `prs`.
   - The index order within each priority section becomes `rank` (step 10), so today's
     ordering is preserved.
   - Any conflicting value is printed in a migration report. The index wins for `status`
     only when the story file has no status.
7. **Archive the history verbatim** under `docs/backlog/`:
   - `CHANGELOG-archive.md` gets the existing changelog lines.
   - `LEGEND.md` and `RETROSPECTIVES.md` get the corresponding `BACKLOG.md` sections.
   - Nothing is deleted from history.
8. **Retire / adapt guards:**
   - `check_backlog_status_sync.py` (BITB-153) is deleted: there is only one copy left.
   - `check_backlog_story_ids.py` (BITB-111) drops the "must have a BACKLOG.md entry"
     rule and keeps the collision rule (or folds into `backlog.py check`).
   - `check_story_ids.py` / `story-id-check.yml` (BITB-235) stay unchanged.
9. **Docs and agent prompts** switch from "read/edit `docs/BACKLOG.md`" to "`make backlog …`
   then open the story file". This covers:
   - `AGENTS.md` → *Backlog Hygiene* (rewritten: create story = one file; complete story =
     edit front matter; changelog = commit subject).
   - `.claude/commands/plan-build-verify.md`
   - `.opencode/agents/orchestrator.md`
   - `scripts/generate-opencode-config.py` (+ regenerated `opencode.json`, + the BITB-280
     live-config gate)
   - `docs/ROADMAP.md` links
   - Repo-wide grep for `BACKLOG.md`. `docs/WIP/**` historical notes are left as-is.
10. **`docs/DONE/` stays where it is** (no mass move). New completions only change
    `status: done`; files stay in `docs/BACKLOG_STORIES/`, so paths remain stable for
    agents. `backlog.py` reads both folders.

## Non-functional requirements

- **Context budget:**
  - `make backlog --status todo,in-progress,in-review --format compact` ≤ 12 KB (≈3k
    tokens) on today's data.
  - `show` ≤ 1 KB without `--full`.
  - Tests assert these budgets so they cannot regress silently.
- **Local/remote LLM parity:** no network, no GitHub token, no third-party Python
  packages. A minimal YAML subset parser lives in the script, because the pod and laptops
  may lack PyYAML. Python 3.12. Runs in < 2 s on 300 stories.
- **Edit reliability:** front-matter keys are one per line with fixed order, so a status
  change is a single-line, uniquely anchored edit.
- **Security:** no new secrets. The workflows use `permissions: contents: read`.
- **Determinism:** same tree gives byte-identical output (stable sort, no timestamps).
- **11 languages / platforms:** not applicable (repo tooling only; no app, API, i18n or
  verse-parsing change). Stated explicitly per the Multilingual rule.

## Acceptance criteria

- [ ] All ~315 story files (BACKLOG_STORIES + DONE) carry valid front matter;
      `make backlog-check` is green; the migration report has zero unresolved conflicts.
- [ ] `docs/BACKLOG.md` is a stub ≤ 80 lines; changelog/legend/retrospectives preserved
      verbatim under `docs/backlog/`.
- [ ] `make backlog` / `make backlog-changelog` work offline with no deps; context budgets
      met and asserted in tests.
- [ ] **Conflict simulation test:** two branches that each add a story and flip another
      story's status, off the same base, merge in either order with **zero** conflicts
      (scripted with `git merge-tree` in `scripts/test_backlog.py`).
- [ ] CI: `backlog-check` runs on story-file changes; a PR editing `docs/BACKLOG.md`
      fails with an actionable message; `main` pushes publish the rendered index to the
      job summary; no workflow has write permission.
- [ ] BITB-153 guard removed, BITB-111 guard adapted, BITB-235 guard unchanged and green.
- [ ] AGENTS.md, plan-build-verify command, orchestrator prompt, generator +
      `opencode.json` updated; `make test-opencode-config-live` green (BITB-280 gate).
- [ ] Repo-wide `grep -rn "BACKLOG.md"` has no stale instruction outside `docs/WIP/**`
      and history archives.
- [ ] BITB-287 story/backlog note: requirement 1 marked superseded by BITB-313.
- [ ] Cutover note in the PR: each open PR touching `docs/BACKLOG.md` at cutover drops its
      `BACKLOG.md` hunk and moves its status into its story's front matter. The CI
      guard's message says exactly that.

## Out of scope

- GitHub Issues/Projects; any bot that commits to `main`; a committed generated index.
- Slimming `AGENTS.md` itself (also large; separate story if wanted).
- Changing story ID allocation (BITB-235). Hardening it with an atomic
  `refs/story-ids/NNN` claim is a possible follow-up.
- Rewriting `docs/WIP/**` historical notes.

## Open questions (to confirm before Plan)

1. Ranking within a priority: optional `rank` field seeded from today's order
   (recommended), or rank by id only?
2. Cutover for the PRs open at merge time: the cutover PR author fixes them, or each owner
   rebases?
