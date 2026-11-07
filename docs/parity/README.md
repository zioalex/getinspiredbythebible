# Parity artifacts

Home of the cross-client parity knowledge graph (BITB-260). Stage 1 (BITB-261) adds the
committed **OpenAPI contract**; later stages add the capability x client registry (BITB-262)
and an on-demand Neo4j view (BITB-263).

## `openapi.json` - the API contract

`docs/parity/openapi.json` is the FastAPI app's OpenAPI schema (`app.openapi()` from
`api/main.py`), committed so that web, Android and future clients can diff against the exact
request/response shapes the backend serves. Keys are sorted, so a diff shows only real
changes. It is **generated - never hand-edit it.** It carries no secrets: `/openapi.json` is
already a public, unauthenticated path (see `TURNSTILE_SKIP_PATHS` in `docs/SECURITY.md`).

### Zero to running (fresh clone)

No database, no LLM or embedding credentials, no network are needed - only the backend
Python dependencies.

```bash
make setup-dev          # once: creates .venv and installs api/requirements*.txt
make parity-export      # regenerate docs/parity/openapi.json
make parity-check       # verify it is current (exit 1 + diff if stale; writes nothing)
```

Without make (what the targets run, and what CI runs):

```bash
pip install -r api/requirements.txt
python scripts/export_openapi.py            # write
python scripts/export_openapi.py --check    # verify
```

The script sets the one environment variable `Settings()` insists on
(a dummy `DATABASE_URL` that is never connected to; see the script), drops every other
environment variable except `PATH`/`HOME`/locale/Python ones (so a shell's `MAX_MESSAGE_LENGTH` or
`LLM_PROVIDER` cannot change the output), and runs from an empty working directory so
no `.env` file can leak into the output. You do not need to export anything yourself.
Verified offline with `env -i PATH=... python scripts/export_openapi.py`.

### When CI says the artifact is stale

The `parity-ci.yml` **stale-check** job fails a PR whose API changes did not regenerate the
artifact. Fix: run `make parity-export` and commit the updated `docs/parity/openapi.json`.

## Breaking-change policy (oasdiff)

The **breaking-diff** job in `.github/workflows/parity-ci.yml` runs
[oasdiff](https://github.com/oasdiff/oasdiff) (pinned docker image `tufin/oasdiff`, no
dependency added to `api/`) comparing the PR's artifact with the base branch's, and writes
the *breaking changes* and *full changelog* to the job summary.

- **Current policy: warn and report, never fail.** The baseline is new and not yet trusted.
- **Flip condition:** once several PRs have shown the report is accurate and free of false
  positives, make it a hard gate by dropping `continue-on-error`/`|| true` and running
  `oasdiff breaking --fail-on ERR`. That is a deliberate decision to be recorded here (date,
  PR) when taken.

## Tests

`python -m pytest scripts/test_export_openapi.py` - ordering determinism, `--check`
pass/fail paths, and (when backend deps are installed) that the committed artifact is current.
