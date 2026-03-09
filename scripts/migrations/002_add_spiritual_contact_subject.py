#!/usr/bin/env python3
"""
Database migration: Add 'spiritual' to contact_submissions subject CHECK constraint.

The original migration (001) created the contact_submissions table with a CHECK
constraint that only allowed: 'bug', 'feature', 'feedback', 'other'.
However, the ContactRequest Pydantic model and the frontend ContactForm have always
included 'spiritual' as a valid subject category. Any contact form submission with
subject='spiritual' would fail with a database constraint violation.

This migration drops the old constraint and recreates it with 'spiritual' included.

Run with: python scripts/migrations/002_add_spiritual_contact_subject.py
"""

import asyncio
import os
import sys
from datetime import datetime

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


async def run_migration():
    """Run the migration to add 'spiritual' to contact_submissions subject constraint."""
    log("Connecting to database...")

    # Parse connection string - handle both local and Azure formats
    database_url = settings.database_url
    clean_url, conn_kwargs = get_migration_connection_params(database_url)
    conn = await asyncpg.connect(clean_url, **conn_kwargs)

    try:
        # Check if the table exists at all
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'contact_submissions'
            );
        """)

        if not table_exists:
            log("Table contact_submissions does not exist — skipping (run 001 first).")
            return

        # Find the existing subject CHECK constraint name
        constraint_name = await conn.fetchval("""
            SELECT conname
            FROM pg_constraint
            WHERE conrelid = 'contact_submissions'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%subject%'
            LIMIT 1;
        """)

        if constraint_name:
            log(f"Dropping old constraint: {constraint_name}")
            await conn.execute(
                f"ALTER TABLE contact_submissions DROP CONSTRAINT {constraint_name};"
            )
        else:
            log("No existing subject CHECK constraint found — will add a new one.")

        log("Adding updated subject CHECK constraint (includes 'spiritual')...")
        await conn.execute("""
            ALTER TABLE contact_submissions
            ADD CONSTRAINT contact_submissions_subject_check
            CHECK (subject IN ('spiritual', 'bug', 'feature', 'feedback', 'other'));
        """)

        log("Migration completed successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
