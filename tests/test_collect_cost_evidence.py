"""Offline regression tests for the BITB-150 cost evidence collector.

No cloud, database or third-party dependency is touched: `subprocess.run` is
replaced by a router that answers every `az`/`psql` invocation.
"""

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "collect_cost_evidence.py"
WRAPPER = ROOT / "scripts" / "collect_cost_evidence.sh"
DOCKERFILE = ROOT / "scripts" / "Dockerfile.cost-collector"
WEEKLY = ROOT / ".github" / "workflows" / "cost-evidence-weekly.yml"
README = ROOT / "scripts" / "README_COST_COLLECTION.md"

SUB = "00000000-0000-0000-0000-0000000000aa"
RG = "bible-app-rg"
CLIENT_SECRET = "test-secret-value"  # pragma: allowlist secret
DATABASE_URL = (  # pragma: allowlist secret
    "postgresql://dbuser:s3cr3t%2Fpw@db.example.com:5432/appdb?sslmode=require"  # pragma: allowlist secret
)
DB_PASSWORD_RAW = "s3cr3t%2Fpw"  # pragma: allowlist secret
DB_PASSWORD = "s3cr3t/pw"  # pragma: allowlist secret
WORKSPACE_GUID = "11111111-2222-3333-4444-555555555555"
BASE_ENV = {
    "AZURE_CLIENT_ID": "test-client",
    "AZURE_CLIENT_SECRET": CLIENT_SECRET,
    "AZURE_TENANT_ID": "test-tenant",
    "AZURE_SUBSCRIPTION_ID": SUB,
    "AZURE_RESOURCE_GROUP": RG,
}
# Mixed-case on purpose: the collector must keep the ARM ID Azure returned.
PG_NAME = "bible-app-bible-db-ab12"
PG_ID = (
    f"/subscriptions/{SUB}/resourceGroups/Bible-App-RG"
    f"/providers/Microsoft.DBforPostgreSQL/flexibleServers/{PG_NAME}"
)
WS_ID = (
    f"/subscriptions/{SUB}/resourceGroups/{RG}"
    "/providers/Microsoft.OperationalInsights/workspaces/bible-app-logs-ab12"
)
EXPECTED_EVIDENCE = {
    "01-cost-by-resource-meter.json",
    "01b-cost-by-resource-type.json",
    "02-log-analytics-billable-gb.json",
    "02b-log-analytics-top-tables.json",
    "03-app-insights-record-counts.json",
    "04-postgres-diagnostic-settings.json",
    "05a-postgres-azure-config.json",
    "05b-postgres-db-size.txt",
    "05c-postgres-top-tables.txt",
    "05d-postgres-all-indexes.txt",
    "05e-postgres-stats-reset.txt",
    "06-cpu_percent.json",
    "06-memory_percent.json",
    "06-storage_percent.json",
    "07-alert-firing-history.json",
    "08-container-apps-config.json",
    "08a-container-app-bible-app-backend.json",
    "09-web-tests.json",
    "09a-web-test-bible-app-availability.json",
    "MANIFEST.json",
}


def load_collector():
    spec = importlib.util.spec_from_file_location("collect_cost_evidence", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def completed(cmd, stdout="", stderr="", code=0):
    return subprocess.CompletedProcess(cmd, code, stdout, stderr)


def as_json(cmd, data):
    return completed(cmd, json.dumps(data))


def failed(cmd, message):
    return completed(cmd, "", message, 1)


def arg_after(cmd, flag):
    return cmd[cmd.index(flag) + 1]


TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc(text):
    return datetime.strptime(text, TIME_FORMAT).replace(tzinfo=timezone.utc)


def iso(moment):
    return moment.strftime(TIME_FORMAT)


def metrics_body(metric, start, end, points=None, timespan=None, series=None, unit="Percent"):
    """Azure Monitor metrics response. points/series entries are (timestamp, average,
    maximum); a None value omits the key, like Azure does for an empty bucket."""
    if series is None:
        if points is None:
            points = [
                (iso(utc(start)), 10.0, 20.0),
                (iso(utc(end) - timedelta(hours=1)), 11.0, 21.0),
            ]
        series = [([], points)]

    def row(stamp, average, maximum):
        data = {"timeStamp": stamp}
        if average is not None:
            data["average"] = average
        if maximum is not None:
            data["maximum"] = maximum
        return data

    return {
        "cost": 0,
        "timespan": timespan or f"{start}/{end}",
        "interval": "PT1H",
        "namespace": "Microsoft.DBforPostgreSQL/flexibleServers",
        "resourceregion": "westeurope",
        "value": [
            {
                "id": f"{PG_ID}/providers/Microsoft.Insights/metrics/{metric}",
                "type": "Microsoft.Insights/metrics",
                "name": {"value": metric, "localizedValue": metric},
                "displayDescription": "",
                "errorCode": "Success",
                "unit": unit,
                "timeseries": [
                    {
                        "metadatavalues": dims,
                        "data": [row(*point) for point in rows],
                    }
                    for dims, rows in series
                ],
            }
        ],
    }


def default_resources(collector):
    return {
        collector.POSTGRES_TYPE: [{"name": PG_NAME, "id": PG_ID}],
        collector.WORKSPACE_TYPE: [{"name": "bible-app-logs-ab12", "id": WS_ID}],
        "Microsoft.App/containerApps": [
            {"name": "bible-app-backend", "id": f"/subscriptions/{SUB}/apps/backend"}
        ],
        "Microsoft.Insights/webtests": [
            {"name": "bible-app-availability", "id": f"/subscriptions/{SUB}/tests/a"}
        ],
    }


class Router:
    """Stands in for subprocess.run, answering like a healthy Azure/psql."""

    def __init__(self, collector, overrides=(), resources=None):
        self.collector = collector
        self.overrides = list(overrides)
        self.resources = resources or default_resources(collector)
        self.calls = []

    def __call__(self, cmd, **kwargs):
        self.calls.append((list(cmd), kwargs))
        for matches, handler in self.overrides:
            if matches(cmd):
                return handler(cmd)
        return self.default(cmd)

    def commands(self, *prefix):
        return [c for c, _ in self.calls if c[: len(prefix)] == list(prefix)]

    def default(self, cmd):
        if cmd[0] == "psql":
            return completed(cmd, " db_size \n---------\n 42 MB\n")
        if cmd[:2] == ["az", "login"] or cmd[:3] == ["az", "account", "set"]:
            return completed(cmd)
        if cmd[:3] == ["az", "resource", "list"]:
            return as_json(cmd, self.resources[arg_after(cmd, "--resource-type")])
        if cmd[:4] == ["az", "monitor", "metrics", "list"]:
            start, end = arg_after(cmd, "--start-time"), arg_after(cmd, "--end-time")
            return as_json(cmd, metrics_body(arg_after(cmd, "--metrics"), start, end))
        if cmd[:3] == ["az", "resource", "show"]:
            if "--query" in cmd:
                return as_json(cmd, WORKSPACE_GUID)
            return as_json(cmd, {"id": arg_after(cmd, "--ids")})
        if cmd[:2] == ["az", "rest"]:
            uri = arg_after(cmd, "--uri")
            if "api.loganalytics.io" in uri:
                return as_json(cmd, {"tables": [{"name": "PrimaryResult", "rows": []}]})
            if "AlertsManagement" in uri:
                return as_json(cmd, {"value": []})
            return as_json(cmd, {"properties": {"rows": []}})
        return as_json(cmd, {"ok": True})


class CollectorTestCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(redirect_stdout(StringIO()))
        self.tmp = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))

    def make_collector(self, env=None):
        full_env = {**BASE_ENV, **(env or {})}
        self.stack.enter_context(patch.dict(os.environ, full_env, clear=True))
        return load_collector()

    def run_main(self, overrides=(), resources=None, env=None, setup=None):
        collector = self.make_collector(env)
        router = Router(collector, overrides, resources)
        self.stack.enter_context(patch.object(subprocess, "run", side_effect=router))
        self.stack.enter_context(patch.object(collector.time, "sleep"))
        # Relative output paths resolve against the process working directory.
        self.stack.callback(os.chdir, Path.cwd())
        os.chdir(self.tmp)
        if setup:
            setup(collector)
        out = StringIO()
        with redirect_stdout(out):
            code = collector.main()
        outdir = self.tmp / collector.OUTDIR
        manifest_path = outdir / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else None
        return SimpleNamespace(
            code=code, stdout=out.getvalue(), outdir=outdir, manifest=manifest, router=router,
            collector=collector,
        )  # fmt: skip


class MainFlowTest(CollectorTestCase):
    def test_success_writes_all_evidence_and_manifest_inside_mount(self):
        run = self.run_main(env={"DATABASE_URL": DATABASE_URL})

        self.assertEqual(run.code, 0)
        self.assertEqual(list(self.tmp.iterdir()), [self.tmp / "cost-evidence"])
        self.assertEqual({f.name for f in run.outdir.iterdir()}, EXPECTED_EVIDENCE)
        self.assertEqual(run.manifest["status"], "complete")
        self.assertEqual(run.manifest["failures"], {})
        self.assertEqual(run.manifest["skipped"], {})
        self.assertEqual(run.manifest["collection"]["postgres_server"], PG_NAME)
        self.assertEqual(run.manifest["collection"]["postgres_server_id"], PG_ID)
        self.assertEqual(run.manifest["collection"]["log_analytics_workspace_id"], WORKSPACE_GUID)
        self.assertEqual(
            (run.outdir / "05b-postgres-db-size.txt").read_text().strip()[-5:], "42 MB"
        )

    def test_actual_postgres_id_is_used_for_config_diagnostics_and_metrics(self):
        run = self.run_main()

        show = run.router.commands("az", "postgres", "flexible-server", "show")[0]
        self.assertEqual(arg_after(show, "--ids"), PG_ID)
        diag = run.router.commands("az", "monitor", "diagnostic-settings", "list")[0]
        self.assertEqual(arg_after(diag, "--resource"), PG_ID)
        metrics = run.router.commands("az", "monitor", "metrics", "list")
        self.assertEqual(len(metrics), 9)  # 3 metrics x 3 thirty-day requests
        self.assertTrue(all(arg_after(m, "--resource") == PG_ID for m in metrics))
        self.assertNotIn("bible-app-mb0172", json.dumps(run.router.calls))

    def test_no_extension_command_and_dynamic_install_disabled(self):
        run = self.run_main()

        for cmd, kwargs in run.router.calls:
            self.assertNotEqual(cmd[:3], ["az", "monitor", "log-analytics"], cmd)
            if cmd[0] == "az":
                self.assertEqual(kwargs["env"]["AZURE_EXTENSION_USE_DYNAMIC_INSTALL"], "no")

    def test_failure_exits_nonzero_but_other_collectors_still_run(self):
        run = self.run_main(
            overrides=[
                (lambda c: c[:3] == ["az", "monitor", "metrics"], lambda c: failed(c, "boom"))
            ]
        )

        self.assertEqual(run.code, 1)
        self.assertEqual(run.manifest["status"], "partial")
        self.assertEqual(
            sorted(run.manifest["failures"]),
            ["06-cpu_percent.json", "06-memory_percent.json", "06-storage_percent.json"],
        )
        self.assertTrue((run.outdir / "09-web-tests.json").exists())
        error = json.loads((run.outdir / "06-cpu_percent.json").read_text())["error"]
        for index in (1, 2, 3):
            self.assertIn(f"chunk {index}/3: boom", error)

    def test_unresolved_postgres_fails_run_and_skips_dependent_collections(self):
        collector = load_collector()  # only to read the type constant
        resources = {**default_resources(collector), collector.POSTGRES_TYPE: []}
        run = self.run_main(resources=resources)

        self.assertEqual(run.code, 1)
        self.assertEqual(run.manifest["status"], "partial")
        self.assertIn("resolve-postgres", run.manifest["failures"])
        self.assertIn("04-postgres-diagnostic-settings.json", run.manifest["skipped"])
        self.assertIn("unresolved", (run.outdir / "05a-postgres-azure-config.json").read_text())
        self.assertEqual(run.router.commands("az", "postgres"), [])
        self.assertEqual(run.router.commands("az", "monitor", "metrics"), [])
        self.assertTrue((run.outdir / "01-cost-by-resource-meter.json").exists())
        self.assertTrue((run.outdir / "08-container-apps-config.json").exists())

    def test_unresolved_workspace_skips_log_queries_and_fails_run(self):
        collector = load_collector()
        resources = {**default_resources(collector), collector.WORKSPACE_TYPE: []}
        run = self.run_main(resources=resources)

        self.assertEqual(run.code, 1)
        self.assertIn("resolve-workspace", run.manifest["failures"])
        for name in (
            "02-log-analytics-billable-gb.json",
            "02b-log-analytics-top-tables.json",
            "03-app-insights-record-counts.json",
        ):
            self.assertIn(name, run.manifest["skipped"])
        self.assertEqual(
            [c for c in run.router.commands("az", "rest") if "loganalytics" in " ".join(c)], []
        )

    def test_crashing_collector_is_recorded_redacted_and_does_not_stop_others(self):
        def setup(collector):
            def collect_web_tests(outdir, report):
                raise RuntimeError(f"x {CLIENT_SECRET}")

            self.stack.enter_context(
                patch.object(collector, "collect_web_tests", collect_web_tests)
            )

        run = self.run_main(setup=setup)

        self.assertEqual(run.code, 1)
        self.assertIn("collect_web_tests", run.manifest["failures"])
        self.assertNotIn(CLIENT_SECRET, json.dumps(run.manifest))
        self.assertNotIn(CLIENT_SECRET, run.stdout)
        self.assertTrue((run.outdir / "08-container-apps-config.json").exists())

    def test_missing_credentials_exit_before_creating_evidence(self):
        run = self.run_main(env={"AZURE_CLIENT_ID": ""})

        self.assertEqual(run.code, 1)
        self.assertIn("AZURE_CLIENT_ID", run.stdout)
        self.assertFalse((self.tmp / "cost-evidence").exists())

    def test_login_failure_stops_without_leaking_secret(self):
        run = self.run_main(
            overrides=[
                (lambda c: c[:2] == ["az", "login"], lambda c: failed(c, f"bad {CLIENT_SECRET}"))
            ]
        )

        self.assertEqual(run.code, 1)
        self.assertNotIn(CLIENT_SECRET, run.stdout)
        self.assertEqual(run.router.commands("az", "resource"), [])

    def test_login_timeout_does_not_print_command_credentials(self):
        def timeout(cmd):
            raise subprocess.TimeoutExpired(cmd, 120)

        run = self.run_main(overrides=[(lambda c: c[:2] == ["az", "login"], timeout)])

        self.assertEqual(run.code, 1)
        self.assertIn("timed out", run.stdout)
        self.assertNotIn(CLIENT_SECRET, run.stdout)

    def test_account_set_failure_stops_the_run(self):
        run = self.run_main(
            overrides=[(lambda c: c[:3] == ["az", "account", "set"], lambda c: failed(c, "nope"))]
        )

        self.assertEqual(run.code, 1)
        self.assertEqual(run.router.commands("az", "resource"), [])
        self.assertFalse((self.tmp / "cost-evidence").exists())


class MetricsChunkingTest(CollectorTestCase):
    """Azure answers at most 30 days per metrics request: 90 days = 3 contiguous requests."""

    NOW = datetime(2026, 10, 23, 10, 49, 49, tzinfo=timezone.utc)
    METRICS_CMD = ["az", "monitor", "metrics", "list"]

    def fetch(self, handler=None, now=None, metric="cpu_percent"):
        """Run fetch_metric against a fake CLI. handler(index, cmd, chunk) may return a
        body dict, raw stdout text, a CompletedProcess, or None for a healthy answer."""
        collector = self.make_collector()
        window = collector.metrics_window(now or self.NOW)
        chunks = collector.metrics_chunks(window)

        def respond(cmd):
            index = [c["start"] for c in chunks].index(arg_after(cmd, "--start-time"))
            result = handler(index, cmd, chunks[index]) if handler else None
            if result is None:
                result = metrics_body(metric, **chunks[index])
            if isinstance(result, subprocess.CompletedProcess):
                return result
            return completed(cmd, result) if isinstance(result, str) else as_json(cmd, result)

        router = Router(collector, [(lambda c: c[:4] == self.METRICS_CMD, respond)])
        self.stack.enter_context(patch.object(subprocess, "run", side_effect=router))
        self.stack.enter_context(patch.object(collector.time, "sleep"))
        evidence = collector.fetch_metric(metric, PG_ID, window)
        return SimpleNamespace(
            evidence=evidence, router=router, chunks=chunks, window=window, collector=collector
        )

    def merged_rows(self, evidence):
        return evidence["data"]["value"][0]["timeseries"][0]["data"]

    def assert_rejected(self, run, index, text):
        evidence = run.evidence
        self.assertFalse(evidence["success"])
        self.assertNotIn("data", evidence)
        self.assertIn(f"chunk {index + 1}/3", evidence["error"])
        self.assertIn(text, evidence["error"])
        self.assertFalse(evidence["chunks"][index]["success"])

    # -- windows ---------------------------------------------------------

    def test_window_is_split_into_three_exact_contiguous_30_day_chunks(self):
        collector = self.make_collector()
        cases = {
            "plain": (self.NOW, ["2026-07-25T10:49:49Z", "2026-08-24T10:49:49Z",
                                 "2026-09-23T10:49:49Z", "2026-10-23T10:49:49Z"]),
            "leap day and year boundary": (
                datetime(2028, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
                ["2027-12-16T12:00:00Z", "2028-01-15T12:00:00Z",
                 "2028-02-14T12:00:00Z", "2028-03-15T12:00:00Z"],
            ),
            "year boundary": (datetime(2027, 1, 20, 0, 0, 30, 999999, tzinfo=timezone.utc), None),
            "leap day inside the last chunk": (
                datetime(2028, 3, 1, 0, 0, 0, tzinfo=timezone.utc), None
            ),
        }  # fmt: skip
        for label, (now, bounds) in cases.items():
            with self.subTest(label):
                window = collector.metrics_window(now)
                chunks = collector.metrics_chunks(window)
                self.assertEqual(utc(window["end"]) - utc(window["start"]), timedelta(days=90))
                self.assertEqual(len(chunks), 3)
                self.assertEqual(chunks[0]["start"], window["start"])
                self.assertEqual(chunks[-1]["end"], window["end"])
                for chunk in chunks:
                    self.assertEqual(utc(chunk["end"]) - utc(chunk["start"]), timedelta(days=30))
                for before, after in zip(chunks, chunks[1:]):
                    self.assertEqual(before["end"], after["start"])
                if bounds:
                    got = [chunks[0]["start"]] + [c["end"] for c in chunks]
                    self.assertEqual(got, bounds)

    def test_metrics_window_keeps_the_exact_90_day_span(self):
        window = self.make_collector().metrics_window(self.NOW)

        self.assertEqual(window, {"start": "2026-07-25T10:49:49Z", "end": "2026-10-23T10:49:49Z"})

    def test_chunks_never_exceed_30_days_for_other_window_lengths(self):
        collector = self.make_collector()
        window = {"start": "2026-01-01T00:00:00Z", "end": "2026-03-12T05:00:00Z"}

        chunks = collector.metrics_chunks(window)

        self.assertEqual(len(chunks), 3)
        spans = [utc(c["end"]) - utc(c["start"]) for c in chunks]
        self.assertEqual(
            spans, [timedelta(days=30), timedelta(days=30), timedelta(days=10, hours=5)]
        )
        self.assertEqual(chunks[-1]["end"], window["end"])

    # -- requests --------------------------------------------------------

    def test_one_cli_request_per_chunk_with_the_chunk_boundaries(self):
        run = self.fetch()

        calls = run.router.commands(*self.METRICS_CMD)
        self.assertEqual(len(calls), 3)
        for cmd, chunk in zip(calls, run.chunks):
            self.assertEqual(arg_after(cmd, "--start-time"), chunk["start"])
            self.assertEqual(arg_after(cmd, "--end-time"), chunk["end"])
            self.assertEqual(arg_after(cmd, "--resource"), PG_ID)
            self.assertEqual(arg_after(cmd, "--metrics"), "cpu_percent")
            self.assertEqual(arg_after(cmd, "--interval"), "PT1H")
            self.assertEqual(cmd[cmd.index("--aggregation") + 1 :][:2], ["Average", "Maximum"])
        self.assertTrue(
            all(kw["timeout"] == 300 for c, kw in run.router.calls if c[:4] == self.METRICS_CMD)
        )
        evidence = run.evidence
        self.assertTrue(evidence["success"])
        self.assertEqual(evidence["window"], run.window)
        self.assertEqual([c["requested"] for c in evidence["chunks"]], run.chunks)
        self.assertEqual(
            [c["actual_timespan"] for c in evidence["chunks"]],
            [f"{c['start']}/{c['end']}" for c in run.chunks],
        )
        self.assertTrue(all(c["success"] and "data" not in c for c in evidence["chunks"]))

    # -- merge -----------------------------------------------------------

    def test_merge_orders_chronologically_dedups_boundaries_and_normalises_timezones(self):
        collector = self.make_collector()
        bounds = collector.metrics_chunks(collector.metrics_window(self.NOW))
        first = utc(bounds[0]["start"])
        boundary1, boundary2 = utc(bounds[0]["end"]), utc(bounds[1]["end"])
        offset = timezone(timedelta(hours=2))
        hour = timedelta(hours=1)
        points = {
            0: [(iso(first), 1.0, 2.0), (iso(boundary1), 5.0, 6.0)],
            1: [
                (iso(boundary2 - hour), 3.0, 4.0),
                (boundary1.astimezone(offset).isoformat(), 5.0, 6.0),
                (iso(boundary1 + hour), 7.0, 8.0),
            ],
            2: [(iso(boundary2), 9.0, 10.0), (iso(utc(bounds[2]["end"]) - hour), 11.0, 12.0)],
        }

        def handler(index, cmd, chunk):
            return metrics_body("cpu_percent", **chunk, points=points[index])

        run = self.fetch(handler)
        self.chunks = run.chunks
        evidence = run.evidence
        self.assertTrue(evidence["success"], evidence.get("error"))
        rows = self.merged_rows(evidence)
        stamps = [datetime.fromisoformat(r["timeStamp"].replace("Z", "+00:00")) for r in rows]
        self.assertEqual(stamps, sorted(stamps))
        self.assertEqual(len(set(s.astimezone(timezone.utc) for s in stamps)), len(stamps))
        self.assertEqual([r["average"] for r in rows], [1.0, 5.0, 7.0, 3.0, 9.0, 11.0])
        self.assertEqual(rows[1]["timeStamp"], self.chunks[0]["end"])  # first occurrence kept
        self.assertEqual(evidence["coverage"]["duplicates_removed"], 1)
        self.assertEqual(evidence["coverage"]["points"], 6)
        self.assertEqual(
            evidence["data"]["timespan"], f"{self.chunks[0]['start']}/{self.chunks[2]['end']}"
        )

    def test_merged_file_keeps_the_azure_response_shape(self):
        run = self.fetch()

        data = run.evidence["data"]
        self.assertEqual(data["interval"], "PT1H")
        self.assertEqual(data["namespace"], "Microsoft.DBforPostgreSQL/flexibleServers")
        self.assertEqual(len(data["value"]), 1)
        metric = data["value"][0]
        self.assertEqual(metric["name"]["value"], "cpu_percent")
        self.assertEqual(metric["unit"], "Percent")
        self.assertEqual(metric["timeseries"][0]["metadatavalues"], [])
        self.assertEqual(
            len(metric["timeseries"][0]["data"]), 6
        )  # 2 per chunk, no boundary overlap
        self.assertEqual(data["timespan"], f"{run.window['start']}/{run.window['end']}")
        self.assertEqual(run.evidence["coverage"]["populated_points"], 6)
        self.assertTrue(run.evidence["coverage"]["fully_populated"])

    def test_dimensioned_series_are_merged_per_identity_and_never_mixed(self):
        def dim(value):
            return [{"name": {"value": "Node", "localizedValue": "Node"}, "value": value}]

        def handler(index, cmd, chunk):
            start = iso(utc(chunk["start"]))
            a = (dim("a"), [(start, 100.0 + index, None)])
            b = (dim("b"), [(start, 200.0 + index, None)])
            ordered = [a, b] if index != 1 else [b, a]
            return metrics_body("cpu_percent", chunk["start"], chunk["end"], series=ordered)

        run = self.fetch(handler)

        series = {
            ts["metadatavalues"][0]["value"]: [r["average"] for r in ts["data"]]
            for ts in run.evidence["data"]["value"][0]["timeseries"]
        }
        self.assertEqual(series, {"a": [100.0, 101.0, 102.0], "b": [200.0, 201.0, 202.0]})

    def test_null_buckets_are_kept_empty_and_reported_not_filled(self):
        def handler(index, cmd, chunk):
            if index != 1:
                return None
            start, end = utc(chunk["start"]), utc(chunk["end"])
            points = [(iso(start), None, None), (iso(end - timedelta(hours=1)), 3.0, 4.0)]
            return metrics_body("cpu_percent", chunk["start"], chunk["end"], points=points)

        run = self.fetch(handler)

        evidence = run.evidence
        self.assertTrue(evidence["success"])
        gap = [r for r in self.merged_rows(evidence) if r["timeStamp"] == run.chunks[1]["start"]]
        self.assertEqual(len(gap), 1)
        self.assertEqual(gap[0], {"timeStamp": run.chunks[1]["start"]})
        self.assertFalse(evidence["coverage"]["fully_populated"])
        self.assertEqual(evidence["coverage"]["points"], 6)
        self.assertEqual(evidence["coverage"]["populated_points"], 5)
        self.assertEqual(evidence["chunks"][1]["points"], 2)
        self.assertEqual(evidence["chunks"][1]["populated_points"], 1)

    # -- truncation ------------------------------------------------------

    def test_truncated_or_shifted_timespan_fails_the_file(self):
        day, hour = timedelta(days=1), timedelta(hours=1)
        cases = {
            "end truncated by 5 days": lambda s, e: (s, e - 5 * day),
            "start narrowed by 5 days": lambda s, e: (s + 5 * day, e),
            "start narrowed just over the tolerance": lambda s, e: (
                s + hour + timedelta(seconds=1),
                e,
            ),
            "end narrowed just over the tolerance": lambda s, e: (
                s,
                e - hour - timedelta(seconds=1),
            ),
            "start widened": lambda s, e: (s - 2 * hour, e),
            "end widened": lambda s, e: (s, e + 2 * hour),
        }
        for label, shift in cases.items():
            with self.subTest(label):

                def handler(index, cmd, chunk, shift=shift):
                    if index != 1:
                        return None
                    start, end = shift(utc(chunk["start"]), utc(chunk["end"]))
                    span = f"{iso(start)}/{iso(end)}"
                    return metrics_body("cpu_percent", chunk["start"], chunk["end"], timespan=span)

                run = self.fetch(handler)

                self.assert_rejected(run, 1, "timespan")
                self.assertEqual(len(run.router.commands(*self.METRICS_CMD)), 3)

    def test_bucket_rounding_within_one_hour_is_accepted(self):
        hour = timedelta(hours=1)

        def handler(index, cmd, chunk):
            start, end = utc(chunk["start"]) + hour, utc(chunk["end"]) - hour
            span = f"{iso(start)}/{iso(end)}"
            return metrics_body("cpu_percent", chunk["start"], chunk["end"], timespan=span)

        run = self.fetch(handler)

        self.assertTrue(run.evidence["success"], run.evidence.get("error"))
        self.assertEqual(
            run.evidence["chunks"][0]["actual_timespan"][:20],
            iso(utc(run.chunks[0]["start"]) + hour),
        )

    def test_azure_cap_on_a_single_90_day_request_would_be_detected(self):
        collector = self.make_collector()
        window = collector.metrics_window(self.NOW)
        start = utc(window["start"])
        body = metrics_body(
            "cpu_percent", window["start"], window["end"],
            timespan=f"{iso(start)}/{iso(start + timedelta(days=31))}",
        )  # fmt: skip

        with self.assertRaises(collector.MetricsError):
            collector.check_returned_timespan(window, body)

    def test_timespan_with_offset_is_compared_in_utc(self):
        collector = self.make_collector()
        chunk = collector.metrics_chunks(collector.metrics_window(self.NOW))[0]
        offset = timezone(timedelta(hours=-5))
        span = "/".join(utc(chunk[k]).astimezone(offset).isoformat() for k in ("start", "end"))

        self.assertEqual(collector.check_returned_timespan(chunk, {"timespan": span}), span)

    # -- request failures ------------------------------------------------

    def test_failure_of_any_single_chunk_fails_the_file_but_keeps_other_chunks(self):
        for failing in range(3):
            with self.subTest(chunk=failing + 1):

                def handler(index, cmd, chunk, failing=failing):
                    return failed(cmd, "boom") if index == failing else None

                run = self.fetch(handler)

                self.assert_rejected(run, failing, "boom")
                self.assertEqual(len(run.router.commands(*self.METRICS_CMD)), 3)
                chunks = run.evidence["chunks"]
                self.assertEqual(chunks[failing]["error"], "boom")
                self.assertNotIn("data", chunks[failing])
                for index in set(range(3)) - {failing}:
                    self.assertTrue(chunks[index]["success"])
                    self.assertEqual(
                        chunks[index]["data"]["value"][0]["name"]["value"], "cpu_percent"
                    )
                self.assertEqual(
                    run.evidence["coverage"], {"chunks_succeeded": 2, "chunks_requested": 3}
                )

    def test_all_chunks_failing_records_every_error(self):
        run = self.fetch(lambda index, cmd, chunk: failed(cmd, f"down {index}"))

        self.assertFalse(run.evidence["success"])
        for index in range(3):
            self.assertIn(f"chunk {index + 1}/3: down {index}", run.evidence["error"])

    # -- empty / malformed -----------------------------------------------

    def test_empty_or_malformed_responses_fail_the_file(self):
        def series(body):
            return body["value"][0]["timeseries"]

        def mutate(change):
            def build(chunk):
                body = metrics_body("cpu_percent", chunk["start"], chunk["end"])
                change(body)
                return body

            return build

        def drop(key):
            return lambda b: b.pop(key)

        def set_item(path, value):
            def change(b):
                target = b
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value

            return change

        def no_populated(b):
            series(b)[0]["data"] = [{"timeStamp": r["timeStamp"]} for r in series(b)[0]["data"]]

        def duplicate_stamp(b):
            series(b)[0]["data"].append(copy.deepcopy(series(b)[0]["data"][0]))

        cases = {
            "non-json stdout": (lambda chunk: "not json", "not a JSON object"),
            "json list": (lambda chunk: [1], "not a JSON object"),
            "empty object": (lambda chunk: {}, "timespan"),
            "missing timespan": (mutate(drop("timespan")), "timespan"),
            "malformed timespan": (mutate(set_item(["timespan"], "nope")), "timespan"),
            "missing value": (mutate(drop("value")), "exactly one metric"),
            "empty value": (mutate(set_item(["value"], [])), "exactly one metric"),
            "two metrics": (
                mutate(lambda b: b["value"].append(copy.deepcopy(b["value"][0]))),
                "exactly one metric",
            ),
            "other metric": (
                mutate(set_item(["value", 0, "name", "value"], "memory_percent")),
                "different metric",
            ),
            "metric error code": (
                mutate(set_item(["value", 0, "errorCode"], "BadRequest")),
                "errorCode",
            ),
            "other interval": (mutate(set_item(["interval"], "PT5M")), "interval"),
            "no timeseries": (mutate(set_item(["value", 0, "timeseries"], [])), "no timeseries"),
            "timeseries without data": (
                mutate(lambda b: series(b)[0].pop("data")),
                "malformed timeseries",
            ),
            "point without timestamp": (
                mutate(lambda b: series(b)[0]["data"][0].pop("timeStamp")),
                "timestamp",
            ),
            "naive timestamp": (
                mutate(lambda b: series(b)[0]["data"][0].update(timeStamp="2026-08-01T00:00:00")),
                "no timezone",
            ),
            "garbage timestamp": (
                mutate(lambda b: series(b)[0]["data"][0].update(timeStamp="yesterday")),
                "unparseable",
            ),
            "point outside the chunk": (
                mutate(lambda b: series(b)[0]["data"][0].update(timeStamp="2030-01-01T00:00:00Z")),
                "outside chunk",
            ),
            "duplicate timestamp": (mutate(duplicate_stamp), "duplicate timestamp"),
            "only empty buckets": (mutate(no_populated), "no populated samples"),
            "duplicate series": (
                mutate(lambda b: series(b).append(copy.deepcopy(series(b)[0]))),
                "duplicate timeseries",
            ),
        }
        for label, (build, expected) in cases.items():
            with self.subTest(label):
                run = self.fetch(lambda index, cmd, chunk: build(chunk) if index == 1 else None)

                self.assert_rejected(run, 1, expected)
                self.assertTrue(run.evidence["chunks"][0]["success"])

    def test_empty_chunk_is_not_reported_as_a_populated_90_day_window(self):
        def handler(index, cmd, chunk):
            if index == 2:
                return metrics_body("cpu_percent", chunk["start"], chunk["end"], series=[([], [])])

        run = self.fetch(handler)

        self.assert_rejected(run, 2, "no populated samples")
        self.assertNotIn("fully_populated", run.evidence["coverage"])

    # -- incompatible shapes ---------------------------------------------

    def test_incompatible_chunks_are_rejected_instead_of_mixed(self):
        def dim(value):
            return [{"name": {"value": "Node", "localizedValue": "Node"}, "value": value}]

        def body(chunk, **kwargs):
            return metrics_body("cpu_percent", chunk["start"], chunk["end"], **kwargs)

        def at(chunk, key, offset=timedelta(0)):
            return iso(utc(chunk[key]) + offset)

        def other_unit(index, cmd, chunk):
            return body(chunk, unit="Count") if index == 1 else None

        def other_series(index, cmd, chunk):
            if index == 1:
                return body(chunk, series=[(dim("a"), [(at(chunk, "start"), 1.0, 2.0)])])

        def extra_series(index, cmd, chunk):
            if index == 1:
                rows = [(at(chunk, "start"), 1.0, 2.0)]
                return body(chunk, series=[([], rows), (dim("a"), rows)])

        def boundary_conflict(index, cmd, chunk):
            # chunk 0 ends on the instant chunk 1 starts; both claim a different value for it
            hour = timedelta(hours=1)
            if index == 0:
                return body(
                    chunk,
                    points=[(at(chunk, "end", -hour), 1.0, 2.0), (at(chunk, "end"), 5.0, 6.0)],
                )
            if index == 1:
                return body(chunk, points=[(at(chunk, "start"), 99.0, 99.0)])

        cases = {
            "other unit": (other_unit, "different metrics, units or intervals"),
            "other series identity": (other_series, "different timeseries"),
            "additional series": (extra_series, "different timeseries"),
            "conflicting boundary value": (boundary_conflict, "conflicting values"),
        }
        for label, (handler, expected) in cases.items():
            with self.subTest(label):
                evidence = self.fetch(handler).evidence

                self.assertFalse(evidence["success"])
                self.assertNotIn("data", evidence)
                self.assertTrue(evidence["error"].startswith("merge: "), evidence["error"])
                self.assertIn(expected, evidence["error"])
                self.assertTrue(all(c["success"] and "data" in c for c in evidence["chunks"]))

    # -- main / manifest ---------------------------------------------------

    def test_success_run_writes_three_chunk_evidence_per_metric(self):
        run = self.run_main()

        self.assertEqual(run.code, 0)
        for metric in ("cpu_percent", "memory_percent", "storage_percent"):
            evidence = json.loads((run.outdir / f"06-{metric}.json").read_text())
            self.assertTrue(evidence["success"])
            self.assertEqual(len(evidence["chunks"]), 3)
            self.assertEqual(evidence["data"]["value"][0]["name"]["value"], metric)
            self.assertEqual(
                evidence["data"]["timespan"],
                f"{evidence['window']['start']}/{evidence['window']['end']}",
            )

    def test_one_failed_chunk_fails_only_that_metric_file_and_the_run(self):
        calls = {"cpu_percent": 0}

        def flaky(cmd):
            metric = arg_after(cmd, "--metrics")
            calls[metric] = calls.get(metric, 0) + 1
            if metric == "cpu_percent" and calls[metric] == 2:
                return failed(cmd, "throttled for good")
            body = metrics_body(
                metric, arg_after(cmd, "--start-time"), arg_after(cmd, "--end-time")
            )
            return as_json(cmd, body)

        run = self.run_main(overrides=[(lambda c: c[:4] == self.METRICS_CMD, flaky)])

        self.assertEqual(run.code, 1)
        self.assertEqual(run.manifest["status"], "partial")
        self.assertEqual(list(run.manifest["failures"]), ["06-cpu_percent.json"])
        self.assertIn("chunk 2/3", run.manifest["failures"]["06-cpu_percent.json"])
        evidence = json.loads((run.outdir / "06-cpu_percent.json").read_text())
        self.assertFalse(evidence["success"])
        self.assertNotIn("data", evidence)
        self.assertEqual([c["success"] for c in evidence["chunks"]], [True, False, True])
        self.assertTrue((run.outdir / "06-memory_percent.json").exists())
        self.assertEqual(len(run.router.commands(*self.METRICS_CMD)), 9)

    def test_truncated_chunk_fails_the_manifest(self):
        def truncated(cmd):
            metric = arg_after(cmd, "--metrics")
            start, end = arg_after(cmd, "--start-time"), arg_after(cmd, "--end-time")
            if metric == "storage_percent":
                end = iso(utc(end) - timedelta(days=2))
            body = metrics_body(metric, start, end)
            return as_json(cmd, body)

        run = self.run_main(overrides=[(lambda c: c[:4] == self.METRICS_CMD, truncated)])

        self.assertEqual(run.code, 1)
        self.assertEqual(list(run.manifest["failures"]), ["06-storage_percent.json"])
        self.assertIn("truncated", run.manifest["failures"]["06-storage_percent.json"])


class RunCliTest(CollectorTestCase):
    def test_success_parses_json_or_returns_text(self):
        collector = self.make_collector()
        with patch.object(
            subprocess, "run", side_effect=[completed([], '{"a": 1}'), completed([], "x\n")]
        ):
            self.assertEqual(collector.run_cli(["az"]), {"success": True, "data": {"a": 1}})
            self.assertEqual(collector.run_cli(["az"]), {"success": True, "data": "x"})

    def test_failure_redacts_credentials(self):
        collector = self.make_collector({"DATABASE_URL": DATABASE_URL})
        stderr = f"err {CLIENT_SECRET} {DATABASE_URL} {DB_PASSWORD} {DB_PASSWORD_RAW}"
        with patch.object(subprocess, "run", return_value=failed([], stderr)):
            result = collector.run_cli(["az"])

        self.assertFalse(result["success"])
        for secret in (CLIENT_SECRET, DATABASE_URL, DB_PASSWORD, DB_PASSWORD_RAW):
            self.assertNotIn(secret, result["error"])

    def test_timeout_message_omits_command(self):
        collector = self.make_collector()
        cmd = ["az", "login", "-p", CLIENT_SECRET]
        with patch.object(subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd, 5)):
            result = collector.run_cli(cmd, timeout=5)

        self.assertEqual(result, {"success": False, "error": "Command timed out after 5s"})


THROTTLED = 'ERROR: Too Many Requests({"error":{"code":"429","message":"Too many requests. Please retry."}})'


class ThrottleRetryTest(CollectorTestCase):
    CMD = ["az", "rest", "--method", "post", "--uri", "/subscriptions/x"]

    def run_with(self, responses, env=None, timeout=180, cmd=None, **kwargs):
        collector = self.make_collector(env)
        collector._JITTER = SimpleNamespace(uniform=lambda low, high: 0.0)
        with (
            patch.object(subprocess, "run", side_effect=responses) as run,
            patch.object(collector.time, "sleep") as sleep,
        ):
            result = collector.run_cli(cmd or self.CMD, timeout=timeout, **kwargs)
        return collector, result, run, sleep

    def test_429_then_success_retries_with_exponential_delay(self):
        _, result, run, sleep = self.run_with(
            [failed([], THROTTLED), failed([], THROTTLED), as_json([], {"ok": 1})]
        )

        self.assertEqual(result, {"success": True, "data": {"ok": 1}, "attempts": 3})
        self.assertEqual(run.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [5.0, 10.0])

    def test_every_attempt_keeps_timeout_and_env(self):
        _, _, run, _ = self.run_with([failed([], THROTTLED), as_json([], {})], timeout=77)

        for call in run.call_args_list:
            self.assertEqual(call.kwargs["timeout"], 77)
            self.assertEqual(call.kwargs["env"]["AZURE_EXTENSION_USE_DYNAMIC_INSTALL"], "no")

    def test_exhausted_retries_report_failure_attempts_and_wait_redacted(self):
        stderr = f"{THROTTLED} {CLIENT_SECRET}"
        collector, result, run, sleep = self.run_with([failed([], stderr)] * 10)

        self.assertFalse(result["success"])
        self.assertEqual(run.call_count, collector.THROTTLE_MAX_ATTEMPTS)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [5.0, 10.0, 20.0, 40.0])
        self.assertEqual(result["attempts"], 5)
        self.assertIn("Too Many Requests", result["error"])
        self.assertIn("still failing after 5 attempts, waited 75s", result["error"])
        self.assertNotIn(CLIENT_SECRET, result["error"])

    def test_delay_is_capped_and_jitter_is_bounded(self):
        collector = self.make_collector()
        for attempt in range(1, 12):
            delay = collector.backoff_delay(attempt)
            self.assertGreaterEqual(delay, 0)
            self.assertLessEqual(
                delay, collector.THROTTLE_MAX_DELAY + collector.THROTTLE_BASE_DELAY / 2
            )

    def test_total_wait_budget_stops_retrying(self):
        collector = self.make_collector()
        collector.THROTTLE_TOTAL_BUDGET = 12
        collector._JITTER = SimpleNamespace(uniform=lambda low, high: 0.0)
        with (
            patch.object(subprocess, "run", side_effect=[failed([], THROTTLED)] * 10) as run,
            patch.object(collector.time, "sleep") as sleep,
        ):
            result = collector.run_cli(self.CMD)

        self.assertFalse(result["success"])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(sleep.call_count, 1)

    def test_503_service_unavailable_is_retried(self):
        _, result, run, _ = self.run_with(
            [failed([], "ERROR: Service Unavailable"), as_json([], [1])]
        )

        self.assertEqual(result["data"], [1])
        self.assertEqual(run.call_count, 2)

    def test_retry_after_in_cli_output_is_honored_and_capped(self):
        _, result, _, sleep = self.run_with(
            [failed([], f"{THROTTLED}\nRetry-After: 17"), as_json([], {})]
        )
        self.assertTrue(result["success"])
        self.assertEqual(sleep.call_args_list[0].args[0], 17.0)

        collector, result, run, sleep = self.run_with(
            [failed([], f"{THROTTLED}\nRetry-After: 3600")] * 3
        )
        self.assertFalse(result["success"])
        self.assertEqual(run.call_count, 1)  # cannot be honored within the delay cap
        sleep.assert_not_called()

    def test_permanent_and_semantic_errors_are_not_retried(self):
        permanent = [
            "ERROR: (AuthorizationFailed) The client does not have authorization",
            "ERROR: (ResourceNotFound) The Resource 'x' was not found.",
            'ERROR: Bad Request({"error":{"code":"400"}})',
            "ERROR: Unauthorized (401)",
            "ERROR: Forbidden (403)",
            "ERROR: Not Found (404)",
            'Bad Request({"error":{"code":"SemanticError","message":"Failed to resolve table \'x\'"}})',
            "exit code 1",
        ]
        for message in permanent:
            with self.subTest(message=message):
                _, result, run, sleep = self.run_with([failed([], message)] * 3)
                self.assertFalse(result["success"])
                self.assertEqual(run.call_count, 1)
                self.assertNotIn("attempts", result)
                sleep.assert_not_called()

    def test_timeout_and_launch_errors_are_not_retried(self):
        for exc in (subprocess.TimeoutExpired(self.CMD, 5), FileNotFoundError("az")):
            with self.subTest(exc=type(exc).__name__):
                _, result, run, sleep = self.run_with(exc)
                self.assertFalse(result["success"])
                self.assertEqual(run.call_count, 1)
                sleep.assert_not_called()

    def test_retry_can_be_disabled_for_login(self):
        _, result, run, sleep = self.run_with(
            [failed([], THROTTLED)] * 3, cmd=["az", "login"], retry_throttled=False
        )

        self.assertFalse(result["success"])
        self.assertEqual(run.call_count, 1)
        sleep.assert_not_called()

    def test_login_in_main_flow_is_not_retried(self):
        run = self.run_main(
            overrides=[(lambda c: c[:2] == ["az", "login"], lambda c: failed(c, THROTTLED))]
        )

        self.assertEqual(run.code, 1)
        self.assertEqual(len(run.router.commands("az", "login")), 1)

    def test_throttled_cost_query_recovers_in_main_flow(self):
        hits = {"n": 0}

        def throttle_once(cmd):
            hits["n"] += 1
            if hits["n"] == 1:
                return failed(cmd, THROTTLED)
            return as_json(cmd, {"properties": {"rows": []}})

        run = self.run_main(overrides=[(lambda c: "CostManagement" in " ".join(c), throttle_once)])

        self.assertEqual(run.code, 0)
        evidence = json.loads((run.outdir / "01-cost-by-resource-meter.json").read_text())
        self.assertTrue(evidence["success"])
        self.assertEqual(evidence["attempts"], 2)

    def test_persistently_throttled_cost_query_fails_run_with_clear_error(self):
        run = self.run_main(
            overrides=[(lambda c: "CostManagement" in " ".join(c), lambda c: failed(c, THROTTLED))]
        )

        self.assertEqual(run.code, 1)
        error = run.manifest["failures"]["01-cost-by-resource-meter.json"]
        self.assertIn("still failing after 5 attempts", error)
        self.assertTrue((run.outdir / "09-web-tests.json").exists())


class ResolutionTest(CollectorTestCase):
    def resolve(self, collector, function, resources, show=None):
        def fake(cmd, timeout=180):
            if cmd[:3] == ["az", "resource", "list"]:
                if isinstance(resources, str):
                    return {"success": False, "error": resources}
                return {"success": True, "data": resources}
            return {
                "success": True,
                "data": (show or {}).get(arg_after(cmd, "--ids"), WORKSPACE_GUID),
            }

        with patch.object(collector, "run_cli", side_effect=fake):
            return getattr(collector, function)()

    def servers(self, *names):
        return [{"name": n, "id": f"/s/{n.upper()}"} for n in names]

    def test_postgres_single_candidate_is_selected_with_actual_id(self):
        collector = self.make_collector()
        result = self.resolve(collector, "resolve_postgres", [{"name": "db1", "id": "/S/DB1"}])
        self.assertEqual(result, {"name": "db1", "id": "/S/DB1"})

    def test_postgres_zero_candidates_fails(self):
        collector = self.make_collector()
        self.assertIn("no PostgreSQL", self.resolve(collector, "resolve_postgres", [])["error"])

    def test_postgres_multiple_candidates_fail_instead_of_picking_first(self):
        collector = self.make_collector()
        result = self.resolve(collector, "resolve_postgres", self.servers("db1", "db2"))
        self.assertNotIn("id", result)
        self.assertIn("POSTGRES_SERVER_NAME", result["error"])
        self.assertIn("db1", result["error"])
        self.assertIn("db2", result["error"])

    def test_postgres_override_matches_case_insensitively(self):
        collector = self.make_collector({"POSTGRES_SERVER_NAME": "DB2"})
        result = self.resolve(collector, "resolve_postgres", self.servers("db1", "db2"))
        self.assertEqual(result, {"name": "db2", "id": "/s/DB2"})

    def test_postgres_override_without_match_fails_even_with_one_server(self):
        collector = self.make_collector({"POSTGRES_SERVER_NAME": "other"})
        result = self.resolve(collector, "resolve_postgres", self.servers("db1"))
        self.assertNotIn("id", result)
        self.assertIn("does not match", result["error"])

    def test_postgres_listing_failure_is_reported(self):
        collector = self.make_collector()
        self.assertEqual(self.resolve(collector, "resolve_postgres", "denied"), {"error": "denied"})

    def test_workspace_single_candidate_returns_customer_id(self):
        collector = self.make_collector()
        result = self.resolve(collector, "resolve_workspace", [{"name": "ws", "id": "/w/ws"}])
        self.assertEqual(result, {"name": "ws", "id": "/w/ws", "customer_id": WORKSPACE_GUID})

    def test_workspace_zero_or_multiple_candidates_fail(self):
        collector = self.make_collector()
        spaces = [{"name": "a", "id": "/w/a"}, {"name": "b", "id": "/w/b"}]
        self.assertIn("error", self.resolve(collector, "resolve_workspace", []))
        self.assertIn("error", self.resolve(collector, "resolve_workspace", spaces))

    def test_workspace_override_by_guid_or_name(self):
        other = "99999999-2222-3333-4444-555555555555"
        spaces = [{"name": "a", "id": "/w/a"}, {"name": "b", "id": "/w/b"}]
        show = {"/w/a": WORKSPACE_GUID, "/w/b": other}
        by_guid = self.make_collector({"LOG_ANALYTICS_WORKSPACE_ID": other.upper()})
        self.assertEqual(self.resolve(by_guid, "resolve_workspace", spaces, show)["name"], "b")
        by_name = self.make_collector({"LOG_ANALYTICS_WORKSPACE_ID": "A"})
        self.assertEqual(self.resolve(by_name, "resolve_workspace", spaces, show)["name"], "a")

    def test_workspace_override_without_match_fails(self):
        collector = self.make_collector({"LOG_ANALYTICS_WORKSPACE_ID": "nope"})
        result = self.resolve(collector, "resolve_workspace", [{"name": "a", "id": "/w/a"}])
        self.assertIn("does not match", result["error"])


class LogsQueryTest(CollectorTestCase):
    def query(self, collector, response, ws=WORKSPACE_GUID):
        with patch.object(collector, "run_cli", return_value=response) as run_cli:
            return collector.run_logs_query(ws, "Usage | take 1", "P30D"), run_cli

    def test_request_shape_matches_logs_query_api_contract(self):
        collector = self.make_collector()
        result, run_cli = self.query(collector, {"success": True, "data": {"tables": []}})

        cmd = run_cli.call_args.args[0]
        self.assertTrue(result["success"])
        self.assertEqual(cmd[:5], ["az", "rest", "--method", "post", "--uri"])
        self.assertEqual(
            arg_after(cmd, "--uri"),
            f"https://api.loganalytics.io/v1/workspaces/{WORKSPACE_GUID}/query",
        )
        self.assertEqual(arg_after(cmd, "--resource"), "https://api.loganalytics.io")
        headers = cmd[cmd.index("--headers") + 1 : cmd.index("--body")]
        self.assertEqual(headers, ["Content-Type=application/json", "Prefer=wait=180"])
        self.assertEqual(
            json.loads(arg_after(cmd, "--body")), {"query": "Usage | take 1", "timespan": "P30D"}
        )
        self.assertGreater(run_cli.call_args.kwargs["timeout"], 180)

    def test_http_200_partial_error_is_a_failure(self):
        collector = self.make_collector()
        body = {"tables": [], "error": {"code": "PartialError", "message": "too much data"}}
        result, _ = self.query(collector, {"success": True, "data": body})

        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "PartialError: too much data")
        self.assertEqual(result["partial_response"], body)

    def test_malformed_responses_are_failures(self):
        collector = self.make_collector()
        for data in ("text", {"unexpected": 1}):
            result, _ = self.query(collector, {"success": True, "data": data})
            self.assertFalse(result["success"], data)

    def test_transport_failure_passes_through(self):
        collector = self.make_collector()
        result, _ = self.query(
            collector, {"success": False, "error": "Command timed out after 240s"}
        )
        self.assertEqual(result, {"success": False, "error": "Command timed out after 240s"})

    def test_invalid_workspace_id_never_reaches_the_cli(self):
        collector = self.make_collector()
        result, run_cli = self.query(collector, {}, ws="../evil")
        self.assertFalse(result["success"])
        run_cli.assert_not_called()

    def test_queries_use_workspace_tables_and_direct_aggregation(self):
        collector = self.make_collector()
        self.assertNotIn("bin(", collector.USAGE_KQL)
        self.assertIn("TotalGB = sum(Quantity) / 1000 by DataType", collector.USAGE_KQL)
        kql = collector.APP_INSIGHTS_KQL
        for table in (
            "AppRequests", "AppDependencies", "AppTraces",
            "AppMetrics", "AppExceptions", "AppAvailabilityResults",
        ):  # fmt: skip
            self.assertIn(table, kql)
        self.assertIn("isfuzzy=true", kql)
        self.assertIn("TimeGenerated", kql)
        self.assertIn("by Type", kql)
        for classic in ("itemType", "timestamp", "customMetrics", " requests,"):
            self.assertNotIn(classic, kql)

    def test_evidence_files_record_query_timespan_and_failure(self):
        run = self.run_main(
            overrides=[
                (
                    lambda c: "api.loganalytics.io" in " ".join(c),
                    lambda c: as_json(
                        c, {"tables": [], "error": {"code": "PartialError", "message": "m"}}
                    ),
                )
            ]
        )

        self.assertEqual(run.code, 1)
        evidence = json.loads((run.outdir / "03-app-insights-record-counts.json").read_text())
        self.assertFalse(evidence["success"])
        self.assertEqual(evidence["timespan"], "P7D")
        self.assertIn("AppRequests", evidence["query"])
        self.assertIn("03-app-insights-record-counts.json", run.manifest["failures"])


class AlertHistoryTest(CollectorTestCase):
    BASE = f"/subscriptions/{SUB}/providers/Microsoft.AlertsManagement/alerts"

    def query(self, token="p2", **override):
        params = {
            "api-version": "2019-03-01",
            "timeRange": "30d",
            "targetResourceGroup": RG,
            "pageCount": "100",
            "ctoken": token,
            **override,
        }
        return "&".join(f"{k}={v}" for k, v in params.items() if v is not None)

    def next_link(self, token):
        return f"https://management.azure.com{self.BASE}?{self.query(token)}"

    def alert(self, name, rule="rule-a", severity="Sev2", condition="Fired"):
        rule_id = f"/subscriptions/{SUB}/resourceGroups/{RG}/providers/microsoft.insights/scheduledqueryrules/{rule}"
        return {
            "name": name,
            "properties": {
                "essentials": {
                    "alertRule": rule_id,
                    "severity": severity,
                    "monitorCondition": condition,
                    "alertState": "New",
                }
            },
        }

    def collect(self, responses):
        collector = self.make_collector()
        report = collector.Report()
        with patch.object(collector, "run_cli", side_effect=responses) as run_cli:
            collector.collect_alert_history(self.tmp, report)
        evidence = json.loads((self.tmp / "07-alert-firing-history.json").read_text())
        return collector, report, evidence, run_cli

    def ok(self, **body):
        return {"success": True, "data": body}

    def test_first_request_uses_alerts_management_api_with_30_day_window(self):
        _, _, _, run_cli = self.collect([self.ok(value=[])])

        uri = arg_after(run_cli.call_args_list[0].args[0], "--uri")
        self.assertIn(f"/subscriptions/{SUB}/providers/Microsoft.AlertsManagement/alerts?", uri)
        for fragment in ("api-version=2019-03-01", "timeRange=30d", f"targetResourceGroup={RG}"):
            self.assertIn(fragment, uri)
        self.assertNotIn("log-analytics", " ".join(run_cli.call_args_list[0].args[0]))

    def test_pagination_follows_next_links_and_aggregates(self):
        _, report, evidence, run_cli = self.collect(
            [
                self.ok(value=[self.alert("a1"), self.alert("a2")], nextLink=self.next_link("p2")),
                self.ok(
                    value=[self.alert("a3", rule="rule-b", severity="Sev1")],
                    nextLink=self.next_link("p3"),
                ),
                self.ok(value=[self.alert("a4", condition="Resolved")]),
            ]
        )

        uris = [arg_after(c.args[0], "--uri") for c in run_cli.call_args_list]
        self.assertEqual(uris[1:], [self.next_link("p2"), self.next_link("p3")])
        self.assertEqual(report.failures, [])
        self.assertEqual(evidence["pages"], 3)
        self.assertEqual(evidence["data"]["total_instances"], 4)
        summary = {
            (s["alertRule"], s["severity"], s["monitorCondition"]): s["instances"]
            for s in evidence["data"]["summary"]
        }
        self.assertEqual(summary[("rule-a", "Sev2", "Fired")], 2)
        self.assertEqual(summary[("rule-b", "Sev1", "Fired")], 1)
        self.assertEqual(summary[("rule-a", "Sev2", "Resolved")], 1)

    def test_empty_result_still_records_retention_limitation(self):
        _, report, evidence, _ = self.collect([self.ok(value=[])])

        self.assertEqual(report.failures, [])
        self.assertEqual(evidence["data"]["total_instances"], 0)
        self.assertEqual(evidence["window"]["retention_days"], 30)
        self.assertIn("30 days", evidence["window"]["limitation"])
        self.assertIn("not a transition", evidence["window"]["limitation"])
        self.assertNotIn("180", json.dumps(evidence))

    def test_foreign_next_link_is_refused(self):
        evil = "https://evil.example/subscriptions/x/providers/Microsoft.AlertsManagement/alerts"
        _, report, evidence, run_cli = self.collect([self.ok(value=[], nextLink=evil)])

        self.assertEqual(run_cli.call_count, 1)
        self.assertEqual(report.failures, ["07-alert-firing-history.json"])
        self.assertFalse(evidence["success"])
        self.assertEqual(evidence["window"]["retention_days"], 30)

    def test_repeating_next_link_terminates_as_failure(self):
        link = self.next_link("same")
        _, report, _, run_cli = self.collect([self.ok(value=[], nextLink=link)] * 3)

        self.assertLessEqual(run_cli.call_count, 3)
        self.assertEqual(report.failures, ["07-alert-firing-history.json"])

    def test_live_azure_link_shape_with_explicit_443_port_is_followed(self):
        live = f"https://management.azure.com:443{self.BASE}?{self.query('tok%2Babc/def=')}"
        _, report, evidence, run_cli = self.collect(
            [self.ok(value=[self.alert("a1")], nextLink=live), self.ok(value=[self.alert("a2")])]
        )

        self.assertEqual(report.failures, [])
        self.assertEqual(evidence["pages"], 2)
        uri = arg_after(run_cli.call_args_list[1].args[0], "--uri")
        self.assertEqual(
            uri, f"https://management.azure.com{self.BASE}?{self.query('tok%2Babc/def=')}"
        )

    def test_relative_arm_link_is_followed(self):
        relative = f"{self.BASE}?{self.query('rel')}"
        _, report, evidence, run_cli = self.collect(
            [self.ok(value=[], nextLink=relative), self.ok(value=[])]
        )

        self.assertEqual(report.failures, [])
        self.assertEqual(evidence["pages"], 2)
        self.assertEqual(
            arg_after(run_cli.call_args_list[1].args[0], "--uri"),
            f"https://management.azure.com{self.BASE}?{self.query('rel')}",
        )

    def test_unsafe_or_malformed_links_are_refused_without_a_second_request(self):
        q = self.query("t")
        evil = "https://evil.example"
        cases = {
            "http scheme": f"http://management.azure.com{self.BASE}?{q}",
            "foreign host": f"{evil}{self.BASE}?{q}",
            "host suffix": f"https://management.azure.com.evil.example{self.BASE}?{q}",
            "userinfo": f"https://management.azure.com@evil.example{self.BASE}?{q}",
            "userinfo decoy": f"https://evil.example@management.azure.com{self.BASE}?{q}",
            "other port": f"https://management.azure.com:8443{self.BASE}?{q}",
            "bad port": f"https://management.azure.com:99999999{self.BASE}?{q}",
            "protocol relative": f"//evil.example{self.BASE}?{q}",
            "scheme without host": f"https:{self.BASE}?{q}",
            "javascript": "javascript:alert(1)",
            "fragment": f"https://management.azure.com{self.BASE}?{q}#frag",
            "path suffix": f"https://management.azure.com{self.BASE}/../../evil?{q}",
            "path suffix segment": f"https://management.azure.com{self.BASE}x?{q}",
            "trailing slash": f"https://management.azure.com{self.BASE}/?{q}",
            "encoded path": f"https://management.azure.com{self.BASE.replace('providers', 'provid%65rs')}?{q}",
            "double slash path": f"https://management.azure.com/{self.BASE}?{q}",
            "other subscription": f"https://management.azure.com{self.BASE.replace(SUB, '1' * 8 + '-0000-0000-0000-000000000000')}?{q}",
            "backslash": f"https://management.azure.com\\@evil.example{self.BASE}?{q}",
            "newline": f"https://management.azure.com{self.BASE}?{q}\nHost: evil",
            "space": f"https://management.azure.com{self.BASE}?{q} x",
            "non-ascii": f"https://management.azure.com{self.BASE}?{q}\u00e9",
            "non-string": {"u": 1},
            "too long": f"https://management.azure.com{self.BASE}?{q}" + "a" * 5000,
            "no query": f"https://management.azure.com{self.BASE}",
            "empty query item": f"https://management.azure.com{self.BASE}?{q}&",
            "relative without slash": f"subscriptions/{SUB}/providers/Microsoft.AlertsManagement/alerts?{q}",
        }
        for label, link in cases.items():
            with self.subTest(label):
                _, report, evidence, run_cli = self.collect([self.ok(value=[], nextLink=link)])
                self.assertEqual(run_cli.call_count, 1)
                self.assertEqual(report.failures, ["07-alert-firing-history.json"])
                self.assertIn("refusing to follow unexpected nextLink", evidence["error"])
                self.assertIn(evidence["next_link_rejection"]["reason"], evidence["error"])

    def test_scope_and_retention_must_not_widen_between_pages(self):
        base = f"https://management.azure.com{self.BASE}?"
        cases = {
            "retention widened": self.query(timeRange="180d"),
            "retention dropped": self.query(timeRange=None),
            "resource group changed": self.query(targetResourceGroup="other-rg"),
            "resource group dropped": self.query(targetResourceGroup=None),
            "api-version changed": self.query(**{"api-version": "2018-05-05"}),
            "no continuation token": self.query(ctoken=None),
            "empty continuation token": self.query(ctoken=""),
            "unknown parameter": self.query() + "&subscriptionId=" + "0" * 8,
            "target resource filter removed": self.query() + "&targetResource=x",
            "repeated parameter": self.query() + "&targetResourceGroup=other-rg",
            "non-numeric pageCount": self.query(pageCount="abc"),
        }
        for label, query in cases.items():
            with self.subTest(label):
                _, report, evidence, run_cli = self.collect(
                    [self.ok(value=[], nextLink=base + query)]
                )
                self.assertEqual(run_cli.call_count, 1)
                self.assertEqual(report.failures, ["07-alert-firing-history.json"])
                self.assertEqual(evidence["window"]["retention_days"], 30)

    def test_case_and_encoding_variants_of_the_same_scope_are_accepted(self):
        link = (
            f"https://MANAGEMENT.azure.com{self.BASE.upper()}?API-Version=2019-03-01"
            f"&TimeRange=30d&targetResourceGroup={RG.upper()}&ctoken=t"
        )
        _, report, evidence, _ = self.collect([self.ok(value=[], nextLink=link), self.ok(value=[])])

        self.assertEqual(report.failures, [])
        self.assertEqual(evidence["pages"], 2)

    def test_rejection_diagnostic_has_host_path_and_param_names_but_no_token(self):
        secret_token = "SUPERSECRETCONTINUATION"  # pragma: allowlist secret
        link = f"https://evil.example{self.BASE}?{self.query(secret_token)}"
        _, _, evidence, _ = self.collect([self.ok(value=[], nextLink=link)])

        diag = evidence["next_link_rejection"]
        self.assertEqual(diag["host"], "evil.example")
        self.assertEqual(diag["path"], self.BASE)
        self.assertEqual(
            diag["query_param_names"],
            ["api-version", "timeRange", "targetResourceGroup", "pageCount", "ctoken"],
        )
        self.assertIn("host", diag["reason"])
        self.assertNotIn(secret_token, json.dumps(evidence))

    def test_repeat_detection_canonicalizes_port_case_order_and_encoding(self):
        a = f"https://management.azure.com{self.BASE}?{self.query('tok')}"
        b = (
            f"https://management.azure.com:443{self.BASE.upper()}?ctoken=tok&pageCount=100"
            f"&targetResourceGroup={RG}&TimeRange=30d&api-version=2019-03-01"
        )
        _, report, evidence, run_cli = self.collect(
            [self.ok(value=[], nextLink=a), self.ok(value=[], nextLink=b), self.ok(value=[])]
        )

        self.assertEqual(run_cli.call_count, 2)
        self.assertEqual(report.failures, ["07-alert-firing-history.json"])
        self.assertIn("repeated nextLink", evidence["error"])

    def test_page_cap_terminates_unbounded_unique_pagination(self):
        collector = self.make_collector()
        pages = [
            self.ok(value=[], nextLink=self.next_link(f"t{i}"))
            for i in range(collector.ALERTS_MAX_PAGES + 5)
        ]
        _, report, evidence, run_cli = self.collect(pages)

        self.assertEqual(run_cli.call_count, collector.ALERTS_MAX_PAGES)
        self.assertEqual(report.failures, ["07-alert-firing-history.json"])
        self.assertIn("exceeded", evidence["error"])
        self.assertEqual(evidence["window"]["retention_days"], 30)

    def test_throttled_page_is_retried_by_run_cli_not_the_pagination_loop(self):
        collector = self.make_collector()
        report = collector.Report()
        responses = [
            failed([], THROTTLED),
            as_json([], {"value": [self.alert("a1")], "nextLink": self.next_link("n")}),
            failed([], THROTTLED),
            as_json([], {"value": [self.alert("a2")]}),
        ]
        with (
            patch.object(subprocess, "run", side_effect=responses) as run,
            patch.object(collector.time, "sleep"),
        ):
            collector.collect_alert_history(self.tmp, report)

        evidence = json.loads((self.tmp / "07-alert-firing-history.json").read_text())
        self.assertEqual(run.call_count, 4)
        self.assertEqual(report.failures, [])
        self.assertEqual(evidence["data"]["total_instances"], 2)

    def test_api_error_and_unexpected_body_fail_with_window_recorded(self):
        for response in ({"success": False, "error": "denied"}, self.ok(unexpected=True)):
            _, report, evidence, _ = self.collect([response])
            self.assertEqual(report.failures, ["07-alert-firing-history.json"])
            self.assertFalse(evidence["success"])
            self.assertEqual(evidence["window"]["timeRange"], "30d")


class PostgresSqlTest(CollectorTestCase):
    def collect(self, env=None, run=None):
        collector = self.make_collector(env)
        report = collector.Report()
        with patch.object(subprocess, "run", side_effect=run) as fake:
            collector.collect_postgres_sql(self.tmp, report)
        return collector, report, fake

    def test_missing_database_url_is_skipped_not_failed(self):
        collector, report, fake = self.collect(run=AssertionError("psql must not run"))

        fake.assert_not_called()
        self.assertEqual(report.failures, [])
        self.assertEqual(report.skipped, sorted(collector.SQL_FILES))
        text = (self.tmp / "05b-postgres-db-size.txt").read_text()
        self.assertIn("DATABASE_URL not set", text)
        self.assertIn("-e DATABASE_URL", text)

    def test_empty_database_url_is_treated_as_unset(self):
        _, report, fake = self.collect(env={"DATABASE_URL": ""}, run=AssertionError("no"))
        fake.assert_not_called()
        self.assertEqual(len(report.skipped), 4)

    def test_url_and_password_never_reach_argv_and_session_is_read_only(self):
        seen = []

        def run(cmd, **kwargs):
            seen.append((cmd, kwargs))
            return completed(cmd, "ok")

        collector, report, _ = self.collect(
            {"DATABASE_URL": DATABASE_URL, "PGHOST": "attacker"}, run
        )

        self.assertEqual(report.failures, [])
        self.assertEqual(len(seen), 4)
        for cmd, kwargs in seen:
            joined = " ".join(cmd)
            for secret in (DATABASE_URL, DB_PASSWORD, DB_PASSWORD_RAW, "dbuser", "db.example.com"):
                self.assertNotIn(secret, joined)
            self.assertEqual(cmd[:4], ["psql", "-X", "-v", "ON_ERROR_STOP=1"])
            env = kwargs["env"]
            self.assertEqual(env["PGHOST"], "db.example.com")
            self.assertEqual(env["PGPORT"], "5432")
            self.assertEqual(env["PGUSER"], "dbuser")
            self.assertEqual(env["PGPASSWORD"], DB_PASSWORD)
            self.assertEqual(env["PGDATABASE"], "appdb")
            self.assertEqual(env["PGSSLMODE"], "require")
            self.assertIn("default_transaction_read_only=on", env["PGOPTIONS"])
            self.assertIn("statement_timeout=", env["PGOPTIONS"])
            self.assertIn("PGCONNECT_TIMEOUT", env)
            self.assertNotIn("DATABASE_URL", env)
            self.assertNotIn("AZURE_CLIENT_SECRET", env)
            self.assertGreater(kwargs["timeout"], 0)

    def test_psql_failure_is_recorded_without_leaking_credentials(self):
        stderr = f"FATAL: password {DB_PASSWORD} rejected for {DATABASE_URL}"
        _, report, _ = self.collect(
            {"DATABASE_URL": DATABASE_URL}, lambda cmd, **kw: failed(cmd, stderr)
        )

        self.assertEqual(len(report.failures), 4)
        for name in report.failures:
            text = (self.tmp / name).read_text()
            self.assertTrue(text.startswith("ERROR:"))
            for secret in (DB_PASSWORD, DATABASE_URL):
                self.assertNotIn(secret, text)
                self.assertNotIn(secret, report.checks[name]["error"])

    def test_missing_psql_binary_and_timeout_are_failures(self):
        for error in (
            FileNotFoundError("psql"),
            subprocess.TimeoutExpired(["psql", DATABASE_URL], 120),
        ):

            def run(cmd, error=error, **kwargs):
                raise error

            _, report, _ = self.collect({"DATABASE_URL": DATABASE_URL}, run)
            self.assertEqual(len(report.failures), 4)
            for name in report.failures:
                self.assertNotIn(DB_PASSWORD, (self.tmp / name).read_text())
                self.assertNotIn(DATABASE_URL, (self.tmp / name).read_text())

    def test_invalid_url_fails_without_echoing_it(self):
        bad = "mysql://u:hunter22@host/db"  # pragma: allowlist secret
        _, report, fake = self.collect({"DATABASE_URL": bad}, AssertionError("no psql"))

        fake.assert_not_called()
        self.assertEqual(len(report.failures), 4)
        self.assertNotIn("hunter22", (self.tmp / "05b-postgres-db-size.txt").read_text())

    def test_psql_env_decodes_credentials_and_rejects_unknown_parameters(self):
        collector = self.make_collector()
        env = collector.psql_env(
            "postgres://u%40x:p%3Aw@h:6543/d%20b?sslmode=verify-full"  # pragma: allowlist secret
        )  # pragma: allowlist secret
        self.assertEqual(
            (env["PGUSER"], env["PGPASSWORD"], env["PGPORT"], env["PGDATABASE"], env["PGSSLMODE"]),
            ("u@x", "p:w", "6543", "d b", "verify-full"),
        )
        with self.assertRaises(ValueError) as caught:
            collector.psql_env(
                "postgresql://u:hunter22@h/d?options=-csearch_path%3Dx"  # pragma: allowlist secret
            )  # pragma: allowlist secret
        self.assertNotIn("hunter22", str(caught.exception))
        with self.assertRaises(ValueError):
            collector.psql_env("postgresql://u:p@h:notaport/d")  # pragma: allowlist secret


class WrapperTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        fake = self.bin / "python3"
        fake.write_text(
            '#!/usr/bin/env bash\necho "SCRIPT=$1"\nshift\necho "ARGS=$*"\n'
            'echo "DB=${DATABASE_URL-unset}"\nexit 7\n'
        )
        fake.chmod(0o755)
        self.env = {"PATH": f"{self.bin}:/usr/bin:/bin", "DATABASE_URL": "marker-value"}

    def run_wrapper(self, wrapper, env=None, cwd=None):
        return subprocess.run(
            ["/bin/bash", str(wrapper), "--flag", "value"],
            capture_output=True, text=True, env=env or self.env, cwd=cwd or self.tmp,
        )  # fmt: skip

    def test_host_layout_execs_sibling_python_forwarding_env_args_and_exit_code(self):
        result = self.run_wrapper(WRAPPER)

        self.assertEqual(result.returncode, 7)
        self.assertIn(f"SCRIPT={SCRIPT.parent}/collect_cost_evidence.py", result.stdout)
        self.assertIn("ARGS=--flag value", result.stdout)
        self.assertIn("DB=marker-value", result.stdout)

    def test_flat_docker_layout_resolves_sibling_regardless_of_cwd(self):
        app = self.tmp / "app"
        app.mkdir()
        flat = app / "collect_cost_evidence.sh"
        flat.write_text(WRAPPER.read_text())
        (app / "collect_cost_evidence.py").write_text("")

        result = self.run_wrapper(flat, cwd="/")

        self.assertEqual(result.returncode, 7)
        self.assertIn(f"SCRIPT={app}/collect_cost_evidence.py", result.stdout)

    def test_missing_python_reports_clearly(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        result = self.run_wrapper(WRAPPER, env={"PATH": str(empty)})

        self.assertEqual(result.returncode, 127)
        self.assertIn("python3 is required", result.stderr)

    def test_wrapper_contains_no_collection_logic(self):
        text = WRAPPER.read_text()
        self.assertIn("exec python3", text)
        self.assertNotIn("az ", text.replace("az and psql", ""))
        self.assertNotIn("log-analytics", text)


class DockerAndWorkflowContractTest(unittest.TestCase):
    def test_dockerfile_ships_flat_scripts_and_bakes_in_no_database_url(self):
        text = DOCKERFILE.read_text()
        instructions = [
            line for line in text.splitlines() if line.strip() and not line.startswith("#")
        ]

        self.assertIn("COPY scripts/collect_cost_evidence.py .", instructions)
        self.assertIn("COPY scripts/collect_cost_evidence.sh .", instructions)
        self.assertIn("ENV PYTHONUNBUFFERED=1", instructions)
        self.assertTrue(any(line.startswith("ENTRYPOINT") for line in instructions))
        self.assertFalse([line for line in instructions if "DATABASE_URL" in line])

    def test_weekly_workflow_forwards_database_url_at_runtime_only(self):
        text = WEEKLY.read_text()
        self.assertIn("-e DATABASE_URL \\", text)
        self.assertNotIn("DATABASE_URL=", text)
        self.assertNotIn("--build-arg", text)

    def test_readme_docker_command_forwards_database_url_and_checks_it_silently(self):
        text = README.read_text()
        self.assertIn("-e DATABASE_URL", text)
        self.assertIn(': "${DATABASE_URL:?', text)
        self.assertNotIn("echo $DATABASE_URL", text)
        self.assertNotIn("180d", text)


if __name__ == "__main__":
    unittest.main()
