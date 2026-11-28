---
id: BITB-376
status: todo
priority: P3
kind: chore
size: S
created: 2026-11-28
---

# BITB-376: `make test-makefile` fails on main (three pre-existing failures)

## Problem

Found while adding the `az-lint` target for BITB-374 (every new Makefile target must be classified in
`scripts/make_target_audit.json`). On a clean checkout of `main`, `python3 -m unittest scripts.test_make_targets`
fails three tests and `python3 scripts/audit_make_targets.py --check` exits non-zero:

- `InventoryTests.test_report_is_current`: `docs/MAKE_TARGET_AUDIT.md` is stale (`--write` regenerates it);
- `InventoryTests.test_docs_reference_only_existing_targets`: `scripts/az-logs.sh` (lines 2, 77, 95) refers to
  `make az-logs`, which is not a target, and `docs/backlog/CHANGELOG-archive.md:43` refers to
  `make check-llm-budget` and `docs/BITB-150-postgres-cost-analysis.md:182,269` to `make golden-set-eval`,
  neither of which exists any more;
- `PythonTargetTests.test_frontend_and_hook_targets`.

No CI job runs `make test-makefile`, so nothing flags this. Regenerating the report is not a
quick fix: `audit_make_targets.py --write` is not idempotent, because the report lists the
dangling `make ...` references including the ones that appear in the report itself, so a second
`--write` produces a different file and `--check` stays "stale" until those references are fixed.
On `main` a regeneration changes about 20 lines; on the BITB-374 branch it changes 289 because the
new `az-lint` target shifts the Makefile line numbers the report cites. BITB-374 therefore added
its target to `scripts/make_target_audit.json` but did not regenerate the report (the failures are
identical with and without it).

## Requirements

- Fix or delete the stale references (`az-logs`, `check-llm-budget`, `golden-set-eval`), regenerate `docs/MAKE_TARGET_AUDIT.md`, repair
  `test_frontend_and_hook_targets`.
- Decide whether `make test-makefile` should run in CI (a path-filtered job on `Makefile`,
  `scripts/audit_make_targets.py`, `scripts/make_target_audit.json`) so it cannot rot again.

## Acceptance criteria

- [ ] `make test-makefile` passes on a clean checkout.
- [ ] A CI job (or a recorded decision not to add one) keeps it green.
