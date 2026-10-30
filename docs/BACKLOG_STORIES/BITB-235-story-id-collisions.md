# BITB-235: Story IDs Collide Between Concurrent PRs

**Status:** 🔍 In Review
**Priority:** P3
**Size:** S
**Created:** 2026-10-23
**Type:** Process / tooling
**Follow-up of:** BITB-218 (PR #1195), BITB-219 (PR #1191)

## Problem

Backlog Hygiene in `AGENTS.md` says to take the highest `BITB-NNN` in `docs/BACKLOG_STORIES/` and
add one. That only sees `main`, so PRs open at the same time pick the same number. On 2026-10-22/23:

- the mobile header story was filed as BITB-206 and renumbered three times (→ 212 → 213 → 219),
  because `main` (#1188, #1194) and open PR #1193 claimed 206, 212 and 213–217 meanwhile;
- the Next.js security story went BITB-214 → 218 for the same reason;
- this story itself was filed as BITB-223 and moved to BITB-235 after #1189 merged its own BITB-223
  (alert-rule rationalization) — #1189 had already renumbered eleven stories (212..222 → 223..233)
  for the same reason; a later merge commit pushed to #1197 also dropped its backlog edits;
- each renumber touched the story file, `docs/BACKLOG.md`, test names and the PR title, and the
  squash commit of #1195 on `main` still reads `(BITB-214)` — a different story (online-voices menu
  copy) — and the released `CHANGELOG.md` for 1.58.0 (#1167) cites BITB-214 for the security fix.

## Options

- A CI check (in `commitlint.yml` or a small script) that fails when a PR adds a
  `docs/BACKLOG_STORIES/BITB-NNN-*` file whose number already exists on the base branch, or is
  claimed by another open PR.
- Make the rule "highest of `main` *and* open PRs + 1" in `AGENTS.md`, or reserve IDs with an
  `IDs reserved` line at the top of `docs/BACKLOG.md` committed straight to `main`.

## Acceptance Criteria

- [x] Two PRs can no longer merge stories with the same ID unnoticed
- [ ] `AGENTS.md` Backlog Hygiene describes the chosen rule
- [ ] Decide whether to correct the 1.58.0 `CHANGELOG.md` line for #1195 (BITB-214 → BITB-218) by hand
