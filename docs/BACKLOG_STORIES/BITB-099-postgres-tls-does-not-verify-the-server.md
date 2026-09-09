# BITB-099: Production Postgres Connections Encrypt but Do Not Authenticate the Server

**Status:** 🚧 In Progress — decision recorded below, implementation on this PR
**Priority:** P2 — a real gap against a public endpoint, but not an active incident
**Size:** S–M (config plus a CA bundle; the work is in getting it right for every caller)
**Created:** 2026-08-18
**Prompted by:** noticed while walking an operator through connecting to production during BITB-096

## Decision (2026-09-09)

**Move to `verify-full`, using the Python/OS default CA trust store — no vendored CA bundle.**

Both `get_async_database_url()` and `get_migration_connection_params()` already special-case only
`sslmode == "require"` to force `check_hostname = False` / `verify_mode = CERT_NONE`; for
`verify-ca`/`verify-full` they already fall through unchanged to `ssl.create_default_context()`'s
own default (`check_hostname=True`, `verify_mode=CERT_REQUIRED`, backed by the platform's default
CA trust store — `SSLContext.load_default_certs()`/certifi on the runners this repo's CI and
Azure Container Apps use). Azure Database for PostgreSQL's server certificate chains to a public
commercial root (Microsoft RSA Root Certificate Authority 2017 / DigiCert) that ships in every
standard OS/Python trust store, so no bundle needs to be vendored or pinned, and there is no
rotation obligation to own beyond keeping the runner/container base image's `ca-certificates`
package current (already an implicit dependency of every other outbound HTTPS call this app
makes, e.g. to the LLM providers).

So the fix is **not** a change to the SSL-context-building logic in either Python helper — it is
changing every DSN that currently asks for `sslmode=require` (the actual production connections:
`deployment/main.tf`'s Container App env var, every `azure-deploy.yml` job, `search-eval-full.yml`,
and the operator-facing runbook/templates) to ask for `sslmode=verify-full` instead, plus a
regression test that pins `verify-full`/`verify-ca` to `CERT_REQUIRED`/`check_hostname=True` so
this can't silently regress, and documenting the decision in code. `sslmode=require`'s own
behavior (`CERT_NONE`) is left unchanged — it's the correct, standard libpq meaning of that mode,
still valid for anyone who deliberately opts into it — only the *default we hand production* moves
to `verify-full`.

## User Story

**As** the operator of a Postgres server with `public_network_access_enabled = true`, **I want**
the application and migration connections to verify the server's certificate, **so that** TLS is
protecting against an active attacker and not only a passive one.

## The Finding

Every connection path resolves `sslmode=require` to an SSL context that explicitly disables
verification. In `api/scripture/database.py::get_async_database_url()`:

```python
if sslmode == "require":
    # Don't verify certificate (like psycopg2's sslmode=require)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
```

`scripts/migrations/utils.py::get_migration_connection_params()` does the same, deliberately
mirroring it. Confirmed by evaluating both functions against the production URL form: each
returns an `SSLContext` with `verify_mode = 0` (`CERT_NONE`).

So traffic to `bible-app-db-mb0172.postgres.database.azure.com` is **encrypted but
unauthenticated**. The client will accept any certificate, from any server, for any hostname. That
defeats TLS against an active man-in-the-middle while still defeating passive eavesdropping.

The server is reachable from the internet — `deployment/main.tf` sets
`public_network_access_enabled = true`, with a firewall rule allowing Azure services
(`0.0.0.0`) and optionally one client IP.

## This Is Deliberate, Which Is Why It Needs a Decision Rather Than a Fix

This is not a bug report. `sslmode=require` means exactly this in libpq — encrypt, do not verify —
and BITB-016 chose the behaviour knowingly, documenting it as matching psycopg2. The comment in
the code says so.

What is missing is anyone having decided it is *acceptable*. It is recorded as an implementation
detail of "make SSL work", never as a security posture with a rationale. This story exists to
force that choice and write the answer down, whichever way it goes.

Two defensible outcomes:

**Move to `verify-full`.** Load the DigiCert Global Root CA that Azure Database for PostgreSQL
presents, set `check_hostname = True` and `verify_mode = CERT_REQUIRED`. Costs a bundled CA file
and a rotation obligation when Azure changes roots — which they have done before, and which
breaks every client at once if unmanaged.

**Keep `require`, and record why.** Defensible if the threat model treats the Azure backbone
between Container Apps and Flexible Server as trusted. That argument is much weaker for the
operator's laptop connecting over the public internet, which is exactly what the BITB-096 runbook
had someone do.

A middle position worth considering: `verify-full` for application and CI connections, `require`
tolerated for ad-hoc human sessions, with the asymmetry stated rather than accidental.

## Scope

Every caller has to move together, or the ones left behind fail confusingly at connect time.
Rescanned 2026-09-09 — the original list of five undercounted it; every DSN below targets the
real production host and needs `sslmode=require` → `sslmode=verify-full`:

- `deployment/main.tf` — builds the Container App's own `DATABASE_URL` env var. **This is the
  running production application's actual connection string**, not caught in the original scope.
- `deployment/outputs.tf` — the Terraform output template handed to operators
- Every job in `.github/workflows/azure-deploy.yml` that exports `DATABASE_URL` (migrations, load,
  embeddings, verse-topics, smoke) — nine occurrences of `?sslmode=require`
- `.github/workflows/search-eval-full.yml` — the nightly prod-read job (BITB-101)
- `.env.production.example` and `docs/HOW-TO-BACKUP-RESTORE-DATABASE.md` — operator-facing
  templates and runbook DSNs
- `api/scripture/database.py::get_async_database_url()` — the application (no logic change; see
  Decision above)
- `scripts/migrations/utils.py::get_migration_connection_params()` — the legacy runner and
  `scripts/backfill_verse_tsv.py` (no logic change)
- `api/alembic/env.py` — derives from `get_async_database_url()`, so it follows automatically
- `docs/MIGRATION_GUIDELINES.md` — living guideline text that documents the DSN form to use

## Acceptance Criteria

- [ ] A decision recorded in the story and in `api/scripture/database.py`'s docstring: verify, or
      accept `require` with a stated threat model
- [ ] If verifying: CA bundle vendored or fetched reproducibly, `check_hostname = True`,
      `verify_mode = CERT_REQUIRED`, and a documented rotation plan
- [ ] All five call paths above move together, proven by connecting from CI and from a laptop
- [ ] A test asserting the resulting `SSLContext` has the intended `verify_mode`, so this cannot
      silently regress to `CERT_NONE` the way it silently persisted
- [ ] BITB-016 cross-referenced, since it is where the current behaviour was chosen

## Related

- BITB-016 — chose the current behaviour; documents `CERT_NONE` as intended
- BITB-096 — the runbook that had an operator connect to production over the public internet
- `api/scripture/database.py`, `scripts/migrations/utils.py`, `deployment/main.tf`
