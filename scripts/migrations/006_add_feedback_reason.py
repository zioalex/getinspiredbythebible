#!/usr/bin/env python3
"""
Database migration: Add reason column to feedback table.

This migration adds an optional reason column to the feedback table to store
the category of what went wrong on negative feedback (e.g. inaccurate, unhelpful,
wrong_verse, tone, other).

Run with: python scripts/migrations/006_add_feedback_reason.py
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
    """Run the migration to add reason column to feedback table."""
    log("Connecting to database...")

    # Parse connection string - handle both local and Azure formats
    database_url = settings.database_url
    clean_url, conn_kwargs = get_migration_connection_params(database_url)
    conn = await asyncpg.connect(clean_url, **conn_kwargs)

    try:
        log("Adding reason column to feedback table...")
        await conn.execute("""
            ALTER TABLE feedback ADD COLUMN IF NOT EXISTS reason VARCHAR(40);
        """)

        log("Migration completed successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
