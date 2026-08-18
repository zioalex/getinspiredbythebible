#!/usr/bin/env python3
"""
Backfill `verse_tsv` from `verses` in resumable batches (BITB-096).

Alembic r0004 creates `verse_tsv` and the trigger that keeps it current, but
deliberately does not populate it: filling 400k rows is bulk data movement, not
schema work, and it has no business running inside a migration that holds a
transaction open (or inside a CI job that will kill it at the 30-minute mark --
see the r0004 docstring for what that cost us on 2026-08-17).

What makes this safe to run against a live production database:

- Every batch is its own transaction. There is no long-lived transaction to
  block autovacuum or to stall a `CREATE INDEX CONCURRENTLY` elsewhere.
- It only INSERTs into `verse_tsv`. `verses` is never written, so its rows are
  not rewritten and `idx_verse_embedding_hnsw` is never touched -- the whole
  reason the tsvector lives in a side table.
- `ON CONFLICT DO NOTHING` plus an id cursor makes it idempotent and
  resumable. Interrupt it, re-run it, run it twice concurrently -- the result
  is the same, and a completed backfill re-run inserts zero rows.
- Nothing reads `verse_tsv` until the BITB-095 query switch deploys, so a
  partial backfill is invisible rather than wrong.

Usage:
    export DATABASE_URL="postgresql+asyncpg://user:pass@host/db?sslmode=require"  # pragma: allowlist secret
    python scripts/backfill_verse_tsv.py
    python scripts/backfill_verse_tsv.py --batch-size 2000 --dry-run

Exit codes:
    0: Success (verse_tsv covers every verse)
    1: Failure (connection error, missing table, or an incomplete backfill)
"""

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent / "migrations"))

from utils import get_migration_connection_params  # noqa: E402

DEFAULT_BATCH_SIZE = 5000

# One statement per batch: it scans a slice, inserts it, and reports both how
# many rows landed and how far the cursor got. The cursor has to advance past
# everything *scanned*, not everything inserted -- rows that ON CONFLICT skipped
# still have to be stepped over, or a re-run across an already-populated range
# would never move. Hence `max(id) FROM batch` rather than from the RETURNING.
#
# Keyed on id so each batch reads a distinct, index-ordered slice.
# `to_tsvector('simple', text)` is character-for-character the expression that
# `idx_verses_fts_simple` and the r0004 trigger both use -- that identity is
# what makes the BITB-095 query switch a plan change, not a semantics change.
BACKFILL_SQL = """
    WITH batch AS (
        SELECT id, text FROM verses WHERE id > $1 ORDER BY id LIMIT $2
    ),
    ins AS (
        INSERT INTO verse_tsv (verse_id, text_tsv)
        SELECT id, to_tsvector('simple', text) FROM batch
        ON CONFLICT (verse_id) DO NOTHING
        RETURNING verse_id
    )
    SELECT
        (SELECT max(id) FROM batch) AS scanned_max,
        (SELECT count(*) FROM ins) AS inserted
"""

# Same scan and the same conflict test, writing nothing.
DRY_RUN_SQL = """
    WITH batch AS (
        SELECT id, text FROM verses WHERE id > $1 ORDER BY id LIMIT $2
    )
    SELECT
        (SELECT max(id) FROM batch) AS scanned_max,
        (SELECT count(*) FROM batch b
          WHERE NOT EXISTS (SELECT 1 FROM verse_tsv t WHERE t.verse_id = b.id)) AS inserted
"""


def log(message: str) -> None:
    """Print a timestamped message, flushed immediately for CI visibility."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


async def _counts(conn: asyncpg.Connection) -> tuple[int, int]:
    """Return (verses, verse_tsv) row counts."""
    verses = await conn.fetchval("SELECT count(*) FROM verses")
    tsv = await conn.fetchval("SELECT count(*) FROM verse_tsv")
    return verses, tsv


async def backfill(conn: asyncpg.Connection, batch_size: int, dry_run: bool) -> int:
    """Insert missing verse_tsv rows in batches. Returns the number inserted."""
    last_id = 0
    inserted = 0
    started = time.monotonic()

    sql = DRY_RUN_SQL if dry_run else BACKFILL_SQL
    verb = "would insert" if dry_run else "inserted"

    while True:
        # Each statement runs outside an explicit transaction, so asyncpg
        # autocommits it: one batch, one transaction, nothing held open.
        row = await conn.fetchrow(sql, last_id, batch_size)

        # No rows left in the scan range -- the table is exhausted.
        if row is None or row["scanned_max"] is None:
            break

        last_id = row["scanned_max"]
        inserted += row["inserted"]
        elapsed = time.monotonic() - started
        log(f"  … {inserted:,} {verb}, cursor at id={last_id:,} ({elapsed:.1f}s)")

    return inserted


async def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill verse_tsv from verses (BITB-096).")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows scanned per transaction (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be inserted without writing anything",
    )
    args = parser.parse_args()

    if args.batch_size < 1:
        log("ERROR: --batch-size must be at least 1")
        return 1

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        log("ERROR: DATABASE_URL is not set")
        return 1

    url, conn_kwargs = get_migration_connection_params(database_url)

    try:
        conn = await asyncpg.connect(url, **conn_kwargs)
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator verbatim
        log(f"ERROR: could not connect: {exc}")
        return 1

    try:
        exists = await conn.fetchval("SELECT to_regclass('public.verse_tsv') IS NOT NULL")
        if not exists:
            log("ERROR: verse_tsv does not exist -- run `alembic upgrade head` first (r0004)")
            return 1

        verses, tsv_before = await _counts(conn)
        log(f"verses={verses:,}  verse_tsv={tsv_before:,}  missing={verses - tsv_before:,}")

        if args.dry_run:
            log("DRY RUN: no rows will be written")

        inserted = await backfill(conn, args.batch_size, args.dry_run)

        verses, tsv_after = await _counts(conn)
        label = "would insert" if args.dry_run else "inserted"
        log(f"Done. {label}={inserted:,}  verses={verses:,}  verse_tsv={tsv_after:,}")

        if args.dry_run:
            return 0

        if tsv_after != verses:
            log(f"ERROR: incomplete -- {verses - tsv_after:,} verses still have no tsvector")
            return 1

        # verse_tsv carries no index on text_tsv (see r0004), so there is no
        # GIN pending list to merge here. ANALYZE still earns its place: the
        # hybrid builders join this table by verse_id, and the planner needs
        # statistics on a table that went from empty to 400k rows in one go.
        log("ANALYZE verse_tsv…")
        analyze_started = time.monotonic()
        await conn.execute("ANALYZE verse_tsv")
        log(f"  done in {time.monotonic() - analyze_started:.1f}s")

        log("verse_tsv covers every verse.")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
