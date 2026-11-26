---
id: BITB-366
status: in-review
priority: P1
kind: chore
size: M
created: 2026-11-26
prs: [1349]
depends_on: [BITB-368]
---

# BITB-366: Label Every PR With Its Kind, Keep Tooling Out of `feat`/`fix`, and Cap Open Product PRs

## User story

As the **owner**, scanning the PR list, I want each PR to show whether it is a feature, an NFR, a
fix, a chore or a spike, and which release it belongs to, without opening it.

## Requirements

1. New `scripts/pr_kind.py` and `.github/workflows/pr-kind.yml` (pull_request opened, edited,
   synchronize; same shape as `story-id-check.yml`): read the `BITB-NNN` ids in the PR title,
   read their front matter at the PR head, apply the `kind/<kind>` label (create the five labels
   when missing) and the GitHub milestone named by `milestone`.
2. Fail the check when: no story id or no `kind`; the linked stories have different kinds (one
   outcome per PR); a `chore`/`spike` PR title uses `feat:`/`fix:` (LEGEND table).
3. Dependabot and release-please PRs: label `kind/chore`, skip the checks.
4. `.github/pull_request_template.md`: add **Kind**, **Milestone**, and a one-sentence **Outcome**
   in the user's words.
5. AGENTS.md: the taxonomy rule in Git Conventions (replacing the `feat` vs `chore` table) and a
   WIP limit in Branch & PR Hygiene — no new product PR (feature/nfr/fix) while 8 are open;
   `pr-kind.yml` posts a one-time warning comment when the limit is exceeded.

## Decisions while building (2026-11-26)

- A story created before the `kind` cut-over (2026-11-27) that has no `kind` gives a warning, not
  a failure, so the PRs already open are not turned red; triage (BITB-367) sets their kinds.
- `revert:` and `merge:` fit every kind. A breaking `!` is allowed.
- Bot PRs (`*[bot]`) and release-please PRs (`release-please--*` branches) are skipped and need
  no story. Fork PRs are classified but not labelled (read-only token).
- The milestone is assigned only when an open GitHub milestone titled `R<n>: ...` exists; until
  BITB-367 creates them, the check warns.
- The WIP warning counts open, non-draft PRs labelled `kind/feature|nfr|fix` and is posted once
  per PR (marker comment).

## Acceptance criteria

- [x] Unit tests for `pr_kind.py` (`scripts/test_pr_kind.py`) cover each failure, the bot skips,
      the pre-cut-over warning, the CLI outputs, and real R1 titles against the real backlog
- [x] This PR (a `chore` story with a `ci:` title) passes its own check and is labelled `kind/chore`
- [ ] On a later PR: a `chore` story with a `fix(opencode):` title fails; a `feature` story gets
      `kind/feature` and its milestone; a Dependabot PR passes
- [ ] Owner step: after merge, the triage pass (BITB-367) sets `kind` on the stories behind the
      open PRs, which then get their labels on their next push or title edit
