---
id: BITB-361
status: todo
priority: P3
size: XS
created: 2026-11-25
depends_on: [BITB-274]
---

# BITB-361: Shrink the `test-scripts` Exclusion List to Zero

**Follow-up of:** BITB-274 (the catch-all `make test-scripts` job, `.github/workflows/scripts-tests.yml`).

## Problem

BITB-274 runs every `scripts/test_*.py` in one CI job, but two files are listed in
`SCRIPTS_TEST_EXCLUDE` (Makefile) and in the *Scripts tests catch-all* table in `docs/CONTRIBUTING.md`:

1. `scripts/test_make_targets.py` is red on main (3 failures: missing-target references such as
   `golden-set-eval`, `check-llm-budget`, `az-logs`, and a stale `docs/MAKE_TARGET_AUDIT.md`). BITB-325 /
   PR #1302 fixes this. Until it merges, the file runs only via `make test-makefile`.
2. `scripts/test_openrouter_fallback.py` is a manual live script, not a pytest module. At import it calls
   `sys.exit(1)` without `OPENROUTER_API_KEY` and then calls the real API. Its `test_` prefix makes it look like
   an offline test.

## Acceptance criteria

- [ ] After BITB-325 merges, remove `scripts/test_make_targets.py` from `SCRIPTS_TEST_EXCLUDE` and the
      CONTRIBUTING table, and regenerate `docs/MAKE_TARGET_AUDIT.md`
      (`python3 scripts/audit_make_targets.py --write`). It now also needs the `test-scripts` row.
- [ ] Rename `scripts/test_openrouter_fallback.py` to a non-test name (e.g. `scripts/probe_openrouter_fallback.py`),
      update every reference (repo-wide grep), and drop its exclusion
- [ ] `SCRIPTS_TEST_EXCLUDE` is empty, and `scripts/test_scripts_tests_guard.py` still passes
