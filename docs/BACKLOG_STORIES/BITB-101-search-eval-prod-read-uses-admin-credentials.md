# BITB-101: The Nightly Prod-Read Path Holds Admin Credentials and Nothing Enforces "Read-Only"

**Status:** 🎯 Todo
**Priority:** P1 — a recurring, unattended, ungated path into the production database holding the
Postgres admin role
**Size:** M (a Terraform-provisioned role + grants + secret plumbing + a workflow swap + one guard test)
**Created:** 2026-08-21
**Prompted by:** PR #968 (BITB-051 P4a), which introduces the first automated recurring prod-database
access path in this repo that is not a deploy

## User Story

**As** the operator of a single-maintainer production service, **I want** the nightly search-eval
read against production to authenticate as a role that is *incapable* of writing, **so that** a bug,
a dependency compromise, or a future edit to the harness cannot damage or exfiltrate production data
using admin rights it never needed.

## Why This Exists

PR #968 adds `.github/workflows/search-eval-full.yml`. Its `eval-prod` job is genuinely read-only in
behaviour — it runs `scripts/run_search_eval.py --run --json`, which issues `SELECT`s and nothing
else. The problem is not what it does. The problem is what it *could* do, and what nothing stops it
from doing.

Evidence is from `.github/workflows/search-eval-full.yml` as of PR #968's head
(`87d29dd`), and `.github/workflows/azure-deploy.yml` on `main` as of `073b7f0`.

### 1. It authenticates as the Postgres admin role

```yaml
# search-eval-full.yml, "Run eval against prod (read-only)"
env:
  DB_USER: ${{ secrets.TF_VAR_DB_ADMIN_USERNAME }}
  DB_PASS: ${{ secrets.TF_VAR_DB_ADMIN_PASSWORD }}
run: |
  export DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:5432/${DB_NAME}?sslmode=require"
```

These are the same credentials `run-migrations` uses to execute DDL. There is no separate read-only
role in this project today, so the workflow reaches for the only credentials that exist.

**"Read-only" is therefore a property of the code's behaviour, not of the grant.** It holds exactly
as long as every future edit to `run_search_eval.py`, `api/search_eval/runner.py`, and everything
they import continues to only ever `SELECT`. Nothing in the database enforces it. The comment in the
step name says "read-only"; the database has never been told.

### 2. Nothing gates it

`grep -n 'environment:' .github/workflows/search-eval-full.yml` returns nothing. Compare
`azure-deploy.yml`, where both `deploy` and `run-migrations` carry `environment: production` and
stop for manual approval before touching prod.

So this path is:

- **unattended** — `schedule: "23 4 * * *"`, nightly, forever, with nobody watching;
- **ungated** — no approval, no reviewer, no environment;
- **manually triggerable** — `workflow_dispatch` by anyone with write access;
- **secret-exposed at repo scope** — because the credentials are bare repository secrets rather than
  environment-scoped ones, they are readable by *any* workflow in the repo, not just this one.

Every other production-touching job in this repository stops at a gate. This one does not, and it is
the one that runs most often.

### 3. It widens the blast radius of a dependency compromise

The job runs `pip install -r api/requirements.txt` and then connects to production as admin. A
compromised transitive dependency therefore gets prod admin, nightly, with no human present.

`run-migrations` installs the same requirements file and holds the same credentials — this is not a
new *class* of exposure. What changes is frequency and supervision: `run-migrations` fires only on a
migration change and waits for a human at an approval gate. `eval-prod` fires every night at 04:23
UTC and waits for nobody.

### 4. Reads are indistinguishable from admin activity

Because the eval authenticates as the admin role, its queries are attributed to the admin role in
Postgres logs and `pg_stat_activity`. There is no way to tell eval traffic from genuine
administrative work after the fact, which matters precisely when you most want to know.

---

## What This Story Is Not

Two things worth stating so nobody spends time on them:

- **This is not a report that a secret leaked.** It has not. I checked whether a connection failure
  could put the DSN into `eval-prod.log` — which is echoed into `$GITHUB_STEP_SUMMARY` and uploaded
  as a 30-day artifact — and found no leak path: neither `run_search_eval.py` nor
  `api/search_eval/runner.py` ever prints the URL, and SQLAlchemy masks the password in `URL` reprs.
  The artifact path is worth a defensive check when this work is picked up, not an incident.
- **This is not an argument against PR #968.** The eval harness is valuable and Route A's "true prod
  numbers" is the whole point of it. The fix is to give it a credential proportionate to what it
  does.

## Proposed Fix

**Create the read-only role the project has never had, and point the eval at it.**

1. **Provision `search_eval_ro` in Terraform** (`deployment/`), so it is reproducible rather than a
   hand-run `psql` snowflake:

   ```sql
   CREATE ROLE search_eval_ro LOGIN PASSWORD '...';
   GRANT CONNECT ON DATABASE <db> TO search_eval_ro;
   GRANT USAGE ON SCHEMA public TO search_eval_ro;
   GRANT SELECT ON verses, verse_embeddings, passages TO search_eval_ro;  -- only what the harness reads
   ALTER ROLE search_eval_ro SET default_transaction_read_only = on;
   ALTER ROLE search_eval_ro SET statement_timeout = '60s';
   ALTER ROLE search_eval_ro SET idle_in_transaction_session_timeout = '60s';
   ```

   `default_transaction_read_only` is the load-bearing line: it makes "read-only" a property the
   database enforces, so the guarantee survives every future edit to the harness. The timeouts follow
   the precedent BITB-097 just set — bound the database from the database, not from the CI runner.

   Grant `SELECT` on the named tables rather than `ALL TABLES IN SCHEMA`, so a future table holding
   something the eval has no business reading is not automatically in scope.

2. **Store its password as a new secret** (`SEARCH_EVAL_DB_PASSWORD`) and **scope it to a GitHub
   environment** (e.g. `search-eval`) rather than adding another bare repo secret. Environment
   scoping is what stops an unrelated workflow from reading it, and gives the access its own audit
   trail. Whether that environment also carries a reviewer is the operator's call — an unattended
   nightly job and a required reviewer are in tension, and BITB-097's follow-up already has the
   approval-gate question open.

3. **Swap `eval-prod` over** and delete `TF_VAR_DB_ADMIN_*` from `search-eval-full.yml` entirely.

4. **Add a regression guard** in the style of `api/tests/test_deploy_workflow_migrations.py`: parse
   `search-eval-full.yml` and assert it references no `TF_VAR_DB_ADMIN_*` secret. The whole failure
   mode here is a credential quietly widening again; a test is what keeps that loud.

## Acceptance Criteria

- [ ] A `search_eval_ro` login role exists, provisioned through Terraform, with `SELECT` on only the
      tables the harness reads
- [ ] `ALTER ROLE search_eval_ro SET default_transaction_read_only = on` is applied, and a write
      attempted as that role is *proven* to fail (rehearsed against a restored copy, not assumed)
- [ ] `statement_timeout` and `idle_in_transaction_session_timeout` set on the role
- [ ] `eval-prod` authenticates with `SEARCH_EVAL_DB_PASSWORD`; `TF_VAR_DB_ADMIN_USERNAME` and
      `TF_VAR_DB_ADMIN_PASSWORD` no longer appear anywhere in `search-eval-full.yml`
- [ ] The new secret is environment-scoped, not a bare repo secret, and a decision is recorded on
      whether that environment requires a reviewer
- [ ] A test asserts `search-eval-full.yml` never references `TF_VAR_DB_ADMIN_*`, so the credential
      cannot silently widen again
- [ ] A nightly run completes green against the new role (the real proof: the grants are sufficient
      for every query the harness actually issues)

## Verification

The grant set is the part most likely to be wrong, and it fails *closed* — an insufficient `SELECT`
grant shows up as a failed eval, not as silent damage. So the cheap proof is simply the first green
nightly run.

The read-only guarantee needs an explicit rehearsal rather than an inspection: connect as
`search_eval_ro` against a restored copy and confirm an `INSERT` and a `CREATE TABLE` both fail. That
is the assertion the whole story turns on, and reading the Terraform will not establish it.

## Timing Note

The cheapest moment to do this is **before PR #968 merges** — that way an ungated nightly admin path
never exists on `main` at all, and the eval's first-ever prod connection is already made with the
right credential. Filed as a follow-up per the maintainer's call; noting the ordering because it
costs nothing to take it now and cannot be un-taken later.

## Related

- **PR #968 / BITB-051 P4a** — introduces the path this story constrains
- **BITB-097** — established the "bound the database from the database" precedent (`lock_timeout` /
  `statement_timeout` as role/session settings) that the timeouts above follow
- **BITB-099** — production Postgres connections encrypt but do not verify the server; same
  connection path, a different weakness in it
- `.github/workflows/search-eval-full.yml`, `deployment/`, `api/tests/test_deploy_workflow_migrations.py`
