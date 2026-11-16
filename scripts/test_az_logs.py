"""Tests for scripts/az-logs.sh (BITB-319) against a recording fake `az`.

Run: python3 -m pytest scripts/test_az_logs.py -q   (also part of `make test-makefile`)

No Azure access: a fake `az` on PATH records every call and answers the few lookups the
script makes (latest ready revision, replica list, workspace ID) from FAKE_* variables.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "az-logs.sh"

FAKE_AZ = r"""#!/bin/bash
_log=""
for _a in "$@"; do _log+="$_a"$'\x1f'; done
printf '%s\x1e' "$_log" >> "$FAKE_LOG"  # RS-terminated: KQL arguments span lines
case "$*" in
  *"containerapp show"*) printf '%s\n' "${FAKE_REVISION-bible-app-backend--0000076}" ;;
  *"containerapp replica list"*) printf '%s\n' "${FAKE_REPLICA-bible-app-backend--0000076-7d9f-abcde}" ;;
  *"log-analytics workspace list"*) printf '%s\n' "${FAKE_WORKSPACE-11111111-2222-3333-4444-555555555555}" ;;
  *"containerapp logs show"*)
    if [ -n "${FAKE_LOGSTREAM_INTERRUPT:-}" ]; then
      # Like Ctrl+C in a terminal: SIGINT reaches the whole foreground group (az + script);
      # az (Python) catches it and exits non-zero.
      kill -INT "$PPID"; sleep 0.2; exit 1
    fi
    if [ -n "${FAKE_LOGSTREAM_FAIL:-}" ]; then
      echo "Got bad status from the logstream API: 500" >&2; exit 1
    fi ;;
  *"log-analytics query"*) echo "TimeGenerated  Log_s" ;;
esac
"""


class AzLogsScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="azlogs_"))
        (self.dir / "bin").mkdir()
        fake = self.dir / "bin" / "az"
        fake.write_text(FAKE_AZ)
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.log = self.dir / "az.log"
        self.log.touch()

    def tearDown(self) -> None:
        for p in sorted(self.dir.rglob("*"), reverse=True):
            p.unlink() if p.is_file() else p.rmdir()
        self.dir.rmdir()

    def run_script(
        self, *args: str, **env: str
    ) -> tuple[subprocess.CompletedProcess, list[list[str]]]:
        run_env = {
            k: v
            for k, v in os.environ.items()
            if k not in {"CA_RG", "HOURS", "LEVEL", "FILTER", "LIMIT", "DAYS", "LA_WORKSPACE_ID"}
        }
        run_env.update(
            PATH=f"{self.dir / 'bin'}:{os.environ['PATH']}", FAKE_LOG=str(self.log), **env
        )
        proc = subprocess.run(
            ["bash", str(SCRIPT), *args],
            env=run_env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        calls = [line.split("\x1f")[:-1] for line in self.log.read_text().split("\x1e")[:-1]]
        return proc, calls

    @staticmethod
    def opt(call: list[str], flag: str) -> str:
        return call[call.index(flag) + 1]

    # ------------------------------------------------------------------ tail ---

    def test_tail_console_names_revision_and_replica(self) -> None:
        proc, calls = self.run_script("tail", "bible-app-backend", "console")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        logs = [c for c in calls if c[:3] == ["containerapp", "logs", "show"]]
        self.assertEqual(len(logs), 1)
        self.assertEqual(self.opt(logs[0], "--revision"), "bible-app-backend--0000076")
        self.assertEqual(self.opt(logs[0], "--replica"), "bible-app-backend--0000076-7d9f-abcde")
        self.assertEqual(self.opt(logs[0], "--type"), "console")
        self.assertEqual(self.opt(logs[0], "--resource-group"), "bible-app-rg")
        self.assertIn("--follow", logs[0])
        replica_call = next(c for c in calls if c[:3] == ["containerapp", "replica", "list"])
        self.assertEqual(self.opt(replica_call, "--revision"), "bible-app-backend--0000076")

    def test_tail_scaled_to_zero_explains_and_does_not_stream(self) -> None:
        proc, calls = self.run_script("tail", "bible-app-backend", "console", FAKE_REPLICA="")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no running replica", proc.stderr)
        self.assertIn("make az-logs-backend-query", proc.stderr)
        self.assertFalse([c for c in calls if c[:3] == ["containerapp", "logs", "show"]])

    def test_tail_logstream_500_points_to_history_query(self) -> None:
        proc, _ = self.run_script("tail", "bible-app-frontend", "console", FAKE_LOGSTREAM_FAIL="1")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("make az-logs-frontend-query", proc.stderr)

    def test_tail_ctrl_c_exits_quietly(self) -> None:
        # Regression (owner run, 2026-11-16): stopping the stream with Ctrl+C printed
        # "Error: Live streaming failed".
        for kind in ("console", "system"):
            with self.subTest(kind):
                proc, _ = self.run_script(
                    "tail", "bible-app-backend", kind, FAKE_LOGSTREAM_INTERRUPT="1"
                )
                self.assertEqual(proc.returncode, 130, proc.stderr)
                self.assertNotIn("Error", proc.stderr)

    def test_tail_system_needs_no_replica(self) -> None:
        proc, calls = self.run_script("tail", "bible-app-backend", "system", CA_RG="other-rg")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            calls,
            [
                [
                    "containerapp",
                    "logs",
                    "show",
                    "--name",
                    "bible-app-backend",
                    "--resource-group",
                    "other-rg",
                    "--type",
                    "system",
                    "--follow",
                ]
            ],
        )

    def test_tail_rejects_unknown_type(self) -> None:
        proc, calls = self.run_script("tail", "bible-app-backend", "everything")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(calls, [])

    # ----------------------------------------------------------------- query ---

    def kql(self, calls: list[list[str]]) -> str:
        q = next(c for c in calls if c[:3] == ["monitor", "log-analytics", "query"])
        self.assertEqual(self.opt(q, "--workspace"), "11111111-2222-3333-4444-555555555555")
        return self.opt(q, "--analytics-query")

    def test_query_defaults(self) -> None:
        proc, calls = self.run_script("query", "bible-app-backend")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        kql = self.kql(calls)
        self.assertIn("ago(24h)", kql)
        self.assertIn("ContainerAppName_s == 'bible-app-backend'", kql)
        self.assertIn(r"matches regex @'\|\s*(ERROR|WARNING)\s*\|'", kql)
        self.assertIn("take 200", kql)
        self.assertNotIn("contains", kql)

    def test_query_options_and_filter_escaping(self) -> None:
        proc, calls = self.run_script(
            "query",
            "bible-app-backend",
            HOURS="6",
            LIMIT="50",
            LEVEL="ERROR|INFO",
            FILTER="it's a \\ test",
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        kql = self.kql(calls)
        self.assertIn("ago(6h)", kql)
        self.assertIn("take 50", kql)
        self.assertIn("(ERROR|INFO)", kql)
        self.assertIn(r"| where Log_s contains 'it\'s a \\ test'", kql)

    def test_query_uses_given_workspace_without_lookup(self) -> None:
        proc, calls = self.run_script(
            "query", "bible-app-backend", LA_WORKSPACE_ID="11111111-2222-3333-4444-555555555555"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertFalse([c for c in calls if "workspace" in c and "list" in c])

    def test_query_rejects_bad_input_before_calling_az(self) -> None:
        for env in (
            {"HOURS": "24; drop"},
            {"HOURS": "0"},
            {"HOURS": "721"},
            {"LIMIT": "abc"},
            {"LEVEL": "ERROR' or 1==1"},
            {"LEVEL": ""},
        ):
            with self.subTest(env):
                self.log.write_text("")
                proc, calls = self.run_script("query", "bible-app-backend", **env)
                if env.get("LEVEL") == "":
                    # Empty LEVEL falls back to the default rather than matching nothing.
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    continue
                self.assertEqual(proc.returncode, 1)
                self.assertEqual(calls, [])

    def test_query_missing_workspace_is_an_error(self) -> None:
        proc, _ = self.run_script("query", "bible-app-backend", FAKE_WORKSPACE="")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("LA_WORKSPACE_ID", proc.stderr)

    # --------------------------------------------------- chat-stream-errors ---

    def test_chat_stream_errors(self) -> None:
        proc, calls = self.run_script("chat-stream-errors", DAYS="3")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        kql = self.kql(calls)
        self.assertIn("ago(3d)", kql)
        for label in (
            "chat_stream_unhandled",
            "llm_all_models_exhausted",
            "llama_guard_malformed",
            "content_safety_block",
        ):
            self.assertIn(label, kql)
        bad, _ = self.run_script("chat-stream-errors", DAYS="31")
        self.assertEqual(bad.returncode, 1)

    def test_unknown_command_prints_usage(self) -> None:
        proc, calls = self.run_script("bogus")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("az-logs.sh tail", proc.stderr)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
