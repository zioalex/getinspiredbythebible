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

## Resolved questions (owner, 2026-11-13)

1. **Ranking:** optional `rank` field, seeded by the migration from today's order inside
   each priority section (10, 20, 30, …). Re-prioritising = one-line edit.
2. **Cutover:** the BITB-313 author resolves every PR still open at cutover (moves its
   `BACKLOG.md` edits into story front matter and pushes).
3. Spec approved; proceed to Plan → Build → Verify.

## Plan (Opus, 2026-11-13)

### Facts found while planning (on `origin/main` @ 2a8b257d)

- `docs/BACKLOG.md` has 285 `### … BITB-NNN` index headings (283 distinct ids). BITB-220
  appears 3× in the Done section, which is duplicated history.
- 14 index entries have **no story file**: BITB-000 … BITB-013.
- 24 story files have no index entry (the BITB-111 exempt list).
- `docs/DONE/` holds 60 BITB story files plus non-story notes (no `BITB-NNN-` prefix),
  which are ignored. BITB-147 has 2 companion files under one id (the allowlist in
  `check_backlog_story_ids.py`).
- ~20 free-text status variants exist in story files (`✅ Merged`, `🔄 In progress — PR
  #1272`, `📋 Backlog`, `Todo`, `✅ Done — PR #1226, merged 2026-10-28`, …).
  `BITB-133` has no `**Status:**` line.
- Sections of `BACKLOG.md`: Changelog, Legend, Retrospectives, P0, P1, P2, P3, Done (Recent
  Completions), Icebox, Notes.

### Front-matter schema (fixed key order; one key per line)

```yaml
---
id: BITB-NNN                 # required, must equal the filename prefix
status: todo                 # required: todo|in-progress|in-review|blocked|done|cancelled
priority: P1                 # required: P0|P1|P2|P3|icebox
size: M                      # optional: XS|S|M|L|XL
rank: 10                     # optional int; sort key inside a priority
created: 2026-11-13          # optional ISO date
prs: [1292]                  # optional inline list of ints
follow_ups: [BITB-314]       # optional inline list of ids
depends_on: []               # optional inline list of ids
supersedes: free text        # optional single-line string
---
```

The title is the file's first `# ` H1 (strip a leading `BITB-NNN:`). There is no `title`
key, because it would trip markdownlint MD025.

### Changes per file

1. **`scripts/backlog.py`** (new, stdlib only, Python 3.12, `from __future__ import
   annotations`, typed, Black/Ruff clean):
   - Minimal front-matter parser and writer for exactly the schema above: scalars, inline
     `[a, b]` lists, `#` comments are not allowed in story files. Writer emits keys in the
     fixed order and omits optional keys that are empty, except `prs: []` (drop that too).
   - Loads stories from `docs/BACKLOG_STORIES/*.md` and `docs/DONE/*.md` (filename
     `BITB-\d+-…`). Companion-file allowlist carried over from `check_backlog_story_ids.py`
     (BITB-147 pair). A story without front matter is a `check` error.
   - Subcommands (argparse):
     - `list`: filters `--status a,b`, `--priority`, `--size`, `--grep` (case-insensitive
       over id+title), and `--all`. The default view is not done/cancelled. Formats:
       `compact` (default) prints `BITB-313  P1  L   todo         #1292  Title`, with the
       title truncated to 90 chars; also `md` and `json`. Sort: priority order
       P0,P1,P2,P3,icebox; then rank (missing rank sorts last); then numeric id.
     - `show ID [--full]`: path, then front matter, then title. `--full` prints the whole
       file.
     - `changelog [--ref origin/main|HEAD] [--since YYYY-MM-DD] [--limit N]`: runs
       `git log --first-parent --format=%cs%x09%s <ref>` and keeps subjects containing
       `BITB-\d+`. It emits `- DATE: BITB-NNN[, BITB-MMM] — subject`. The ref falls back
       to `HEAD` when `origin/main` is missing.
     - `check`: schema/enums, filename id == `id`, unique ids (allowlist), refs in
       `follow_ups`/`depends_on` exist, no bold
       `**Status:**|**Priority:**|**Size:**|**Created:**` line left in the header block.
       It prints `path: problem — fix hint`, exits 1 on any error and prints an `OK: N
       stories` summary.
     - `render`: full markdown index grouped by priority, then In Review / In Progress /
       Todo / Blocked, then a Done section; one table row per story. Output is
       deterministic.
     - `next-id`: highest id across both dirs + 1 (local tree only; the doc says to also
       run the BITB-235 open-PR check).
2. **`scripts/migrate_backlog_frontmatter.py`** (new, one-off, kept with tests):
   - Parses `BACKLOG.md` index entries: section, heading emoji, `**Status/Priority/Size/
     Created:**`, and position inside the section (for `rank` = 10, 20, …, per P0–P3
     section only).
   - Parses each story file's header block (text before the first `## `).
   - Merge rule: story file wins; the index fills gaps. `priority` comes from the file's
     Priority line, else the index line, else the index section (Icebox → `icebox`). Done
     section entries without a priority get `P3`, and this is reported.
   - Status normalization map: 🎯/Todo/📋 Backlog → todo; 🚧/🔄 In progress → in-progress;
     🔍/🔄 In Review → in-review; ✅ Done/Merged/Complete → done; ❌ → cancelled; ⏸/Blocked
     → blocked. An unknown value aborts with the file named.
   - `#\d+` found in the status text is added to `prs`. Any remaining free text after the
     status word (e.g. "merged 2026-10-28") is kept as a `**Status note:** …` line so no
     information is lost.
   - Removes the four bold lines from the header block, inserts front matter at the top,
     and leaves everything else byte-identical.
   - Index-only entries (BITB-000…013) become new files
     `docs/DONE/BITB-0NN-<slug-from-title>.md` (or `BACKLOG_STORIES/` if not done), with
     front matter plus the index entry body.
   - Duplicate index headings (BITB-220) are merged; the first occurrence wins, and this is
     reported.
   - `--dry-run` prints a report: counts, every conflict between file and index values,
     every defaulted field. Must be idempotent: a second run is a no-op.
3. **Run the migration** and commit the result (all story files + new BITB-000…013 files).
   Re-run to prove idempotence.
4. **`docs/backlog/`** (new):
   - `CHANGELOG-archive.md`: the old changelog section verbatim, with a one-paragraph
     header saying it is frozen and pointing to `make backlog-changelog`.
   - `LEGEND.md`: the legend, rewritten for the new enums.
   - `RETROSPECTIVES.md`: verbatim.
   - `NOTES.md`: the Notes section verbatim.
5. **`docs/BACKLOG.md`** becomes a ≤ 80-line stub covering:
   - what moved where;
   - `make backlog` examples (what's open in P1, find by text, show one story,
     changelog);
   - how to create, complete and cancel a story (edit front matter only; the changelog
     is the commit subject);
   - the CI guard and the `backlog-stub-edit` label exemption.
6. **Makefile**: `backlog` (`ARGS=` pass-through, default `list`), `backlog-changelog`,
   `backlog-check`, all with `##` help. Add `backlog-check` to `make test`'s prerequisites
   only if that is cheap; otherwise add it to CI only.
7. **CI**:
   - **`test_update.yml`**: replace the BITB-111 and BITB-153 guard steps with one step
     `python3 scripts/backlog.py check`.
   - **New `.github/workflows/backlog.yml`**, with `permissions: contents: read` and these
     jobs:
     - (a) `pull_request` job `backlog-check`, path-filtered on stories, scripts and the
       workflow: runs `backlog.py check` and `pytest scripts/test_backlog.py
       scripts/test_migrate_backlog_frontmatter.py`.
     - (b) `pull_request` job `backlog-stub-guard`, not path-filtered so it always runs:
       fails if `git diff --name-only origin/$BASE...HEAD` contains `docs/BACKLOG.md`,
       unless the PR title contains `BITB-313` or the PR has the label
       `backlog-stub-edit`. Both come from the event payload, so no token is needed. The
       `::error` message tells the author to edit story front matter instead.
     - (c) `push` to `main` (paths: stories/DONE): runs `backlog.py render` and appends it
       to `$GITHUB_STEP_SUMMARY`, plus `backlog.py changelog --limit 50`. Checkout uses
       `fetch-depth: 0`. No write anywhere.
   - **`story-id-check.yml`**: unchanged.
8. **Delete** `scripts/check_backlog_status_sync.py`, `scripts/check_backlog_story_ids.py`
   and `scripts/test_check_backlog_story_ids.py`. Their still-relevant rules (unique ids,
   companion allowlist) live in `backlog.py check`, and tests are ported into
   `scripts/test_backlog.py`.
9. **Tests**:
   - **`scripts/test_backlog.py`**:
     - parser/writer round-trip;
     - every `check` error class;
     - list filters, sort and truncation;
     - changelog from a temp git repo;
     - render determinism.
   - **Context budgets** (asserted against the real repo tree):
     - open-items compact list ≤ 12 KB;
     - `show` ≤ 1 KB.
   - **Conflict simulation**: temp git repo. Base has 3 stories. Branch A adds story X
     and flips story 1's status; branch B adds story Y and flips story 2's status. Assert
     `git merge-tree --write-tree` (git ≥ 2.38) reports no conflict in both orders.
   - **`scripts/test_migrate_backlog_frontmatter.py`**:
     - fixture BACKLOG.md and story files covering each status variant;
     - PR extraction and status note;
     - rank seeding;
     - index-only entry creation;
     - duplicate heading;
     - idempotence.
10. **Docs and prompts**:
    - **`AGENTS.md`**:
      - rewrite *Backlog Hygiene* bullets 2–6 (new story = one file with front matter;
        complete = `status: done` + `prs`; cancel = `status: cancelled` + reason line;
        changelog = conventional commit subject with BITB id; follow-ups unchanged;
        discovery via `make backlog`);
      - keep the BITB-235 ID allocation bullets but replace "`docs/BACKLOG.md`
        changelog/summary lines" in the collision paragraph with front matter;
      - add `scripts/backlog.py` to the repo-layout or testing notes.
    - **`.claude/commands/plan-build-verify.md`**: lines 38 and 78.
    - **`.opencode/agents/orchestrator.md`**: the allowlist line (keep `docs/BACKLOG.md`
      out; stories and DONE stay), plus a "query the backlog with `make backlog`, never
      read docs/BACKLOG.md whole" note.
    - **`scripts/generate-opencode-config.py`**: line 188 table row, then regenerate
      `opencode.json` with the generator and run `scripts/test_generate_opencode_config.py`.
    - **`docs/ROADMAP.md`**: repoint links.
    - **BITB-287 story**: note "requirement 1 superseded by BITB-313 (GitHub ignores merge
      drivers)".
    - Repo-wide `grep -rn "BACKLOG.md"`: fix live instructions; leave `docs/WIP/**`,
      `docs/audits/**`, archived stories and `frontend/` comments alone.

### Verification

- `python3 scripts/backlog.py check` green;
  `pytest scripts/test_backlog.py scripts/test_migrate_backlog_frontmatter.py
  scripts/test_check_story_ids.py scripts/test_generate_opencode_config.py` green.
- `black --check -l 100`, `ruff check` (repo config) and `mypy` on the new scripts.
- markdownlint on `docs/BACKLOG.md`, `docs/backlog/*.md` and a sample of migrated stories.
  Front matter must not break MD041/MD025 under the repo's `.markdownlint*` config; if
  it does, adjust the config with `front_matter_title: ""`.
- Spot-check 10 migrated stories (mixed statuses, DONE, index-only) against the old
  index.
- `make test-opencode-config-live` cannot run in the sandbox (no opencode binary); the PR's
  `opencode-ci.yml` is the gate.
