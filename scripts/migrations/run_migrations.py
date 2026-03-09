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
import time
import traceback
from datetime import datetime
from pathlib import Path

import asyncpg

# Add the api directory to the path for config access
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "api"))

from config import settings  # noqa: E402

# Add the migrations directory to path for local utils
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from utils import get_migration_connection_params  # noqa: E402


def log(message: str) -> None:
    """Print timestamped log message, flushed immediately for CI visibility."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def get_migration_description(file_path: Path) -> str:
    """Extract a one-line description from the migration file.

    For .py files: returns the module docstring first line.
    For .sql files: returns the first non-empty comment line (-- or /* content).
    Returns empty string if nothing found.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        if file_path.suffix == ".py":
            import ast

            tree = ast.parse(content)
            docstring = ast.get_docstring(tree)
            if docstring:
                return docstring.splitlines()[0].strip()
        elif file_path.suffix == ".sql":
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("--"):
                    desc = line.lstrip("-").strip()
                    if desc:
                        return desc
    except Exception:
        pass
    return ""


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
    result = await conn.fetchval("SELECT 1 FROM schema_migrations WHERE version = $1", version)
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
        log(f"   (no executable SQL — reference-only file, recording as applied)")
        return

    await conn.execute(sql)


async def main() -> int:
    """Main migration runner."""
    log("=" * 80)
    log("Database Migration Runner")
    log("=" * 80)

    # Get database connection
    database_url = settings.database_url
    clean_url, conn_kwargs = get_migration_connection_params(database_url)

    try:
        conn = await asyncpg.connect(clean_url, **conn_kwargs)
    except Exception as e:
        log(f"❌ Failed to connect to database: {e}")
        return 1

    try:
        # Ensure tracking table exists
        await ensure_schema_migrations_table(conn)

        # Dump already-applied migrations at startup
        rows = await conn.fetch(
            "SELECT version, applied_at FROM schema_migrations ORDER BY applied_at"
        )
        if rows:
            log(f"\nAlready applied ({len(rows)} migrations):")
            for row in rows:
                log(
                    f"  ✓ {row['version']}  "
                    f"(applied {row['applied_at'].strftime('%Y-%m-%d %H:%M UTC')})"
                )
        else:
            log("No migrations applied yet (fresh database).")
        log("")

        # Discover all migrations
        migrations_dir = Path(__file__).parent
        migrations = discover_migrations(migrations_dir)

        if not migrations:
            log("\nℹ️  No migration files found.")
            return 0

        log(f"Found {len(migrations)} migration files")
        log("-" * 80)

        skipped_count = 0
        applied_count = 0
        newly_applied: list[str] = []

        for migration_file in migrations:
            version = migration_file.stem  # filename without extension
            checksum = calculate_checksum(migration_file)

            # Check if already applied
            if await is_migration_applied(conn, version):
                log(f"⏭  Skipping {version} (already applied)")
                skipped_count += 1
                continue

            # Apply the migration
            log(f"▶  Running {migration_file.name}")
            log(f"   Path:     {migration_file.resolve()}")
            log(f"   Checksum: {checksum[:16]}...")
            desc = get_migration_description(migration_file)
            if desc:
                log(f"   Description: {desc}")

            start = time.time()
            try:
                if migration_file.suffix == ".py":
                    await run_python_migration(migration_file)
                elif migration_file.suffix == ".sql":
                    await run_sql_migration(conn, migration_file)
                else:
                    log(f"⚠️  Unknown file type: {migration_file.name}")
                    continue

                # Record successful migration
                await record_migration(conn, version, checksum)
                elapsed = time.time() - start
                log(f"✅ {version} completed in {elapsed:.1f}s")
                applied_count += 1
                newly_applied.append(version)

            except Exception as e:
                elapsed = time.time() - start
                log(f"❌ Migration {version} failed after {elapsed:.1f}s: {e}")
                log(traceback.format_exc())
                log("\n⚠️  Migration stopped. Fix the error and re-run.")
                log(f"   Failed migration NOT recorded (will retry on next run)")
                return 1

        # Summary
        log("-" * 80)
        log(f"\n📊 Summary:")
        log(f"   Skipped (already applied): {skipped_count}")
        log(f"   Applied (new):             {applied_count}")
        log(f"\n✅ All migrations completed successfully!")

        # Write GitHub Actions step summary
        summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary_path:
            with open(summary_path, "a") as f:
                f.write("## Database Migration Summary\n\n")
                f.write(f"- **Total migration files found:** {len(migrations)}\n")
                f.write(f"- **Skipped (already applied):** {skipped_count}\n")
                f.write(f"- **Applied (new this run):** {applied_count}\n\n")
                if applied_count > 0:
                    f.write("### Newly Applied\n\n")
                    for v in newly_applied:
                        f.write(f"- `{v}`\n")
                else:
                    f.write("_No new migrations — database schema is up to date._\n")

        return 0

    finally:
        await conn.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
