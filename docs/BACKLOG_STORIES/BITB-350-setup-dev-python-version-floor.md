---
id: BITB-350
status: todo
priority: P2
size: S
created: 2026-11-19
---

# BITB-350: `make venv` Builds an Unusable Virtualenv Wherever `python3` Is Older Than 3.12

## Bug report

On a machine (or agent sandbox) whose default `python3` predates 3.12, `make venv` / `make setup-dev`
silently produce a virtualenv the project cannot use, and the failure surfaces much later as a
confusing pip resolution error rather than "wrong Python".

**Reproduced 2026-11-19** in a cloud agent session: `/usr/bin/python3` is 3.11.18 (3.12 and 3.13 are
installed but not default; 3.14 is absent), and the repo `.venv` was Python 3.11.18 with no
dependencies installed. `pip install -r api/requirements-dev.txt` cannot resolve, because
`numpy==2.5.4` needs 3.12 or newer. The session had to build a 3.14 venv by hand with `uv` before it
could run the backend suite at all, and `make parity-check` failed with
`ModuleNotFoundError: No module named 'fastapi'` for the same reason.

**Root cause.** `Makefile:51` sets `PYTHON_VERSION := python3` — whatever `python3` resolves to — and
the `venv` target only recreates the environment when the interpreter or `pip` is *missing* or the
directory is owned by another uid. It never checks the interpreter's **version**. Meanwhile
`api/pyproject.toml` declares `requires-python = ">=3.12"` and sets mypy's `python_version = "3.14"`,
and CI runs the production version (BITB-304), so the Makefile is the only place with no floor.

## Requirements

- `make venv` fails fast with an actionable message when the chosen interpreter is below the
  `requires-python` floor — naming the version found, the version needed, and how to override.
- Allow an override, e.g. `make venv PYTHON_VERSION=python3.14`, and document it.
- Prefer the newest suitable interpreter on `PATH` (`python3.14`, then `3.13`, `3.12`) instead of
  hardcoding bare `python3`.
- Treat an existing `.venv` whose interpreter is below the floor as stale and recreate it, the same
  way a different-uid `.venv` is already recreated.
- Read the floor from `api/pyproject.toml` rather than duplicating a version literal in the Makefile.

## Tests

- `scripts/` (or `make test-makefile`, BITB-325) coverage: a fake `python3` below the floor on `PATH`
  makes `make venv` exit non-zero with the actionable message.
- An existing `.venv` below the floor is recreated rather than reported as "already exists".

## Acceptance criteria

- [ ] `make venv` cannot produce a virtualenv below `requires-python`
- [ ] The error names the found version, the required version and the override
- [ ] `docs/LOCAL_DEVELOPMENT.md` documents the interpreter requirement and the override
- [ ] Covered by the Makefile test tier, not only by hand

## Related

BITB-304 (align the Python runtime in CI), BITB-325 (`make test-makefile` green on main).
