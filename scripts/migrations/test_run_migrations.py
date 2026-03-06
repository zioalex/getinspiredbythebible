"""
Tests for the migration runner.

These tests use unittest.mock to avoid needing a real database.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Import the module under test
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import run_migrations


@pytest.fixture
def mock_conn():
    """Create a mock asyncpg connection."""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock()
    conn.close = AsyncMock()
    return conn


@pytest.fixture
def mock_migrations_dir(tmp_path):
    """Create a temporary directory with mock migration files."""
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    # Create some migration files
    (migrations_dir / "001_first.py").write_text("# Migration 1")
    (migrations_dir / "002_second.sql").write_text("-- Migration 2")
    (migrations_dir / "003_third.py").write_text("# Migration 3")

    return migrations_dir


def test_calculate_checksum(tmp_path):
    """Test that checksum calculation is consistent."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")

    checksum1 = run_migrations.calculate_checksum(test_file)
    checksum2 = run_migrations.calculate_checksum(test_file)

    # Same content = same checksum
    assert checksum1 == checksum2
    # SHA-256 produces 64-character hex string
    assert len(checksum1) == 64
    assert all(c in "0123456789abcdef" for c in checksum1)


def test_discover_migrations_sorted(mock_migrations_dir):
    """Test that migrations are discovered and sorted correctly."""
    migrations = run_migrations.discover_migrations(mock_migrations_dir)

    assert len(migrations) == 3
    # Should be sorted alphabetically: 001, 002, 003
    assert migrations[0].name == "001_first.py"
    assert migrations[1].name == "002_second.sql"
    assert migrations[2].name == "003_third.py"


def test_discover_migrations_mixed_order(tmp_path):
    """Test sorting with mixed .py and .sql files."""
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    # Create files in a mixed order
    (migrations_dir / "003_third.sql").write_text("-- Migration 3")
    (migrations_dir / "001_first.py").write_text("# Migration 1")
    (migrations_dir / "002_second.py").write_text("# Migration 2")
    (migrations_dir / "004_fourth.sql").write_text("-- Migration 4")

    migrations = run_migrations.discover_migrations(migrations_dir)

    # Should be sorted by filename prefix
    assert len(migrations) == 4
    assert migrations[0].name == "001_first.py"
    assert migrations[1].name == "002_second.py"
    assert migrations[2].name == "003_third.sql"
    assert migrations[3].name == "004_fourth.sql"


@pytest.mark.asyncio
async def test_ensure_schema_migrations_table(mock_conn):
    """Test that schema_migrations table creation SQL is correct."""
    await run_migrations.ensure_schema_migrations_table(mock_conn)

    # Should execute CREATE TABLE IF NOT EXISTS
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0][0]
    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in call_args
    assert "version" in call_args
    assert "applied_at" in call_args
    assert "checksum" in call_args


@pytest.mark.asyncio
async def test_is_migration_applied_true(mock_conn):
    """Test checking if a migration is already applied."""
    mock_conn.fetchval.return_value = 1

    result = await run_migrations.is_migration_applied(mock_conn, "001_test")

    assert result is True
    mock_conn.fetchval.assert_called_once()


@pytest.mark.asyncio
async def test_is_migration_applied_false(mock_conn):
    """Test checking if a migration is not applied."""
    mock_conn.fetchval.return_value = None

    result = await run_migrations.is_migration_applied(mock_conn, "001_test")

    assert result is False
    mock_conn.fetchval.assert_called_once()


@pytest.mark.asyncio
async def test_record_migration(mock_conn):
    """Test recording a successful migration."""
    await run_migrations.record_migration(mock_conn, "001_test", "abc123")

    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0]
    assert "INSERT INTO schema_migrations" in call_args[0]
    assert call_args[1] == "001_test"
    assert call_args[2] == "abc123"


@pytest.mark.asyncio
async def test_skips_already_applied_migration(mock_conn, mock_migrations_dir, capsys):
    """Test that already-applied migrations are skipped."""
    # Mock: first migration already applied
    async def mock_is_applied(conn, version):
        return version == "001_first"

    with (
        patch("run_migrations.asyncpg.connect", return_value=mock_conn),
        patch("run_migrations.is_migration_applied", side_effect=mock_is_applied),
        patch("run_migrations.discover_migrations", return_value=[mock_migrations_dir / "001_first.py"]),
        patch("run_migrations.run_python_migration", new_callable=AsyncMock) as mock_run,
    ):
        exit_code = await run_migrations.main()

    # Should NOT call run_migration for already-applied migration
    mock_run.assert_not_called()

    # Should print skip message
    captured = capsys.readouterr()
    assert "⏭  Skipping 001_first (already applied)" in captured.out
    assert exit_code == 0


@pytest.mark.asyncio
async def test_applies_new_py_migration(mock_conn, mock_migrations_dir, capsys):
    """Test that new Python migrations are applied and recorded."""
    migration_file = mock_migrations_dir / "001_first.py"

    with (
        patch("run_migrations.asyncpg.connect", return_value=mock_conn),
        patch("run_migrations.is_migration_applied", return_value=False),
        patch("run_migrations.discover_migrations", return_value=[migration_file]),
        patch("run_migrations.run_python_migration", new_callable=AsyncMock) as mock_run,
        patch("run_migrations.record_migration", new_callable=AsyncMock) as mock_record,
    ):
        exit_code = await run_migrations.main()

    # Should run the migration
    mock_run.assert_called_once_with(migration_file)

    # Should record it
    mock_record.assert_called_once()
    recorded_version = mock_record.call_args[0][1]
    assert recorded_version == "001_first"

    # Should print success
    captured = capsys.readouterr()
    assert "▶  Running 001_first.py" in captured.out
    assert "✅ 001_first completed" in captured.out
    assert exit_code == 0


@pytest.mark.asyncio
async def test_applies_new_sql_migration(mock_conn, mock_migrations_dir, capsys):
    """Test that new SQL migrations are applied and recorded."""
    migration_file = mock_migrations_dir / "002_second.sql"

    with (
        patch("run_migrations.asyncpg.connect", return_value=mock_conn),
        patch("run_migrations.is_migration_applied", return_value=False),
        patch("run_migrations.discover_migrations", return_value=[migration_file]),
        patch("run_migrations.run_sql_migration", new_callable=AsyncMock) as mock_run,
        patch("run_migrations.record_migration", new_callable=AsyncMock) as mock_record,
    ):
        exit_code = await run_migrations.main()

    # Should run the SQL migration
    mock_run.assert_called_once_with(mock_conn, migration_file)

    # Should record it
    mock_record.assert_called_once()
    recorded_version = mock_record.call_args[0][1]
    assert recorded_version == "002_second"

    # Should print success
    captured = capsys.readouterr()
    assert "▶  Running 002_second.sql" in captured.out
    assert "✅ 002_second completed" in captured.out
    assert exit_code == 0


@pytest.mark.asyncio
async def test_stops_on_failure(mock_conn, mock_migrations_dir, capsys):
    """Test that migration stops on error and does NOT record the failed migration."""
    migration_file = mock_migrations_dir / "001_first.py"

    # Make the migration fail
    async def mock_run_fails(*args, **kwargs):
        raise RuntimeError("Migration failed!")

    with (
        patch("run_migrations.asyncpg.connect", return_value=mock_conn),
        patch("run_migrations.is_migration_applied", return_value=False),
        patch("run_migrations.discover_migrations", return_value=[migration_file]),
        patch("run_migrations.run_python_migration", side_effect=mock_run_fails),
        patch("run_migrations.record_migration", new_callable=AsyncMock) as mock_record,
    ):
        exit_code = await run_migrations.main()

    # Should NOT record the failed migration
    mock_record.assert_not_called()

    # Should print error and exit with code 1
    captured = capsys.readouterr()
    assert "❌ Migration 001_first failed" in captured.out
    assert "Migration failed!" in captured.out
    assert exit_code == 1


@pytest.mark.asyncio
async def test_sorts_migrations_correctly(tmp_path):
    """Test that mixed .py and .sql files are sorted by filename prefix."""
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()

    # Create files deliberately out of order
    (migrations_dir / "005_last.sql").write_text("-- Last")
    (migrations_dir / "001_first.py").write_text("# First")
    (migrations_dir / "003_middle.sql").write_text("-- Middle SQL")
    (migrations_dir / "002_second.py").write_text("# Second")
    (migrations_dir / "004_fourth.py").write_text("# Fourth")

    migrations = run_migrations.discover_migrations(migrations_dir)

    # Should be sorted numerically by prefix
    expected_order = [
        "001_first.py",
        "002_second.py",
        "003_middle.sql",
        "004_fourth.py",
        "005_last.sql",
    ]

    actual_order = [m.name for m in migrations]
    assert actual_order == expected_order


@pytest.mark.asyncio
async def test_run_python_migration_missing_function():
    """Test that Python migrations without run_migration() function raise an error."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        # Write a Python file without run_migration()
        f.write("# No run_migration function here\n")
        f.flush()
        file_path = Path(f.name)

    try:
        with pytest.raises(RuntimeError, match="missing run_migration"):
            await run_migrations.run_python_migration(file_path)
    finally:
        file_path.unlink()


@pytest.mark.asyncio
async def test_run_sql_migration(mock_conn, tmp_path):
    """Test that SQL migrations are executed correctly."""
    sql_file = tmp_path / "test.sql"
    sql_content = "CREATE TABLE test (id INT);"
    sql_file.write_text(sql_content)

    await run_migrations.run_sql_migration(mock_conn, sql_file)

    # Should execute the SQL content
    mock_conn.execute.assert_called_once_with(sql_content)


@pytest.mark.asyncio
async def test_connection_failure(capsys):
    """Test that connection failures are handled gracefully."""
    with patch("run_migrations.asyncpg.connect", side_effect=Exception("Connection failed")):
        exit_code = await run_migrations.main()

    # Should print error and exit with code 1
    captured = capsys.readouterr()
    assert "❌ Failed to connect to database" in captured.out
    assert "Connection failed" in captured.out
    assert exit_code == 1
