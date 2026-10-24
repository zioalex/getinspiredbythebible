"""Offline tests for the Makefile (BITB-220). Standard library only.

Run with `make test-makefile` or `python3 -m unittest scripts.test_make_targets -v`.

Recipes are executed for real (not just `make -n`) inside a throwaway sandbox whose `az`,
`docker`, `kubectl`, `terraform`, `curl`, `sudo`, `bash`, `npm`, `npx`, `gradlew` and venv tools
are recording fakes, so these tests assert the exact command lines the Makefile builds and how
failures propagate -- without touching docker, the cloud, the network or a package index.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_make_targets as audit  # noqa: E402

ROOT = audit.ROOT
US = "\x1f"
RS = "\x1e"

# One recording fake serves every tool; behaviour is selected by the program name and FAKE_* env.
FAKE_TOOL = r"""#!/bin/bash
name=$(basename "$0")
# Build the whole record in a variable and append it with ONE write(): piped fakes
# (e.g. `kubectl create ... | kubectl apply`) run concurrently, and separate printf
# appends would interleave and corrupt a line. A single O_APPEND write under PIPE_BUF
# is atomic.
_log="$name"$'\x1f'"$PWD"
for _a in "$@"; do _log+=$'\x1f'"$_a"; done
for _k in $FAKE_ENV_KEYS; do _log+=$'\x1e'"$_k=${!_k-UNSET}"; done
printf '%s\n' "$_log" >> "${FAKE_LOG:?}"
fail="FAKE_FAIL_$(printf '%s' "$name" | tr 'a-z.-' 'A-Z__')"
if [ -n "${!fail:-}" ]; then echo "fake $name: forced failure" >&2; exit "${!fail}"; fi
case "$name" in
  curl) echo "${FAKE_CURL_OUT-203.0.113.7}" ;;
  sudo) exit "${FAKE_SUDO_RC:-1}" ;;
  terraform) [ "${1:-}" = version ] && echo "Terraform v${FAKE_TF_VERSION:-1.10.5}" ;;
  kubectl) [ "${1:-}" = create ] && printf 'apiVersion: v1\nkind: ConfigMap\n' ;;
  docker)
    [ "${1:-} ${2:-}" = "volume inspect" ] && [ -n "${FAKE_DOCKER_NO_VOLUME:-}" ] && exit 1
    [ "${1:-} ${2:-}" = "volume rm" ] && [ -n "${FAKE_DOCKER_VOLRM_FAIL:-}" ] && exit 1
    [ "${1:-}" = run ] && [ -n "${FAKE_DOCKER_RUN_OUT:-}" ] && echo "$FAKE_DOCKER_RUN_OUT"
    exit 0 ;;
  az)
    case "${1:-} ${2:-}" in
      "containerapp show")
        if printf '%s ' "$@" | grep -q fqdn; then echo "${FAKE_AZ_FQDN-app.example.azurecontainerapps.io}"
        else echo "${FAKE_AZ_IMAGE-testacr.azurecr.io/bible-backend:abc1234}"; fi ;;
      "acr repository") printf 'tag-one\ntag-two\n' ;;
      "storage account") echo "${FAKE_AZ_STORAGE-tfstateacct}" ;;
    esac ;;
  python)
    case "${1:-}" in
      -c) [ "${2:-}" = "import pytest, alembic" ] && exit "${FAKE_IMPORT_RC:-0}" ;;
      *generate-opencode-config.py)
        if [ -n "${FAKE_GEN_FAIL:-}" ]; then echo "generator exploded" >&2; exit 1; fi
        cat "${FAKE_GEN_SOURCE:?}" ;;
    esac
    if [ "${1:-} ${2:-}" = "-m pytest" ]; then
      case "${FAKE_FAIL_PYTEST:-}" in
        api) [[ $PWD == */api ]] && exit 1 ;;
        migrations) [[ $PWD == */scripts/migrations ]] && exit 1 ;;
        any) exit 1 ;;
      esac
    fi ;;
esac
exit 0
"""

ENV_KEYS = (
    "TAG DATABASE_URL RATE_LIMIT_BACKEND LLM_PROVIDER BACKEND_API_URL FRONTEND_URL "
    "PG_RG PG_SERVER SERVER DUMP_ARGS NEW_SERVER RESTORE_POINT DUMP"
)
SCRUBBED = set(ENV_KEYS.split()) | {
    "MAKEFLAGS", "MAKELEVEL", "MFLAGS", "BASE_URL", "CATEGORY", "NAMESPACE", "POD_IP",
    "COMPOSE_PROJECT_NAME", "ARGS", "RULE", "REPO", "VENV", "ALEMBIC_TEST_ALLOW_HOST",
    "NEXT_PUBLIC_API_URL", "ACR_NAME",
}


@dataclass
class Call:
    tool: str
    cwd: str
    args: list[str]
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Result:
    rc: int
    out: str
    err: str
    calls: list[Call]

    def of(self, tool: str, *prefix: str) -> list[Call]:
        return [c for c in self.calls if c.tool == tool and c.args[: len(prefix)] == list(prefix)]

    def argv(self, tool: str, *prefix: str) -> list[list[str]]:
        return [c.args for c in self.of(tool, *prefix)]

    @property
    def text(self) -> str:
        return self.out + self.err


class Sandbox:
    """A scratch checkout: real Makefile + real scripts/, fake everything that has side effects."""

    def __init__(self, with_venv: bool = True) -> None:
        # Upper-case + dot on purpose: docker-reset-db must sanitise the directory name.
        self.dir = Path(tempfile.mkdtemp(prefix="Make.Audit_"))
        self.log = self.dir / "fake.log"
        self.log.touch()
        (self.dir / "bin").mkdir()
        shutil.copy(ROOT / "Makefile", self.dir / "Makefile")
        for name in ("scripts", "k8s", "tools"):
            (self.dir / name).symlink_to(ROOT / name)
        for name in (".env.local.example", ".env.dev.example", "opencode.json"):
            shutil.copy(ROOT / name, self.dir / name)
        for d in ("api", "frontend", "android", "deployment", ".github/workflows"):
            (self.dir / d).mkdir(parents=True, exist_ok=True)
        (self.dir / "CHANGELOG.md").write_text("# changelog\n")
        (self.dir / ".secrets.baseline").write_text("{}\n")
        (self.dir / ".github/workflows/azure-deploy.yml").write_text('  TF_VERSION: "1.10.5"\n')
        (self.dir / "deployment/terraform.tfvars").write_text(
            'backend_image  = "old/backend:1"\nfrontend_image = "old/frontend:1"\n'
        )
        (self.dir / "deployment/terraform.tfvars.secrets").write_text("# secrets\n")
        self.write_env_production()
        for tool in (
            "az docker kubectl terraform curl sudo bash npm npx node dependency-check.sh"
        ).split():
            self._fake(self.dir / "bin" / tool)
        self._fake(self.dir / "android/gradlew")
        if with_venv:
            for tool in ("python", "pip", "detect-secrets", "pre-commit"):
                self._fake(self.dir / ".venv/bin" / tool)

    def _fake(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(FAKE_TOOL)
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def write_env_production(self, api_url: str = "https://api.example.org/a b") -> None:
        (self.dir / ".env.production").write_text(
            f'ACR_NAME=testacr\nNEXT_PUBLIC_API_URL="{api_url}"\n'
        )

    def cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)

    def make(self, *args: str, env: dict[str, str] | None = None) -> Result:
        run_env = {k: v for k, v in os.environ.items() if k not in SCRUBBED}
        run_env.update(
            PATH=f"{self.dir / 'bin'}:{os.environ['PATH']}",
            HOME=str(self.dir),
            LC_ALL="C",
            FAKE_LOG=str(self.log),
            FAKE_ENV_KEYS=ENV_KEYS,
            FAKE_GEN_SOURCE=str(ROOT / "opencode.json"),
        )
        run_env.update(env or {})
        self.log.write_text("")
        proc = subprocess.run(
            ["make", "-f", "Makefile", *args],
            cwd=self.dir,
            env=run_env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return Result(proc.returncode, proc.stdout, proc.stderr, self._calls())

    def _calls(self) -> list[Call]:
        calls = []
        # Split on the real newline only: str.splitlines() would also break on the
        # \x1e (RS) byte that separates the recorded env entries within one record.
        for line in self.log.read_text().split("\n"):
            if not line:
                continue
            head, *envs = line.split(RS)
            tool, cwd, *args = head.split(US)
            env = dict(e.split("=", 1) for e in envs)
            calls.append(Call(tool, str(Path(cwd).relative_to(self.dir) if cwd != str(self.dir) else "."), args, env))
        return calls


class SandboxCase(unittest.TestCase):
    with_venv = True

    def setUp(self) -> None:
        self.sb = Sandbox(with_venv=self.with_venv)
        self.addCleanup(self.sb.cleanup)

    def make(self, *args: str, **env: str) -> Result:
        return self.sb.make(*args, env=env)


# --------------------------------------------------------------------------- inventory ---


class InventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.targets = audit.load_targets()
        cls.cls = audit.load_classification()

    def test_every_target_is_classified_and_invariants_hold(self) -> None:
        self.assertEqual(audit.check_invariants(self.targets, self.cls), [])

    def test_every_target_dry_runs_cleanly(self) -> None:
        failures = {n: audit.dry_run(n).stderr.strip()[:200] for n in self.targets if audit.dry_run(n).returncode}
        self.assertEqual(failures, {})

    def test_recipe_paths_exist(self) -> None:
        missing = {
            n: audit.missing_paths(t, self.cls["generated_paths"]) for n, t in self.targets.items()
        }
        self.assertEqual({n: m for n, m in missing.items() if m}, {})

    def test_docs_reference_only_existing_targets(self) -> None:
        refs = audit.doc_references(
            set(self.targets), self.cls["doc_scan_skip"], self.cls["doc_ref_ignore"]
        )
        self.assertEqual(refs, [])

    def test_report_is_current(self) -> None:
        dry = {n: audit.dry_run(n).returncode for n in self.targets}
        report = audit.build_report(self.targets, self.cls, dry, [])
        self.assertEqual(audit.REPORT.read_text(encoding="utf-8"), report)

    def test_report_ends_with_exactly_one_newline(self) -> None:
        # Regression: --write appended a second \n, which end-of-file-fixer then stripped.
        dry = {n: 0 for n in self.targets}
        report = audit.build_report(self.targets, self.cls, dry, [])
        self.assertTrue(report.endswith("\n") and not report.endswith("\n\n"))
        on_disk = audit.REPORT.read_bytes()
        self.assertTrue(on_disk.endswith(b"\n") and not on_disk.endswith(b"\n\n"))

    def test_report_is_markdownlint_safe(self) -> None:
        # Regression: markdownlint --fix rewrites bare URLs and padded code spans, making
        # the generated file stale. Check the inputs it is built from.
        report = audit.REPORT.read_text(encoding="utf-8")
        stripped = re.sub(r"`[^`\n]*`", "", report)
        self.assertEqual(re.findall(r"https?://\S+", stripped), [], "bare URL outside a code span")
        spans = re.findall(r"`([^`\n]+)`", report)
        self.assertEqual([s for s in spans if s != s.strip()], [], "padded code span")

    def test_help_lists_every_described_target(self) -> None:
        # Regression: the help regex was [a-zA-Z_-]+ so test-e2e, test-e2e-local and
        # collect-k8s-diagnostics (digits in the name) never appeared.
        hidden = [n for n, t in self.targets.items() if t.help_text and not t.in_help]
        self.assertEqual(hidden, [])
        for name in ("test-e2e", "test-e2e-local", "collect-k8s-diagnostics"):
            self.assertTrue(self.targets[name].in_help, name)

    def test_phony_covers_everything_but_the_env_file_rules(self) -> None:
        not_phony = sorted(n for n, t in self.targets.items() if not t.phony)
        self.assertEqual(not_phony, [".env.dev", ".env.local"])

    def test_every_declared_phony_target_is_discovered(self) -> None:
        # Regression: the command-line goal `::` in `make -pRrq :` leaked the
        # "# Not a target" flag onto the next target, dropping `security`.
        text = (ROOT / "Makefile").read_text()
        block = re.search(r"^\.PHONY:\s*(.*(?:\n\t.*)*)", text, re.M).group(1)
        declared = set(block.replace("\\", " ").split())
        missing = sorted(declared - set(self.targets))
        self.assertEqual(missing, [], f"declared .PHONY targets not discovered: {missing}")
        self.assertIn("security", self.targets)

    def test_classification_references_real_tests(self) -> None:
        names = {n for n in dir(sys.modules[__name__]) if n.endswith("Tests") or n.endswith("Case")}
        known: set[str] = set()
        for cname in names:
            klass = getattr(sys.modules[__name__], cname)
            known |= {f"{cname}.{m}" for m in dir(klass) if m.startswith("test_")}
        for target, entry in self.cls["targets"].items():
            for test in entry.get("tests", []):
                self.assertIn(test, known, f"{target} cites unknown test {test}")
        for defect in self.cls["defects"]:
            for test in filter(None, (t.strip() for t in defect.get("test", "").split(","))):
                self.assertIn(test, known, f"{defect['id']} cites unknown test {test}")

    def test_android_compose_matches_ci_workflow(self) -> None:
        # Regression: `./gradlew testDebugCompose` is not a Gradle task.
        workflow = (ROOT / ".github/workflows/android-compose-tests.yml").read_text()
        for flag in (":app:testDebugUnitTest", "-PcomposeTestsOnly", '--tests "*ComposeTest"'):
            self.assertIn(flag, workflow)
        gradle = (ROOT / "android/app/build.gradle.kts").read_text()
        self.assertNotIn('register<Test>("testDebugCompose")', gradle)
        self.assertNotIn("testDebugCompose", (ROOT / "Makefile").read_text().replace("`testDebugCompose`", ""))

    def test_dev_compose_volume_name_is_declared(self) -> None:
        # Regression: the Makefile removed getinspired-dev_postgres_data, a volume that never existed.
        compose = (ROOT / "docker-compose.dev.yml").read_text()
        volumes = re.search(r"^volumes:\n((?:  .*\n|\n)+)", compose, re.M)
        declared = re.findall(r"^  (\w+):", volumes.group(1), re.M)
        self.assertIn("postgres_data_dev", declared)
        self.assertNotIn("postgres_data", declared)

    def test_make_firewall_flags_match_azure_cli_grammar(self) -> None:
        # The retired --rule-name flag must not appear in any recipe; it is still named in
        # the Makefile comment that explains why it is wrong, so exclude whole-line comments.
        mk = "\n".join(
            ln for ln in (ROOT / "Makefile").read_text().splitlines()
            if not ln.lstrip().startswith("#")
        )
        self.assertNotIn("--rule-name", mk)
        for path in ("deployment/README.md", "deployment/scripts/import-existing-resources.sh"):
            self.assertNotIn("--rule-name", (ROOT / path).read_text(), path)


# ------------------------------------------------------------------------ make plumbing ---


class MakePlumbingTests(SandboxCase):
    def test_default_goal_prints_help_not_first_recipe(self) -> None:
        res = self.make()
        self.assertEqual(res.rc, 0)
        self.assertIn("Available commands", res.out)
        self.assertEqual(res.calls, [])

    def test_files_named_like_targets_do_not_make_them_up_to_date(self) -> None:
        for name in ("test", "lint", "clean", "docker-up", "help", "format"):
            (self.sb.dir / name).write_text("")
        res = self.make("-n", "lint", "test", "clean")
        self.assertNotIn("is up to date", res.text)
        self.assertIn("ruff", res.out)

    def test_absolute_venv_override_is_not_prefixed_with_cwd(self) -> None:
        # Regression: $(CURDIR)/$(PYTHON) turned VENV=/opt/venv into <cwd>//opt/venv/bin/python.
        res = self.make("-n", "lint", "VENV=/opt/shared-venv")
        self.assertIn("/opt/shared-venv/bin/python -m ruff", res.out)
        self.assertNotIn(f"{self.sb.dir}//opt", res.out)
        res = self.make("-n", "lint", "VENV=rel-venv")
        self.assertIn(f"{self.sb.dir}/rel-venv/bin/python -m ruff", res.out)

    def test_env_file_is_created_from_its_template_once(self) -> None:
        res = self.make("docker-up")
        self.assertEqual(res.rc, 0)
        self.assertEqual(
            (self.sb.dir / ".env.local").read_text(), (ROOT / ".env.local.example").read_text()
        )
        (self.sb.dir / ".env.local").write_text("EDITED=1\n")
        self.make("docker-up")
        self.assertEqual((self.sb.dir / ".env.local").read_text(), "EDITED=1\n")


class ScriptPythonTests(unittest.TestCase):
    def test_script_python_prefers_venv_and_falls_back_to_python3(self) -> None:
        for with_venv, expected in ((True, "/.venv/bin/python -m pytest"), (False, "python3 -m pytest")):
            sb = Sandbox(with_venv=with_venv)
            self.addCleanup(sb.cleanup)
            res = sb.make("-n", "test-dns-watchdog")
            self.assertIn(expected, res.out, with_venv)
            if not with_venv:
                self.assertNotIn(".venv", res.out)


# ------------------------------------------------------------------------------ python ---


class PythonTargetTests(SandboxCase):
    def test_test_backend_fails_when_pytest_fails(self) -> None:
        # Regression: both pytest lines ended in `|| true`, so a red suite printed success.
        for where in ("api", "migrations"):
            res = self.make("test-backend", FAKE_FAIL_PYTEST=where)
            self.assertNotEqual(res.rc, 0, where)
            self.assertNotIn("Backend tests complete", res.out, where)

    def test_test_backend_supplies_ci_equivalent_env(self) -> None:
        res = self.make("test-backend")
        self.assertEqual(res.rc, 0, res.text)
        api = [c for c in res.of("python", "-m", "pytest") if c.cwd == "api"]
        self.assertEqual(len(api), 1)
        self.assertEqual(api[0].args, ["-m", "pytest", "-v", "--tb=short"])
        self.assertEqual(api[0].env["DATABASE_URL"], "postgresql://test:test@localhost/test")  # pragma: allowlist secret
        self.assertEqual(api[0].env["RATE_LIMIT_BACKEND"], "memory")
        self.assertEqual(api[0].env["LLM_PROVIDER"], "ollama")

    def test_test_backend_respects_caller_env(self) -> None:
        res = self.make("test-backend", DATABASE_URL="postgresql://u@localhost/mine", RATE_LIMIT_BACKEND="postgres")
        api = [c for c in res.of("python", "-m", "pytest") if c.cwd == "api"][0]
        self.assertEqual(api.env["DATABASE_URL"], "postgresql://u@localhost/mine")
        self.assertEqual(api.env["RATE_LIMIT_BACKEND"], "postgres")

    def test_check_all_fails_when_backend_pytest_fails(self) -> None:
        ok = self.make("check-all")
        self.assertEqual(ok.rc, 0, ok.text)
        bad = self.make("check-all", FAKE_FAIL_PYTEST="api")
        self.assertNotEqual(bad.rc, 0)
        self.assertNotIn("All checks passed", bad.out)

    def test_golden_test_does_not_need_a_real_database_url(self) -> None:
        res = self.make("golden-test")
        call = res.of("python", "-m", "pytest")[0]
        self.assertEqual(call.args, ["-m", "pytest", "tests/test_golden_set.py", "-v", "-m", "golden_set"])
        self.assertEqual(call.env["DATABASE_URL"], "postgresql://test:test@localhost/test")  # pragma: allowlist secret
        res = self.make("golden-test", DATABASE_URL="postgresql://u@localhost/mine")
        self.assertEqual(res.of("python", "-m", "pytest")[0].env["DATABASE_URL"], "postgresql://u@localhost/mine")

    def test_golden_live_quotes_user_values(self) -> None:
        res = self.make("golden-live")
        self.assertEqual(
            res.of("python")[-1].args,
            ["scripts/run_golden_set.py", "--base-url", "http://localhost:8000", "--category", "interpretation"],
        )
        evil = "http://x/;touch pwned"
        res = self.make("golden-live", BASE_URL=evil, CATEGORY="a b")
        args = res.of("python")[-1].args
        self.assertEqual(args[args.index("--base-url") + 1], evil)
        self.assertEqual(args[args.index("--category") + 1], "a b")
        self.assertFalse((self.sb.dir / "pwned").exists())

    def test_alembic_roundtrip_sequence_on_local_host(self) -> None:
        res = self.make("alembic-roundtrip", DATABASE_URL="postgresql+asyncpg://u:p@localhost:5432/db")
        self.assertEqual(res.rc, 0, res.text)
        steps = [a[2:] for a in res.argv("python", "-m", "alembic")]
        self.assertEqual(steps, [["upgrade", "head"], ["check"], ["downgrade", "base"], ["upgrade", "head"]])

    def test_alembic_roundtrip_refuses_unsafe_targets(self) -> None:
        cases = {
            "unset": {},
            "remote host": {"DATABASE_URL": "postgresql://u:p@prod.example.com/db"},
            "host= override on a local authority": {"DATABASE_URL": "postgresql://u:p@localhost/db?host=prod.example.com"},
            "hostaddr= override": {"DATABASE_URL": "postgresql://u:p@127.0.0.1/db?hostaddr=10.1.1.1"},
        }
        for label, env in cases.items():
            with self.subTest(label):
                res = self.make("alembic-roundtrip", **env)
                self.assertNotEqual(res.rc, 0)
                self.assertEqual(res.argv("python", "-m", "alembic"), [])

    def test_alembic_roundtrip_override_flag_is_explicit(self) -> None:
        res = self.make(
            "alembic-roundtrip", DATABASE_URL="postgresql://u:p@ci-db.internal/db", ALEMBIC_TEST_ALLOW_HOST="1"
        )
        self.assertEqual(res.rc, 0, res.text)
        self.assertEqual(len(res.argv("python", "-m", "alembic")), 4)

    def test_db_upgrade_only_upgrades(self) -> None:
        res = self.make("db-upgrade")
        self.assertEqual([a[2:] for a in res.argv("python", "-m", "alembic")], [["upgrade", "head"], ["current"]])

    def test_update_baseline_uses_scan_baseline_without_update_flag(self) -> None:
        res = self.make("update-baseline")
        self.assertEqual(res.argv("detect-secrets"), [["scan", "--baseline", ".secrets.baseline"]])

    @unittest.skipUnless(
        (ROOT / ".venv/bin/detect-secrets").exists() or shutil.which("detect-secrets"),
        "detect-secrets not installed",
    )
    def test_detect_secrets_cli_accepts_scan_baseline_and_rejects_update(self) -> None:
        exe = str(ROOT / ".venv/bin/detect-secrets") if (ROOT / ".venv/bin/detect-secrets").exists() else "detect-secrets"
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "a.txt").write_text("hello\n")
            base = Path(tmp, "base.json")
            first = subprocess.run([exe, "scan"], cwd=tmp, capture_output=True, text=True, check=False)
            base.write_text(first.stdout)
            ok = subprocess.run([exe, "scan", "--baseline", str(base)], cwd=tmp, capture_output=True, text=True, check=False)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            bad = subprocess.run([exe, "scan", "--baseline", str(base), "--update"], cwd=tmp, capture_output=True, text=True, check=False)
            self.assertNotEqual(bad.returncode, 0)

    def test_gen_opencode_config_replaces_atomically(self) -> None:
        src = self.sb.dir / "generated.json"
        src.write_text('{"agent": {}}\n')
        res = self.make("gen-opencode-config", FAKE_GEN_SOURCE=str(src))
        self.assertEqual(res.rc, 0, res.text)
        target = self.sb.dir / "opencode.json"
        self.assertEqual(target.read_text(), '{"agent": {}}\n')
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)
        self.assertEqual(list(self.sb.dir.glob("opencode.json.*")), [])

    def test_gen_opencode_config_failure_keeps_the_committed_file(self) -> None:
        # Regression: `> opencode.json` truncated the artifact before the generator ran.
        before = (self.sb.dir / "opencode.json").read_text()
        res = self.make("gen-opencode-config", FAKE_GEN_FAIL="1")
        self.assertNotEqual(res.rc, 0)
        self.assertEqual((self.sb.dir / "opencode.json").read_text(), before)
        self.assertEqual(list(self.sb.dir.glob("opencode.json.*")), [])

    def test_sync_opencode_configmap_pipes_dry_run_into_apply(self) -> None:
        res = self.make("sync-opencode-configmap")
        self.assertEqual(res.rc, 0, res.text)
        # `kubectl create ... | kubectl apply -f -` runs both stages concurrently, so their
        # log order is not guaranteed; assert the two calls are present without ordering them.
        calls = res.argv("kubectl")
        self.assertEqual(len(calls), 2)
        self.assertIn(
            ["create", "configmap", "opencode-config", "--from-file=opencode.json=opencode.json",
             "-n", "kubeopencode-system", "--dry-run=client", "-o", "yaml"],
            calls,
        )
        self.assertIn(["apply", "-f", "-"], calls)

    def test_python_tool_targets_pass_through_user_args(self) -> None:
        res = self.make("export-blocked-samples", ARGS="--format csv --since 2026-05-01")
        self.assertEqual(res.of("python")[-1].args, ["scripts/export_blocked_samples.py", "--format", "csv", "--since", "2026-05-01"])
        res = self.make("follow-up-eval", ARGS="--language it")
        self.assertEqual(res.of("python")[-1].args, ["scripts/run_follow_up_eval.py", "--language", "it"])
        res = self.make("follow-up-checklist")
        self.assertEqual(res.of("python")[-1].args, ["scripts/run_follow_up_eval.py", "--checklist"])
        self.assertEqual(self.make("validate-env-strict").of("python")[-1].args, ["scripts/validate-env.py", "--strict"])

    def test_functional_and_e2e_targets_set_their_urls(self) -> None:
        self.assertEqual(self.make("test-functional-local").of("python", "-m", "pytest")[0].env["BACKEND_API_URL"], "http://localhost:8000")
        self.assertEqual(self.make("test-e2e-local").of("python", "-m", "pytest")[0].env["FRONTEND_URL"], "http://localhost:3000")
        res = self.make("test-functional", BACKEND_API_URL="https://api.example.org")
        self.assertEqual(res.of("python", "-m", "pytest")[0].env["BACKEND_API_URL"], "https://api.example.org")
        # test-e2e targets the production frontend by default: no FRONTEND_URL override.
        e2e = self.make("test-e2e").of("python", "-m", "pytest")[0]
        self.assertEqual(e2e.args, ["-m", "pytest", "tests/e2e/", "-m", "e2e", "-v", "--tb=short"])
        self.assertEqual(e2e.env["FRONTEND_URL"], "UNSET")

    def test_lint_format_typecheck_security_command_lines(self) -> None:
        for target, needles in {
            "lint": ["ruff", "black", "lint"],
            "format": ["black", "isort", "ruff", "prettier"],
            "type-check": ["mypy", "tsc"],
            "security": ["bandit", "safety", "audit", "detect-secrets"],
        }.items():
            with self.subTest(target):
                res = self.make(target)
                self.assertEqual(res.rc, 0, res.text)
                flat = " ".join(" ".join(c.args) + " " + c.tool for c in res.calls)
                for needle in needles:
                    self.assertIn(needle, flat)

    def test_frontend_and_hook_targets(self) -> None:
        res = self.make("test-frontend")
        self.assertEqual(
            [(c.tool, c.args) for c in res.calls],
            [("npm", ["run", "lint"]), ("npx", ["tsc", "--noEmit"]), ("npm", ["run", "build"])],
        )
        self.assertEqual(self.make("pre-commit").argv("pre-commit", "run"), [["run", "--all-files"]])
        self.assertEqual(self.make("install-hooks").argv("pre-commit"), [["install"], ["install", "--hook-type", "commit-msg"]])

    def test_install_deps_installs_only_when_sentinel_import_fails(self) -> None:
        self.assertEqual(self.make("install-deps").of("pip"), [])
        res = self.make("install-deps", FAKE_IMPORT_RC="1")
        self.assertEqual(len(res.of("pip")), 2)

    def test_metrics_targets_use_stdlib_python3(self) -> None:
        for target in ("repo-metrics", "audit-metrics"):
            res = self.make("-n", target)
            self.assertIn("python3 tools/", res.out)
            self.assertNotIn(".venv", res.out)


# -------------------------------------------------------------------------------- clean ---


class CleanupTests(SandboxCase):
    def _populate(self) -> None:
        for d in ("frontend/.next", "frontend/node_modules", "api/__pycache__"):
            (self.sb.dir / d).mkdir(parents=True)
            (self.sb.dir / d / "x").write_text("x")

    def test_clean_never_blocks_on_a_sudo_password_prompt(self) -> None:
        # Regression: bare `sudo rm` hung waiting for a password; -n fails fast and rm takes over.
        self._populate()
        res = self.make("clean")
        self.assertEqual(res.rc, 0, res.text)
        self.assertTrue(res.of("sudo"))
        self.assertTrue(all(c.args[0] == "-n" for c in res.of("sudo")))
        for d in ("frontend/.next", "frontend/node_modules", "api/__pycache__"):
            self.assertFalse((self.sb.dir / d).exists(), d)

    def test_clean_all_removes_venv_and_reports_once(self) -> None:
        res = self.make("clean-all")
        self.assertFalse((self.sb.dir / ".venv").exists())
        self.assertEqual(res.out.count("Full cleanup complete"), 1)

    def test_fix_permissions_does_not_claim_a_full_cleanup(self) -> None:
        # Regression: the clean-all success line was stranded at the end of fix-permissions.
        self._populate()
        res = self.make("fix-permissions", FAKE_SUDO_RC="0")
        self.assertEqual(res.rc, 0, res.text)
        self.assertNotIn("Full cleanup", res.out)
        self.assertEqual(
            sorted(a[-1] for a in res.argv("sudo")), ["frontend/.next", "frontend/node_modules"]
        )


# ---------------------------------------------------------------------------------- az ---


class AzureTests(SandboxCase):
    SERVER = "bible-app-db-mb0172"
    FW = ["postgres", "flexible-server", "firewall-rule"]

    def test_firewall_add_ip_uses_server_name_and_name(self) -> None:
        res = self.make("az-pg-add-ip")
        self.assertEqual(res.rc, 0, res.text)
        self.assertEqual(
            res.argv("az"),
            [self.FW + ["create", "--resource-group", "bible-app-rg", "--server-name", self.SERVER,
                        "--name", self.SERVER, "--start-ip-address", "203.0.113.7",
                        "--end-ip-address", "203.0.113.7"]],
        )

    def test_firewall_list_and_remove(self) -> None:
        self.assertEqual(
            self.make("az-pg-list-rules", SERVER="restored-copy").argv("az"),
            [self.FW + ["list", "--resource-group", "bible-app-rg", "--server-name", "restored-copy", "--output", "table"]],
        )
        self.assertEqual(
            self.make("az-pg-remove-ip", RULE="my-rule").argv("az"),
            [self.FW + ["delete", "--resource-group", "bible-app-rg", "--server-name", self.SERVER, "--name", "my-rule", "--yes"]],
        )

    def test_firewall_never_emits_the_retired_rule_name_flag(self) -> None:
        calls = []
        for t, env in (("az-pg-add-ip", {}), ("az-pg-list-rules", {}), ("az-pg-remove-ip", {"RULE": "r"})):
            calls += self.make(t, **env).argv("az")
        self.assertTrue(calls)
        self.assertFalse([a for a in calls if "--rule-name" in a])

    def test_firewall_remove_requires_a_rule(self) -> None:
        res = self.make("az-pg-remove-ip")
        self.assertNotEqual(res.rc, 0)
        self.assertEqual(res.calls, [])

    def test_firewall_add_ip_aborts_without_an_ip(self) -> None:
        for env in ({"FAKE_FAIL_CURL": "22"}, {"FAKE_CURL_OUT": ""}):
            with self.subTest(env):
                res = self.make("az-pg-add-ip", **env)
                self.assertNotEqual(res.rc, 0)
                self.assertEqual(res.of("az"), [])

    def test_firewall_server_value_is_one_argument(self) -> None:
        res = self.make("az-pg-list-rules", SERVER="x;touch pwned")
        args = res.of("az")[0].args
        self.assertEqual(args[args.index("--server-name") + 1], "x;touch pwned")
        self.assertFalse((self.sb.dir / "pwned").exists())

    def test_acr_listing_succeeds_and_propagates_failure(self) -> None:
        for target, flag in (("az-acr-list-images", "--detail"), ("az-acr-list-tags", "--output")):
            with self.subTest(target):
                res = self.make(target)
                self.assertEqual(res.rc, 0, res.text)
                self.assertEqual(
                    [a[a.index("--repository") + 1] for a in res.argv("az")], ["bible-backend", "bible-frontend"]
                )
                self.assertIn(flag, res.argv("az")[0])
                self.assertIn("tag-one", res.out)
                # Regression: `az ... 2>/dev/null | head || echo` exited 0 when az failed.
                bad = self.make(target, FAKE_FAIL_AZ="1")
                self.assertNotEqual(bad.rc, 0)

    def test_get_backend_url(self) -> None:
        self.assertIn("https://app.example.azurecontainerapps.io", self.make("docker-get-backend-url").out)
        # Regression: `az | xargs` returned xargs's status, hiding a failed az.
        self.assertNotEqual(self.make("docker-get-backend-url", FAKE_FAIL_AZ="1").rc, 0)
        self.assertNotEqual(self.make("docker-get-backend-url", FAKE_AZ_FQDN="").rc, 0)

    def test_deployed_images_resolves_digest_and_reports_failures(self) -> None:
        res = self.make("az-deployed-images")
        self.assertEqual(res.rc, 0, res.text)
        digest_calls = res.argv("az", "acr")
        self.assertEqual(len(digest_calls), 2)
        self.assertIn("[?name=='abc1234'].{Tag: name, Digest: digest, Created: createdTime}", digest_calls[0])
        bad = self.make("az-deployed-images", FAKE_FAIL_AZ="1")
        self.assertNotEqual(bad.rc, 0)
        self.assertIn("Could not retrieve backend image", bad.out)

    def test_deploy_prod_quick_updates_both_apps(self) -> None:
        res = self.make("docker-deploy-prod-quick")
        self.assertEqual(res.rc, 0, res.text)
        upd = res.argv("az", "containerapp", "update")
        self.assertEqual(
            [(a[a.index("--name") + 1], a[a.index("--resource-group") + 1], a[a.index("--image") + 1]) for a in upd],
            [("bible-app-backend", "bible-app-rg", "testacr.azurecr.io/bible-backend:latest"),
             ("bible-app-frontend", "bible-app-rg", "testacr.azurecr.io/bible-frontend:latest")],
        )

    def test_log_targets(self) -> None:
        for target, app, kind in (
            ("az-logs-backend", "bible-app-backend", "console"),
            ("az-logs-frontend", "bible-app-frontend", "console"),
            ("az-logs-backend-system", "bible-app-backend", "system"),
            ("az-logs-frontend-system", "bible-app-frontend", "system"),
        ):
            with self.subTest(target):
                self.assertEqual(
                    self.make(target).argv("az"),
                    [["containerapp", "logs", "show", "--name", app, "--resource-group", "bible-app-rg",
                      "--type", kind, "--follow"]],
                )

    def test_image_info_requires_repo_and_tag(self) -> None:
        self.assertNotEqual(self.make("az-image-info").rc, 0)
        res = self.make("az-image-info", REPO="bible-backend", TAG="abc1234")
        self.assertEqual(res.rc, 0, res.text)
        self.assertEqual(res.argv("az")[0][:4], ["acr", "repository", "show-tags", "--name"])

    def test_db_helper_targets_hand_the_right_command_and_env_to_the_script(self) -> None:
        table = {
            "db-backup-info": "info", "db-backup": "dump", "db-restore-verify": "verify",
            "db-restore-local": "restore-local", "db-restore-new-server": "restore-new-server",
            "db-restore-same-server": "restore-same-server", "db-rehearse-alembic": "rehearse",
            "db-server-url": "server-url", "db-delete-server": "delete-server",
        }
        for target, command in table.items():
            with self.subTest(target):
                res = self.make(target, SERVER="copy-1", DUMP="backups/x.dump")
                self.assertEqual(res.argv("bash"), [["scripts/db-backup-restore.sh", command]])
                env = res.of("bash")[0].env
                self.assertEqual((env["PG_RG"], env["PG_SERVER"]), ("bible-app-rg", "bible-app-db-mb0172"))
        self.assertEqual(self.make("db-server-url", SERVER="copy-1").of("bash")[0].env["SERVER"], "copy-1")
        schema = self.make("db-backup-schema", DUMP_ARGS="--exclude-table x").of("bash")[0]
        self.assertEqual(schema.args, ["scripts/db-backup-restore.sh", "dump"])
        self.assertEqual(schema.env["DUMP_ARGS"], "--schema-only --exclude-table x")


# ---------------------------------------------------------------------------- terraform ---


class TerraformTests(SandboxCase):
    VARS = ["-var-file=terraform.tfvars", "-var-file=terraform.tfvars.secrets"]

    def test_plan_apply_destroy_refresh_use_both_var_files_in_deployment(self) -> None:
        table = {
            "tf-plan": ["plan"], "tf-apply": ["apply"], "tf-apply-auto": ["apply"],
            "tf-destroy": ["destroy"], "tf-refresh": ["refresh"],
        }
        for target, verb in table.items():
            with self.subTest(target):
                res = self.make(target)
                self.assertEqual(res.rc, 0, res.text)
                call = res.of("terraform")[0]
                self.assertEqual(call.cwd, "deployment")
                extra = ["-auto-approve"] if target == "tf-apply-auto" else []
                self.assertEqual(call.args, verb + self.VARS + extra)

    def test_secrets_file_is_required(self) -> None:
        (self.sb.dir / "deployment/terraform.tfvars.secrets").unlink()
        for target in ("tf-plan", "tf-apply", "tf-apply-auto", "tf-destroy", "tf-refresh"):
            with self.subTest(target):
                res = self.make(target)
                self.assertNotEqual(res.rc, 0)
                self.assertEqual(res.of("terraform"), [])

    def test_read_only_and_format_targets(self) -> None:
        self.assertEqual(self.make("tf-fmt").argv("terraform"), [["fmt", "-recursive"]])
        self.assertEqual(self.make("tf-output").argv("terraform"), [["output"]])
        self.assertEqual(self.make("tf-state-list").argv("terraform"), [["state", "list"]])
        self.assertEqual(self.make("tf-validate").argv("terraform"), [["init", "-backend=false", "-upgrade"], ["validate"]])

    def test_version_check_warns_on_mismatch_but_does_not_fail(self) -> None:
        self.assertIn("versions match", self.make("tf-check-version").out)
        res = self.make("tf-check-version", FAKE_TF_VERSION="1.9.0")
        self.assertEqual(res.rc, 0)
        self.assertIn("Version mismatch", res.out)

    def test_init_prefers_backend_hcl_then_detects_the_storage_account(self) -> None:
        (self.sb.dir / "deployment/backend.hcl").write_text("")
        self.assertIn(["init", "-backend-config=backend.hcl"], self.make("tf-init").argv("terraform"))
        (self.sb.dir / "deployment/backend.hcl").unlink()
        res = self.make("tf-init")
        init = [a for a in res.argv("terraform") if a[:1] == ["init"]][0]
        self.assertIn("-backend-config=storage_account_name=tfstateacct", init)
        self.assertIn("-backend-config=key=bible-app.tfstate", init)
        bad = self.make("tf-init", FAKE_AZ_STORAGE="")
        self.assertNotEqual(bad.rc, 0)
        self.assertEqual([a for a in bad.argv("terraform") if a[:1] == ["init"]], [])


# ---------------------------------------------------------------------------- docker ---


class DockerTests(SandboxCase):
    DEV = ["compose", "-p", "getinspired-dev", "--env-file", ".env.dev", "-f", "docker-compose.dev.yml"]
    LP = ["compose", "-p", "getinspired-local-prod"]

    def test_compose_command_lines(self) -> None:
        table = {
            "docker-up": [["compose", "--env-file", ".env.local", "up", "-d"]],
            "docker-up-gpu": [["compose", "--env-file", ".env.local", "-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml", "up", "-d"]],
            "docker-down": [["compose", "down"]],
            "docker-logs": [["compose", "logs", "-f"]],
            "docker-build": [["compose", "build"]],
            "docker-restart": [["compose", "restart"]],
            "docker-restart-api": [["compose", "restart", "api"]],
            "docker-restart-frontend": [["compose", "restart", "frontend"]],
            "docker-test": [["compose", "build", "api", "frontend"], ["compose", "run", "--rm", "api", "pytest", "-v"]],
            "docker-down-dev": [self.DEV + ["down"]],
            "docker-logs-dev": [self.DEV + ["logs", "-f"]],
            "docker-restart-dev": [self.DEV + ["restart"]],
            "docker-restart-dev-api": [self.DEV + ["restart", "api"]],
            "docker-restart-dev-frontend": [self.DEV + ["restart", "frontend"]],
            "docker-reinit-dev-db": [self.DEV + ["rm", "-sf", "db-init"], self.DEV + ["up", "-d", "db-init"]],
            "docker-logs-dev-init": [["logs", "-f", "getinspired-dev-db-init-1"]],
            "docker-down-local-prod": [self.LP + ["-f", "docker-compose.local-prod.yml", "down", "--remove-orphans"]],
            "docker-logs-local-prod": [self.LP + ["-f", "docker-compose.local-prod.yml", "logs", "-f"]],
            "docker-restart-local-prod-api": [self.LP + ["-f", "docker-compose.local-prod.yml", "restart", "api"]],
            "docker-up-local-prod": [self.LP + ["--env-file", ".env.production", "-f", "docker-compose.local-prod.yml", "up", "-d"]],
            "docker-up-local-prod-build": [self.LP + ["--env-file", ".env.production", "-f", "docker-compose.local-prod.yml", "up", "-d", "--build"]],
            "docker-up-prod": [["compose", "--env-file", ".env.production", "up", "-d", "--build"]],
            "docker-up-prod-gpu": [["compose", "--env-file", ".env.production", "-f", "docker-compose.yml", "-f", "docker-compose.gpu.yml", "up", "-d", "--build"]],
            "docker-up-dev-gpu": [["volume", "inspect", "ollama_data"], self.DEV + ["-f", "docker-compose.gpu.yml", "up", "-d"]],
            "docker-up-dev": [["volume", "inspect", "ollama_data"], self.DEV + ["up", "-d"]],
        }
        for target, expected in table.items():
            with self.subTest(target):
                res = self.make(target)
                self.assertEqual(res.rc, 0, res.text)
                self.assertEqual(res.argv("docker"), expected)

    def test_dev_stack_creates_the_shared_ollama_volume_when_absent(self) -> None:
        res = self.make("docker-up-dev", FAKE_DOCKER_NO_VOLUME="1")
        self.assertIn(["volume", "create", "ollama_data"], res.argv("docker"))

    def test_production_targets_refuse_without_env_file(self) -> None:
        (self.sb.dir / ".env.production").unlink()
        for target in ("docker-up-prod", "docker-up-local-prod", "docker-up-prod-gpu", "docker-up-local-prod-acr-be"):
            with self.subTest(target):
                res = self.make(target)
                self.assertNotEqual(res.rc, 0)
                self.assertEqual(res.of("docker"), [])

    def test_acr_backend_stack_passes_tag_and_warns_on_remote_api_url(self) -> None:
        res = self.make("docker-up-local-prod-acr-be", TAG="abc1234")
        call = res.of("docker")[0]
        self.assertEqual(call.env["TAG"], "abc1234")
        self.assertIn("docker-compose.local-prod-acr-be.yml", call.args)
        self.assertIn("NEXT_PUBLIC_API_URL", res.out)  # remote URL warning
        self.sb.write_env_production("http://localhost:8000")
        self.assertNotIn("NEXT_PUBLIC_API_URL", self.make("docker-up-local-prod").out)
        self.assertEqual(self.make("docker-up-local-prod-acr-be").of("docker")[0].env["TAG"], "")

    def test_reset_db_removes_the_volume_compose_would_actually_name(self) -> None:
        # Regression: the volume name was hardcoded, so a renamed clone or worktree "reset" nothing.
        expected = re.sub(r"[^a-z0-9_-]", "", self.sb.dir.name.lower()) + "_postgres_data"
        res = self.make("docker-reset-db")
        self.assertEqual(res.argv("docker", "volume"), [["volume", "rm", expected]])
        self.assertTrue(res.argv("docker", "compose"), [["compose", "down"]])
        res = self.make("docker-reset-db", COMPOSE_PROJECT_NAME="myproj")
        self.assertEqual(res.argv("docker", "volume"), [["volume", "rm", "myproj_postgres_data"]])
        self.assertIn("Volume not found", self.make("docker-reset-db", FAKE_DOCKER_VOLRM_FAIL="1").out)

    def test_reset_db_dev_removes_the_declared_dev_volume(self) -> None:
        res = self.make("docker-reset-db-dev")
        self.assertEqual(res.argv("docker", "compose"), [["compose", "-p", "getinspired-dev", "-f", "docker-compose.dev.yml", "down"]])
        self.assertEqual(res.argv("docker", "volume"), [["volume", "rm", "getinspired-dev_postgres_data_dev"]])

    def test_prod_image_builds_and_pushes_to_acr(self) -> None:
        res = self.make("docker-build-prod-backend")
        self.assertEqual(res.rc, 0, res.text)
        self.assertEqual(res.argv("az"), [["acr", "login", "--name", "testacr"]])
        self.assertEqual(
            res.argv("docker"),
            [["build", "-t", "testacr.azurecr.io/bible-backend:latest", "-t", "testacr.azurecr.io/bible-backend:latest", "./api"],
             ["push", "testacr.azurecr.io/bible-backend:latest"], ["push", "testacr.azurecr.io/bible-backend:latest"]],
        )

    def test_frontend_build_arg_is_one_argument_and_changelog_is_unstaged(self) -> None:
        res = self.make("docker-build-prod-frontend")
        self.assertEqual(res.rc, 0, res.text)
        build = res.argv("docker", "build")[0]
        self.assertEqual(build[build.index("--build-arg") + 1], "NEXT_PUBLIC_API_URL=https://api.example.org/a b")
        self.assertFalse((self.sb.dir / "frontend/CHANGELOG.md").exists())
        # The staged CHANGELOG must be removed even when the build fails.
        res = self.make("docker-build-prod-frontend", FAKE_FAIL_DOCKER="1")
        self.assertNotEqual(res.rc, 0)
        self.assertFalse((self.sb.dir / "frontend/CHANGELOG.md").exists())

    def test_verify_frontend_fails_when_localhost_is_baked_in(self) -> None:
        self.assertEqual(self.make("docker-verify-frontend").rc, 0)
        res = self.make("docker-verify-frontend", FAKE_DOCKER_RUN_OUT="x localhost:8000 y")
        self.assertNotEqual(res.rc, 0)
        self.assertIn("localhost:8000 found in image", res.out)

    def test_update_tfvars_and_terraform_deploy(self) -> None:
        res = self.make("docker-deploy-prod")
        self.assertEqual(res.rc, 0, res.text)
        tfvars = (self.sb.dir / "deployment/terraform.tfvars").read_text()
        self.assertIn('backend_image  = "testacr.azurecr.io/bible-backend:latest"', tfvars)
        self.assertIn('frontend_image = "testacr.azurecr.io/bible-frontend:latest"', tfvars)
        self.assertEqual(res.argv("terraform")[0][:1], ["apply"])
        self.assertIn("-auto-approve", res.argv("terraform")[0])

    def test_kubeopencode_dev_image_targets(self) -> None:
        res = self.make("lint-kubeopencode-dev-image")
        self.assertEqual(
            res.argv("docker"),
            [["run", "--rm", "-i", "hadolint/hadolint:v2.12.0", "hadolint", "--ignore", "DL3008", "--ignore", "DL3018", "-"]],
        )
        base = ["build", "-f", "k8s/kubeopencode/dev-image/Dockerfile", "-t"]
        self.assertEqual(self.make("build-kubeopencode-dev-image").argv("docker"), [base + ["kubeopencode-agent-dev:local", "."]])
        evil = "img:1;touch pwned"
        self.assertEqual(self.make("build-kubeopencode-dev-image", TAG=evil).argv("docker"), [base + [evil, "."]])
        self.assertFalse((self.sb.dir / "pwned").exists())

    def test_functional_tests_degrade_gracefully_without_services(self) -> None:
        res = self.make("functional-test", FAKE_FAIL_CURL="7", FAKE_FAIL_DOCKER="1")
        self.assertEqual(res.rc, 0, res.text)
        self.assertIn("API not running", res.out)
        self.assertEqual(self.make("functional-test-dev", FAKE_FAIL_CURL="7").rc, 0)


# ------------------------------------------------------------------------------- misc ---


class MiscTargetTests(SandboxCase):
    def test_android_targets_call_gradle_with_real_tasks(self) -> None:
        table = {
            "android-test": ["testDebugUnitTest", "--no-daemon"],
            "android-test-compose": [":app:testDebugUnitTest", "-PcomposeTestsOnly", "--tests", "*ComposeTest", "--no-daemon"],
            "android-build": ["assembleDebug", "--no-daemon"],
            "android-build-prod": ["assembleDebug", "--no-daemon", "-PbaseUrl=https://api.voxquieta.org/"],
            "android-lint": ["lintDebug", "--no-daemon"],
            "android-clean": ["clean", "--no-daemon"],
        }
        for target, args in table.items():
            with self.subTest(target):
                res = self.make(target)
                self.assertEqual(res.rc, 0, res.text)
                self.assertEqual([(c.cwd, c.args) for c in res.of("gradlew")], [("android", args)])

    def test_android_compose_report_path_matches_the_task_that_ran(self) -> None:
        self.assertIn("reports/tests/testDebugUnitTest/index.html", self.make("android-test-compose").out)

    def test_android_security_check_scans_the_gradle_cache(self) -> None:
        res = self.make("android-security-check")
        self.assertEqual(res.rc, 0, res.text)
        self.assertEqual(res.argv("gradlew"), [[":app:dependencies", "--configuration", "releaseRuntimeClasspath", "--no-daemon"]])
        scan = res.argv("dependency-check.sh")[0]
        self.assertEqual(scan[scan.index("--failOnCVSS") + 1], "7")

    def test_k8s_script_targets(self) -> None:
        self.assertEqual(self.make("verify-kubeopencode-netpol").argv("bash"), [["scripts/verify-kubeopencode-netpol.sh"]])
        self.assertEqual(self.make("collect-k8s-diagnostics").argv("bash"), [["scripts/collect-k8s-diagnostics.sh"]])
        res = self.make("collect-k8s-diagnostics", NAMESPACE="my ns", POD_IP="10.0.0.9")
        self.assertEqual(res.argv("bash"), [["scripts/collect-k8s-diagnostics.sh", "--namespace", "my ns", "--pod-ip", "10.0.0.9"]])
        evil = self.make("collect-k8s-diagnostics", NAMESPACE="x;touch pwned")
        self.assertEqual(evil.argv("bash")[0][-1], "x;touch pwned")
        self.assertFalse((self.sb.dir / "pwned").exists())

    def test_deploy_dns_watchdog_applies_the_manifests(self) -> None:
        call = self.make("deploy-dns-watchdog").argv("kubectl")[0]
        self.assertEqual(call[0], "apply")
        files = [call[i + 1] for i, a in enumerate(call) if a == "-f"]
        self.assertEqual(len(files), 5)
        for f in files:
            self.assertTrue((ROOT / f).exists(), f)

    def test_update_env_backend_url_runs_the_helper(self) -> None:
        self.assertIn("scripts/update-env-backend-url.sh", self.make("-n", "update-env-backend-url").out)

    def test_pytest_static_check_targets_run_their_suite(self) -> None:
        # These targets shell out to pytest on a specific file; a fake pytest cannot assert
        # anything meaningful, so pin the command line with `make -n` instead (they stay
        # classified `static` in make_target_audit.json).
        for target, suite in (
            ("test-kubeopencode-netpol", "scripts/test_kubeopencode_netpol.py"),
            ("test-cluster-triage", "scripts/test_cluster_triage.py"),
            ("test-dns-watchdog", "scripts/test_dns_watchdog.py"),
        ):
            with self.subTest(target):
                out = self.make("-n", target).out
                self.assertIn("-m pytest %s -q" % suite, out)


if __name__ == "__main__":
    unittest.main()
