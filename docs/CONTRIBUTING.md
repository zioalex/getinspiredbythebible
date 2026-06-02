# Contributing

## CI pipelines and path filters

Most workflows are path-filtered so they only run when relevant files change:

| Workflow           | Runs when these paths change                                                    |
| ------------------ | ------------------------------------------------------------------------------- |
| `android-ci.yml`   | `android/**`, the workflow file itself                                          |
| `azure-deploy.yml` | `api/**`, `frontend/**`, `scripts/**`, `deployment/**`, the workflow file       |
| `test_update.yml`  | `api/**`, `frontend/**`, `docker-compose*.yml`, `scripts/**`, the workflow file |
| `pre-commit.yml`   | every PR (lints docs, configs, and code)                                        |
| `commitlint.yml`   | every PR (lints commit messages)                                                |

A PR that changes **only** files under `docs/` (e.g. a backlog story) will skip
`android-ci.yml`, `azure-deploy.yml`, and `test_update.yml`. Only
`pre-commit.yml` and `commitlint.yml` will run.

### Branch-protection and skipped checks

When a workflow is skipped because no path matched, GitHub records its status
as **skipped**, not **success**. If your branch-protection rule requires a
specific check (e.g. `Backend API Tests`) to pass, a doc-only PR will be
blocked forever because that check never transitions to success.

**Fix options (choose one):**

1. **Recommended — require a status that always runs.** Change the required
   check from `Backend API Tests` to `Pre-Commit Hooks` (which runs on every
   PR). Backend/frontend test jobs remain as advisory signals on doc-only PRs.

2. **Aggregator job.** Add a tiny `ci-gate` job at the end of
   `test_update.yml` that runs with `if: always()` and checks
   `needs.*.result`. Map `skipped` → success and `failure` → failure. Require
   only `ci-gate` in branch protection.

Re-requesting a review on a doc-only PR will **not** unblock it — the skipped
check simply doesn't meet a "required: success" rule. The approaches above are
the only reliable solutions.

### Stale branches can silently overwrite merged work

If a long-lived branch is created from `main` **before** another PR merges, and
both touch the same file, the older branch can silently revert the newer change
on merge — no conflict, because one branch wholesale-replaces the file the other
edited. This is how the emphasized beta-tester CTA was lost: a homepage refactor
(`page.tsx` → `ChatIsland.tsx`) branched before the CTA landed and carried the
pre-CTA markup.

**Prevent it (recommended):** enable **Settings → Branches → Branch protection
→ "Require branches to be up to date before merging"** on `main`. GitHub then
forces each PR to merge/rebase the latest `main` before it can merge, turning a
silent overwrite into a visible conflict (or at least re-running CI against the
combined tree).

**Defense in depth:** add a focused regression test for any user-facing element
that must not disappear. The CTA is now guarded by the `Android beta-tester CTA`
tests in `frontend/src/app/[locale]/page.test.tsx`, which assert both entry
points to `/tester` (the header pill and the welcome-screen card) still render —
so a future overwrite fails CI instead of shipping.

## Commit message convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/).
Every commit title must match:

```
<type>(<scope>): <subject>
```

Common types: `feat`, `fix`, `chore`, `docs`, `ci`, `test`, `refactor`.

The `commitlint.yml` workflow enforces this on every PR.

## Translation completeness

The Android string-resource translation-validation job (`android-ci.yml`,
`translation-validation` step) requires every key in
`android/app/src/main/res/values/strings.xml` (default English) to also exist
in every locale file under `values-{locale}/strings.xml`.

When you add a new string key to the default file, add a matching key to
**all** locale files in the same PR. The CI job will fail and list every
missing key if you forget.

Supported locales: `ar`, `de`, `es`, `fr`, `hi`, `it`, `ko`, `pt`, `ru`, `zh`.
