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
az postgres flexible-server show \
  --resource-group "$PG_RG" --name "$PG_SERVER" \
  --query "{earliest:backup.earliestRestoreDate, retention:backup.backupRetentionDays, geo:backup.geoRedundantBackup}" -o table
```

`earliestRestoreDate` is authoritative — it is often later than
"now minus 7 days" (a server rebuild or SKU change resets it).

---

## Scenario A — restore to a new server (point-in-time)

The native path. Non-destructive: production keeps running untouched while the
restored copy comes up beside it.

```bash
export RESTORE_POINT="2026-07-30T14:25:00Z"        # UTC, inside the window
export NEW_SERVER="${PG_SERVER}-restore-$(date +%Y%m%d)"

az postgres flexible-server restore \
  --resource-group "$PG_RG" \
  --name "$NEW_SERVER" \
  --source-server "$PG_SERVER" \
  --restore-time "$RESTORE_POINT"
```

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
# 0. SAFETY: take a fresh dump of current state first — this is your undo
pg_dump "postgresql://<user>:<pass>@<fqdn>:5432/${PG_DB}?sslmode=require" \
  -Fc -f "pre-restore-$(date +%Y%m%dT%H%M%S).dump"

# 1. Get the good data (e.g. dump it from a Scenario A restored server)
pg_dump "postgresql://<user>:<pass>@<restored-fqdn>:5432/${PG_DB}?sslmode=require" \
  -Fc -f good.dump

# 2. Stop writes — scale the backend to zero so nothing writes mid-restore
az containerapp update -g "$PG_RG" -n <backend-app> --min-replicas 0 --max-replicas 0

# 3. Restore into the live database, replacing objects
pg_restore --clean --if-exists --no-owner --no-acl \
  -d "postgresql://<user>:<pass>@<fqdn>:5432/${PG_DB}?sslmode=require" good.dump

# 4. Bring the backend back
az containerapp update -g "$PG_RG" -n <backend-app> --min-replicas 1 --max-replicas <n>
```

- `--clean --if-exists` drops each object before recreating it. **This is the
  destructive step.** Do not run it without step 0.
- `--no-owner --no-acl` because Azure gives you no superuser; roles from the
  source will not exist verbatim on the target.
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
pg_dump "postgresql://<user>:<pass>@<fqdn>:5432/${PG_DB}?sslmode=require" \
  -Fc -f prod.dump

# 2. Local PG 16 + pgvector (PGPASSWORD keeps credentials off the command line)
export PGPASSWORD=local
docker run -d --name pg-restore -e POSTGRES_PASSWORD="$PGPASSWORD" \
  -e POSTGRES_DB=bibledb -p 5433:5432 pgvector/pgvector:pg16

# 3. HNSW index rebuilds are the slow part — give them memory
psql "postgresql://postgres@localhost:5433/bibledb" \
  -c "ALTER SYSTEM SET maintenance_work_mem = '512MB';" -c "SELECT pg_reload_conf();"

# 4. Restore
pg_restore --no-owner --no-acl -j 4 \
  -d "postgresql://postgres@localhost:5433/bibledb" prod.dump
```

This is the environment to use for the **schema-change rehearsal** referenced
in [`docs/MIGRATION_GUIDELINES.md`](MIGRATION_GUIDELINES.md) — run the migration
against this copy and confirm the result before touching production.

---

## Scenario D — take a portable logical backup

Use before any risky operation, and to keep a copy beyond the 7-day window.

```bash
pg_dump "postgresql://<user>:<pass>@<fqdn>:5432/${PG_DB}?sslmode=require" \
  -Fc --no-owner --no-acl \
  -f "bibledb-$(date +%Y%m%dT%H%M%SZ).dump"
```

- `-Fc` (custom format) is required for parallel restore (`pg_restore -j`) and
  selective restore (`-t`). Do not use plain SQL for a database this size.
- Embeddings dominate the size — expect the dump to be **large and slow**.
  Compress and store it outside the DB's region if it is a real safety net.
- To exclude the bulk and keep only operational data:
  `--exclude-table-data='verses' --exclude-table-data='passages'`
  (schema is preserved; embeddings are re-derivable via the seeding scripts).

---

## Verification checklist

Run against the restored target **before** cutting over or declaring success.

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
