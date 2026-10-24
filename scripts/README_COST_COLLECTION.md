# BITB-150 Cost Analysis — Evidence Collection

Automated, non-interactive collection of all Phase 0 cost evidence for
[BITB-150](../BACKLOG_STORIES/BITB-150-azure-cost-analysis-monitoring-and-database.md).
Run once for the initial analysis, then weekly (via the committed GitHub Actions
workflow) to catch cost drift and new optimisation opportunities.

## Scripts Inventory

| File | Purpose |
|------|---------|
| `scripts/create_cost_collection_spn.sh` | **One-time setup.** Creates the Azure service principal + all 6 required RBAC roles and prints its credentials |
| `scripts/collect_cost_evidence.py` | The collector — single implementation (resource discovery, Logs/Alerts/Cost REST calls, SQL, manifest). Requires `python3` |
| `scripts/collect_cost_evidence.sh` | Thin wrapper that `exec`s `python3` on the sibling `collect_cost_evidence.py` (works from `scripts/` and from the flat `/app` image layout), forwarding arguments, environment and exit code. It contains no collection logic, so it cannot drift from the Python collector |
| `scripts/Dockerfile.cost-collector` | Container image — Debian slim + Azure CLI via pip + `psql` (built and smoke-tested in CI) |
| `tests/test_collect_cost_evidence.py` | Offline regression tests (no cloud, no database) — run by the PR gate |
| `.github/workflows/cost-collector-build.yml` | PR gate — runs the regression tests, builds the image and smoke-tests `az`/`psql`/wrapper/`DATABASE_URL` forwarding whenever the collector files change |
| `.github/workflows/cost-evidence-weekly.yml` | Weekly scheduled run (Mon 06:00 UTC); commits complete evidence, uploads partial evidence as an artifact and fails the job |
| `docs/BACKLOG_STORIES/cost-evidence-collection-report.md` | Phase 0 report template — paste evidence outputs into its placeholders |

## Prerequisites (one-time)

### 1. Create the service principal

`scripts/create_cost_collection_spn.sh` creates an Azure AD service principal
with **least-privilege read-only roles** scoped to the `bible-app-rg` resource
group, then prints the credentials as `export` lines. Requires an interactive
`az login` with an account that can create service principals and assign roles
(Owner or User Access Administrator on the resource group).

```bash
az login   # once, with a privileged account

./scripts/create_cost_collection_spn.sh bitb150-cost-collector
```

Sample output (the secret is shown **only once** — save it immediately):

```
export AZURE_CLIENT_ID="      <appId>"
export AZURE_CLIENT_SECRET="  <password>"
export AZURE_TENANT_ID="      <tenant>"
export AZURE_SUBSCRIPTION_ID="f5bc5a63-92f8-4ab6-ad94-84673eeebb56"
```

The script is idempotent: if the SP already exists it offers to reset its
credentials and re-verify the role assignments instead of creating a duplicate.

### 2. RBAC roles the script assigns

All scoped to `/subscriptions/<sub>/resourceGroups/bible-app-rg`, all
**read-only**:

| Role | Needed for |
|------|-----------|
| Cost Management Reader | Cost Management Query API via `az rest` (meters, 3-month breakdown) |
| Monitoring Reader | Azure Monitor metrics (90-day CPU/memory/storage), diagnostic settings, alert instances |
| Log Analytics Reader | Logs query API via `az rest` (billable GB, App Insights record counts) |
| PostgreSQL Flexible Server Reader | `az postgres flexible-server show` (SKU, provisioned storage) |
| Azure Container Apps Reader | Container Apps replica/CPU/memory config |
| App Configuration Data Reader | App Insights component config |

To assign them manually instead (not recommended — use the script):

```bash
az role assignment create --assignee <SP_APP_ID> \
  --role "Cost Management Reader" \
  --scope "/subscriptions/<sub>/resourceGroups/bible-app-rg"
# ...repeat per role
```

### 3. Set the required secrets

| Env var | Source |
|---------|--------|
| `AZURE_CLIENT_ID` | `appId` from the SPN script |
| `AZURE_CLIENT_SECRET` | `password` from the SPN script (shown once) |
| `AZURE_TENANT_ID` | `tenant` from the SPN script |
| `AZURE_SUBSCRIPTION_ID` | Defaults to `f5bc5a63-92f8-4ab6-ad94-84673eeebb56` |
| `DATABASE_URL` | PostgreSQL connection string — **runtime only, optional**; needed for the in-database queries (DB size, top tables, `idx_scan`, `stats_reset`). It must be exported on the host and forwarded with `docker run -e DATABASE_URL`; it is never baked into the image or passed as a build argument. Use a read-only role; the collector also opens a read-only session. Without it the SQL outputs are skipped with a warning (not a failure) |

Optional overrides (not secrets):

| Env var | Default / effect |
|---------|------------------|
| `AZURE_RESOURCE_GROUP` | `bible-app-rg` |
| `POSTGRES_SERVER_NAME` | Server name (case-insensitive). By default the collector discovers flexible servers in the resource group and requires **exactly one**; with several (or none) it fails instead of guessing. The real name in `deployment/main.tf` is `<prefix>-db-<suffix>`, not a fixed string |
| `LOG_ANALYTICS_WORKSPACE_ID` | Workspace customer ID (GUID) or name. Same rule: exactly one workspace is discovered unless this selects one |

The resolved resources are recorded in `MANIFEST.json` under `resolution`.

### 4. Temporarily allow your IP for SQL collection

For a PostgreSQL server using public access, allow your host's public IPv4
address before running the collector with `DATABASE_URL`. These commands change
the **PostgreSQL server firewall**, not an NSG. Run them from the repository
root on the host, with Azure CLI authenticated to the correct subscription as
an account allowed to manage firewall rules; the read-only collector service
principal is not intended to make these changes.

```bash
# Inspect existing rules first; note whether the rule below already exists.
make az-pg-list-rules

# Allow only your current public IPv4 address, then verify the rule.
make az-pg-add-ip
make az-pg-list-rules
```

The default server is `bible-app-db-mb0172`. The add target creates or updates
a rule with the **same name as the server**. If that rule already exists,
record its original IP range before proceeding: the target overwrites it.
These steps assume the container uses the same public egress IP as the host;
a remote Docker daemon or different VPN/proxy route may need a different rule.
Do not enable public access on a private-only server just to run this guide.

Run the collector using one of the methods below. **After collection finishes,
including on failure**, remove the temporary rule if you created it:

```bash
make az-pg-remove-ip RULE=bible-app-db-mb0172
make az-pg-list-rules
```

Removal does not prompt for confirmation. Do not delete a pre-existing shared
rule: restore its original IP range instead using your normal firewall
management process.

For another server (for example a restored copy), use the same override for
every step; the rule name again matches that server:

```bash
make az-pg-list-rules SERVER=restored-copy
make az-pg-add-ip SERVER=restored-copy
# Run collection with POSTGRES_SERVER_NAME=restored-copy and a matching DATABASE_URL.
make az-pg-remove-ip SERVER=restored-copy RULE=restored-copy
make az-pg-list-rules SERVER=restored-copy
```

## Quick Start (three run methods)

### Option 1: Docker (recommended — self-contained)

```bash
# The image is also built and smoke-tested by CI on every PR that touches
# the collector files (.github/workflows/cost-collector-build.yml)
docker build -t bitb150-cost-collector -f scripts/Dockerfile.cost-collector .

# DATABASE_URL must be exported on the host first (the check prints nothing
# if it is set, and never prints its value):
: "${DATABASE_URL:?export DATABASE_URL to collect the SQL evidence}"

docker run --rm -t \
  -e AZURE_CLIENT_ID -e AZURE_CLIENT_SECRET \
  -e AZURE_TENANT_ID -e AZURE_SUBSCRIPTION_ID \
  -e DATABASE_URL \
  -e POSTGRES_SERVER_NAME -e LOG_ANALYTICS_WORKSPACE_ID \
  -v "$(pwd)/cost-evidence:/app/cost-evidence" \
  bitb150-cost-collector
```

`-e VAR` (no value) forwards the host's exported variable at runtime; unset
ones (e.g. the two overrides) are simply not passed. If you want a run without
the SQL evidence, omit the `:` check line and `-e DATABASE_URL`: those four
files are then marked skipped in `MANIFEST.json`.

Each run writes to `/app/cost-evidence/cost-evidence-<timestamp>/`, inside the
mounted directory, so the files persist on the host under
`./cost-evidence/cost-evidence-<timestamp>/`. **Rebuild the image after updating
the collector scripts** (`docker build ...` above); an existing image still
contains the old scripts.

The image needs no Azure CLI extensions at all, and the collector sets
`AZURE_EXTENSION_USE_DYNAMIC_INSTALL=no` for every `az` call so nothing can be
auto-installed. Costs, Log Analytics queries and alerts go through core
`az rest`; `az monitor log-analytics query` is deliberately **not** used (it is
an auto-installing extension and timed out). The `az costmanagement query`
command from the original story does not exist in any CLI version.

### Option 2: Python script directly

```bash
python3 scripts/collect_cost_evidence.py
```

Prerequisites: `python3` (3.8+), `az`, and `psql` for the SQL evidence. No
third-party Python packages.

### Option 3: Bash wrapper

```bash
./scripts/collect_cost_evidence.sh
```

Identical behaviour: the wrapper only `exec`s `python3` on the sibling
`collect_cost_evidence.py` (so it needs the same prerequisites).

## What It Collects

All Phase 0 evidence per `docs/BACKLOG_STORIES/cost-evidence-collection-report.md`:

| # | Data | Output File |
|---|------|-------------|
| 1 | Cost by resource + meter (3 months) | `01-cost-by-resource-meter.json` |
| 2 | Cost by resource type | `01b-cost-by-resource-type.json` |
| 3 | Log Analytics billable GB/DataType (30d) | `02-log-analytics-billable-gb.json` |
| 4 | Top 10 Log Analytics tables | `02b-log-analytics-top-tables.json` |
| 5 | App Insights record counts (7d) | `03-app-insights-record-counts.json` |
| 6 | PostgreSQL diagnostic settings (drift) | `04-postgres-diagnostic-settings.json` |
| 7 | PostgreSQL Azure config (storage, SKU) | `05a-postgres-azure-config.json` |
| 8 | PostgreSQL DB size | `05b-postgres-db-size.txt` |
| 9 | Top 10 tables by size | `05c-postgres-top-tables.txt` |
| 10 | All indexes + scan counts | `05d-postgres-all-indexes.txt` |
| 11 | Stats reset timestamp | `05e-postgres-stats-reset.txt` |
| 12 | 90-day CPU % (3 × 30-day requests, merged) | `06-cpu_percent.json` |
| 13 | 90-day Memory % (3 × 30-day requests, merged) | `06-memory_percent.json` |
| 14 | 90-day Storage % (3 × 30-day requests, merged) | `06-storage_percent.json` |
| 15 | Alert instances for the resource group (30 days — Azure's retention) | `07-alert-firing-history.json` |
| 16 | Container Apps config | `08-container-apps-config.json` |
| 17 | Web tests config | `09-web-tests.json` |

Notes on the evidence:

- Azure Monitor keeps platform metrics for 93 days but answers at most 30 days per request (a single
  90-day request came back as ~31 days). Each `06-{metric}.json` is therefore three contiguous
  30-day `PT1H` requests that exactly cover the 90-day window, merged chronologically into the usual
  `data.value[].timeseries[].data[]` shape (shared boundary timestamps de-duplicated, UTC-sorted).
  The file also lists `chunks[]` (requested start/end, the `data.timespan` Azure returned, point
  counts) and `coverage`. The file is `success: false` — and `MANIFEST.json` records a failure — if any
  chunk fails, returns an empty/malformed body, a different metric/unit/interval/series set, or a
  `data.timespan` whose start or end is more than 1 hour from the request (truncated). Raw data of the
  chunks that did return is kept in the failed file. Empty buckets are never filled in;
  `coverage.fully_populated: false` marks null gaps (e.g. a server younger than 90 days), and a chunk
  with no populated sample at all fails.
- Log Analytics queries are `az rest` POSTs to
  `https://api.loganalytics.io/v1/workspaces/{id}/query` (audience
  `https://api.loganalytics.io`, `Prefer: wait=180`), per the
  [request format](https://learn.microsoft.com/azure/azure-monitor/logs/api/request-format).
  An HTTP 200 body containing `error` (partial failure) is treated as a failed
  collection, not as evidence. Each file records its `query` and `timespan`.
- App Insights is workspace-based, so counts come from `AppRequests`,
  `AppDependencies`, `AppTraces`, `AppMetrics`, `AppExceptions` and
  `AppAvailabilityResults` by `Type`. `Records` is the number of ingested rows.
- Alerts come from `Microsoft.AlertsManagement/alerts` (api-version
  `2019-03-01`, subscription scope filtered by `targetResourceGroup`,
  `timeRange=30d`, `nextLink` followed). Azure keeps alerts for only **30
  days**, so older firings cannot be recovered, and each item is an alert
  *instance* (current state), not a Fired/Resolved transition history. The
  limitation is written into the file even when the result is empty.
- Every `az` read call is retried when Azure throttles it (HTTP 429) or answers 503: up to 5
  attempts with exponential backoff (5, 10, 20, 40 s + jitter, 180 s total budget). `Retry-After`
  is honored when it appears in the CLI output (`az` usually shows only the status text). Permanent
  errors (400/401/403/404, KQL errors), timeouts and `az login` are not retried. A call that is
  still throttled fails with `still failing after N attempts` in `MANIFEST.json`; re-run later.
- The alerts `nextLink` Azure returns is absolute and includes `:443`
  (`https://management.azure.com:443/subscriptions/<sub>/providers/Microsoft.AlertsManagement/alerts?...&ctoken=...`).
  It is followed only if it is ARM https, this subscription's alerts list, and keeps the same
  `api-version`, `timeRange=30d` and `targetResourceGroup`. A refused link is recorded as
  `next_link_rejection` (reason, host, path, parameter names — never token values).

## Recurring Runs

### GitHub Actions (weekly) — configured at `.github/workflows/cost-evidence-weekly.yml`

Runs every Monday 06:00 UTC:

1. Builds the collector Docker image
2. Runs evidence collection against production Azure (`DATABASE_URL` is forwarded at runtime)
3. Uploads the evidence directory as a workflow artifact (also when collection failed, so partial evidence is not lost)
4. Commits new evidence to `cost-evidence/cost-evidence-<timestamp>/` — **only when the collection succeeded**
5. Cleans up directories older than 4 weeks
6. Fails the job when any collection failed

The collector exits non-zero when any collection fails; `MANIFEST.json` then has
`status: partial` plus per-file `failures`. Skipped optional steps (no
`DATABASE_URL`) give `status: complete_with_skips` and exit 0.

**Required repository secrets** (Settings → Secrets and variables → Actions):

| Secret | Description |
|--------|-------------|
| `AZURE_CLIENT_ID` | SP App ID from `create_cost_collection_spn.sh` |
| `AZURE_CLIENT_SECRET` | SP secret (shown once at creation) |
| `AZURE_TENANT_ID` | Azure AD tenant ID |
| `AZURE_SUBSCRIPTION_ID` | `f5bc5a63-92f8-4ab6-ad94-84673eeebb56` |
| `DATABASE_URL` | PostgreSQL connection string (optional, runtime-only, for SQL queries) |

**Manual trigger:** Actions → Weekly Cost Evidence Collection → Run workflow

### Local cron

```bash
# Add to crontab (weekly Mondays 6 AM)
0 6 * * 1 cd /path/to/repo && ./scripts/collect_cost_evidence.sh >> /var/log/bitb150-cost.log 2>&1
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| `apt-get: command not found` during `docker build` | Legacy image was based on `mcr.microsoft.com/azure-cli` (Azure Linux — no apt). Current Dockerfile builds on `python:3.12-slim`; pull the latest |
| `'costmanagement' is misspelled or not recognized` | You are running the story's original `az costmanagement query` — that command does not exist (the extension only ships `export` subcommands). Use the collectors, which call the Cost Management Query API via native `az rest` |
| `No extension found with name 'postgres'`/`'monitor'` | Legacy versions of these scripts tried to install non-existent extensions. Current versions need **zero** extensions and disable dynamic installs — rebuild the image |
| `ResourceNotFound` for `bible-app-mb0172` | Legacy hard-coded server name. The collector now discovers the server in the resource group; rebuild the image. If it reports several servers, set `POSTGRES_SERVER_NAME` |
| `resolve-postgres` / `resolve-workspace` in `failures` | Zero or several matches in the resource group, or the SP cannot list them. Read the message in `MANIFEST.json`, set the override env var, or check the SP's Reader roles |
| Logs query `Command timed out after 240s` or `PartialError` | The workspace query itself was too heavy or hit a service limit; the file records the exact `error`. Re-run later or narrow the query — the failure is surfaced, never silently written as evidence |
| `DATABASE_URL not set — skipped` | Export `DATABASE_URL` on the host and add `-e DATABASE_URL` to `docker run` (the weekly workflow already does) |
| `Too Many Requests` … `still failing after 5 attempts` | The Cost Management/ARM API stayed throttled through the bounded retries. Wait a few minutes and re-run; the Cost Management Query API has a small per-tenant quota, so avoid parallel runs |
| `07-alert-firing-history.json`: `refusing to follow unexpected nextLink (reason)` | Read `next_link_rejection` in the file (host, path, parameter names). A legitimate Azure link that is refused means the Alerts API changed shape — update `normalize_next_link` with evidence, do not relax it blindly |
| `az rest` returns `AuthorizationFailed` | The SP is missing **Cost Management Reader** on the resource group — re-run `create_cost_collection_spn.sh` |
| `az login` fails | Check SP credentials; ensure the secret hasn't expired (the script resets credentials for an existing SP) |
| `psql: connection failed` | Check `DATABASE_URL`; ensure your IP is allowed in the PG firewall (`client_ip` in `terraform.tfvars`) |
| KQL query returns empty | Verify the workspace ID; check the time range |
| `Permission denied` / `AuthorizationFailed` | A RBAC role is missing — re-run `create_cost_collection_spn.sh`, which verifies all six assignments |

## Output Structure

```
cost-evidence/cost-evidence-20261022-143000/
├── MANIFEST.json          # status, resolved resources, failures, skips, file list
├── 01-cost-by-resource-meter.json
├── 01b-cost-by-resource-type.json
├── 02-log-analytics-billable-gb.json
├── 02b-log-analytics-top-tables.json
├── 03-app-insights-record-counts.json
├── 04-postgres-diagnostic-settings.json
├── 05a-postgres-azure-config.json
├── 05b-postgres-db-size.txt
├── 05c-postgres-top-tables.txt
├── 05d-postgres-all-indexes.txt
├── 05e-postgres-stats-reset.txt
├── 06-cpu_percent.json
├── 06-memory_percent.json
├── 06-storage_percent.json
├── 07-alert-firing-history.json
├── 08-container-apps-config.json
└── 09-web-tests.json
```

Share the entire directory (zip/tar) for analysis, or let the weekly workflow
commit it to the repo.
