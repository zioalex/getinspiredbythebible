#!/usr/bin/env python3
"""
Database migration runner with tracking.

This script discovers and runs all migration files in order (001_*.py, 002_*.sql, etc.)
and tracks which migrations have been applied in a schema_migrations table.

- Migrations are sorted alphabetically by filename (001_ before 002_, regardless of .py or .sql)
- Already-applied migrations are skipped automatically
- On success, the migration version is recorded with a SHA-256 checksum
- On failure, the script stops immediately without recording the migration

Usage:
    export DATABASE_URL="postgresql+asyncpg://user:pass@host/db?ssl=require"  # pragma: allowlist secret
    python scripts/migrations/run_migrations.py

Exit codes:
    0: Success (all pending migrations applied)
    1: Failure (migration error, rollback recommended)
"""

import asyncio
import hashlib
import importlib.util
import os
import sys
from pathlib import Path

import asyncpg

# Add the api directory to the path for config access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from config import settings  # noqa: E402

# Add the migrations directory to path for local utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from utils import get_migration_connection_params  # noqa: E402


async def ensure_schema_migrations_table(conn: asyncpg.Connection) -> None:
    """Create the schema_migrations tracking table if it doesn't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     VARCHAR(255) PRIMARY KEY,
            applied_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            checksum    VARCHAR(64)
        );
    """)


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def discover_migrations(migrations_dir: Path) -> list[Path]:
    """
    Discover all migration files in the migrations directory.

    Returns:
        List of migration files sorted alphabetically (001_ before 002_, .py and .sql mixed)
    """
    # Find all .py and .sql files starting with digits
    py_files = list(migrations_dir.glob("[0-9][0-9][0-9]_*.py"))
    sql_files = list(migrations_dir.glob("[0-9][0-9][0-9]_*.sql"))

    # Combine and sort alphabetically by filename
    all_migrations = py_files + sql_files
    all_migrations.sort(key=lambda p: p.name)

    return all_migrations


async def is_migration_applied(conn: asyncpg.Connection, version: str) -> bool:
    """Check if a migration version has already been applied."""
    result = await conn.fetchval(
        "SELECT 1 FROM schema_migrations WHERE version = $1", version
    )
    return result is not None


async def record_migration(conn: asyncpg.Connection, version: str, checksum: str) -> None:
    """Record a successfully applied migration."""
    await conn.execute(
        "INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)",
        version,
        checksum,
    )


async def run_python_migration(file_path: Path) -> None:
    """Load and run a Python migration file."""
    # Load the module dynamically
    spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load migration module: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Call the run_migration() function
    if not hasattr(module, "run_migration"):
        raise RuntimeError(f"Migration {file_path.name} missing run_migration() function")

    # Run the migration (it's already async, so await it)
    await module.run_migration()


async def run_sql_migration(conn: asyncpg.Connection, file_path: Path) -> None:
    """Read and execute a SQL migration file.

    If the file contains no executable statements (e.g. it is reference-only
    documentation with all SQL wrapped in block comments), the migration is
    recorded as successfully applied without executing anything.
    """
    import re

    sql = file_path.read_text()

    # Strip block comments (/* ... */) and line comments (-- ...) then check
    # whether any non-whitespace remains.  If not, treat the file as a no-op.
    without_block_comments = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    without_comments = re.sub(r"--[^\n]*", "", without_block_comments)
    has_statements = bool(without_comments.strip())

    if not has_statements:
        print(f"   (no executable SQL — reference-only file, recording as applied)")
        return

    await conn.execute(sql)


async def main() -> int:
    """Main migration runner."""
    print("=" * 80)
    print("Database Migration Runner")
    print("=" * 80)

    # Get database connection
    database_url = settings.database_url
    clean_url, conn_kwargs = get_migration_connection_params(database_url)

    try:
        conn = await asyncpg.connect(clean_url, **conn_kwargs)
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return 1

    try:
        # Ensure tracking table exists
        await ensure_schema_migrations_table(conn)

        # Discover all migrations
        migrations_dir = Path(__file__).parent
        migrations = discover_migrations(migrations_dir)

        if not migrations:
            print("\nℹ️  No migration files found.")
            return 0

        print(f"\nFound {len(migrations)} migration files")
        print("-" * 80)

        skipped_count = 0
        applied_count = 0

        for migration_file in migrations:
            version = migration_file.stem  # filename without extension
            checksum = calculate_checksum(migration_file)

            # Check if already applied
            if await is_migration_applied(conn, version):
                print(f"⏭  Skipping {version} (already applied)")
                skipped_count += 1
                continue

            # Apply the migration
            print(f"▶  Running {migration_file.name}...")

            try:
                if migration_file.suffix == ".py":
                    await run_python_migration(migration_file)
                elif migration_file.suffix == ".sql":
                    await run_sql_migration(conn, migration_file)
                else:
                    print(f"⚠️  Unknown file type: {migration_file.name}")
                    continue

                # Record successful migration
                await record_migration(conn, version, checksum)
                print(f"✅ {version} completed")
                applied_count += 1

            except Exception as e:
                print(f"❌ Migration {version} failed: {e}")
                print("\n⚠️  Migration stopped. Fix the error and re-run.")
                print(f"   Failed migration NOT recorded (will retry on next run)")
                return 1

        # Summary
        print("-" * 80)
        print(f"\n📊 Summary:")
        print(f"   Skipped (already applied): {skipped_count}")
        print(f"   Applied (new):             {applied_count}")
        print(f"\n✅ All migrations completed successfully!")

        return 0

    finally:
        await conn.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
