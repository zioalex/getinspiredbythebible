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
