# BITB-274: Wire All scripts/test_*.py Into CI — One Job, Not One-off Wiring

**Status:** 🎯 Todo
**Priority:** P2
**Size:** S
**Created:** 2026-11-08
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

- [ ] Audit table in the PR: file → runs-in-CI-today (yes/no) → runs after this PR
- [ ] `make test-scripts` exists and runs the family
- [ ] CI executes every `scripts/test_*.py` (or an explicitly documented exclusion)
- [ ] A future `scripts/test_foo.py` added with no other CI edits still runs (path filter on `scripts/**`)

## Out of Scope

Changing any test's logic; the oasdiff container-path fix (BITB-273, PR #1255).

**Related:** BITB-261 (context), BITB-273 (parallel parity-CI fix), BITB-277 (feeds the registry).
