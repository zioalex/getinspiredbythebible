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
