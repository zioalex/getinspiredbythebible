# Claude Code — Project Instructions

## Scheduled PR Maintenance Routine

When running as a scheduled routine, perform the following steps in order:

### 1. Dependabot PRs

- List all open dependabot PRs.
- For each PR, check `mergeable_state` and CI check runs.
- **Broken / dirty (conflicts):** trigger `@dependabot rebase` by posting a comment.
- **Behind main, CI green:** trigger `@dependabot rebase` by posting a comment.
- **Blocked, CI green, already on main:** note it — requires human approval, skip.
- Superseded PRs (e.g. aiohttp 3.14.0 when 3.14.1 is open) get rebased too; dependabot closes them automatically when the newer one merges.

### 2. Fix and Bug PRs — merge one at a time

After handling dependabot PRs, look for open PRs authored by humans (not dependabot) that carry a `fix` or `bug` label, or whose title starts with `fix:` / `fix(...):`  .

For each qualifying PR, **in order from oldest to newest**:

1. Check `mergeable_state` and CI check runs.
2. If `mergeable_state` is `dirty`: post `@dependabot rebase` is not applicable — instead note the conflict and skip; a human must resolve it.
3. If `mergeable_state` is `behind` and CI is green: use `update_pull_request_branch` (or equivalent) to rebase it, then wait for CI to re-run before proceeding to the next PR.
4. If `mergeable_state` is `clean` and all required CI checks pass: merge the PR using a **squash merge**.
5. After each merge, stop and check whether any remaining PRs now have conflicts before continuing to the next one.
6. If CI is failing on a PR: skip it and report the failure in the routine summary.

**Process only one PR per run.** After a successful merge, finish the routine and report. The next scheduled run will pick up the next one.

### 3. Routine summary

At the end of each run, report:
- Dependabot PRs rebased (count + list)
- Fix/bug PRs merged (title + number), or reason skipped
- Any items requiring human attention (approvals, unresolvable conflicts, failing CI)
