---
id: BITB-366
status: todo
priority: P1
kind: chore
size: M
created: 2026-11-26
depends_on: [BITB-365]
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

## Acceptance criteria

- [ ] Unit tests for `pr_kind.py` (`scripts/test_pr_kind.py`) cover each failure and the bot skips
- [ ] On a draft PR, a `chore` story with a `fix(opencode):` title fails; a `feature` story gets
      `kind/feature` and its milestone; a Dependabot PR passes
- [ ] Owner step: after merge, label the open PRs (triage pass in BITB-367)
