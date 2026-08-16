"""add verses.text_tsv generated column (BITB-062)

Revision ID: r0004
Revises: r0003
Create Date: 2026-08-01 00:00:00.000000

``search_verses_text`` (``api/scripture/repository.py``) matches against
``to_tsvector('simple', text) @@ plainto_tsquery(...)``, which the planner can
only use via ``idx_verses_fts_simple`` (migration 003) -- an *expression* index.
A generated, persisted column lets Postgres index the value directly, and is a
prerequisite for retiring the expression index once the query itself switches
over (a deliberate follow-up: deploy runs new app code before run-migrations, so
shipping the query switch alongside the migration would 500 public search for
the deploy window).

Additive only. ``idx_verses_fts_simple`` stays, and no query changes, so there
is no functional or performance regression window.

**This revision really does reach production.** BITB-089 shipped, so the deploy
pipeline runs ``alembic upgrade head`` -- there is no longer any need for a
paired ``scripts/migrations/`` file, and that system is frozen. The original
version of this change carried both under an "interim dual-write" note that has
since expired.

Locking, which now matters because this deploys automatically:

* ``ALTER TABLE ... ADD COLUMN ... GENERATED ALWAYS AS ... STORED`` is a full
  table rewrite under ``ACCESS EXCLUSIVE``. On ~400k verses (measured) that is
  low single-digit seconds -- brief, but it does block reads and writes.
* The GIN index is therefore built with ``CREATE INDEX CONCURRENTLY`` inside an
  ``autocommit_block()``, the pattern ``api/alembic/README.md`` documents for
  exactly this. Concurrently cannot run inside a transaction, and Alembic wraps
  each revision in one by default. A plain build would hold a write lock for the
  ~30-60s the equivalent ``idx_verses_fts_simple`` build took.

``CONCURRENTLY`` cannot be rolled back if it fails partway; it leaves an INVALID
index behind. The ``DROP INDEX IF EXISTS`` immediately before the build clears
any such leftover, so a retry is clean.

Idempotent throughout (``IF NOT EXISTS`` / ``IF EXISTS``).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0004"
down_revision: Union[str, None] = "r0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "idx_verses_text_tsv"


def upgrade() -> None:
    # op.add_column has no IF NOT EXISTS, hence raw SQL.
    op.execute(
        "ALTER TABLE verses ADD COLUMN IF NOT EXISTS text_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED"
    )
    with op.get_context().autocommit_block():
        # Clear any INVALID leftover from a previously failed CONCURRENTLY run,
        # which would otherwise make the build below a silent no-op.
        op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {INDEX_NAME} ON verses USING GIN (text_tsv)"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {INDEX_NAME}")
    op.execute("ALTER TABLE verses DROP COLUMN IF EXISTS text_tsv")
