"""add verse_tsv side table for verse full-text search (BITB-096)

Revision ID: r0004
Revises: r0003
Create Date: 2026-08-01 00:00:00.000000

The verse FTS queries in ``api/scripture/repository.py`` match against
``to_tsvector('simple', text)``, which the planner can only reach through
``idx_verses_fts_simple`` (``scripts/migrations/003``) -- an *expression* index.
This revision persists that value so it can be indexed directly, which is the
prerequisite for retiring the expression index (BITB-095).

It stores the tsvector in a **side table keyed by ``verse_id``**, not as a
column on ``verses``. That shape is the whole point of this revision, and it
replaces an earlier version of ``r0004`` that used

    ALTER TABLE verses ADD COLUMN text_tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED

...which took production down for roughly 45 minutes on 2026-08-17. Why it
failed, since the reasoning constrains everything below:

* A ``STORED`` generated column forces a **full table rewrite under
  ``ACCESS EXCLUSIVE``**. On ~400k verses on a 2-vCPU server that rewrite was
  still running after 33 minutes, blocking every read and write of ``verses``.
* The ``run-migrations`` job hit ``timeout-minutes: 30`` and died. That killed
  the *client*, not the server-side DDL: the orphaned ``ALTER TABLE`` went on
  holding its lock for another 15 minutes, working toward a ``COMMIT`` that
  could never arrive, because Alembic -- the only thing that would have sent
  it -- no longer existed. **A CI timeout does not stop a migration.** Hence
  the ``statement_timeout`` below: the bound has to be enforced by the
  database, not by the harness running it.
* ``verses`` also carries ``idx_verse_embedding_hnsw`` over 1536-dimension
  vectors in production. Any approach that rewrites rows -- a table rewrite, a
  shadow-table copy, or a batched ``UPDATE`` backfill -- pays to rebuild or
  churn that index as well. Writing into a separate table touches none of it.

So every statement here runs against an **empty** table and is pure catalog
work: sub-second, with only momentary locks on ``verses`` (``SHARE ROW
EXCLUSIVE`` to add the foreign key, ``ACCESS EXCLUSIVE`` to attach the trigger
and drop the stale column). ``lock_timeout`` makes sure it never *queues* for
those -- a queued ``ACCESS EXCLUSIVE`` request blocks every reader behind it,
which is how a fast migration still takes a site down.

There is deliberately no ``CONCURRENTLY`` and no ``autocommit_block()`` here,
unlike what ``api/alembic/README.md`` documents for index builds: both exist to
avoid holding a lock through a long build, and on an empty table there is no
build to speak of. The GIN index is created empty and populated by the
backfill's inserts (``scripts/backfill_verse_tsv.py``), which runs outside any
migration and holds no lock anyone waits on.

Nothing reads ``verse_tsv`` until the query switch in BITB-095 lands, so this
revision is invisible to users on its own, and ``downgrade()`` removes it
cleanly.

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
INDEX_NAME = "idx_verse_tsv_tsv"
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

    # Drops the generated column from the superseded version of this revision.
    # DROP COLUMN is metadata-only in Postgres, so this is instant even on 400k
    # rows -- it is not the rewrite that ADD COLUMN ... STORED was. A no-op in
    # production (that column never successfully landed); on a dev or CI
    # database already stamped at the old r0004 it removes the column and, with
    # it, the dependent idx_verses_text_tsv.
    op.execute("ALTER TABLE verses DROP COLUMN IF EXISTS text_tsv")

    op.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            verse_id integer PRIMARY KEY REFERENCES verses(id) ON DELETE CASCADE,
            text_tsv tsvector NOT NULL
        )
        """)
    op.execute(f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON {TABLE_NAME} USING GIN (text_tsv)")

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
    # The index and the foreign key go with the table.
    op.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
