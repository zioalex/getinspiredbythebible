"""Offline tests for the az-pg-* firewall targets in the Makefile (BITB-150).

`make -n` prints recipes without running them; the real-run tests put fake
`az`/`curl` executables first on PATH, so no cloud or network is ever touched.
"""

import json
import os
import shlex
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CREATE = ["postgres", "flexible-server", "firewall-rule", "create"]
LIST = ["postgres", "flexible-server", "firewall-rule", "list"]
DELETE = ["postgres", "flexible-server", "firewall-rule", "delete"]

FAKE_AZ = """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["FAKE_AZ_LOG"], "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
"""
FAKE_CURL = "#!/bin/sh\necho 203.0.113.7\n"


def _env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in ("MAKEFLAGS", "MFLAGS", "SERVER", "RULE")}
    env.update(extra)
    return env


def _dry_run(target, *overrides):
    result = subprocess.run(
        ["make", "-n", target, *overrides],
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _az_tokens(dry_run_output):
    """Tokens of the `az ...` command in a dry-run recipe, without the leading `az`."""
    tokens = shlex.split(dry_run_output.replace("\\\n", " "))
    start = tokens.index("az") + 1
    end = tokens.index("&&", start) if "&&" in tokens[start:] else len(tokens)
    return tokens[start:end]


def _split(tokens, subcommand):
    """Assert the command prefix and return the flags as an ordered list of (flag, value)."""
    assert tokens[: len(subcommand)] == subcommand, tokens
    rest = tokens[len(subcommand) :]
    flags = []
    i = 0
    while i < len(rest):
        flag = rest[i]
        if i + 1 < len(rest) and not rest[i + 1].startswith("--"):
            flags.append((flag, rest[i + 1]))
            i += 2
        else:
            flags.append((flag, None))
            i += 1
    return flags


class MakefileFirewallDryRunTests(unittest.TestCase):
    def test_add_ip_uses_server_name_and_rule_name_flags(self):
        flags = _split(_az_tokens(_dry_run("az-pg-add-ip")), CREATE)
        by_flag = dict(flags)
        server = by_flag["--server-name"]
        self.assertTrue(server.startswith("bible-app-db-"), server)
        self.assertEqual(
            flags,
            [
                ("--resource-group", "bible-app-rg"),
                ("--server-name", server),
                ("--name", server),
                ("--start-ip-address", "$MY_IP"),
                ("--end-ip-address", "$MY_IP"),
            ],
        )

    def test_list_rules_uses_server_name(self):
        flags = _split(_az_tokens(_dry_run("az-pg-list-rules")), LIST)
        by_flag = dict(flags)
        self.assertTrue(by_flag["--server-name"].startswith("bible-app-db-"))
        self.assertNotIn("--name", by_flag)
        self.assertEqual(
            flags,
            [
                ("--resource-group", "bible-app-rg"),
                ("--server-name", by_flag["--server-name"]),
                ("--output", "table"),
            ],
        )

    def test_remove_ip_names_the_rule_with_name_and_confirms(self):
        flags = _split(_az_tokens(_dry_run("az-pg-remove-ip", "RULE=my-rule")), DELETE)
        by_flag = dict(flags)
        self.assertEqual(
            flags,
            [
                ("--resource-group", "bible-app-rg"),
                ("--server-name", by_flag["--server-name"]),
                ("--name", "my-rule"),
                ("--yes", None),
            ],
        )
        self.assertNotEqual(by_flag["--name"], by_flag["--server-name"])

    def test_server_override_applies_to_every_target(self):
        add = dict(_split(_az_tokens(_dry_run("az-pg-add-ip", "SERVER=pitr-copy")), CREATE))
        listing = dict(_split(_az_tokens(_dry_run("az-pg-list-rules", "SERVER=pitr-copy")), LIST))
        remove = dict(
            _split(_az_tokens(_dry_run("az-pg-remove-ip", "SERVER=pitr-copy", "RULE=r1")), DELETE)
        )
        self.assertEqual(add["--server-name"], "pitr-copy")
        self.assertEqual(add["--name"], "pitr-copy")
        self.assertEqual(listing["--server-name"], "pitr-copy")
        self.assertEqual(remove["--server-name"], "pitr-copy")
        self.assertEqual(remove["--name"], "r1")

    def test_rule_name_flag_is_never_used(self):
        for target, extra in (
            ("az-pg-add-ip", ()),
            ("az-pg-list-rules", ()),
            ("az-pg-remove-ip", ("RULE=r1",)),
        ):
            with self.subTest(target=target):
                self.assertNotIn("--rule-name", _dry_run(target, *extra))

    def test_arguments_are_quoted(self):
        output = _dry_run("az-pg-remove-ip", "RULE=r1")
        for flag in ("--resource-group", "--server-name", "--name"):
            self.assertIn(f'{flag} "', output)
        self.assertIn('--start-ip-address "$MY_IP"', _dry_run("az-pg-add-ip").replace("\\\n", " "))

    def test_quoting_keeps_a_rule_name_with_spaces_as_one_argument(self):
        tokens = _az_tokens(_dry_run("az-pg-remove-ip", "RULE=my rule"))
        self.assertEqual(dict(_split(tokens, DELETE))["--name"], "my rule")


class MakefileFirewallFakeAzTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bin = Path(tmp.name)
        self.log = self.bin / "az.log"
        for name, body in (("az", FAKE_AZ), ("curl", FAKE_CURL)):
            path = self.bin / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def _make(self, *args):
        env = _env(PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", FAKE_AZ_LOG=str(self.log))
        return subprocess.run(
            ["make", *args], cwd=ROOT, env=env, capture_output=True, text=True
        )

    def _calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_remove_ip_without_rule_fails_before_calling_az(self):
        result = self._make("az-pg-remove-ip")
        self.assertEqual(result.returncode, 2)
        self.assertIn("RULE=rule-name", result.stdout)
        self.assertEqual(self._calls(), [])

    def test_remove_ip_with_empty_rule_fails_before_calling_az(self):
        result = self._make("az-pg-remove-ip", "RULE=")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self._calls(), [])

    def test_add_ip_passes_the_expected_argv_to_az(self):
        result = self._make("az-pg-add-ip", "SERVER=pitr-copy")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self._calls(),
            [
                CREATE
                + [
                    "--resource-group", "bible-app-rg",
                    "--server-name", "pitr-copy",
                    "--name", "pitr-copy",
                    "--start-ip-address", "203.0.113.7",
                    "--end-ip-address", "203.0.113.7",
                ]
            ],
        )

    def test_list_and_remove_pass_the_expected_argv_to_az(self):
        self.assertEqual(self._make("az-pg-list-rules", "SERVER=pitr-copy").returncode, 0)
        self.assertEqual(self._make("az-pg-remove-ip", "SERVER=pitr-copy", "RULE=r1").returncode, 0)
        self.assertEqual(
            self._calls(),
            [
                LIST + ["--resource-group", "bible-app-rg", "--server-name", "pitr-copy",
                        "--output", "table"],
                DELETE + ["--resource-group", "bible-app-rg", "--server-name", "pitr-copy",
                          "--name", "r1", "--yes"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
