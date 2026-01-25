#!/usr/bin/env python3
"""
Run database migrations.

Usage:
    python run_migration.py 001_add_translations.sql
"""

import asyncio
import sys
from pathlib import Path

import asyncpg


async def run_migration(migration_file: Path, database_url: str):
    """Execute a SQL migration file."""

    print(f"🔄 Running migration: {migration_file.name}")

    # Read migration SQL
    sql = migration_file.read_text()

    # Connect to database
    conn = await asyncpg.connect(database_url)

    try:
        # Execute migration in a transaction
        async with conn.transaction():
            await conn.execute(sql)

        print(f"✅ Migration {migration_file.name} completed successfully")

        # Show verification info
        print("\n📊 Verification:")

        # Check translations table
        translations = await conn.fetch("SELECT code, name, language FROM translations ORDER BY code")
        print(f"\nTranslations available: {len(translations)}")
        for t in translations:
            print(f"  - {t['code']}: {t['name']} ({t['language']})")

        # Check verse counts
        verse_counts = await conn.fetch(
            "SELECT translation, COUNT(*) as count FROM verses GROUP BY translation ORDER BY translation"
        )
        print(f"\nVerse counts by translation:")
        for vc in verse_counts:
            print(f"  - {vc['translation']}: {vc['count']:,} verses")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <migration_file.sql>")
        sys.exit(1)

    migration_file = Path(__file__).parent / "migrations" / sys.argv[1]

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)

    # Get database URL from environment or use default
    import os
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://bible:bible123@localhost:5432/bibledb"  # pragma: allowlist secret
    )

    await run_migration(migration_file, database_url)


if __name__ == "__main__":
    asyncio.run(main())
