# Contributing

## CI pipelines and path filters

Most workflows are path-filtered so they only run when relevant files change:

| Workflow             | Runs when these paths change                                                      |
| -------------------- | -------------------------------------------------------------------------------- |
| `android-ci.yml`     | `android/**`, the workflow file itself                                            |
| `azure-deploy.yml`   | `api/**`, `frontend/**`, `scripts/**`, `deployment/**`, the workflow file        |
| `test_update.yml`    | `api/**`, `frontend/**`, `docker-compose*.yml`, `scripts/**`, the workflow file  |
| `pre-commit.yml`     | every PR (lints docs, configs, and code)                                          |
| `commitlint.yml`     | every PR (lints commit messages)                                                  |
| `story-id-check.yml` | `docs/BACKLOG_STORIES/**`, `scripts/check_story_ids.py`, the workflow file        |
| `parity-ci.yml`      | `api/**`, `docs/parity/**`, `scripts/export_openapi.py` + its test, the workflow file |
| `az-lint.yml`        | `.github/workflows/**`, `.github/actions/**`, `scripts/**`, `deployment/**/*.sh`, `deployment/**/*.tf`, `.python-version`, `Makefile`, `api/**/*.py` |

A PR that changes **only** files under `docs/` (e.g. a backlog story) will skip
`android-ci.yml`, `azure-deploy.yml`, and `test_update.yml`. Only `pre-commit.yml`,
`commitlint.yml`, and — when it touches `docs/BACKLOG_STORIES/` — `story-id-check.yml`
will run (or, for `docs/parity/`, `parity-ci.yml`: its hard stale-artifact gate +
export-script tests and the warn-only breaking-change report via the official
`oasdiff/oasdiff-action` — see `docs/parity/README.md`).

### Scheduled workflows (BITB-304)

Three workflows run on a schedule (and by hand via *Run workflow*), never on pull requests:

| Workflow                        | Schedule                         | What it does |
| ------------------------------- | -------------------------------- | ------------ |
| `model-existence-probe.yml`     | Mondays 06:17 UTC                | Runs `scripts/check_configured_models.py`: every model ID configured in `api/config.py`, `api/providers/llama_guard.py`, `api/providers/claude.py` and `deployment/variables.tf` must exist in OpenRouter's public `/api/v1/models` list; the Claude default is checked against Anthropic's `/v1/models` only when the optional `ANTHROPIC_API_KEY` secret is set (otherwise reported as skipped). No completion calls. Exit 1 = ID missing (a model was retired: fix the config), exit 2 = network/HTTP error (re-run). |
| `dependency-majors-report.yml`  | 1 Jan/Apr/Jul/Oct, 07:23 UTC     | Runs `scripts/report_dependency_majors.py`: writes a table of direct dependencies in `api/requirements.txt` and `frontend/package.json` whose latest major is ahead to the job summary. Report only, never fails on "behind", no GitHub Issue: file follow-up stories from it. Dependabot keeps ignoring majors. |
| `acr-purge.yml`                 | Sundays 03:23 UTC                | BITB-372: `acr purge` via `az acr run` on `bible-backend` / `bible-frontend`: every tag newer than 14 days is kept, and of the older tags only the newest 10 per repo are kept (`--ago 14d --keep 10`); the rest and untagged manifests are deleted. The tags of the images running in the backend/frontend Container Apps are locked first (so purge skips them) and unlocked in an `if: always()` step; the job fails if it cannot read the deployed images. Manual runs have a `dry_run` input (default true); scheduled runs delete. Needs the `ARM_*` and `TELEGRAM_*` secrets; the deploy SPN (Contributor) already has the required ACR Tasks/metadata permissions. Side effect: `skip_build` rollbacks can only target tags newer than 14 days plus ~10 older ones. |

Run the first two locally: `python3 scripts/check_configured_models.py` (set `ANTHROPIC_API_KEY` to include
the Claude check) or `python3 scripts/report_dependency_majors.py`. Their tests are
`scripts/test_check_configured_models.py` and `scripts/test_report_dependency_majors.py`.

### Azure CLI command lint (BITB-374)

`az-lint.yml` checks every `az ...` command in the repo against the real Azure CLI, so a wrong flag
fails the PR instead of failing in production (BITB-372's `az acr show-usage --registry` was the
trigger). `scripts/check_az_commands.py` reads the `run:` scripts of the workflows and composite
actions, `scripts/**/*.sh`, `deployment/**/*.sh`, Terraform `local-exec` `command` strings and heredocs in
`deployment/**/*.tf` (`${...}` read as variables), the `Makefile` recipes and `["az", ...]` argv lists in
`scripts/**/*.py` and `api/**/*.py` (including the list passed to a module-local wrapper such as
`_az([...])` whose body is `["az", *args]`; a call with no literal command path is listed as a notice), then asks `az <command> --help` whether the command and each flag
exists. It needs no Azure login and no secrets. `az` inside `echo`, comments, heredocs and other prose
is ignored, and so is the content of `az acr run --cmd "..."`.

```bash
pip install azure-cli==2.93.0      # the version pinned in az-lint.yml (AZ_CLI_VERSION)
make az-lint                       # lint everything (exit 0 clean, 1 findings, 2 no az binary)
make az-lint ARGS="--list"         # print every extracted invocation, no az needed
make az-lint ARGS="--skip-missing-extensions"   # local run without the extensions installed
python3 scripts/check_az_commands.py .github/workflows/acr-purge.yml   # one file
python3 -m pytest scripts/test_check_az_commands.py -q                  # the linter's own tests
```

The pre-push hook `az-lint` runs the same check when `az` is on your PATH and prints a skip notice
otherwise; CI always runs it.

- **Add an extension.** If a command lives in an Azure CLI extension (with dynamic install off the CLI
  reports it as "misspelled", so the linter names the extension itself), add `name==version` to
  `scripts/az-extensions.txt` (versions: `src/index.json` in `Azure/azure-cli-extensions`) and, for a
  new extension command group, a prefix to `KNOWN_EXTENSION_PREFIXES` in the script. CI runs
  `az extension add` for each line. The CLI version is pinned once, in `az-lint.yml`.
- **Allowlist a finding.** Add `path:pattern  # reason` to `scripts/az-lint-allowlist.txt`: `path` is the
  repo-relative file, `pattern` a substring of the normalised command (`az acr show-usage --registry`).
  A reason is mandatory, and an entry that matches no finding fails the run as stale, so delete the
  entry when the command is fixed. Prefer fixing the command; allowlist only what cannot be fixed in the
  same PR, and file a story.
- **Wrapper functions** (`retry az ...`, `xargs az ...`, `bash -c "az ..."`) are not in command position
  and are not linted: call `az` directly where you can.

### Python version (BITB-304)

The backend's Python minor version lives in one place, `.python-version` (currently `3.14`).
`api/Dockerfile` must use the same `FROM python:X.Y-slim` tag (enforced by
`api/tests/test_runtime_alignment.py`), every workflow reads it with
`python-version-file: ".python-version"`, and the Black/Ruff/MyPy targets in `api/pyproject.toml`
match it. To bump Python, change `.python-version`, the Dockerfile and the `pyproject.toml`
targets together.

### Story-ID duplicate-claim check (BITB-235)

`story-id-check.yml` fails a PR that adds a `docs/BACKLOG_STORIES/BITB-NNN-*.md`
file whose number is already claimed on the base branch or added by another open
PR against the same base. Deleting the old story file in the same PR releases its
claim (renumbers are fine); adding two files with one number in a single PR is not.
When it fails, renumber this PR's story per `AGENTS.md` -> *Backlog Hygiene*: the
first claimant keeps the ID, the later PR renumbers before merging.

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

## Benchmark before you build on a performance claim

If a story's justification is performance, the claim must carry a
measurement at production scale (≥400,000 rows on `verses`, a real
1536-dimension embedding column, comparable hardware) before a second PR
builds on it. A dev-stack timing, or a reasoned argument about what the
query planner "should" do, is not a measurement.

**Cautionary example:** the August 2026 tsvector work (see the
[2026-08-17 tsvector migration outage
retrospective](RETROSPECTIVES/2026-08-17-tsvector-migration-outage.md))
assumed the main search path recomputed `to_tsvector` per row. That was
false — the query was already served by the expression index
`idx_verses_fts_simple`. Benchmarked afterwards at 403,856 rows, routing
`search_verses_text` through the new side table was 37% slower (0.105ms ->
0.144ms); only the `ts_rank` call sites won. The GIN index built on the
assumption was dropped for having no reader, and a planned Phase 2 was
cancelled outright. One hour of benchmarking after the fact could have been
spent before the migration that caused 45 minutes of downtime.

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
