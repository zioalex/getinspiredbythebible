# BITB-097: The Deploy Pipeline Cannot Be Trusted With Migrations

**Status:** 🚧 In Progress — marker was stale; corrected 2026-08-28. Defects **1, 2, 4 and 5 shipped**
in PR #1005 (`deploy` needs `run-migrations`; `functional-tests` needs both; `deployment/**` and
`azure-deploy.yml` added to `test_update.yml`'s trigger paths; `concurrency` group with
`cancel-in-progress: false`), with `api/tests/test_deploy_workflow_migrations.py` guarding them.
**Defect 3 is still open**: no job-level `PGOPTIONS` (`lock_timeout`/`statement_timeout`) on
`run-migrations` — only per-revision `SET LOCAL` in r0004/r0005 and the legacy runner's
`server_settings`, which is exactly the "depends on every future author remembering" gap this defect
described. The approval-gate decision (defect 5, second half) also remains the operator's call.
**Priority:** P1 — five defects, each independently capable of causing or hiding an outage
**Size:** M (mostly workflow YAML; one decision about the approval gate is the operator's)
**Created:** 2026-08-18
**Prompted by:** the 2026-08-17 production outage (BITB-096) and the 2026-08-18 deploy that never fired

## User Story

**As** the operator of a single-maintainer production service, **I want** the deploy pipeline to
run migrations before the code that needs them, to bound them from the database, and to actually
fire when I merge, **so that** a schema change cannot take the site down for 45 minutes and a
merged fix cannot silently never reach production.

## Why This Exists

BITB-096 replaced the migration that caused the 2026-08-17 outage. **It fixed the migration, not
the pipeline.** Every defect below was a contributing cause or a concealment, and all five are
still live. A safe migration ran through this pipeline yesterday only because it was written
defensively — the pipeline offered it no protection it did not bring itself.

Evidence is from `.github/workflows/azure-deploy.yml` and `.github/workflows/test_update.yml` as
of `9840e8b`, plus the runs listed in each section.

---

### 1. `deploy` runs before `run-migrations`

```yaml
deploy:          needs: [changes, build-backend, build-frontend, tf-plan]
run-migrations:  needs: [changes, deploy]
```

New application code goes live **before** the migration it depends on. On 2026-08-17 the #955
image was serving traffic and returning 500 on every verse read before `run-migrations` had even
started — the failure was total for the length of the migration, then longer.

**Fix:** invert to `deploy: needs: [..., run-migrations]`.

**This is not free, and the story must say so.** Migrating first means the *old* code runs against
the *new* schema for the length of the deploy. That is safe only under expand/contract discipline:
a migration must be backward-compatible with the currently-deployed application. Additive tables
and columns are; renames, drops and type changes are not, and must be split across two deploys.
Inverting the order without adopting that rule trades one failure mode for another. The rule
belongs in `docs/MIGRATION_GUIDELINES.md` as part of this change.

### 2. `functional-tests` races the migration

```yaml
functional-tests: needs: [deploy]
```

It depends on `deploy` but not `run-migrations`, so the two run **concurrently**. On 2026-08-17
`functional-tests` started at 20:53:45, four seconds after `deploy` finished, while
`run-migrations` sat unapproved. All 33 failures it reported were unavoidable — the smoke tests
were testing a system mid-migration and calling it broken.

**Fix:** `needs: [deploy, run-migrations]`, keeping the existing `if: always() && ...` shape so a
skipped migration job does not skip the tests.

### 3. A CI timeout does not stop a migration

`run-migrations` carries `timeout-minutes: 30`. On 2026-08-17 it expired mid-`ALTER TABLE`. That
killed the *client*; the server-side DDL kept its `ACCESS EXCLUSIVE` lock for a further **15
minutes**, working toward a `COMMIT` that could never arrive, because Alembic no longer existed to
send it. Recovery needed `pg_cancel_backend()` against the leader pid by hand.

The harness timeout is not a bound on the work. **Only the database can bound the database.**

`r0004` now sets `lock_timeout` and `statement_timeout` itself, but that protects exactly one
revision and depends on every future author remembering.

**Fix:** set them once, in the job, so every revision inherits them:

```yaml
- name: Run Alembic migrations
  env:
    PGOPTIONS: "-c lock_timeout=5s -c statement_timeout=25min"
```

`statement_timeout` must sit *below* `timeout-minutes` so the database gives up first and rolls
back cleanly, rather than the runner vanishing and orphaning the statement. Alternatively set both
on the migration role with `ALTER ROLE ... SET`, which also covers manual runs.

### 4. Merging to `main` does not necessarily deploy

`azure-deploy.yml` has **no `push` trigger**. On `main` it fires only via:

```yaml
on:
  workflow_run:
    workflows: ["CI/CD - Test Application"]
```

and that workflow's own `push.paths` are `api/**`, `frontend/**`, `tests/**`,
`docker-compose*.yml`, `scripts/**`, `.github/workflows/test_update.yml`.

**`deployment/**` is not in the list. Neither is `azure-deploy.yml` itself.** So a merge touching
only Terraform never runs the test workflow, never emits `workflow_run`, and never deploys.
Observed 2026-08-18: #1002 (a `deployment/main.tf`-only fix) merged and nothing happened.

The infrastructure-as-code directory and the deploy workflow are the two paths where "merged but
not applied" is hardest to notice and most damaging.

**Fix:** add `deployment/**` and `.github/workflows/azure-deploy.yml` to `test_update.yml`'s
`push.paths` and `pull_request.paths`. Preferred over giving `azure-deploy.yml` its own `push`
trigger, because it preserves the single invariant worth keeping: nothing deploys unless the test
workflow passed first.

### 5. The `production` approval gate has a two-week queue

Both `deploy` and `run-migrations` use `environment: production`, which requires manual approval.
As of 2026-08-18 there were **16 runs in `waiting`**, the oldest from **11 August**.

Two distinct harms:

- On 2026-08-17 `deploy` was approved and `run-migrations` was not, so the pipeline did the one
  dangerous half of the pair. **The gate did not prevent the outage; its partial application
  caused it.** Approving one and not the other must be impossible.
- There is no `concurrency` group on the workflow, so every push queues another run and none
  supersedes its predecessor. That is how 16 accumulated.

**Fix, two parts.** Add a concurrency group so superseded runs cancel:

```yaml
concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: false   # true would cancel a running migration -- see defect 3
```

`cancel-in-progress` must stay `false`: cancelling a run mid-migration is precisely the
client-killed-DDL-survives failure. Cancel *queued* runs, never running ones.

Then decide the gate itself — the operator's call, not a code change:

- **Drop the required reviewer** and let the tests gate. Honest about how this repo actually
  operates, and removes the partial-approval hazard entirely.
- **Keep it**, but make approving one job approve both, and add an alert when anything sits in
  `waiting` longer than an hour.

Leaving it as-is is the one option this story argues against: a gate nobody services is not
control, it is latency plus a queue.

---

## Acceptance Criteria

- [ ] `deploy` depends on `run-migrations`, not the reverse
- [ ] `docs/MIGRATION_GUIDELINES.md` states the expand/contract rule that ordering now requires,
      with the two-deploy split spelled out for renames, drops and type changes
- [ ] `functional-tests` depends on both `deploy` and `run-migrations`
- [ ] `lock_timeout` and `statement_timeout` set at the job or role level, with
      `statement_timeout` strictly below `timeout-minutes`
- [ ] `deployment/**` and `.github/workflows/azure-deploy.yml` added to `test_update.yml`'s
      trigger paths; proven by a Terraform-only change reaching production
- [ ] `concurrency` group added with `cancel-in-progress: false`
- [ ] The 16 stranded `waiting` runs cleared, and a decision recorded on the approval gate
- [ ] A test in `api/tests/test_deploy_workflow_migrations.py` asserting the job dependency
      order, so the ordering cannot silently regress — the existing file already guards the
      workflow's Alembic wiring (BITB-089) and is the natural home

## Verification

Ordering and dependencies are structural and can be asserted by parsing the YAML — that is what
the existing `test_deploy_workflow_migrations.py` does, and it is worth more than reading the
diff.

The trigger fix needs an end-to-end proof, not an inspection: make a trivial `deployment/**`
change, merge it, and confirm a deploy run appears. Defect 4 is precisely the class of bug that
looks fine in YAML and does nothing in practice.

For the timeout fix, a rehearsal against a restored copy: start a long statement, confirm the
database aborts it at `statement_timeout` and that the lock is released without manual
intervention.

## Related

- BITB-096 — the side-table migration; its follow-ups section lists all five of these
- BITB-089 — why the pipeline runs Alembic at all, and where the ordering came from
- BITB-062 / PR #955 — the outage this traces back to
- `.github/workflows/azure-deploy.yml`, `.github/workflows/test_update.yml`,
  `api/tests/test_deploy_workflow_migrations.py`
