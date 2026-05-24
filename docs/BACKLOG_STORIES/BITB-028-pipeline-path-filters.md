# BITB-028: Skip Irrelevant CI Pipelines on Doc-Only / Story-Only Changes

**Status:** ✅ Done (test_update.yml already has path filters added in PR #577 on 2026-05-17; verified 2026-05-24)

## User Story

As a contributor, I want CI to skip pipelines that have nothing to do with my change (e.g. backend + frontend + integration tests when I only added a story under `docs/BACKLOG_STORIES/`), so that PRs that touch only documentation don't burn ~15 minutes of runner time and don't show a wall of unrelated failed/queued checks.

## Problem

After scanning all workflows under `.github/workflows/`, the picture is mixed:

| Workflow                                                   | Path filters?                                                       | Behaviour on a doc-only PR                                                                                                                      |
| ---------------------------------------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `android-ci.yml`                                           | ✅ `android/**` + own file                                          | correctly skipped                                                                                                                               |
| `azure-deploy.yml`                                         | ✅ `api/**`, `frontend/**`, `scripts/**`, `deployment/**`, own file | correctly skipped                                                                                                                               |
| `test_update.yml` (Backend + Frontend + Integration tests) | ❌ none                                                             | **runs everything** — backend pytest, frontend Vitest matrix on Node 20 + 22, plus a full docker-compose integration suite with Postgres/Ollama |
| `pre-commit.yml`                                           | ❌ none                                                             | runs (acceptable — it lints `docs/**` too)                                                                                                      |
| `commitlint.yml`                                           | ❌ none                                                             | runs (intentional — must lint commit messages on every PR)                                                                                      |
| `release-please.yml`                                       | n/a — push to main only                                             | not affected                                                                                                                                    |
| `prod-monitor.yml`                                         | n/a — schedule only                                                 | not affected                                                                                                                                    |
| `android-publish.yml`, `android-debug.yml`                 | `workflow_dispatch` only                                            | not affected                                                                                                                                    |

So the real waste is **`test_update.yml`**. A PR that only adds a markdown file under `docs/BACKLOG_STORIES/` (the most common "low-risk" change) currently spins up:

- a Postgres service container + backend pytest run,
- a Node 20 _and_ Node 22 frontend test matrix (two parallel jobs),
- a full docker-compose integration test that pulls Ollama, builds the API and frontend images, and runs end-to-end checks.

That's ~10–15 runner-minutes for a change that cannot affect any of those code paths.

The user-reported symptom — "all the android tests run when only a story has been created" — is most likely conflating the heavy `test_update.yml` run with `android-ci.yml`. We should both verify the Android side is genuinely path-filtered (it is) and fix the bigger leak in `test_update.yml`.

## Proposed Changes

### 1. Add path filters to `test_update.yml`

Restrict trigger paths to the directories the workflow actually exercises:

```yaml
on:
  pull_request:
    branches: [main, "feature/**"]
    paths:
      - "api/**"
      - "frontend/**"
      - "docker-compose*.yml"
      - "scripts/**"
      - ".github/workflows/test_update.yml"
  push:
    branches: [main, feature/initial-implementation]
    paths:
      - "api/**"
      - "frontend/**"
      - "docker-compose*.yml"
      - "scripts/**"
      - ".github/workflows/test_update.yml"
```

Notes:

- `commitlint.config.cjs`, `release-please-config.json`, repo-level `*.md` files, and anything under `docs/`, `android/`, `multiple_embeddings/`, `data/`, `infra/` will then no longer trigger backend/frontend/integration tests.
- Keep the workflow's own filename in the path list so a CI tweak still runs the suite once.
- Verify by opening a draft PR that touches only `docs/BACKLOG_STORIES/foo.md` and confirming `test_update.yml` is skipped while `commitlint.yml` and `pre-commit.yml` still run.

### 2. Split frontend-only vs backend-only triggers (optional, follow-up)

The current `test_update.yml` is one workflow with three jobs. A frontend-only change still kicks off backend pytest (and vice-versa). A cleaner split — either two `paths` lists guarded per-job via `dorny/paths-filter`, or two separate workflow files — would let frontend-only PRs skip backend pytest and integration tests.

If we go this route, mirror the pattern already used in `azure-deploy.yml` (line ~156, `dorny/paths-filter@v4` with named filters) so we don't introduce a new technique.

### 3. Add a "required-checks" awareness section to `docs/CONTRIBUTING.md`

If a PR's files match no path filter for a given workflow, GitHub records the workflow as **skipped**, not **success**. Branch-protection rules that require `Backend API Tests` to pass will then block doc-only PRs forever.

Two options, document both:

- **Recommended**: switch the required check to `Pre-Commit Hooks` (which always runs) and treat backend/frontend tests as advisory-on-skip. Document that a blocked check from a doc-only PR can be auto-resolved by re-requesting review.
- Or use a tiny "required-status" aggregator job (`if: always()` + sums `needs.*.result`) that converts a skipped backend-tests job into a passing check for branch protection.

### 4. Re-confirm Android path filters work

Open a doc-only PR and confirm `android-ci.yml` shows as skipped (not as a failed check). The current filter `paths: ["android/**", ".github/workflows/android-ci.yml"]` should already do this — this is a verification step, not a code change.

## Acceptance Criteria

- [ ] A PR whose only change is `docs/BACKLOG_STORIES/<foo>.md` does **not** trigger `test_update.yml` (backend, frontend matrix, integration tests).
- [ ] A PR whose only change is under `docs/` does **not** trigger `android-ci.yml` (already true — verified, not changed).
- [ ] A PR that modifies `api/**` still runs backend pytest _and_ the integration tests.
- [ ] A PR that modifies `frontend/**` still runs the frontend matrix _and_ the integration tests (because the integration suite covers both).
- [ ] Branch-protection required-status configuration is documented so that doc-only PRs are not blocked by skipped jobs (see "Required-checks awareness" section in `docs/CONTRIBUTING.md`).
- [ ] `pre-commit.yml` and `commitlint.yml` continue to run on every PR (no regression in linting).

## Files to Modify / Add

| File                                                      | Change                                                   |
| --------------------------------------------------------- | -------------------------------------------------------- |
| `.github/workflows/test_update.yml`                       | Add `paths:` lists to `pull_request` and `push` triggers |
| `docs/CONTRIBUTING.md` (or new section)                   | Document branch-protection behaviour with skipped checks |
| (Optional, follow-up) `.github/workflows/test_update.yml` | Per-job path filters via `dorny/paths-filter`            |

## Out of Scope

- Reorganising the integration test stack itself (keeping the docker-compose run as-is).
- Cost/runtime improvements to backend/frontend tests (separate optimisation work).
- Enabling Android instrumented tests on more PR types.

## Priority

P2 – Medium (CI cost + signal-to-noise; no broken functionality).

## Size

S (< 4 hours) — primarily a YAML edit + a documentation note + a verification PR.

## Assignee

devops / repo-maintainer
