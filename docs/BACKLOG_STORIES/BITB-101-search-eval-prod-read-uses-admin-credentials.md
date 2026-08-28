# BITB-101: The Nightly Prod-Read Path Holds Admin Credentials and Nothing Enforces "Read-Only"

**Status:** 🚧 In Progress — implementation shipped; role created; the operator has since created
the `search-eval` environment and set `SEARCH_EVAL_DB_PASSWORD`. That surfaced a defect in this
story's own gating (see *Post-delivery defect* below), fixed in PR #1018 alongside BITB-107; the next
scheduled/manual `eval-prod` run after that merges is the completion signal.
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

- [x] A `search_eval_ro` login role exists, provisioned through Alembic (not Terraform — this repo has
      no `postgresql` Terraform provider and no existing precedent for Terraform-managed Postgres
      roles/grants; all schema/role-level DDL here goes through Alembic, which already runs with admin
      credentials under a gated `environment: production` deploy job, so the new role rides that same
      mechanism instead — see `api/alembic/versions/r0005_add_search_eval_ro_role.py`), with `SELECT`
      on only the tables the harness reads (`verses`, `books`, `verse_tsv`, `passages` — the last was
      caught by independent verification: `search_passages_*` runs unconditionally even when
      `max_passages=0`, since that value only ever becomes a query `LIMIT`, never a guard)
- [x] `ALTER ROLE search_eval_ro SET default_transaction_read_only = on` is applied
  - [ ] a write attempted as that role is *proven* to fail, rehearsed against a restored copy — this is
        an explicit operator step per this story's own Verification section, not something a migration
        or this PR can do; pending operator rehearsal
- [x] `statement_timeout` and `idle_in_transaction_session_timeout` set on the role
- [x] `eval-prod` authenticates with `SEARCH_EVAL_DB_PASSWORD`; `TF_VAR_DB_ADMIN_USERNAME` and
      `TF_VAR_DB_ADMIN_PASSWORD` no longer appear anywhere in `search-eval-full.yml`
- [x] The new secret is environment-scoped (`search-eval` GitHub environment wired into the
      `eval-prod` job via `environment: search-eval`), not a bare repo secret. Recorded decision on
      the reviewer question: **no required reviewer** on the `search-eval` environment, consistent
      with this being an unattended nightly job — a required reviewer would just mean the job silently
      never runs (nobody is watching to approve it at 04:23 UTC), which is worse than the current
      fail-closed-on-missing-secret behavior.
- [x] A test asserts `search-eval-full.yml` never references `TF_VAR_DB_ADMIN_*`, so the credential
      cannot silently widen again (`api/tests/test_search_eval_workflow_credentials.py`)
- [x] The environment-scoped secret is checked from a job that can actually read it
      (`prod-secret-check`), so the fail-closed default is not fail-always — see *Post-delivery
      defect* below; guarded by
      `test_preflight_does_not_check_the_environment_scoped_secret`
- [ ] A nightly run completes green against the new role (the real proof: the grants are sufficient
      for every query the harness actually issues) — the operator has now created the environment and
      set the secret, and PR #1018 carries both remaining pieces (the gating fix above and BITB-107's
      `EMBEDDING_DIMENSIONS=1536` for `eval-prod`). The first green scheduled or manual `eval-prod`
      run after that PR merges is the completion signal

## Post-delivery defect: the environment secret was checked from a job that cannot see it

Found 2026-08-28, after the operator completed their part of this story.

`eval-prod` still skipped on every run — including run
[33207972265](https://github.com/zioalex/getinspiredbythebible/actions/runs/33207972265), whose
`preflight` job reported `HAS_DB: false` with the secret correctly set. The cause is the interaction
between the two halves of this story's own design:

- the secret is **environment-scoped** (`search-eval`), which is the security property this story
  exists to establish; and
- its presence was checked in **`preflight`**, a job with no `environment:` declaration.

An environment-scoped secret is only present in a job's `secrets` context when that job itself
declares the environment. In `preflight`, `secrets.SEARCH_EVAL_DB_PASSWORD` is therefore *always* the
empty string — identically so on a correctly-configured repo and on one where nothing was ever
provisioned. The gate could only ever evaluate `has_db=false`, so the "skip until the operator sets
the secret" fail-closed default was really "skip forever". Nothing in the run said so: the notice
("Azure login or prod DB secrets are not configured") was indistinguishable from the pre-provisioning
state it was written for, and the job summary's own configuration table reported the same `false` it
had reported all along.

The fix keeps the environment scoping and moves the check to a job that can see it. A new
`prod-secret-check` job — scoped to `search-eval`, no checkout, one boolean — publishes
`has_db_password`, and `eval-prod` gates on that. `preflight` keeps only the repo-scoped half
(`TF_VAR_DB_NAME`, now reported as its own row so a genuinely missing DB name is distinguishable from
a missing password) and stays out of the environment, so `eval-smoke` — which needs no prod
credential at all — never inherits the environment's branch policy or any reviewer a future operator
adds. That last point is why the check is a separate job rather than an `environment:` line on
`preflight`: the reviewer question this story recorded as the operator's call stays the operator's
call, without it silently becoming a gate on the credential-light route too.

Guarded by four tests in `api/tests/test_search_eval_workflow_credentials.py`, the one that matters
being `test_preflight_does_not_check_the_environment_scoped_secret` — the mistake is invisible in
review (the expression is valid, the secret name is spelled correctly, and the job goes green), so
only a test that knows *which job* may read the secret can keep it from returning.

Note for the first green run: this fix only un-skips `eval-prod`. Making it *pass* needs
`EMBEDDING_DIMENSIONS=1536` on that job as well — prod's embedding column is `vector(1536)` while
`config.py` defaults to 1024 — which is BITB-107's change, carried in the same PR (#1018). The two
are independent defects that happen to sit on the same job, and the nightly needs both.

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
