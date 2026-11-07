# BITB-268: Make-Target Audit Fails on Main — Dangling `golden-set-eval` References

**Status:** 🎯 Todo
**Priority:** P3
**Size:** S
**Created:** 2026-11-07
**Found by:** BITB-261 verification (PR #1251)

## Problem

On `origin/main`, three tests in `scripts/test_make_targets.py` fail
(`test_docs_reference_only_existing_targets`, `test_report_is_current`,
`test_frontend_and_hook_targets`). Docs (e.g. `docs/BITB-150-postgres-cost-analysis.md`) reference
`make golden-set-eval`, which is not a Makefile target. Regenerating `docs/MAKE_TARGET_AUDIT.md` adds
self-referencing lines, so `audit_make_targets.py --check` never settles.

## Acceptance Criteria

- [ ] No doc references a non-existent make target (add the target or fix the references)
- [ ] The audit report no longer lists itself as a dangling-reference source; `--write` is idempotent
- [ ] `pytest scripts/test_make_targets.py` is green
