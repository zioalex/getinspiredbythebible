"""Tests for `scripts/db-backup-restore.sh` (see docs/HOW-TO-BACKUP-RESTORE-DATABASE.md).

The script can drop a production database, so the parts worth testing are the
URL rewriting (a wrong URL points a destructive command at the wrong place) and
the guards that stand in front of every destructive path.

The script is written to be *sourceable* — it only dispatches when executed —
so the helpers can be exercised directly rather than through a live database.
Nothing here touches a real server: every case either fails a guard before any
network call, or is pure string handling.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "db-backup-restore.sh"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")


def _source_and_run(snippet: str, *args: str) -> subprocess.CompletedProcess:
    """Source the script (without dispatching) and run `snippet`.

    `$0` is deliberately not the script path: the script only calls `main` when
    `$0 == BASH_SOURCE[0]`, and `bash -c '...' <script>` would set `$0` to the
    script and trip that check.
    """
    return subprocess.run(
        ["bash", "-c", f'source "$1" && {snippet}', "_", str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )


def _call_helper(func: str, arg: str) -> str:
    """Source the script and echo the result of one helper function."""
    result = _source_and_run(f'{func} "$2"', arg)
    assert result.returncode == 0, f"{func} failed: {result.stderr}"
    return result.stdout.strip()


def _run(*args: str, env_extra: dict | None = None) -> subprocess.CompletedProcess:
    """Execute the script as a subcommand (guards are expected to reject)."""
    import os

    env = {**os.environ, **(env_extra or {})}
    # Ensure nothing leaks in from the developer's shell.
    for leaked in ("DATABASE_URL", "DUMP", "CONFIRM", "PG_RG", "PG_SERVER", "NEW_SERVER"):
        env.pop(leaked, None)
    env.update(env_extra or {})
    return subprocess.run(
        ["bash", str(_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        env=env,
    )


def test_script_exists_and_is_executable():
    assert _SCRIPT.is_file(), f"missing: {_SCRIPT}"


class TestNormalizeLibpqUrl:
    """The app speaks `postgresql+asyncpg://...?ssl=require`; libpq tools do not.

    Getting this wrong is exactly the trap documented as Rule #1 in
    docs/MIGRATION_GUIDELINES.md, so it is pinned here.
    """

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            # asyncpg driver suffix + asyncpg's `ssl` spelling
            (
                "postgresql+asyncpg://u@h:5432/db?ssl=require",
                "postgresql://u@h:5432/db?sslmode=require",
            ),
            # already correct — must be left alone
            (
                "postgresql://u@h:5432/db?sslmode=require",
                "postgresql://u@h:5432/db?sslmode=require",
            ),
            # `sslmode` must not be double-rewritten into `sslmodemode`
            ("postgresql://h/db?sslmode=verify-full", "postgresql://h/db?sslmode=verify-full"),
            # no query string at all
            ("postgresql://h/db", "postgresql://h/db"),
            # `ssl` as a trailing parameter — the case a naive bash 5.2
            # ${var//&ssl=/&sslmode=} silently corrupts, because '&' in the
            # replacement expands to the matched text
            ("postgresql://h/db?a=1&ssl=require", "postgresql://h/db?a=1&sslmode=require"),
            # `ssl` first of several
            ("postgresql://h/db?ssl=require&b=2", "postgresql://h/db?sslmode=require&b=2"),
            ("postgres+asyncpg://h/db", "postgresql://h/db"),
        ],
    )
    def test_rewrites(self, raw, expected):
        assert _call_helper("normalize_libpq_url", raw) == expected


class TestUrlHost:
    @pytest.mark.parametrize(
        ("url", "expected"),
        [
            (
                "postgresql://bible:pw@localhost:5432/bibledb",  # pragma: allowlist secret
                "localhost",
            ),
            (
                "postgresql://u:p@prod.postgres.database.azure.com:5432/db?sslmode=require",  # pragma: allowlist secret
                "prod.postgres.database.azure.com",
            ),
            ("postgresql://db/bibledb", "db"),
            ("postgresql://127.0.0.1/bibledb", "127.0.0.1"),
        ],
    )
    def test_extracts_host(self, url, expected):
        assert _call_helper("url_host", url) == expected


class TestRedactUrl:
    def test_password_never_reaches_output(self):
        """The script logs the target it is about to act on — it must not log
        the password while doing so."""
        secret = "sup3rs3cret"  # noqa: S105  # pragma: allowlist secret
        out = _call_helper("redact_url", f"postgresql://bible:{secret}@h:5432/db")
        assert secret not in out
        assert out == "postgresql://bible:****@h:5432/db"

    def test_url_without_password_is_unchanged(self):
        url = "postgresql://bible@h:5432/db"
        assert _call_helper("redact_url", url) == url


class TestDestructiveGuards:
    """Every destructive path must refuse before it touches anything."""

    def test_restore_same_server_rejects_wrong_confirmation(self, tmp_path):
        dump = tmp_path / "fake.dump"
        dump.write_bytes(b"")
        result = _run(
            "restore-same-server",
            env_extra={
                "DATABASE_URL": "postgresql://u@prod.example.com:5432/db",
                "DUMP": str(dump),
                "CONFIRM": "not-the-host",
            },
        )
        assert result.returncode == 1
        assert "CONFIRM does not match" in result.stderr
        # It must not have reached pg_restore.
        assert "Restoring..." not in result.stdout

    def test_restore_same_server_requires_a_dump(self):
        result = _run(
            "restore-same-server",
            env_extra={"DATABASE_URL": "postgresql://u@h:5432/db"},
        )
        assert result.returncode == 1
        assert "DUMP is not set" in result.stderr

    def test_restore_same_server_rejects_missing_dump_file(self):
        result = _run(
            "restore-same-server",
            env_extra={
                "DATABASE_URL": "postgresql://u@h:5432/db",
                "DUMP": "/nonexistent/nope.dump",
                "CONFIRM": "h",
            },
        )
        assert result.returncode == 1
        assert "Dump file not found" in result.stderr

    def test_commands_require_database_url(self):
        for cmd in ("dump", "verify"):
            result = _run(cmd)
            assert result.returncode == 1, cmd
            assert "DATABASE_URL is not set" in result.stderr, cmd

    def test_restore_new_server_requires_its_arguments(self):
        result = _run("restore-new-server", env_extra={"PG_RG": "rg", "PG_SERVER": "srv"})
        assert result.returncode == 1
        assert "NEW_SERVER is not set" in result.stderr

    def test_unknown_command_fails(self):
        result = _run("definitely-not-a-command")
        assert result.returncode == 1
        assert "Unknown command" in result.stderr

    def test_help_exits_zero_and_lists_commands(self):
        result = _run("--help")
        assert result.returncode == 0
        for cmd in ("dump", "verify", "restore-local", "restore-same-server"):
            assert cmd in result.stdout

    def test_restore_local_ignores_database_url(self):
        """`restore-local` must build its own localhost URL, never use DATABASE_URL.

        Otherwise an exported production URL — the common case, since the other
        targets need one — could aim a restore at production.
        """
        result = _run(
            "restore-local",
            env_extra={"DATABASE_URL": "postgresql://u@prod.example.com:5432/db"},
        )
        assert result.returncode == 1
        # It stops on the missing dump (or on docker), never on DATABASE_URL,
        # and the production host must not appear anywhere in its output.
        assert "DATABASE_URL" not in result.stderr
        assert "prod.example.com" not in result.stdout + result.stderr
        assert "DUMP is not set" in result.stderr or "docker not found" in result.stderr


# --- BITB-329: Terraform-derived defaults and libpq root-cert handling --------


def _write_tf(tmp_path: Path, tfvars: str | None, variables: str | None = None) -> Path:
    d = tmp_path / "deployment"
    d.mkdir()
    if tfvars is not None:
        (d / "terraform.tfvars").write_text(tfvars)
    if variables is not None:
        (d / "variables.tf").write_text(variables)
    return d


def _run_server_url(tmp_path: Path, tf_dir: Path, **env) -> subprocess.CompletedProcess:
    """Run `server-url` with a fake `az` that returns an FQDN."""
    import os

    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    az = bindir / "az"
    az.write_text("#!/bin/sh\necho srv.postgres.database.azure.com\n")
    az.chmod(0o755)
    e = {k: v for k, v in os.environ.items() if k not in ("DB_USER", "PG_DB")}
    e.update(
        PATH=f"{bindir}:{e['PATH']}",
        PG_RG="rg",
        SERVER="srv",
        TF_DIR=str(tf_dir),
        **env,
    )
    return subprocess.run(
        ["bash", str(_SCRIPT), "server-url"], capture_output=True, text=True, env=e, cwd="/"
    )


class TestServerUrlDefaults:
    def test_defaults_come_from_tfvars(self, tmp_path):
        tf = _write_tf(
            tmp_path,
            '# db_admin_username = "commented"\ndb_name_suffix = "nope"\nother_db_name = "nope"\n'
            'db_admin_username = "alice"  # c\n  db_name="prod_db"\n',
        )
        r = _run_server_url(tmp_path, tf)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == (
            "postgresql://alice@srv.postgres.database.azure.com:5432/prod_db?sslmode=verify-full"
        )

    def test_env_overrides_win(self, tmp_path):
        tf = _write_tf(tmp_path, 'db_admin_username = "alice"\ndb_name = "prod_db"\n')
        r = _run_server_url(tmp_path, tf, DB_USER="bob", PG_DB="other")
        assert r.stdout.strip().startswith("postgresql://bob@")
        assert "/other?sslmode=verify-full" in r.stdout

    def test_missing_tfvars_falls_back_to_variables_tf_default(self, tmp_path):
        tf = _write_tf(
            tmp_path,
            None,
            'variable "db_name_suffix" {\n  default = "nope"\n}\n'
            'variable "db_admin_username" {\n  type = string\n  default = "vtf_user"\n}\n'
            'variable "db_name" {\n  default = "vtf_db"\n}\n',
        )
        r = _run_server_url(tmp_path, tf)
        assert "postgresql://vtf_user@" in r.stdout and "/vtf_db?" in r.stdout

    def test_missing_everything_falls_back_to_bibleadmin_bibleapp(self, tmp_path):
        r = _run_server_url(tmp_path, tmp_path / "nonexistent")
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == (
            "postgresql://bibleadmin@srv.postgres.database.azure.com:5432/bibleapp"
            "?sslmode=verify-full"
        )

    def test_real_repo_tfvars_match_production_names(self):
        result = _source_and_run("tf_setting db_admin_username x; echo; tf_setting db_name x")
        assert result.stdout.split() == ["bibleadmin", "bibleapp"]

    def test_default_resolves_regardless_of_cwd(self, tmp_path):
        import os

        r = subprocess.run(
            [
                "bash",
                "-c",
                'source "$1" && tf_setting db_name x',
                "_",
                str(_SCRIPT),
            ],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={k: v for k, v in os.environ.items() if k != "TF_DIR"},
        )
        assert r.stdout == "bibleapp"


def _libpq_env(tmp_path: Path, version_out: str | None, *, root_crt=False, preset=None):
    import os

    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    if root_crt:
        (home / ".postgresql").mkdir()
        (home / ".postgresql" / "root.crt").write_text("x")
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    if version_out is not None:
        pg = bindir / "pg_dump"
        pg.write_text(f"#!/bin/sh\necho '{version_out}'\n")
        pg.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "PGSSLROOTCERT"}
    env["HOME"] = str(home)
    # Keep real pg_dump/psql off the PATH so only the fake is seen.
    env["PATH"] = f"{bindir}:/usr/bin:/bin"
    if preset:
        env["PGSSLROOTCERT"] = preset
    return env


def _ensure(env, url="postgresql://u@h:5432/d?sslmode=verify-full"):
    return subprocess.run(
        [
            "bash",
            "-c",
            'source "$1" && ensure_libpq_sslrootcert "$2" && echo "CERT=${PGSSLROOTCERT:-}"',
            "_",
            str(_SCRIPT),
            url,
        ],
        capture_output=True,
        text=True,
        env=env,
    )


class TestLibpqRootCert:
    @pytest.mark.parametrize(
        "version", ["pg_dump (PostgreSQL) 16.4 (Ubuntu 16.4-1)", "pg_dump (PostgreSQL) 17.2"]
    )
    def test_auto_sets_system_on_libpq_16_plus(self, tmp_path, version):
        r = _ensure(_libpq_env(tmp_path, version))
        assert r.returncode == 0, r.stderr
        assert "CERT=system" in r.stdout
        assert "PGSSLROOTCERT=system" in r.stderr

    def test_not_overridden_when_already_set(self, tmp_path):
        r = _ensure(_libpq_env(tmp_path, "pg_dump (PostgreSQL) 16.4", preset="/my/ca.pem"))
        assert "CERT=/my/ca.pem" in r.stdout

    def test_not_set_when_root_crt_exists(self, tmp_path):
        r = _ensure(_libpq_env(tmp_path, "pg_dump (PostgreSQL) 16.4", root_crt=True))
        assert r.returncode == 0 and "CERT=\n" in r.stdout + "\n"

    def test_not_set_when_url_has_sslrootcert(self, tmp_path):
        url = "postgresql://u@h/d?sslmode=verify-full&sslrootcert=/x.pem"
        r = _ensure(_libpq_env(tmp_path, "pg_dump (PostgreSQL) 16.4"), url)
        assert r.stdout.strip() == "CERT="

    def test_noop_for_non_verifying_sslmode(self, tmp_path):
        r = _ensure(
            _libpq_env(tmp_path, "pg_dump (PostgreSQL) 16.4"), "postgresql://u@h/d?sslmode=require"
        )
        assert r.stdout.strip() == "CERT="

    def test_libpq_15_errors_with_install_instructions(self, tmp_path):
        r = _ensure(_libpq_env(tmp_path, "pg_dump (PostgreSQL) 15.8 (Debian 15.8-1)"))
        assert r.returncode != 0
        assert "DigiCertGlobalRootG2.crt.pem" in r.stderr
        assert "Microsoft%20RSA%20Root%20Certificate%20Authority%202017.crt" in r.stderr
        assert "~/.postgresql/root.crt" in r.stderr

    def test_verify_ca_never_uses_system_store(self, tmp_path):
        # libpq >= 16 rejects sslrootcert=system with sslmode=verify-ca.
        r = _ensure(
            _libpq_env(tmp_path, "pg_dump (PostgreSQL) 16.4"),
            "postgresql://u@h:5432/d?sslmode=verify-ca",
        )
        assert r.returncode != 0
        assert "CERT=system" not in r.stdout
        assert "~/.postgresql/root.crt" in r.stderr


def _function_body(name: str) -> str:
    """Return the shell source of function `name` in the script (up to the closing brace)."""
    lines = _SCRIPT.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{name}()"))
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "}")
    return "\n".join(lines[start : end + 1])


class TestRootCertCallSites:
    """Every remote libpq path ensures a root cert; the asyncpg (alembic) path never does."""

    @pytest.mark.parametrize("func", ["cmd_dump", "cmd_verify", "cmd_restore_same_server"])
    def test_remote_libpq_commands_ensure_root_cert(self, func):
        assert 'ensure_libpq_sslrootcert "$DB_URL"' in _function_body(func)

    def test_rehearse_never_sets_system_store(self):
        # asyncpg reads PGSSLROOTCERT as a file path, so "system" would break alembic.
        assert "ensure_libpq_sslrootcert" not in _function_body("cmd_rehearse")
