#!/usr/bin/env python3
"""
Database migration: HNSW index on topics.embedding (BITB-062).

``search_topics_semantic`` (``api/scripture/repository.py``) already queries with the
index-friendly ``ORDER BY embedding <=> q LIMIT n`` shape, but ``topics.embedding`` has
no vector index at all (unlike ``verses``/``passages``, which both have
``idx_verse_embedding_hnsw`` / ``idx_passage_embedding_hnsw``) — every call is a full
sequential scan. The topics table is small (tens to low hundreds of rows), so this is
cheap relative to migration 007's per-translation verse indexes.

Why numbered 011 and not 009: PR #866 (open, not yet merged as of this migration) already
claims 009 (``009_add_rate_limit_tables.sql``) and 010
(``010_schedule_rate_limit_purge.sql``). Numbering this 011 avoids a collision regardless
of merge order.

Why a .py migration (not .sql): ``CREATE INDEX CONCURRENTLY`` cannot run inside a
transaction block, but ``run_migrations.py:run_sql_migration`` executes the whole file in
one implicit transaction. The statement below runs as its own autocommit
``conn.execute(...)`` instead — same pattern as migration 007.

This migration does NOT set ``hnsw.ef_search`` — see migration 007's docstring for why
(managed Postgres forbids persisting it at the database/role level; the app sets it per
session instead).

Run with: python scripts/migrations/011_add_topic_hnsw_index.py
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

INDEX_NAME = "idx_topic_embedding_hnsw"


def log(message: str) -> None:
    """Print timestamped log message, flushed immediately for CI visibility."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


async def run_migration():
    """Create the HNSW index on topics.embedding."""
    log("Connecting to database...")
    database_url = settings.database_url
    clean_url, conn_kwargs = get_migration_connection_params(database_url)
    conn = await asyncpg.connect(clean_url, **conn_kwargs)

    try:
        log(f"Building HNSW index {INDEX_NAME} on topics.embedding...")
        # Drop any invalid leftover from a previously failed CONCURRENTLY run so the
        # rebuild below is not skipped by an existing-but-invalid index.
        await conn.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
        await conn.execute(
            f"CREATE INDEX CONCURRENTLY {INDEX_NAME} ON topics "
            f"USING hnsw (embedding vector_cosine_ops) "
            f"WITH (m = 16, ef_construction = 64)"
        )

        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_prewarm")
            await conn.execute(f"SELECT pg_prewarm('{INDEX_NAME}')")
            log("Prewarmed index into shared_buffers.")
        except Exception as e:  # noqa: BLE001
            log(f"pg_prewarm skipped (non-fatal): {e}")

        log("Migration completed successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
