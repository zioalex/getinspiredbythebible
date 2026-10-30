# BITB-261: Parity KG Stage 1 — Committed OpenAPI Contract Artifact & Breaking-Change CI

**Status:** 🎯 Todo — dispatchable immediately
**Priority:** P2
**Size:** M
**Created:** 2026-10-30
**Part of:** BITB-260 — Stage 1 of 3 (contracts layer)

## User Story

**As the** maintainer of multiple clients of the same backend (web, Android, iOS-to-come),
**I want** the FastAPI app's OpenAPI contract exported as a committed, machine-diffable artifact,
with CI that fails when the artifact is stale and reports breaking changes per PR, **so that** no
client can silently drift from the backend's actual request/response shapes.

## Requirements

1. **`scripts/export_openapi.py`** (new):
   - Imports the FastAPI app (`api/main.py:app`) **offline** — no live database, no LLM keys.
     If `Settings()` validation requires env vars, use the same defaults the offline test suite
     uses; the implementer verifies the exact invocation and documents it. This is the story's
     main technical risk — prove it before building anything else.
   - Writes `docs/parity/openapi.json` with deterministic ordering (sorted paths/schemas) so a
     diff is meaningful rather than churn.
   - `--check` mode: regenerates in memory and exits non-zero when the committed artifact differs
     — the same pattern as `scripts/generate_localized_book_map.py --check`.
2. **CI** (a new `parity-ci.yml` or a job in `test_update.yml` — implementer's choice, documented
   in the workflow file):
   - Stale-artifact check on every PR: fail.
   - **oasdiff** breaking-change report against the PR base, posted as a PR comment or job
     summary. **Policy: warn-and-report initially, not fail** — flipping to a hard gate is a
     deliberate later decision recorded in `docs/parity/README.md` once the baseline is trusted.
     oasdiff runs via its docker image or a pinned binary (it is a Go tool; do not add an npm
     dependency to `api/`).
   - Note: `/openapi.json` is already a public unauthenticated path (see `TURNSTILE_SKIP_PATHS`
     in `docs/SECURITY.md`), so the artifact carries no secrets.
3. **Tests:** `scripts/test_export_openapi.py` — offline, mirroring the `scripts/test_*.py`
   convention; cover ordering determinism and the `--check` pass/fail paths.
4. **Makefile:** `parity-export` and `parity-check` targets, registered per the make-target
   audit convention (`scripts/make_target_audit.json`).
5. **Docs:** `docs/parity/README.md` (new directory home) — zero-to-running for a fresh clone:
   what the artifact is, how to regenerate it, and the oasdiff warn/fail policy. Per the AGENTS.md
   documentation-completeness rule, script and docs land in the same PR.

## Acceptance Criteria

- [ ] `make parity-export` regenerates `docs/parity/openapi.json` offline on a fresh clone (no DB,
      no LLM credentials)
- [ ] The `--check` mode fails CI when the artifact is stale, and the README documents
      regeneration as the fix
- [ ] PRs receive an oasdiff breaking-change report (warning-level; policy and its flip condition
      documented in `docs/parity/README.md`)
- [ ] Offline unit tests for the script pass; `make pre-commit` is clean
- [ ] The diff touches only `scripts/`, `docs/`, `.github/`, and `Makefile` (+ its audit json) —
      no application behavior changes

## Out of Scope

- openapi-generated clients (follow-up candidate once this lands)
- Pact consumer/provider verification (candidate, filed when stage 2 lands)
- The parity registry itself (BITB-262)
- Making oasdiff a hard CI gate (deliberate later decision)
- Spectral spec linting (candidate follow-up; keep this stage minimal)

## Files Likely to Change

| Path | Change |
|---|---|
| `scripts/export_openapi.py` | New — offline OpenAPI export + `--check` |
| `scripts/test_export_openapi.py` | New — offline tests |
| `docs/parity/openapi.json` | New — the committed contract artifact |
| `docs/parity/README.md` | New — zero-to-running + policy record |
| `.github/workflows/parity-ci.yml` (or `test_update.yml`) | New/updated — stale check + oasdiff report |
| `Makefile` + `scripts/make_target_audit.json` | `parity-export` / `parity-check` |

## Related

- **BITB-260** — the decision record this implements (stage 1 of 3)
- **BITB-262 / BITB-263** — the next stages
- **BITB-086 / BITB-109** — the citations contract this artifact will formally capture
