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

This migration does NOT set ``hnsw.ef_search``. The ANN needs
``ef_search >= vector_candidate_pool`` to return a full candidate pool (pgvector's
default of 40 and migration 002's 80 are both below the pool of 100), but managed
Postgres (Azure Flexible Server, AWS RDS) forbids *persisting* that GUC at the
database or role level: ``ALTER DATABASE/ROLE ... SET hnsw.ef_search`` raises
``permission denied to set parameter`` even for the admin role. An earlier version
of this migration ran ``ALTER DATABASE ... SET hnsw.ef_search`` and failed CI with
exactly that error. The knob now lives in the application instead, which issues
``SET hnsw.ef_search`` per session on every pooled connection (see
``api/scripture/database.py``) — a session-level SET of a namespaced custom GUC
needs no special privilege and is the vendor-recommended way to tune it.

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
    """Create per-translation partial HNSW indexes for verse search."""
    log("Connecting to database...")
    database_url = settings.database_url
    clean_url, conn_kwargs = get_migration_connection_params(database_url)
    conn = await asyncpg.connect(clean_url, **conn_kwargs)

    try:
        # NOTE: hnsw.ef_search is intentionally NOT set here. Managed Postgres
        # (Azure Flexible Server / AWS RDS) refuses to persist it at the database or
        # role level — `ALTER DATABASE ... SET hnsw.ef_search` raised "permission
        # denied to set parameter" and failed CI. The application sets it per session
        # on every pooled connection instead (api/scripture/database.py), which needs
        # no special privilege. See the module docstring for the full story.

        # 1. Discover the translations actually present so the index set tracks
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

        # 2. One partial HNSW index per translation. CONCURRENTLY keeps the verses
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

        # 3. Warm the new indexes into shared_buffers so the first post-deploy query
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
