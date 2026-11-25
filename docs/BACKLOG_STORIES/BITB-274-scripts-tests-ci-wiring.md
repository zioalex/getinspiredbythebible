---
id: BITB-274
status: in-review
priority: P2
size: S
rank: 80
created: 2026-11-08
follow_ups: [BITB-361]
---

# BITB-274: Wire All scripts/test_*.py Into CI — One Job, Not One-off Wiring

**Follow-up to:** BITB-261 (its verifier found the pattern gap: scripts tests are wired into CI one-by-one, so a new one can silently ship unexecuted)

## User Story

**As the** maintainer, **I want** every `scripts/test_*.py` in the repo to execute in CI automatically,
**so that** a test file added today can never again ship as dead code (BITB-261's `test_export_openapi.py`
initially existed but ran nowhere — caught only by independent verification).

## Problem

Scripts tests are invoked ad-hoc: `test_generate_localized_book_map.py` is individually named inside the
backend-tests job; the story-ID checker tests run under their own check; nothing guarantees a newly added
`scripts/test_*.py` runs anywhere. Today there are ~15 `scripts/test_*.py` files — audit which actually
execute in CI.

## Requirements

1. Audit: list every `scripts/test_*.py` and whether each runs in CI today.
2. Add a `test-scripts` Make target running the whole family with plain `python -m pytest scripts/test_*.py`
   (each file must be independently runnable offline; flag any that need DB/network and mark/skip accordingly).
3. Wire it into CI: a step in `test_update.yml` (or the parity workflow for parity-related ones) triggered on
   any PR touching `scripts/**` — path filters must cover every test file's subject files.
4. Exclude nothing silently: any file that cannot run in CI must be listed in the README with the reason.

## Acceptance Criteria

- [x] Audit table in the PR: file → runs-in-CI-today (yes/no) → runs after this PR
- [x] `make test-scripts` exists and runs the family
- [x] CI executes every `scripts/test_*.py` (or an explicitly documented exclusion)
- [x] A future `scripts/test_foo.py` added with no other CI edits still runs (path filter on `scripts/**`)

## Out of Scope

Changing any test's logic; the oasdiff container-path fix (BITB-273, PR #1255).

**Related:** BITB-261 (context), BITB-273 (parallel parity-CI fix), BITB-277 (feeds the registry).

## Audit (2026-11-25) and result

Workflows: `test_update` = test_update.yml, `opencode-ci`, `parity-ci`, `backlog`, `story-id`
= story-id-check, `auto-update` = auto-update-prs-ci, `secrets` = secrets-expiry-check,
`models` = model-existence-probe (scheduled), `majors` = dependency-majors-report (scheduled).
`catch-all` = the new `scripts-tests.yml` (`make test-scripts`).

| File | Runs in PR CI today | Runs after this PR |
| ---- | ------------------- | ------------------ |
| test_auto_update_prs.py | yes (auto-update) | yes (+ catch-all) |
| test_az_logs.py | no | yes (catch-all; also `make test-makefile`) |
| test_backlog.py | yes (backlog) | yes (+ catch-all) |
| test_check_configured_models.py | scheduled only (models) | yes (catch-all) |
| test_check_crisis_resources.py | scheduled only (crisis-resources-staleness) | yes (catch-all) |
| test_check_secrets_inventory.py | yes (secrets) | yes (+ catch-all) |
| test_check_story_ids.py | yes (story-id) | yes (+ catch-all) |
| test_cluster_triage.py | yes (opencode-ci) | yes (+ catch-all) |
| test_dns_watchdog.py | yes (opencode-ci) | yes (+ catch-all) |
| test_export_openapi.py | yes (parity-ci) | yes (+ catch-all) |
| test_export_retrieval_misses.py | no (importorskip sqlalchemy) | yes (catch-all; api deps installed) |
| test_generate_localized_book_map.py | yes (test_update) | yes (+ catch-all) |
| test_generate_opencode_config.py | yes (opencode-ci) | yes (+ catch-all) |
| test_kubeopencode_manifests.py | yes (opencode-ci) | yes (+ catch-all) |
| test_kubeopencode_netpol.py | yes (opencode-ci) | yes (+ catch-all) |
| test_make_targets.py | no | excluded: red on main until BITB-325 / PR #1302 merges (still `make test-makefile`) |
| test_migrate_backlog_frontmatter.py | yes (backlog) | yes (+ catch-all) |
| test_openrouter_fallback.py | no | excluded: manual live script needing `OPENROUTER_API_KEY` |
| test_report_dependency_majors.py | scheduled only (majors) | yes (catch-all) |
| test_run_search_eval_probe.py | no | yes (catch-all; api deps installed) |

Implementation: `make test-scripts` (Makefile, `SCRIPTS_TEST_EXCLUDE`), `.github/workflows/scripts-tests.yml`
(paths `scripts/**`, `Makefile`), guard test `scripts/test_scripts_tests_guard.py`, docs in
`docs/CONTRIBUTING.md`.

## Follow-ups

- BITB-361: shrink the exclusion list to zero.
- When PR #1302 (BITB-325) merges: drop `scripts/test_make_targets.py` from `SCRIPTS_TEST_EXCLUDE` and the
  CONTRIBUTING table row, and regenerate `docs/MAKE_TARGET_AUDIT.md` (`python3 scripts/audit_make_targets.py --write`;
  it is already stale on main and now also needs the `test-scripts` row).
