# How to Back Up and Restore the Database

Operator runbook for the production PostgreSQL database (Azure Database for
PostgreSQL **Flexible Server**, PG 16). Covers taking a backup, restoring to a
**new** server, restoring onto the **same** server, and restoring into a local
instance for rehearsal.

See also: [`deployment/main.tf`](../deployment/main.tf) (server + backup
configuration), [`docs/MIGRATION_GUIDELINES.md`](MIGRATION_GUIDELINES.md)
(schema changes), [`Makefile`](../Makefile) (`az-pg-*` firewall targets).

> **Read this first:** Azure point-in-time restore **always creates a new
> server**. There is no in-place "roll back this server" button. If you need
> the data back on the *existing* server, that is a logical restore
> (`pg_dump`/`pg_restore`) — see [Scenario B](#scenario-b--restore-onto-the-same-server).

---

## Commands

Every step below is wrapped by a Make target. They all delegate to
[`scripts/db-backup-restore.sh`](../scripts/db-backup-restore.sh), which owns
the safety guards — prefer them over running the raw commands by hand.

| Target                        | Does                                            | Risk        |
| ----------------------------- | ----------------------------------------------- | ----------- |
| `make db-backup-info`         | Retention, earliest restore point, geo setting   | read-only   |
| `make db-backup`              | `pg_dump -Fc` into `backups/`                    | read-only   |
| `make db-restore-verify`      | Post-restore checklist                           | read-only   |
| `make db-restore-local`       | **Creates** a local pgvector container, restores into it | local only |
| `make db-restore-new-server`  | Azure PITR into a **new** server                 | provisions  |
| `make db-restore-same-server` | Replace an existing database from a dump         | **destructive** |

```bash
# Connection: DATABASE_URL for the target, PGPASSWORD for the password.
# Never put the password in the URL — the script redacts what it logs, but
# your shell history does not.
export DATABASE_URL='postgresql://bible@<fqdn>:5432/bibledb?sslmode=require'
export PGPASSWORD='...'
```

The script accepts the app's own URL form (`postgresql+asyncpg://...?ssl=require`)
and rewrites it to what `psql`/`pg_dump` need — see
[Rule #1](MIGRATION_GUIDELINES.md#-rule-1-never-pass-ssl-parameters-in-connection-url).

**The two destructive targets require you to retype the target** (the host, or
the container name) before they do anything. Non-interactively, pass it as
`CONFIRM=...`. A y/n prompt would be too easy to answer by reflex.

---

## What protection exists today

From [`deployment/main.tf:384-408`](../deployment/main.tf):

| Setting                        | Value               | Consequence                                            |
| ------------------------------ | ------------------- | ------------------------------------------------------ |
| `backup_retention_days`        | `7`                 | Point-in-time restore window is **7 days**, no further. |
| `geo_redundant_backup_enabled` | `false`             | **No geo-restore.** Backups live in one region only.    |
| `auto_grow_enabled`            | `true`              | Storage grows automatically; no disk-full cliff.        |
| `version`                      | `16`                | Restore targets must be PG 16.                          |
| `sku_name`                     | `B_Standard_B2s`    | Burstable — restores are slower than on a General SKU.  |
| `azure.extensions`             | `vector,uuid-ossp,pg_cron,pg_prewarm` | `vector` must be allowlisted on any target. |

Azure takes these backups automatically. **Nothing in this repo schedules a
logical (`pg_dump`) backup** — if you want a copy that outlives the 7-day
window or leaves the region, you must take it yourself
([Scenario D](#scenario-d--take-a-portable-logical-backup)).

⚠️ **Known limitation:** with a 7-day window and no geo-redundancy, a
corruption discovered on day 8, or a region-level outage, is not recoverable
from Azure's automatic backups. Take a manual logical backup before anything
destructive, and keep one off-region if the data matters beyond a week.

---

## Pick your scenario

| Goal                                            | Scenario | Method                     | Downtime      |
| ----------------------------------------------- | -------- | -------------------------- | ------------- |
| Recover from a bad change, keep prod running    | [A](#scenario-a--restore-to-a-new-server-point-in-time) | PITR → new server | none until cutover |
| Put data back on the **existing** server        | [B](#scenario-b--restore-onto-the-same-server) | `pg_dump`/`pg_restore` | **yes** |
| Rehearse a migration / test a restore           | [C](#scenario-c--restore-into-a-local-instance) | dump → local Docker | none |
| Keep a copy beyond 7 days or off-region         | [D](#scenario-d--take-a-portable-logical-backup) | `pg_dump -Fc` | none |
| Rehearse when the dump will not fit on disk     | [E](#scenario-e--rehearse-in-azure-no-local-disk) | PITR → copy → rehearse → delete | none |

---

## Preparation (all scenarios)

```bash
# 1. Variables (see Makefile: PG_SERVER / PG_RG)
export PG_RG="bible-app-rg"
export PG_SERVER="bible-app-db-<suffix>"     # az postgres flexible-server list -g "$PG_RG" -o table
export PG_DB="<db_name>"                     # TF_VAR_DB_NAME

# 2. Open the firewall for your IP (remember to close it afterwards)
make az-pg-add-ip

# 3. Confirm how far back you can actually restore
make db-backup-info
```

`earliestRestoreDate` is authoritative — it is often later than
"now minus 7 days" (a server rebuild or SKU change resets it).

---

## Scenario A — restore to a new server (point-in-time)

The native path. Non-destructive: production keeps running untouched while the
restored copy comes up beside it.

```bash
make db-restore-new-server \
  NEW_SERVER="${PG_SERVER}-restore-$(date +%Y%m%d)" \
  RESTORE_POINT="2026-07-30T14:25:00Z"          # UTC, inside the window
```

It asks you to retype the new server name before provisioning anything.
Underneath it runs `az postgres flexible-server restore --source-server ...
--restore-time ...`; use `az` directly if you need flags the target does not
expose.

Takes roughly 10–30 minutes on the Burstable SKU. The restored server is a
**separate Azure resource** with its own FQDN, billed separately — delete it
when done.

Then verify ([checklist](#verification-checklist)), and if you are cutting
over:

```bash
# Point the app at the restored server, then redeploy/restart the container app
az containerapp update -g "$PG_RG" -n <backend-app> \
  --set-env-vars DATABASE_URL="postgresql://<user>:<pass>@<new-fqdn>:5432/${PG_DB}?sslmode=require"
```

⚠️ **Terraform drift.** The connection string is managed in
[`deployment/main.tf:93`](../deployment/main.tf). A manual `containerapp update`
will be reverted by the next `terraform apply`. Cutover is only finished when
the change is reflected in Terraform/its variables.

> `sslmode=require` (not `ssl=require`) — see
> [Rule #1 in MIGRATION_GUIDELINES.md](MIGRATION_GUIDELINES.md#-rule-1-never-pass-ssl-parameters-in-connection-url).

---

## Scenario B — restore onto the same server

**Azure cannot do this natively.** PITR only ever produces a new server. To get
data back onto the existing server you replace the database contents logically,
which means **downtime and a destructive step**.

```bash
# 0. SAFETY: dump the CURRENT state first — this is your only undo
DATABASE_URL="postgresql://bible@<fqdn>:5432/${PG_DB}?sslmode=require" make db-backup

# 1. Get the good data (e.g. from a Scenario A restored server)
DATABASE_URL="postgresql://bible@<restored-fqdn>:5432/${PG_DB}?sslmode=require" \
  make db-backup DUMP=good.dump

# 2. Stop writes — scale the backend to zero so nothing writes mid-restore
az containerapp update -g "$PG_RG" -n <backend-app> --min-replicas 0 --max-replicas 0

# 3. Replace the live database. Prompts for the hostname before doing anything.
DATABASE_URL="postgresql://bible@<fqdn>:5432/${PG_DB}?sslmode=require" \
  make db-restore-same-server DUMP=good.dump

# 4. Verify, then bring the backend back
DATABASE_URL="postgresql://bible@<fqdn>:5432/${PG_DB}?sslmode=require" make db-restore-verify
az containerapp update -g "$PG_RG" -n <backend-app> --min-replicas 1 --max-replicas <n>
```

- Step 3 runs `pg_restore --clean --if-exists`, which drops each object before
  recreating it. **This is the destructive step.** The target refuses to run
  until you retype the hostname; do not skip step 0 to save time.
- `--no-owner --no-acl` are always passed, because Azure gives you no superuser
  and roles from the source will not exist verbatim on the target.
- Restoring into a *differently named* database on the same server and renaming
  afterwards is gentler, but PG will not let you rename a database with open
  connections — you still need step 2.

**Prefer Scenario A + cutover** whenever you can. It is reversible; this is not.

---

## Scenario C — restore into a local instance

For rehearsing a migration, testing this runbook, or debugging with production
shaped data.

```bash
# 1. Dump prod (read-only, safe)
DATABASE_URL="postgresql://bible@<fqdn>:5432/${PG_DB}?sslmode=require" make db-backup

# 2. Bring up PG 16 + pgvector locally and restore into it
make db-restore-local DUMP=backups/<the-file>.dump

# 3. Check it
DATABASE_URL="postgresql://postgres@localhost:5433/bibledb" PGPASSWORD=local \
  make db-restore-verify
```

**You do not need a local database first — this creates one.** It requires
Docker and a dump file, nothing else. `db-restore-local` starts
`pgvector/pgvector:pg16` as the container `bibledb-restore` on port 5433, waits
for it to accept connections, raises `maintenance_work_mem` to 512MB (HNSW
rebuilds are the slow part), and restores with `-j 4`. If that container
already exists it asks you to retype the name before recreating it.

**Azure-only extensions are filtered out of the restore.** A production dump
carries `CREATE EXTENSION pg_cron`, a `cron` schema, and the contents of
`cron.job` / `cron.job_run_details`. The `pgvector/pgvector:pg16` image does not
ship pg_cron, so every one of those entries fails and `pg_restore` exits
non-zero, aborting the target — even though nothing this application reads is
missing. `db-restore-local` therefore drops those entries from the dump's table
of contents before restoring, and prints how many it skipped. Errors that
survive the filter are real: the target stops rather than hand you a partial
copy to rehearse against.

Any *other* extension the dump creates that the local server cannot provide is
detected and skipped automatically — the target compares the dump's extension
list against `pg_available_extensions` and reports what it dropped. pg_cron is
only the hardcoded default because its `cron` schema needs skipping too, which
cannot be derived from the extension name.

When a restore does fail, the target prints the **distinct** error causes (the
raw output repeats the same handful once per failed object) and the path to the
full log, so you can tell an Azure-only extension apart from a real problem.

Add to the lists if a future extension brings its own schema, or set
`SKIP_EXTENSIONS=''` to restore the dump verbatim:

```bash
SKIP_EXTENSIONS='pg_cron azure_storage' SKIP_SCHEMAS='cron azure_storage' \
  make db-restore-local DUMP=backups/<the-file>.dump
```

Note that `make db-restore-verify` lists the extensions actually present, so
the filtered ones are visibly absent from the restored copy — expected, and
irrelevant to a schema rehearsal, which only reads the `public` schema.

It is also the one target that **ignores `DATABASE_URL`** — it builds its own
`postgresql://postgres@localhost:5433/bibledb`. That is deliberate: you will
usually have a production URL exported for the other targets, and this command
must never be able to aim at it. Override `LOCAL_PORT`, `LOCAL_DB`,
`LOCAL_CONTAINER`, `JOBS` or `PGPASSWORD` (default `local`) if the defaults
collide with something.

This is the environment to use for the **schema-change rehearsal** referenced
in [`docs/MIGRATION_GUIDELINES.md`](MIGRATION_GUIDELINES.md) — run the migration
against this copy and confirm the result before touching production.

**If the dump does not fit on your disk**, you almost certainly do not need the
data. Embeddings dominate the size, and a schema rehearsal never reads a row:

```bash
DATABASE_URL="postgresql://bible@<fqdn>:5432/${PG_DB}?sslmode=require" make db-backup-schema
make db-restore-local DUMP=backups/<the-file>.dump
```

`db-backup-schema` is `db-backup` with `--schema-only` — same custom format,
same filter, a fraction of the size. Every table, column, index and constraint
is present; only rows are absent. `make db-restore-verify` will report zero row
counts on such a copy, which is expected. If you need real data volumes (to
time a migration, say), use [Scenario E](#scenario-e--rehearse-in-azure-no-local-disk)
instead of trying to fit the full dump locally.

---

## Scenario D — take a portable logical backup

Use before any risky operation, and to keep a copy beyond the 7-day window.

```bash
make db-backup                          # -> backups/<host>-<timestamp>.dump
make db-backup DUMP=/path/to/name.dump  # explicit destination
```

- `-Fc` (custom format) is always used: it is required for parallel restore
  (`pg_restore -j`) and selective restore (`-t`). Plain SQL is unusable at this
  size.
- Embeddings dominate the size — expect the dump to be **large and slow**.
  Store it outside the DB's region if it is a real safety net.
- To skip the bulk and keep only operational data:

  ```bash
  make db-backup DUMP_ARGS="--exclude-table-data=verses --exclude-table-data=passages"
  ```

  Schema is preserved; embeddings are re-derivable via the seeding scripts.
- `backups/` and `*.dump` are git-ignored, so a dump cannot be committed by
  accident.

---

## Scenario E — rehearse in Azure (no local disk)

For the [BITB-089](BACKLOG_STORIES/BITB-089-deploy-alembic-migrations-from-ci.md)
Stage 1 rehearsal when a full dump will not fit locally, or when the rehearsal
needs production's real data volumes.

Azure copies the data server-side: nothing transits your machine, and no dump
file is written. The trade is a second billable server for as long as it exists
— **the last step is not optional.**

```bash
# 0. Variables (see Preparation above)
export PG_RG="bible-app-rg"
export PG_SERVER="bible-app-db-<suffix>"
export PG_DB="<db_name>"
export COPY="${PG_SERVER}-rehearse-$(date +%Y%m%d)"

# 1. Copy production into a new server (10–30 min on Burstable)
make db-backup-info                                  # pick a point inside the window
make db-restore-new-server NEW_SERVER="$COPY" RESTORE_POINT="2026-08-09T20:00:00Z"

# 2. Reach it: the copy has its own firewall, and its own FQDN
make az-pg-add-ip SERVER="$COPY"
export DATABASE_URL="$(make -s db-server-url SERVER="$COPY")"
export PGPASSWORD='<the production admin password>'  # a PITR copy keeps it

# 3. Confirm the copy is sound before drawing conclusions from it
make db-restore-verify

# 4. Rehearse: stamp -> check -> upgrade (this is the Stage 1 gate)
make db-rehearse-alembic

# 5. Tear it down — it bills until you do
make db-delete-server SERVER="$COPY"
make az-pg-remove-ip RULE="$COPY" SERVER="$COPY"
```

Notes on the pieces:

- **The firewall targets take `SERVER=`.** Without it they act on production,
  which is not where your rehearsal is.
- **`db-server-url` prints a URL with no password.** `PGPASSWORD` supplies it —
  both libpq and asyncpg read that variable, so it never has to be in the URL
  (or in your shell history).
- **A PITR copy keeps the source's admin credentials and server parameters**,
  including the `azure.extensions` allow-list, so `vector` and pg_cron are
  present exactly as in production. This is what makes it a better rehearsal
  target than a local container.
- **`db-rehearse-alembic` refuses to run against production.** It compares the
  target host against `PG_SERVER`; there is no override. Stamping production is
  a deliberate one-time operator step (Stage 2 in
  [`MIGRATION_GUIDELINES.md`](MIGRATION_GUIDELINES.md)), and `upgrade head`
  against production belongs to the deploy pipeline.
- **`db-delete-server` refuses `PG_SERVER`** for the same reason, and asks you
  to retype the server name. Deleting a server also deletes its automatic
  backups — fine for a rehearsal copy, unrecoverable for anything else.

---

## Verification checklist

Run against the restored target **before** cutting over or declaring success.

```bash
DATABASE_URL="<target-url>" make db-restore-verify
```

It runs the queries below and **exits non-zero if any index is invalid** — the
failure this checklist exists to catch, because the restore otherwise looks
successful while searches silently fall back to sequential scans.

```sql
-- 1. Extensions present (vector is the one that breaks silently)
SELECT extname, extversion FROM pg_extension ORDER BY 1;

-- 2. All expected tables, with row counts
SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;

-- 3. Indexes rebuilt — HNSW indexes are the slow, easily-missed ones
SELECT indexname, tablename FROM pg_indexes
WHERE schemaname='public' AND indexdef ILIKE '%hnsw%';

-- 4. Anything left invalid after restore
SELECT indexrelid::regclass FROM pg_index WHERE NOT indisvalid;

-- 5. Migration bookkeeping matches what you expect
SELECT * FROM schema_migrations ORDER BY 1;
```

Then a functional check — a semantic search exercises pgvector, the HNSW
indexes, and the embedding columns in one shot:

```bash
curl -s "https://<host>/api/v1/scripture/search?q=hope&max_verses=3" | jq '.verses | length'
```

**Finally:** close the firewall (`az-pg-add-ip` names the rule after the
server), and delete any temporary restored server:

```bash
make az-pg-remove-ip RULE="$PG_SERVER"
az postgres flexible-server delete -g "$PG_RG" -n "$NEW_SERVER" --yes   # if you made one
```

---

## Gotchas

| Symptom                                          | Cause                                                                 |
| ------------------------------------------------ | --------------------------------------------------------------------- |
| `extension "vector" is not allow-listed`          | Target server lacks `vector` in `azure.extensions`. Set it *before* restoring. |
| `parameter 'ssl' cannot be changed now`           | `?ssl=require` in an asyncpg URL. Use `sslmode=require`. See Rule #1.  |
| Restore finishes fast, searches are slow          | HNSW indexes not rebuilt / invalid. Check query 3 and 4 above.         |
| `role "..." does not exist`                       | Missing `--no-owner --no-acl`.                                        |
| `extension "pg_cron" is not available` (local)    | Azure-only extension in the dump. Filtered by default — see Scenario C. |
| `must be superuser`                               | Expected on Azure. Use `--no-owner --no-acl`; never `pg_dumpall`.      |
| PITR refuses your timestamp                       | Outside the window — check `earliestRestoreDate`, and use UTC.         |
| Restored server reverts after a deploy            | Terraform still points at the old FQDN (`deployment/main.tf:93`).      |

---

## What this runbook does not cover

- **Automated/scheduled logical backups.** None exist; Scenario D is manual.
- **Geo-redundant recovery.** Disabled (`geo_redundant_backup_enabled = false`);
  a region outage is not covered by Azure's automatic backups.
- **Restoring a deleted server.** Azure can restore a *dropped* Flexible Server
  only within a limited window and only via support — do not rely on it.
