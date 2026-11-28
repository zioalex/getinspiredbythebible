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
  `make check-llm-budget`, which no longer exists;
- `PythonTargetTests.test_frontend_and_hook_targets`.

No CI job runs `make test-makefile`, so nothing flags this. BITB-374 added its target to the JSON
classification but deliberately did not regenerate the report, to keep unrelated churn (289 changed
lines) out of that PR.

## Requirements

- Fix or delete the stale references, regenerate `docs/MAKE_TARGET_AUDIT.md`, repair
  `test_frontend_and_hook_targets`.
- Decide whether `make test-makefile` should run in CI (a path-filtered job on `Makefile`,
  `scripts/audit_make_targets.py`, `scripts/make_target_audit.json`) so it cannot rot again.

## Acceptance criteria

- [ ] `make test-makefile` passes on a clean checkout.
- [ ] A CI job (or a recorded decision not to add one) keeps it green.
