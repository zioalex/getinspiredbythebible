# BITB-165: Auto-update opted-in PR branches when main moves

**Status:** 🚧 In Progress | **Priority:** P2 | **Size:** S | **Created:** 2026-09-29

## User story

As the repo owner, I want opted-in pull requests to be brought up to date with `main`
automatically, so that with GitHub auto-merge they merge themselves once green and I stop
pressing "Update branch" on every PR after each merge.

## Why it exists

Branch protection on `main` enables "Require branches to be up to date before merging". Every
merge therefore leaves every other open PR behind, and each needs a manual "Update branch"
click before it can merge. A merge queue would solve this, but merge queues are only available
for organization-owned repositories; this is a personal-account repository.

## Design

* `.github/workflows/auto-update-prs.yml` runs on every push to `main`, when auto-merge is
  enabled on a PR, when the `autoupdate` label is added, and on manual dispatch.
* `scripts/auto_update_prs.py` (stdlib only) lists open PRs against `main`, and for each
  opted-in PR that is behind calls `PUT /pulls/{n}/update-branch` with `expected_head_sha`.
* **Opt-in:** auto-merge enabled on the PR, or the `autoupdate` label.
* **Skipped:** drafts, fork PRs (cannot push), Dependabot (rebases its own PRs) and
  release-please PRs (regenerated).
* **PAT required:** branch updates made with the default `GITHUB_TOKEN` do not trigger
  workflows, so CI would never run on the updated PR and auto-merge would wait forever. The
  token is `AUTO_UPDATE_PR_TOKEN`, falling back to `RELEASE_PLEASE_TOKEN`.
* The workflow always checks out the default branch, never the PR head, so PR-modified script
  code never runs with the PAT. Top-level permissions are `contents: read`.
* Merge conflicts (HTTP 422) are reported as warnings and do not stop other PRs; auth or
  permission errors fail the run loudly.

## Acceptance criteria

* A push to `main` updates every opted-in, non-draft, same-repo PR that is behind
* PRs that are up to date, drafts, forks, Dependabot, release-please and non-opted-in PRs are
  left untouched
* A conflicting PR produces a warning and the remaining PRs are still processed
* A bad or missing token fails the run with a message naming `AUTO_UPDATE_PR_TOKEN`
* Enabling auto-merge or adding the `autoupdate` label updates just that PR
* Tests cover eligibility, pagination, dry run, error handling and workflow safety guards
* Green CI on the PR

## Setup (manual, one-time)

1. Settings → General → enable **Allow auto-merge**.
2. Optionally create secret `AUTO_UPDATE_PR_TOKEN`: a fine-grained PAT scoped to this repo
   only with Contents read/write and Pull requests read/write. Otherwise the workflow falls
   back to `RELEASE_PLEASE_TOKEN`.
3. Per PR, click **Enable auto-merge** or add the label `autoupdate`.
4. Optional dry run: Actions → Auto-update PR branches → Run workflow with `dry_run` enabled.

## Trade-offs

Each merge to `main` re-runs CI on every opted-in PR that is behind, which costs CI minutes
proportional to the number of opted-in PRs.

Each update is a merge commit pushed as the PAT's owner. It re-triggers CI on the PR, and if
branch protection has "Dismiss stale pull request approvals when new commits are pushed" enabled,
it dismisses existing approvals.

A transient API error on one PR is reported as an `error` row and the run fails at the end, but
the other PRs are still processed. A 401/403 (token or permission problem) aborts the run.

## Out of scope

Fork PRs, Dependabot PRs and release-please PRs; resolving merge conflicts automatically.
