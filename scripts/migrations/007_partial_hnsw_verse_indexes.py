#!/usr/bin/env python3
"""
Database migration: per-translation partial HNSW indexes for verse search.

Phase 2 (chat latency). The single full HNSW index on ``verses.embedding``
(``idx_verse_embedding_hnsw``, ~2.6 GB) returns ``hnsw.ef_search`` nearest
neighbours across ALL translations, then the ``WHERE translation = :t`` filter
drops the non-matching ones AFTER the index scan. For a per-language chat query
that thins the candidate pool (observed: 32 kept / 48 removed at ef_search=80)
and hurts recall for the requested translation.

This migration creates one PARTIAL HNSW index per translation
(``... WHERE translation = '<t>'``) so each language's ANN is fully index-backed:
the filter is satisfied by the index (no post-filter, 0 rows removed), the LIMIT
fills, and the per-query working set drops ~12x (each partial is ~1/12th the size
and fits in shared_buffers). The full index is kept for the no-translation search
path (``/scripture/search`` without a translation).

It also raises ``hnsw.ef_search`` to >= vector_candidate_pool so the ANN can
return a full candidate pool (the old default of 80 was below the pool of 100).

Why a .py migration (not .sql): ``CREATE INDEX CONCURRENTLY`` cannot run inside a
transaction block, but ``run_migrations.py:run_sql_migration`` executes the whole
file in one implicit transaction. Here each statement is issued as its own
autocommit ``conn.execute(...)`` instead.

Run with: python scripts/migrations/007_partial_hnsw_verse_indexes.py
"""

import asyncio
import os
import re
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


# Index names must be plain identifiers; translation codes are short slugs
# (web, kjv, ita1927, schlachter, ...). Sanitise defensively before inlining,
# since identifiers and predicate literals cannot be bound parameters.
_UNSAFE = re.compile(r"[^a-z0-9_]")


def index_name(translation: str) -> str:
    """Deterministic partial-index name for a translation code."""
    return f"idx_verse_emb_hnsw_{_UNSAFE.sub('_', translation.lower())}"


async def run_migration():
    """Create per-translation partial HNSW indexes and raise hnsw.ef_search."""
    log("Connecting to database...")
    database_url = settings.database_url
    clean_url, conn_kwargs = get_migration_connection_params(database_url)
    conn = await asyncpg.connect(clean_url, **conn_kwargs)

    try:
        # 1. ef_search >= candidate pool so the ANN returns a full pool. Use
        #    current_database() (not a hard-coded name like migration 002's
        #    `bibleapp`) so this is robust to the actual prod database name.
        #
        #    This is best-effort: ALTER DATABASE ... SET requires DB-owner/superuser
        #    privileges that the Azure Flexible Server app role does not have, so it
        #    raises InsufficientPrivilegeError there. The application applies the same
        #    GUC per session in api/scripture/database.py (the runtime source of truth),
        #    so a failure here is non-fatal — we just skip the DB-wide default, which
        #    only benefits non-app clients (psql, ad-hoc tools).
        ef_search = max(settings.hnsw_ef_search, settings.vector_candidate_pool)
        dbname = await conn.fetchval("SELECT current_database()")
        log(f"Setting hnsw.ef_search = {ef_search} on database '{dbname}'")
        # dbname/ef_search are not bindable in ALTER DATABASE; dbname comes from the
        # server and ef_search is an int from config, so inlining is safe.
        try:
            await conn.execute(f'ALTER DATABASE "{dbname}" SET hnsw.ef_search = {int(ef_search)}')
        except asyncpg.exceptions.InsufficientPrivilegeError:
            log(
                "Skipping ALTER DATABASE SET hnsw.ef_search (insufficient privilege); "
                "the application sets it per session at the connection level instead."
            )

        # 2. Discover the translations actually present so the index set tracks
        #    reality instead of a hard-coded list that can drift.
        rows = await conn.fetch(
            "SELECT DISTINCT translation FROM verses "
            "WHERE translation IS NOT NULL ORDER BY translation"
        )
        translations = [r["translation"] for r in rows]
        if not translations:
            log("No translations found in verses table — nothing to index.")
            return
        log(f"Found {len(translations)} translations: {', '.join(translations)}")

        # 3. One partial HNSW index per translation. CONCURRENTLY keeps the verses
        #    table readable during the build; each statement runs in its own
        #    autocommit execute because CONCURRENTLY cannot run inside a txn.
        for t in translations:
            idx = index_name(t)
            literal = t.replace("'", "''")
            log(f"Building partial HNSW index {idx} (translation={t})...")
            # Drop any invalid leftover from a previously failed CONCURRENTLY run
            # so the rebuild below is not skipped by an existing-but-invalid index.
            await conn.execute(f"DROP INDEX IF EXISTS {idx}")
            await conn.execute(
                f"CREATE INDEX CONCURRENTLY {idx} ON verses "
                f"USING hnsw (embedding vector_cosine_ops) "
                f"WITH (m = 16, ef_construction = 64) "
                f"WHERE translation = '{literal}'"
            )

        # 4. Warm the new indexes into shared_buffers so the first post-deploy query
        #    doesn't pay the cold-cache penalty. Best-effort: pg_prewarm must be
        #    allow-listed (azure.extensions); skip silently if unavailable.
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_prewarm")
            for t in translations:
                await conn.execute(f"SELECT pg_prewarm('{index_name(t)}')")
            log("Prewarmed partial indexes into shared_buffers.")
        except Exception as e:  # noqa: BLE001
            log(f"pg_prewarm skipped (non-fatal): {e}")

        log("Migration completed successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
