#!/usr/bin/env python3
"""
BITB-150 Phase 0 Cost Analysis — Automated Data Collection (Python)

Collects all Phase 0 cost evidence non-interactively. Every Azure call is a
core Azure CLI command (`az rest`, `az resource`, `az monitor metrics`,
`az monitor diagnostic-settings`, `az postgres flexible-server show`); the
collector never calls `az monitor log-analytics query`, because that command
belongs to an auto-installing extension and timed out in production runs.
The in-database queries use `psql`.

Usage:
    export AZURE_CLIENT_ID="..."
    export AZURE_CLIENT_SECRET="..."
    export AZURE_TENANT_ID="..."
    export AZURE_SUBSCRIPTION_ID="f5bc5a63-92f8-4ab6-ad94-84673eeebb56"
    export DATABASE_URL="postgresql://..."   # optional, for SQL queries
    python3 scripts/collect_cost_evidence.py

Optional overrides:
    AZURE_RESOURCE_GROUP         resource group to inspect (default bible-app-rg)
    POSTGRES_SERVER_NAME         flexible server name; required if the group holds several
    LOG_ANALYTICS_WORKSPACE_ID   workspace customer ID (GUID) or name; required if several

Output: ./cost-evidence/cost-evidence-<timestamp>/  (evidence files + MANIFEST.json)
Exit status is non-zero when any collection failed; MANIFEST.json records
every failure and skip. A skipped optional step (no DATABASE_URL) is not a failure.

Command inventory:
    costs            az rest -> Cost Management Query API
    resources        az resource list/show        (discovers Postgres + workspace)
    workspace KQL    az rest POST https://api.loganalytics.io/v1/workspaces/{id}/query
                     (https://learn.microsoft.com/azure/azure-monitor/logs/api/request-format)
    alerts           az rest GET Microsoft.AlertsManagement/alerts 2019-03-01 (30 days max)
    metrics          az monitor metrics list --metrics
    diag settings    az monitor diagnostic-settings list
    postgres config  az postgres flexible-server show
    container apps   az resource list/show
    web tests        az resource list/show
    sql              psql (read-only session, connection via PG* env vars)
"""

import json
import os
import random
import re
import subprocess
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, quote, unquote, urlsplit

# ─── Configuration ──────────────────────────────────────────────────────────
SUBSCRIPTION_ID = os.getenv("AZURE_SUBSCRIPTION_ID") or "f5bc5a63-92f8-4ab6-ad94-84673eeebb56"
RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP") or "bible-app-rg"
TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
OUTDIR = Path("cost-evidence") / f"cost-evidence-{TIMESTAMP}"

COST_API_VERSION = "2023-11-01"
POSTGRES_TYPE = "Microsoft.DBforPostgreSQL/flexibleServers"
WORKSPACE_TYPE = "Microsoft.OperationalInsights/workspaces"

LOGS_API = "https://api.loganalytics.io"
LOGS_WAIT_SECONDS = 180  # server-side Prefer: wait=
LOGS_CLI_TIMEOUT = LOGS_WAIT_SECONDS + 60  # subprocess must outlive the server wait

ALERTS_API_VERSION = "2019-03-01"
ALERTS_RETENTION_DAYS = 30  # https://learn.microsoft.com/azure/azure-monitor/alerts/alerts-overview
ALERTS_MAX_PAGES = 50
ARM_HOST = "management.azure.com"
# Query parameters the Alerts list nextLink is known to carry (observed live 2026-10-23).
ALERTS_LINK_PARAMS = frozenset(
    {"api-version", "timerange", "targetresourcegroup", "pagecount", "ctoken", "skiptoken"}
)
ALERTS_TOKEN_PARAMS = ("ctoken", "skiptoken")
ALERTS_MAX_LINK_LENGTH = 4096

# Bounded retry for throttled (429) / transient (503) read calls. Worst case waits
# ~THROTTLE_TOTAL_BUDGET seconds per command before reporting the failure.
THROTTLE_MAX_ATTEMPTS = 5
THROTTLE_BASE_DELAY = 5.0
THROTTLE_MAX_DELAY = 60.0
THROTTLE_TOTAL_BUDGET = 180.0
# `az` surfaces only the status text/code on stderr, so match those (never bare numbers).
TRANSIENT_ERROR_RE = re.compile(
    r"too many requests|toomanyrequests|service unavailable|\"code\"\s*:\s*\"?(?:429|503)\"?",
    re.IGNORECASE,
)
RETRY_AFTER_RE = re.compile(r"retry-after\W{1,5}(\d{1,5})\b", re.IGNORECASE)
_JITTER = random.SystemRandom()

TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
# Azure Monitor serves platform metrics for 93 days but returns at most 30 days per query
# (https://learn.microsoft.com/azure/azure-monitor/metrics/data-platform-metrics#retention-of-metrics),
# so a 90-day window is fetched as three contiguous requests.
METRICS_WINDOW_DAYS = 90
METRICS_CHUNK_DAYS = 30
METRICS_INTERVAL = "PT1H"
METRICS_TIMESPAN_TOLERANCE = timedelta(hours=1)  # bucket rounding in the returned timespan
METRIC_VALUE_KEYS = ("average", "maximum", "minimum", "total", "count")

PSQL_TIMEOUT = 120
PSQL_STATEMENT_TIMEOUT_MS = 60000
PSQL_CONNECT_TIMEOUT = "15"
PSQL_URL_PARAMS = {"sslmode": "PGSSLMODE", "sslrootcert": "PGSSLROOTCERT"}

SQL_FILES = (
    "05b-postgres-db-size.txt",
    "05c-postgres-top-tables.txt",
    "05d-postgres-all-indexes.txt",
    "05e-postgres-stats-reset.txt",
)

USAGE_KQL = (
    "Usage "
    "| where TimeGenerated > ago(30d) and IsBillable == true "
    "| summarize TotalGB = sum(Quantity) / 1000 by DataType "
    "| order by TotalGB desc"
)

# Workspace-based Application Insights tables (not the classic requests/itemType schema).
APP_INSIGHTS_KQL = (
    "union isfuzzy=true AppRequests, AppDependencies, AppTraces, AppMetrics, "
    "AppExceptions, AppAvailabilityResults "
    "| where TimeGenerated > ago(7d) "
    "| summarize Records = count() by Type "
    "| order by Records desc"
)


# ─── Report ─────────────────────────────────────────────────────────────────


class Report:
    """Tracks the outcome of every collection so the run can fail loudly."""

    def __init__(self) -> None:
        self.checks: Dict[str, Dict[str, str]] = {}
        self.resolved: Dict[str, Any] = {}

    def ok(self, name: str) -> None:
        self.checks[name] = {"status": "ok"}

    def fail(self, name: str, error: str) -> None:
        self.checks[name] = {"status": "failed", "error": str(error)[:500]}

    def skip(self, name: str, reason: str) -> None:
        self.checks[name] = {"status": "skipped", "reason": reason}

    def names(self, status: str) -> List[str]:
        return sorted(n for n, c in self.checks.items() if c["status"] == status)

    @property
    def failures(self) -> List[str]:
        return self.names("failed")

    @property
    def skipped(self) -> List[str]:
        return self.names("skipped")

    @property
    def status(self) -> str:
        if self.failures:
            return "partial"
        return "complete_with_skips" if self.skipped else "complete"


def record(report: Report, name: str, result: Dict[str, Any]) -> None:
    if result.get("success"):
        report.ok(name)
    else:
        report.fail(name, result.get("error", "unknown error"))


# ─── Helpers ────────────────────────────────────────────────────────────────


def _secret_values() -> List[str]:
    values: set[str] = set()
    secret = os.getenv("AZURE_CLIENT_SECRET")
    url = os.getenv("DATABASE_URL")
    for value in (secret, url):
        if value:
            values.update((value, quote(value, safe="")))
    if url:
        try:
            password = urlsplit(url).password
        except ValueError:
            password = None
        if password:
            values.update((password, unquote(password), quote(unquote(password), safe="")))
    return sorted((v for v in values if len(v) >= 4), key=len, reverse=True)


def redact(text: str) -> str:
    """Mask credentials so they never reach evidence files, logs or the manifest."""
    for value in _secret_values():
        text = text.replace(value, "***")
    return text


def cli_env() -> Dict[str, str]:
    """Subprocess env that forbids `az` from installing extensions on the fly."""
    env = dict(os.environ)
    env["AZURE_EXTENSION_USE_DYNAMIC_INSTALL"] = "no"
    return env


def backoff_delay(attempt: int, retry_after: Optional[int] = None) -> float:
    """Exponential delay (capped) plus jitter; a server Retry-After replaces the exponent."""
    base = (
        float(retry_after) if retry_after is not None else THROTTLE_BASE_DELAY * 2 ** (attempt - 1)
    )
    return min(THROTTLE_MAX_DELAY, base) + _JITTER.uniform(0, THROTTLE_BASE_DELAY / 2)


def run_cli(cmd: List[str], timeout: int = 180, retry_throttled: bool = True) -> Dict[str, Any]:
    """Run an Azure CLI command; throttled (429) and 503 failures are retried a
    bounded number of times with backoff. Permanent errors, timeouts and
    commands called with retry_throttled=False (login) are never retried."""
    attempt = 1
    waited = 0.0
    while True:
        result = _run_cli_once(cmd, timeout)
        if result["success"] or not retry_throttled:
            break
        if not TRANSIENT_ERROR_RE.search(result["error"]):
            break
        match = RETRY_AFTER_RE.search(result["error"])
        retry_after = int(match.group(1)) if match else None
        delay = backoff_delay(attempt, retry_after)
        if (
            attempt >= THROTTLE_MAX_ATTEMPTS
            or (retry_after is not None and retry_after > THROTTLE_MAX_DELAY)
            or waited + delay > THROTTLE_TOTAL_BUDGET
        ):
            break
        print(f"  throttled; retry {attempt + 1}/{THROTTLE_MAX_ATTEMPTS} in {delay:.0f}s")
        time.sleep(delay)
        waited += delay
        attempt += 1
    if attempt > 1:
        result["attempts"] = attempt
        if not result["success"]:
            result["error"] += f" [still failing after {attempt} attempts, waited {waited:.0f}s]"
    return result


def _run_cli_once(cmd: List[str], timeout: int) -> Dict[str, Any]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=cli_env())
    except subprocess.TimeoutExpired:
        # Not str(e): TimeoutExpired renders the full command, credentials included.
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": redact(f"{type(e).__name__}: {e}")}
    if result.returncode == 0:
        try:
            return {"success": True, "data": json.loads(result.stdout)}
        except json.JSONDecodeError:
            return {"success": True, "data": result.stdout.strip()}
    error = result.stderr.strip() or f"exit code {result.returncode}"
    return {"success": False, "error": redact(error)}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def write_text(path: Path, text: str) -> None:
    with open(path, "w") as f:
        f.write(text)


def safe_name(name: str) -> str:
    return name.replace("/", "_")


def cost_window() -> Dict[str, str]:
    """Last 3 FULL months, inclusive end. Recomputed at every run so weekly
    reruns stay meaningful (the story's 2026-07-01..2026-09-01 window was the
    initial snapshot only)."""
    today = datetime.now(timezone.utc).date()
    first_of_this_month = today.replace(day=1)
    m = first_of_this_month.month - 3
    y = first_of_this_month.year
    while m <= 0:
        m += 12
        y -= 1
    return {
        "from": f"{y:04d}-{m:02d}-01",
        "to": (first_of_this_month - timedelta(days=1)).isoformat(),
    }


def metrics_window(now: Optional[datetime] = None) -> Dict[str, str]:
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    return {
        "start": (now - timedelta(days=METRICS_WINDOW_DAYS)).strftime(TIME_FORMAT),
        "end": now.strftime(TIME_FORMAT),
    }


def cost_query_body(window: Dict[str, str], groupings: List[Dict[str, str]]) -> str:
    return json.dumps(
        {
            "type": "ActualCost",
            "timeframe": "Custom",
            "timePeriod": {"from": window["from"], "to": window["to"]},
            "dataset": {
                "granularity": "Monthly",
                "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                "grouping": groupings,
            },
        }
    )


# ─── Resource discovery ─────────────────────────────────────────────────────


def list_resources(resource_type: str) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    result = run_cli(
        [
            "az", "resource", "list",
            "--resource-group", RESOURCE_GROUP,
            "--resource-type", resource_type,
            "--output", "json",
        ]
    )  # fmt: skip
    if not result["success"]:
        return None, result["error"]
    if not isinstance(result["data"], list):
        return None, "unexpected output from `az resource list`"
    return result["data"], None


def select_resource(
    candidates: List[Dict[str, Any]], label: str, override: Optional[str], override_env: str
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Pick exactly one resource; never fall back to "the first one"."""
    names = sorted(c.get("name", "") for c in candidates)
    if override:
        matches = [c for c in candidates if c.get("name", "").lower() == override.lower()]
        if len(matches) == 1:
            return matches[0], None
        return None, (
            f"{override_env} does not match any {label} in resource group "
            f"{RESOURCE_GROUP} (found: {', '.join(names) or 'none'})"
        )
    if len(candidates) == 1:
        return candidates[0], None
    if not candidates:
        return None, f"no {label} found in resource group {RESOURCE_GROUP}"
    return None, (
        f"{len(candidates)} {label}s found in resource group {RESOURCE_GROUP} "
        f"({', '.join(names)}); set {override_env} to choose one"
    )


def resolve_postgres() -> Dict[str, Any]:
    servers, error = list_resources(POSTGRES_TYPE)
    if error:
        return {"error": error}
    server, error = select_resource(
        servers or [],
        "PostgreSQL flexible server",
        os.getenv("POSTGRES_SERVER_NAME"),
        "POSTGRES_SERVER_NAME",
    )
    if error or not server:
        return {"error": error or "no server selected"}
    if not server.get("id") or not server.get("name"):
        return {"error": "discovered PostgreSQL server has no name/id"}
    # Keep the ARM ID exactly as Azure returned it (casing included).
    return {"name": server["name"], "id": server["id"]}


def workspace_customer_id(workspace: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    result = run_cli(
        [
            "az", "resource", "show", "--ids", workspace["id"],
            "--query", "properties.customerId", "--output", "json",
        ]
    )  # fmt: skip
    if not result["success"]:
        return None, result["error"]
    try:
        return str(uuid.UUID(str(result["data"]))), None
    except ValueError:
        return None, "workspace customerId is not a GUID"


def resolve_workspace() -> Dict[str, Any]:
    workspaces, error = list_resources(WORKSPACE_TYPE)
    if error:
        return {"error": error}
    workspaces = workspaces or []
    override = (os.getenv("LOG_ANALYTICS_WORKSPACE_ID") or "").strip()
    if override:
        matches = []
        for ws in workspaces:
            customer_id, error = workspace_customer_id(ws)
            if error:
                return {"error": error}
            if override.lower() in (str(customer_id).lower(), ws.get("name", "").lower()):
                matches.append((ws, customer_id))
        if len(matches) != 1:
            names = ", ".join(sorted(w.get("name", "") for w in workspaces)) or "none"
            return {
                "error": "LOG_ANALYTICS_WORKSPACE_ID does not match exactly one workspace "
                f"in resource group {RESOURCE_GROUP} (found: {names})"
            }
        workspace, customer_id = matches[0]
    else:
        selected, error = select_resource(
            workspaces, "Log Analytics workspace", None, "LOG_ANALYTICS_WORKSPACE_ID"
        )
        if error or not selected:
            return {"error": error or "no workspace selected"}
        workspace = selected
        customer_id, error = workspace_customer_id(workspace)
        if error:
            return {"error": error}
    return {"name": workspace.get("name"), "id": workspace.get("id"), "customer_id": customer_id}


def unresolved(outdir: Path, report: Report, files: List[str], key: str) -> None:
    """Record evidence files that cannot be collected because discovery failed."""
    error = (report.resolved.get(key) or {}).get("error", f"{key} was not resolved")
    for name in files:
        payload = {"success": False, "error": f"{key} unresolved: {error}"}
        if name.endswith(".txt"):
            write_text(outdir / name, f"ERROR: {payload['error']}")
        else:
            write_json(outdir / name, payload)
        report.skip(name, f"{key} unresolved (see the resolution failure)")


# ─── Log Analytics (native az rest) ─────────────────────────────────────────


def run_logs_query(workspace_id: str, query: str, timespan: str) -> Dict[str, Any]:
    """POST a KQL query to the Logs query API. HTTP 200 bodies carrying an
    `error` (partial failure) are reported as failures, not as evidence."""
    try:
        workspace_id = str(uuid.UUID(workspace_id))
    except ValueError:
        return {"success": False, "error": "invalid Log Analytics workspace ID"}
    result = run_cli(
        [
            "az", "rest", "--method", "post",
            "--uri", f"{LOGS_API}/v1/workspaces/{workspace_id}/query",
            "--resource", LOGS_API,
            "--headers", "Content-Type=application/json", f"Prefer=wait={LOGS_WAIT_SECONDS}",
            "--body", json.dumps({"query": query, "timespan": timespan}),
        ],
        timeout=LOGS_CLI_TIMEOUT,
    )  # fmt: skip
    if not result["success"]:
        return result
    data = result["data"]
    if not isinstance(data, dict):
        return {"success": False, "error": "unexpected non-JSON Logs query response"}
    if data.get("error"):
        error = data["error"]
        if isinstance(error, dict):
            error = f"{error.get('code', 'Error')}: {error.get('message', '')}"
        return {"success": False, "error": str(error), "partial_response": data}
    if not isinstance(data.get("tables"), list):
        return {"success": False, "error": "Logs query response has no tables"}
    return {"success": True, "data": data}


def logs_evidence(
    outdir: Path, report: Report, ws_id: str, name: str, query: str, timespan: str
) -> None:
    result = run_logs_query(ws_id, query, timespan)
    write_json(outdir / name, {"query": query, "timespan": timespan, **result})
    record(report, name, result)


# ─── Collections ────────────────────────────────────────────────────────────


def collect_cost_management(outdir: Path, report: Report) -> None:
    """1. Cost Management Query API (native `az rest` — the CLI extension has
    no `query` subcommand, so this is the only supported CLI path)."""
    print("[1/10] Collecting Cost Management data (3 full months)...")
    window = cost_window()
    print(f"  window: {window['from']} .. {window['to']}")

    uri = (
        f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}"
        f"/providers/Microsoft.CostManagement/query?api-version={COST_API_VERSION}"
    )
    queries = (
        ("01-cost-by-resource-meter.json", [
            {"name": "ResourceId", "type": "Dimension"},
            {"name": "MeterSubCategory", "type": "Dimension"},
        ]),
        ("01b-cost-by-resource-type.json", [{"name": "ResourceType", "type": "Dimension"}]),
    )  # fmt: skip
    for name, groupings in queries:
        result = run_cli(
            [
                "az", "rest", "--method", "post", "--uri", uri,
                "--body", cost_query_body(window, groupings),
            ]
        )  # fmt: skip
        write_json(outdir / name, {"window": window, **result})
        record(report, name, result)


def collect_log_analytics(outdir: Path, report: Report) -> None:
    """2. Billable GB per DataType (30 days) from the Usage table."""
    print("[2/10] Querying Log Analytics usage...")
    files = ["02-log-analytics-billable-gb.json", "02b-log-analytics-top-tables.json"]
    workspace = report.resolved.get("workspace") or {}
    if "customer_id" not in workspace:
        unresolved(outdir, report, files, "workspace")
        return
    print(f"  workspace: {workspace.get('name')}")
    logs_evidence(outdir, report, workspace["customer_id"], files[0], USAGE_KQL, "P30D")
    logs_evidence(
        outdir, report, workspace["customer_id"], files[1], USAGE_KQL + " | limit 10", "P30D"
    )


def collect_app_insights(outdir: Path, report: Report) -> None:
    """3. Ingested record counts by Type (7 days). App Insights is
    workspace-based (deployment/main.tf sets workspace_id), so its data lives
    in the App* tables of the Log Analytics workspace. `Records` counts
    ingested rows, which is what drives ingestion cost."""
    print("[3/10] Querying App Insights record counts...")
    name = "03-app-insights-record-counts.json"
    workspace = report.resolved.get("workspace") or {}
    if "customer_id" not in workspace:
        unresolved(outdir, report, [name], "workspace")
        return
    logs_evidence(outdir, report, workspace["customer_id"], name, APP_INSIGHTS_KQL, "P7D")


def collect_postgres_diagnostic_settings(outdir: Path, report: Report) -> None:
    """4. PostgreSQL diagnostic settings (drift check)."""
    print("[4/10] Checking PostgreSQL diagnostic settings...")
    name = "04-postgres-diagnostic-settings.json"
    server = report.resolved.get("postgres") or {}
    if "id" not in server:
        unresolved(outdir, report, [name], "postgres")
        return
    result = run_cli(
        ["az", "monitor", "diagnostic-settings", "list", "--resource", server["id"],
         "--output", "json"]
    )  # fmt: skip
    write_json(outdir / name, result)
    record(report, name, result)


def collect_postgres_azure_config(outdir: Path, report: Report) -> None:
    """5a. PostgreSQL Azure-level config (provisioned storage, SKU)."""
    print("[5/10] Collecting PostgreSQL Azure config...")
    name = "05a-postgres-azure-config.json"
    server = report.resolved.get("postgres") or {}
    if "id" not in server:
        unresolved(outdir, report, [name], "postgres")
        return
    result = run_cli(
        [
            "az", "postgres", "flexible-server", "show", "--ids", server["id"],
            "--query", "{storage:storage.storageSizeGb, tier:sku.tier, sku:sku.name, iops:storage.iops}",
            "--output", "json",
        ]
    )  # fmt: skip
    write_json(outdir / name, result)
    record(report, name, result)


def psql_env(database_url: str) -> Dict[str, str]:
    """Child env for psql: the URL is split into PG* variables so that neither
    the URL nor the password ever appears on a command line. Raises ValueError
    with a message that does not echo any part of the URL."""
    invalid = ValueError("DATABASE_URL is not a valid postgresql:// URL")
    try:
        parts = urlsplit(database_url)
        port = parts.port
        params = parse_qsl(parts.query, keep_blank_values=True)
    except ValueError:
        raise invalid from None
    if parts.scheme not in ("postgresql", "postgres") or not parts.hostname:
        raise invalid
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("PG") and k not in ("DATABASE_URL", "AZURE_CLIENT_SECRET")
    }
    env["PGHOST"] = parts.hostname
    if port:
        env["PGPORT"] = str(port)
    if parts.username:
        env["PGUSER"] = unquote(parts.username)
    if parts.password:
        env["PGPASSWORD"] = unquote(parts.password)
    database = unquote(parts.path.lstrip("/"))
    if database:
        env["PGDATABASE"] = database
    for key, value in params:
        if key not in PSQL_URL_PARAMS:
            raise ValueError(
                "DATABASE_URL has an unsupported query parameter "
                f"(supported: {', '.join(sorted(PSQL_URL_PARAMS))})"
            )
        env[PSQL_URL_PARAMS[key]] = value
    env["PGCONNECT_TIMEOUT"] = PSQL_CONNECT_TIMEOUT
    env["PGAPPNAME"] = "bitb150-cost-collector"
    env["PGOPTIONS"] = (
        "-c default_transaction_read_only=on " f"-c statement_timeout={PSQL_STATEMENT_TIMEOUT_MS}"
    )
    return env


def collect_postgres_sql(outdir: Path, report: Report) -> None:
    """5b-e. In-database evidence via psql (requires DATABASE_URL at runtime)."""
    print("[6/10] Running PostgreSQL SQL queries...")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        message = (
            "DATABASE_URL not set — skipped. Export it on the host and pass it with "
            "`docker run -e DATABASE_URL` to collect in-database evidence."
        )
        print(f"  WARNING: {message}")
        for name in SQL_FILES:
            write_text(outdir / name, message)
            report.skip(name, "DATABASE_URL not set")
        return

    try:
        env = psql_env(database_url)
    except ValueError as e:
        for name in SQL_FILES:
            write_text(outdir / name, f"ERROR: {e}")
            report.fail(name, str(e))
        return

    queries = {
        "05b-postgres-db-size.txt":
            "SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size;",
        "05c-postgres-top-tables.txt": (
            "SELECT relname, "
            "pg_size_pretty(pg_total_relation_size(relid)) AS total, "
            "pg_size_pretty(pg_indexes_size(relid)) AS indexes "
            "FROM pg_catalog.pg_statio_user_tables "
            "ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;"
        ),
        "05d-postgres-all-indexes.txt": (
            "SELECT indexrelname, idx_scan, pg_size_pretty(pg_relation_size(indexrelid)) AS size "
            "FROM pg_stat_user_indexes "
            "ORDER BY pg_relation_size(indexrelid) DESC;"
        ),
        "05e-postgres-stats-reset.txt":
            "SELECT stats_reset FROM pg_stat_database WHERE datname = current_database();",
    }  # fmt: skip

    for filename, query in queries.items():
        try:
            result = subprocess.run(
                ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-c", query],
                capture_output=True, text=True, timeout=PSQL_TIMEOUT, env=env,
            )  # fmt: skip
        except subprocess.TimeoutExpired:
            error = f"psql timed out after {PSQL_TIMEOUT}s"
        except Exception as e:  # noqa: BLE001
            error = redact(f"{type(e).__name__}: {e}")
        else:
            if result.returncode == 0:
                write_text(outdir / filename, result.stdout)
                report.ok(filename)
                continue
            error = redact(result.stderr.strip() or f"psql exit code {result.returncode}")
        write_text(outdir / filename, f"ERROR: {error}")
        report.fail(filename, error)


class MetricsError(ValueError):
    """A metrics response cannot be trusted as evidence for the window it was asked for."""


SeriesKey = Tuple[Tuple[str, str], ...]


@dataclass
class MetricChunk:
    actual: str
    data: Dict[str, Any]
    entry: Dict[str, Any]
    identity: Tuple[Any, ...]
    interval: Optional[str]
    series: Dict[SeriesKey, Dict[datetime, Dict[str, Any]]]
    meta: Dict[SeriesKey, Dict[str, Any]]
    points: int
    populated: int


def parse_utc(text: Any) -> datetime:
    """Timezone-aware timestamp -> UTC; naive or unparseable values are rejected."""
    if not isinstance(text, str):
        raise MetricsError(f"timestamp {_printable(repr(text))} is not a string")
    try:
        parsed = datetime.fromisoformat(text.strip())
    except ValueError:
        raise MetricsError(f"unparseable timestamp {_printable(text)}") from None
    if parsed.tzinfo is None:
        raise MetricsError(f"timestamp {_printable(text)} has no timezone")
    return parsed.astimezone(timezone.utc)


def metrics_chunks(window: Dict[str, str]) -> List[Dict[str, str]]:
    """Split the window into contiguous requests of at most METRICS_CHUNK_DAYS."""
    cursor, end = parse_utc(window["start"]), parse_utc(window["end"])
    step = timedelta(days=METRICS_CHUNK_DAYS)
    chunks = []
    while cursor < end:
        stop = min(cursor + step, end)
        chunks.append({"start": cursor.strftime(TIME_FORMAT), "end": stop.strftime(TIME_FORMAT)})
        cursor = stop
    return chunks


def check_returned_timespan(requested: Dict[str, str], data: Dict[str, Any]) -> str:
    """Azure may truncate a request; the returned data.timespan is the only proof of coverage."""
    actual = data.get("timespan")
    if not isinstance(actual, str) or actual.count("/") != 1:
        raise MetricsError("data.timespan missing or malformed")
    got_start, got_end = (parse_utc(part) for part in actual.split("/"))
    for label, got, want in (
        ("start", got_start, parse_utc(requested["start"])),
        ("end", got_end, parse_utc(requested["end"])),
    ):
        if abs(got - want) > METRICS_TIMESPAN_TOLERANCE:
            raise MetricsError(
                f"returned timespan {_printable(actual, 60)} {label} is more than 1h from the "
                f"requested {requested['start']}/{requested['end']} (truncated or shifted)"
            )
    return actual


def metric_values(point: Dict[str, Any]) -> Tuple[Any, ...]:
    return tuple(point.get(key) for key in METRIC_VALUE_KEYS)


def is_populated(point: Dict[str, Any]) -> bool:
    return any(value is not None for value in metric_values(point))


def series_key(metadata: Any) -> SeriesKey:
    if metadata is None:
        return ()
    if not isinstance(metadata, list):
        raise MetricsError("timeseries.metadatavalues is not a list")
    pairs = []
    for item in metadata:
        label = item.get("name") if isinstance(item, dict) else None
        if not isinstance(label, dict) or not isinstance(label.get("value"), str):
            raise MetricsError("malformed timeseries.metadatavalues entry")
        pairs.append((label["value"].lower(), str(item.get("value"))))
    return tuple(sorted(pairs))


def parse_metric_chunk(metric: str, requested: Dict[str, str], data: Any) -> MetricChunk:
    """Validate one response; anything ambiguous is rejected rather than repaired."""
    if not isinstance(data, dict):
        raise MetricsError("response body is not a JSON object")
    actual = check_returned_timespan(requested, data)
    interval = data.get("interval")
    if interval is not None and interval != METRICS_INTERVAL:
        raise MetricsError(f"returned interval {_printable(str(interval), 20)}, not the requested")
    values = data.get("value")
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
        raise MetricsError("expected exactly one metric in data.value")
    entry = values[0]
    label = entry.get("name")
    name = label.get("value") if isinstance(label, dict) else None
    if not isinstance(name, str) or name.lower() != metric.lower():
        raise MetricsError(f"data.value holds a different metric than requested ({metric})")
    if entry.get("errorCode") not in (None, "Success"):
        raise MetricsError(f"metric errorCode {_printable(str(entry.get('errorCode')), 40)}")
    timeseries = entry.get("timeseries")
    if not isinstance(timeseries, list) or not timeseries:
        raise MetricsError("empty result: no timeseries")

    low = parse_utc(requested["start"]) - METRICS_TIMESPAN_TOLERANCE
    high = parse_utc(requested["end"]) + METRICS_TIMESPAN_TOLERANCE
    series: Dict[SeriesKey, Dict[datetime, Dict[str, Any]]] = {}
    meta: Dict[SeriesKey, Dict[str, Any]] = {}
    points = populated = 0
    for item in timeseries:
        if not isinstance(item, dict) or not isinstance(item.get("data"), list):
            raise MetricsError("malformed timeseries entry")
        key = series_key(item.get("metadatavalues"))
        if key in series:
            raise MetricsError("duplicate timeseries identity in one response")
        rows: Dict[datetime, Dict[str, Any]] = {}
        for point in item["data"]:
            if not isinstance(point, dict):
                raise MetricsError("malformed data point")
            when = parse_utc(point.get("timeStamp"))
            if not low <= when <= high:
                raise MetricsError(
                    f"data point {_printable(str(point['timeStamp']))} outside chunk"
                )
            if when in rows:
                raise MetricsError(f"duplicate timestamp {when.isoformat()} in one series")
            rows[when] = point
            points += 1
            populated += is_populated(point)
        series[key] = rows
        meta[key] = {k: v for k, v in item.items() if k != "data"}
    if not populated:
        raise MetricsError("no populated samples in chunk")
    return MetricChunk(
        actual=actual,
        data=data,
        entry=entry,
        identity=(entry.get("id"), name.lower(), entry.get("unit")),
        interval=interval,
        series=series,
        meta=meta,
        points=points,
        populated=populated,
    )


def merge_metric_chunks(chunks: List[MetricChunk]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Merge chronologically ordered chunks into one response-shaped body (+ coverage).
    Different metric/unit/interval/series sets or conflicting boundary values are rejected."""
    first, last = chunks[0], chunks[-1]
    for chunk in chunks[1:]:
        if chunk.identity != first.identity or chunk.interval != first.interval:
            raise MetricsError("chunks describe different metrics, units or intervals")
        if set(chunk.series) != set(first.series):
            raise MetricsError("chunks contain different timeseries")

    removed = 0
    merged_series = []
    total = populated = 0
    populated_times: List[datetime] = []
    for key in first.series:
        merged: Dict[datetime, Dict[str, Any]] = {}
        for chunk in chunks:
            for when, point in chunk.series[key].items():
                have = merged.get(when)
                if have is None:
                    merged[when] = point
                    continue
                removed += 1
                if metric_values(have) == metric_values(point) or not is_populated(point):
                    continue
                if is_populated(have):
                    raise MetricsError(f"conflicting values for one instant {when.isoformat()}")
                merged[when] = point
        rows = [merged[when] for when in sorted(merged)]
        total += len(rows)
        populated_times += [when for when in sorted(merged) if is_populated(merged[when])]
        populated += sum(is_populated(row) for row in rows)
        merged_series.append({**first.meta[key], "data": rows})

    timespan = f"{first.actual.split('/')[0]}/{last.actual.split('/')[1]}"
    data = {k: v for k, v in first.data.items() if k not in ("value", "timespan", "cost")}
    data["timespan"] = timespan
    data["value"] = [{**first.entry, "timeseries": merged_series}]
    coverage = {
        "actual_timespan": timespan,
        "points": total,
        "populated_points": populated,
        "fully_populated": total == populated,
        "first_populated": min(populated_times).isoformat() if populated_times else None,
        "last_populated": max(populated_times).isoformat() if populated_times else None,
        "duplicates_removed": removed,
    }
    return data, coverage


def fetch_metric(metric: str, resource_id: str, window: Dict[str, str]) -> Dict[str, Any]:
    """One metric over the window as ordered 30-day requests; success only if every
    request covered its chunk and the merge is unambiguous."""
    requests = metrics_chunks(window)
    summaries: List[Dict[str, Any]] = []
    parsed: List[MetricChunk] = []
    errors: List[str] = []
    for index, requested in enumerate(requests, 1):
        result = run_cli(
            [
                "az", "monitor", "metrics", "list",
                "--resource", resource_id,
                "--metrics", metric,
                "--interval", METRICS_INTERVAL,
                "--start-time", requested["start"],
                "--end-time", requested["end"],
                "--aggregation", "Average", "Maximum",
                "--output", "json",
            ],
            timeout=300,
        )  # fmt: skip
        summary: Dict[str, Any] = {
            "index": index,
            "requested": requested,
            "actual_timespan": None,
            "success": False,
            "points": 0,
            "populated_points": 0,
        }
        if "attempts" in result:
            summary["attempts"] = result["attempts"]
        error = result.get("error", "unknown error")
        if result["success"]:
            body = result.get("data")
            summary["raw"] = body
            if isinstance(body, dict) and isinstance(body.get("timespan"), str):
                summary["actual_timespan"] = body["timespan"][:80]
            try:
                chunk = parse_metric_chunk(metric, requested, body)
            except MetricsError as e:
                error = str(e)
            else:
                parsed.append(chunk)
                summary.update(success=True, points=chunk.points, populated_points=chunk.populated)
                error = ""
        if error:
            summary["error"] = error
            errors.append(f"chunk {index}/{len(requests)}: {error}")
        summaries.append(summary)
        time.sleep(0.5)  # be nice to the API

    evidence: Dict[str, Any] = {"window": window, "chunk_days": METRICS_CHUNK_DAYS}
    merged: Optional[Dict[str, Any]] = None
    if not errors:
        try:
            merged, coverage = merge_metric_chunks(parsed)
        except MetricsError as e:
            errors.append(f"merge: {e}")
    if merged is not None:
        for summary in summaries:
            del summary["raw"]  # the merged body already carries it
        evidence.update(success=True, chunks=summaries, coverage=coverage, data=merged)
    else:
        for summary in summaries:  # keep whatever Azure returned as partial evidence
            if "raw" in summary:
                summary["data"] = summary.pop("raw")
        evidence.update(
            success=False,
            error="; ".join(errors),
            chunks=summaries,
            coverage={"chunks_succeeded": len(parsed), "chunks_requested": len(requests)},
        )
    return evidence


def collect_postgres_metrics(outdir: Path, report: Report) -> None:
    """6. 90-day CPU/Memory/Storage utilisation (note the --metrics flag,
    plural — verified against the CLI reference). Azure answers at most 30 days
    per request, so each metric is three contiguous 30-day requests."""
    print("[7/10] Collecting PostgreSQL utilisation metrics (90 days, 3 x 30-day requests)...")
    metrics = ("cpu_percent", "memory_percent", "storage_percent")
    server = report.resolved.get("postgres") or {}
    if "id" not in server:
        unresolved(outdir, report, [f"06-{m}.json" for m in metrics], "postgres")
        return
    window = metrics_window()

    for metric in metrics:
        print(f"  fetching {metric}...")
        result = fetch_metric(metric, server["id"], window)
        name = f"06-{metric}.json"
        write_json(outdir / name, result)
        record(report, name, result)


def alerts_uri() -> str:
    return (
        f"{alerts_path()}"
        f"?api-version={ALERTS_API_VERSION}&timeRange={ALERTS_RETENTION_DAYS}d"
        f"&targetResourceGroup={quote(RESOURCE_GROUP, safe='')}&pageCount=100"
    )


def alerts_path() -> str:
    return f"/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.AlertsManagement/alerts"


def _printable(text: str, limit: int = 80) -> str:
    return "".join(c if 32 < ord(c) < 127 else "?" for c in text)[:limit]


def normalize_next_link(link: Any) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Validate an Alerts `nextLink` and return (accepted, rejection).

    Azure returns an absolute https link that includes the default port, e.g.
    `https://management.azure.com:443/subscriptions/<sub>/providers/
    Microsoft.AlertsManagement/alerts?api-version=..&timeRange=..&
    targetResourceGroup=..&pageCount=..&ctoken=..` (verified live). Relative ARM
    paths are accepted too (the first request uses one). Anything else - other
    host/scheme/userinfo/port, fragment, other path, other subscription, widened
    scope or retention - is rejected. `accepted` holds the canonical absolute
    request `uri` and a loop-detection `key`; `rejection` holds a reason and
    secret-free diagnostics (host/path/query parameter names, never values).
    """
    diag: Dict[str, Any] = {}

    def reject(reason: str) -> Tuple[None, Dict[str, Any]]:
        return None, {"reason": reason, **diag}

    if not isinstance(link, str) or not link:
        return reject("nextLink is not a non-empty string")
    if len(link) > ALERTS_MAX_LINK_LENGTH:
        return reject("nextLink is too long")
    if any(ord(c) <= 32 or ord(c) >= 127 or c == "\\" for c in link):
        return reject("nextLink contains whitespace, control, non-ASCII or backslash characters")
    try:
        parts = urlsplit(link)
        port = parts.port
    except ValueError:
        return reject("nextLink is not a parseable URL")
    diag.update(
        host=_printable(parts.hostname or ""),
        path=_printable(parts.path, 200),
        query_param_names=[_printable(k, 40) for k, _ in parse_qsl(parts.query, True)][:20],
    )
    if parts.netloc or parts.scheme:
        if parts.scheme.lower() != "https" or not parts.netloc:
            return reject("nextLink scheme must be https")
        if "@" in parts.netloc:
            return reject("nextLink has userinfo")
        if (parts.hostname or "").lower() != ARM_HOST:
            return reject(f"nextLink host is not {ARM_HOST}")
        if port not in (None, 443):
            return reject("nextLink port is not 443")
    elif not parts.path.startswith("/") or parts.path.startswith("//"):
        return reject("relative nextLink must be a single-slash absolute path")
    if parts.fragment:
        return reject("nextLink has a fragment")
    if parts.path.lower() != alerts_path().lower():
        return reject("nextLink path is not this subscription's alerts list")

    params: Dict[str, str] = {}
    for raw in parts.query.split("&"):
        name, _, value = raw.partition("=")
        key = unquote(name).lower()
        if key not in ALERTS_LINK_PARAMS:
            return reject("nextLink has an unexpected query parameter")
        if key in params:
            return reject("nextLink repeats a query parameter")
        params[key] = unquote(value)
    if params.get("api-version") != ALERTS_API_VERSION:
        return reject("nextLink api-version differs from the first request")
    if params.get("timerange", "").lower() != f"{ALERTS_RETENTION_DAYS}d":
        return reject("nextLink timeRange differs from the first request")
    if params.get("targetresourcegroup", "").lower() != RESOURCE_GROUP.lower():
        return reject("nextLink targetResourceGroup differs from the first request")
    if "pagecount" in params and not params["pagecount"].isdigit():
        return reject("nextLink pageCount is not numeric")
    if not any(params.get(t) for t in ALERTS_TOKEN_PARAMS):
        return reject("nextLink carries no continuation token")

    # Only the continuation token is case-sensitive; scope values compare case-insensitively.
    link_key = tuple(
        sorted((k, v if k in ALERTS_TOKEN_PARAMS else v.lower()) for k, v in params.items())
    )
    return {"uri": f"https://{ARM_HOST}{alerts_path()}?{parts.query}", "key": link_key}, None


def summarize_alerts(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    instances = []
    counts: Counter = Counter()
    for item in items:
        essentials = (item.get("properties") or {}).get("essentials") or {}
        rule = essentials.get("alertRule") or ""
        instance = {
            "name": item.get("name"),
            "alertRule": rule,
            "severity": essentials.get("severity"),
            "monitorCondition": essentials.get("monitorCondition"),
            "alertState": essentials.get("alertState"),
            "monitorService": essentials.get("monitorService"),
            "targetResourceName": essentials.get("targetResourceName"),
            "startDateTime": essentials.get("startDateTime"),
            "lastModifiedDateTime": essentials.get("lastModifiedDateTime"),
        }
        instances.append(instance)
        counts[(rule.rsplit("/", 1)[-1], instance["severity"], instance["monitorCondition"])] += 1
    summary = [
        {"alertRule": r, "severity": s, "monitorCondition": c, "instances": n}
        for (r, s, c), n in counts.most_common()
    ]
    return {"total_instances": len(instances), "summary": summary, "instances": instances}


def collect_alert_history(outdir: Path, report: Report) -> None:
    """7. Alert instances for the resource group. Azure Monitor keeps alerts for
    only 30 days, so this is NOT a 180-day firing history, and each item is one
    alert instance (current state), not every Fired/Resolved transition."""
    print("[8/10] Querying alert instances (30-day Azure retention)...")
    name = "07-alert-firing-history.json"
    limitation = {
        "api": f"Microsoft.AlertsManagement/alerts {ALERTS_API_VERSION}",
        "timeRange": f"{ALERTS_RETENTION_DAYS}d",
        "retention_days": ALERTS_RETENTION_DAYS,
        "limitation": (
            f"Azure retains alerts for {ALERTS_RETENTION_DAYS} days; older firings cannot "
            "be recovered. Items are alert instances, not a transition-by-transition "
            "Fired/Resolved history. An empty result means no instances in this window."
        ),
    }
    items: List[Dict[str, Any]] = []
    seen: set = set()
    uri: Optional[str] = alerts_uri()
    pages = 0
    error = None
    rejected: Optional[Dict[str, Any]] = None
    while uri and error is None:
        result = run_cli(["az", "rest", "--method", "get", "--uri", uri])
        if not result["success"]:
            error = result["error"]
            break
        data = result["data"]
        if not isinstance(data, dict) or not isinstance(data.get("value"), list):
            error = "unexpected alerts response"
            break
        items.extend(data["value"])
        pages += 1
        next_link = data.get("nextLink")
        if not next_link:
            break
        accepted, rejected = normalize_next_link(next_link)
        if rejected or not accepted:
            error = f"refusing to follow unexpected nextLink ({(rejected or {}).get('reason')})"
            break
        if accepted["key"] in seen:
            error = "alerts pagination did not terminate (repeated nextLink)"
        elif pages >= ALERTS_MAX_PAGES:
            error = f"alerts pagination exceeded {ALERTS_MAX_PAGES} pages"
        seen.add(accepted["key"])
        uri = accepted["uri"]

    payload: Dict[str, Any] = {"window": limitation, "pages": pages}
    if error:
        payload.update({"success": False, "error": error, "partial_instances": len(items)})
        if rejected:
            payload["next_link_rejection"] = rejected
        report.fail(name, error)
    else:
        payload.update({"success": True, "data": summarize_alerts(items)})
        report.ok(name)
    write_json(outdir / name, payload)


def collect_container_apps(outdir: Path, report: Report) -> None:
    """8. Container Apps config via native az resource (the `containerapp`
    extension is deliberately avoided)."""
    print("[9/10] Collecting Container Apps config...")
    listing = run_cli(
        [
            "az", "resource", "list",
            "--resource-group", RESOURCE_GROUP,
            "--resource-type", "Microsoft.App/containerApps",
            "--output", "json",
        ]
    )  # fmt: skip
    write_json(outdir / "08-container-apps-config.json", listing)
    record(report, "08-container-apps-config.json", listing)

    if listing["success"] and isinstance(listing["data"], list):
        for app in listing["data"]:
            name = f"08a-container-app-{safe_name(app.get('name', 'unknown'))}.json"
            detail = run_cli(["az", "resource", "show", "--ids", app["id"], "--output", "json"])
            write_json(outdir / name, detail)
            record(report, name, detail)


def collect_web_tests(outdir: Path, report: Report) -> None:
    """9. App Insights web tests via native az resource (the
    `az monitor app-insights web-test` command group does not exist)."""
    print("[10/10] Collecting web test config...")
    listing = run_cli(
        [
            "az", "resource", "list",
            "--resource-group", RESOURCE_GROUP,
            "--resource-type", "Microsoft.Insights/webtests",
            "--output", "json",
        ]
    )  # fmt: skip
    write_json(outdir / "09-web-tests.json", listing)
    record(report, "09-web-tests.json", listing)

    if listing["success"] and isinstance(listing["data"], list):
        for test in listing["data"]:
            name = f"09a-web-test-{safe_name(test.get('name', 'unknown'))}.json"
            detail = run_cli(["az", "resource", "show", "--ids", test["id"], "--output", "json"])
            write_json(outdir / name, detail)
            record(report, name, detail)


# ─── Manifest ──────────────────────────────────────────────────────────────


def write_manifest(outdir: Path, report: Report) -> None:
    postgres = report.resolved.get("postgres") or {}
    workspace = report.resolved.get("workspace") or {}
    manifest = {
        "status": report.status,
        "collection": {
            "timestamp": TIMESTAMP,
            "subscription_id": SUBSCRIPTION_ID,
            "resource_group": RESOURCE_GROUP,
            "postgres_server": postgres.get("name"),
            "postgres_server_id": postgres.get("id"),
            "log_analytics_workspace": workspace.get("name"),
            "log_analytics_workspace_id": workspace.get("customer_id"),
            "cost_window": cost_window(),
            "alerts_retention_days": ALERTS_RETENTION_DAYS,
        },
        "resolution": report.resolved,
        "failures": {n: report.checks[n]["error"] for n in report.failures},
        "skipped": {n: report.checks[n]["reason"] for n in report.skipped},
        "checks": report.checks,
        "files": sorted(f.name for f in outdir.iterdir() if f.is_file()),
        "notes": (
            "Core Azure CLI only (no extensions; dynamic extension install is disabled). "
            "Costs: `az rest` POST to the Cost Management Query API "
            f"(api-version {COST_API_VERSION}). Logs: `az rest` POST to "
            f"{LOGS_API}/v1/workspaces/{{id}}/query. Alerts: Azure keeps "
            f"{ALERTS_RETENTION_DAYS} days only. status=partial means at least one "
            "collection failed; complete_with_skips means only optional steps were skipped."
        ),
    }
    write_json(outdir / "MANIFEST.json", manifest)


# ─── Main ──────────────────────────────────────────────────────────────────


def authenticate() -> bool:
    print("\n[0/10] Authenticating...")
    client_id = os.getenv("AZURE_CLIENT_ID")
    client_secret = os.getenv("AZURE_CLIENT_SECRET")
    tenant_id = os.getenv("AZURE_TENANT_ID")
    if not (client_id and client_secret and tenant_id):
        print("ERROR: set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID")
        return False

    auth = run_cli(
        [
            "az", "login", "--service-principal",
            "-u", client_id, "-p", client_secret, "--tenant", tenant_id,
            "--output", "none",
        ],
        timeout=120,
        retry_throttled=False,
    )  # fmt: skip
    if not auth["success"]:
        print(f"Auth failed: {auth['error']}")
        return False
    account = run_cli(["az", "account", "set", "--subscription", SUBSCRIPTION_ID])
    if not account["success"]:
        print(f"Could not select subscription: {account['error']}")
        return False
    return True


def resolve_resources(report: Report) -> None:
    print("\nResolving resources...")
    report.resolved["postgres"] = resolve_postgres()
    report.resolved["workspace"] = resolve_workspace()
    for key, label in (("postgres", "PostgreSQL server"), ("workspace", "Log Analytics workspace")):
        error = report.resolved[key].get("error")
        if error:
            print(f"  ERROR resolving {label}: {error}")
            report.fail(f"resolve-{key}", error)
        else:
            print(f"  {label}: {report.resolved[key]['name']}")


def main() -> int:
    print("=" * 72)
    print("BITB-150 Phase 0 Cost Evidence Collection (Python)")
    print(f"Timestamp: {TIMESTAMP}")
    print(f"Output: {OUTDIR}")
    print("=" * 72)

    if not authenticate():
        return 1
    ensure_dir(OUTDIR)
    report = Report()
    resolve_resources(report)

    steps = [
        collect_cost_management,
        collect_log_analytics,
        collect_app_insights,
        collect_postgres_diagnostic_settings,
        collect_postgres_azure_config,
        collect_postgres_sql,
        collect_postgres_metrics,
        collect_alert_history,
        collect_container_apps,
        collect_web_tests,
    ]
    for step in steps:
        try:
            step(OUTDIR, report)
        except Exception as e:  # noqa: BLE001 — one broken collector must not stop the rest
            error = redact(f"{type(e).__name__}: {e}")
            print(f"  ERROR in {step.__name__}: {error}")
            report.fail(step.__name__, error)

    write_manifest(OUTDIR, report)

    print("\n" + "=" * 72)
    print(f"Status: {report.status}. Files in {OUTDIR}:")
    for f in sorted(OUTDIR.iterdir()):
        print(f"  {f.name}")
    for name in report.skipped:
        print(f"  SKIPPED {name}: {report.checks[name]['reason']}")
    for name in report.failures:
        print(f"  FAILED  {name}: {report.checks[name]['error']}")
    print("=" * 72)
    print(f"\nShare: tar -czf {OUTDIR}.tar.gz {OUTDIR}/")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
