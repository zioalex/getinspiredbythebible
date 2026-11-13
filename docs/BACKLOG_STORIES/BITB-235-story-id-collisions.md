# BITB-235: Story IDs Collide Between Concurrent PRs

**Status:** 🔍 In Review (allocation rule: PR #1220; CI check: PR #1221)
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

**Struck again 2026-10-26, proving the story was never implemented:** open PR #1203 claimed
BITB-241 on 2026-10-24 (web read-aloud, Linux Firefox) and open PR #1215 claimed BITB-241 again on
2026-10-26 (fast pre-commit stages) — the second session checked only its local checkout, exactly
the failure mode described above. Resolved 2026-10-27 by first-claimant practice: #1203 keeps 241
and #1215 renumbered to BITB-243 (story file, BACKLOG.md, AGENTS.md, docs/PRE_COMMIT_SETUP.md and
k8s/kubeopencode/dev-image/README.md references updated; PR title updated).

## Options

- A CI check (in `commitlint.yml` or a small script) that fails when a PR adds a
  `docs/BACKLOG_STORIES/BITB-NNN-*` file whose number already exists on the base branch, or is
  claimed by another open PR.
- Make the rule "highest of `main` *and* open PRs + 1" in `AGENTS.md`, or reserve IDs with an
  `IDs reserved` line at the top of `docs/BACKLOG.md` committed straight to `main`.

**Decision (2026-10-27):** the AGENTS.md rule is codified (PR #1220) — allocate by *highest across
`origin/main` and every open PR's story files*, the **claim is the open PR** (push the story branch
and open the PR immediately; a numbered story on a local branch claims nothing), and on collision
the **earlier claimant keeps the ID** while the later PR renumbers before merge. A rule is not
enforcement — the CI check above remains the open acceptance criterion, since the 2026-10-26
collision happened *while the old rule was already in AGENTS.md*.

## Acceptance Criteria

- [x] Two PRs can no longer merge stories with the same ID unnoticed (PR #1221)
- [x] `AGENTS.md` Backlog Hygiene describes the chosen rule (PR #1220, 2026-10-27)
- [ ] Decide whether to correct the 1.58.0 `CHANGELOG.md` line for #1195 (BITB-214 → BITB-218) by hand
