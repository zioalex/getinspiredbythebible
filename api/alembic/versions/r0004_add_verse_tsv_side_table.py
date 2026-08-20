"""add verse_tsv side table for verse full-text search (BITB-096)

Revision ID: r0004
Revises: r0003
Create Date: 2026-08-01 00:00:00.000000

Stores ``to_tsvector('simple', text)`` per verse in a side table keyed by
``verse_id``, so ``search_verses_hybrid`` / ``_multi`` can read the value in
their ``ts_rank`` instead of recomputing it for every candidate row.

This replaces an earlier version of ``r0004`` that used

    ALTER TABLE verses ADD COLUMN text_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED

...which took production down for roughly 45 minutes on 2026-08-17:

* A ``STORED`` generated column forces a **full table rewrite under
  ``ACCESS EXCLUSIVE``**. On ~400k verses on a 2-vCPU server that rewrite was
  still running after 33 minutes, blocking every read and write of ``verses``.
* The ``run-migrations`` job hit ``timeout-minutes: 30`` and died. That killed
  the *client*, not the server-side DDL: the orphaned ``ALTER TABLE`` went on
  holding its lock for another 15 minutes, working toward a ``COMMIT`` that
  could never arrive, because Alembic -- the only thing that would have sent
  it -- no longer existed. **A CI timeout does not stop a migration.** Hence
  the ``statement_timeout`` below: the bound has to come from the database.
* ``verses`` also carries ``idx_verse_embedding_hnsw`` over 1536-dimension
  vectors in production. Any approach that rewrites rows -- a table rewrite, a
  shadow-table copy, or a batched ``UPDATE`` backfill -- pays to rebuild or
  churn that index too. Writing into a separate table touches none of it.

**There is deliberately no index on ``verse_tsv.text_tsv``.** An earlier draft
of this revision built a GIN index here, on the assumption that
``search_verses_text`` would match ``@@`` against this table. Measured on
403,856 rows, that turned out to be a *regression*: the existing expression
index ``idx_verses_fts_simple`` (``scripts/migrations/003``) already stores the
same computed tsvectors, so the lookup was always index-backed, and routing it
through a join costs an extra primary-key hop -- 0.144 ms/query against
0.105 ms for the expression index. ``search_verses_text`` therefore keeps using
``idx_verses_fts_simple``, and this table is read only by ``ts_rank``, which
uses no index at all: it is reached by ``verse_id`` from the already-narrowed
HNSW candidate pool. A GIN index here would have no reader and cost write
overhead on every seed. That is the whole measured benefit, and it is real but
modest: 2.75 ms -> 0.24 ms per hybrid query over a 200-row candidate pool.

Every statement runs against an **empty** table and is pure catalog work:
sub-second, with only momentary locks on ``verses`` (``SHARE ROW EXCLUSIVE``
to add the foreign key, ``ACCESS EXCLUSIVE`` to attach the trigger and drop the
stale column). ``lock_timeout`` makes sure it never *queues* for those -- a
queued ``ACCESS EXCLUSIVE`` request blocks every reader behind it, which is how
even a fast migration takes a site down.

Bulk population lives in ``scripts/backfill_verse_tsv.py``, outside any
migration. Nothing reads ``verse_tsv`` until the BITB-095 query switch lands,
so this revision is invisible on its own and ``downgrade()`` removes it cleanly.

Idempotent throughout (``IF NOT EXISTS`` / ``IF EXISTS``).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0004"
down_revision: Union[str, None] = "r0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE_NAME = "verse_tsv"
TRIGGER_NAME = "verses_tsv_sync"
FUNCTION_NAME = "verse_tsv_sync"


def _set_timeouts() -> None:
    """Bound this migration from inside the database.

    ``SET LOCAL`` scopes both to Alembic's transaction, so nothing leaks into
    the session afterwards.

    ``lock_timeout`` is the important one: the statements below are instant
    once they hold their locks, but a request for ``ACCESS EXCLUSIVE`` that has
    to *wait* queues every subsequent reader behind it. Five seconds means a
    busy table fails the migration instead of stalling the application.
    """
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '10min'")


def upgrade() -> None:
    _set_timeouts()

    # Drops the generated column from the superseded version of this revision,
    # and the GIN index from the superseded draft of this one. DROP COLUMN is
    # metadata-only in Postgres, so this is instant even on 400k rows -- it is
    # not the rewrite that ADD COLUMN ... STORED was. Both are no-ops in
    # production (neither ever landed); on a dev or CI database stamped at
    # either earlier form they converge it on this schema.
    op.execute("ALTER TABLE verses DROP COLUMN IF EXISTS text_tsv")
    op.execute("DROP INDEX IF EXISTS idx_verse_tsv_tsv")

    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            verse_id integer PRIMARY KEY REFERENCES verses(id) ON DELETE CASCADE,
            text_tsv tsvector NOT NULL
        )
        """)

    # `verses` takes no writes at runtime -- it is static reference data, and
    # nothing in api/ inserts, updates or deletes a Verse. The seeding scripts
    # do write it, though, so the table has to stay correct without anyone
    # remembering to re-run the backfill.
    #
    # DELETEs need no branch here: the foreign key's ON DELETE CASCADE removes
    # the matching row.
    op.execute(f"""
        CREATE OR REPLACE FUNCTION {FUNCTION_NAME}() RETURNS trigger AS $$
        BEGIN
            INSERT INTO {TABLE_NAME} (verse_id, text_tsv)
            VALUES (NEW.id, to_tsvector('simple', NEW.text))
            ON CONFLICT (verse_id) DO UPDATE SET text_tsv = EXCLUDED.text_tsv;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """)
    op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON verses")
    op.execute(f"""
        CREATE TRIGGER {TRIGGER_NAME}
            AFTER INSERT OR UPDATE OF text ON verses
            FOR EACH ROW EXECUTE FUNCTION {FUNCTION_NAME}()
        """)


def downgrade() -> None:
    _set_timeouts()
    op.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME} ON verses")
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION_NAME}()")
    # The foreign key goes with the table.
    op.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
