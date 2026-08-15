"""pipeline probe: prove a revision reaches production via CI (BITB-089)

Revision ID: r0002
Revises: r0001
Create Date: 2026-08-15 07:40:00.000000

The last open BITB-089 criterion is proving the deploy pipeline actually applies
a committed revision to production -- "not by asserting the YAML looks right".
Everything verified so far concerns the *database*; nothing has yet shown that a
file under ``api/alembic/versions/`` travels through the path filter, the
install step, the SSL form and the preflight and lands on production.

This revision exists only to demonstrate that. ``r0003`` removes it again.

Why a table comment on ``sessions``:

* It creates no object and occupies no storage. The blast radius is one row in
  ``pg_description``.
* ``sessions`` is one of the five legacy tables deliberately excluded from
  Alembic's view by ``include_name`` in ``api/alembic/env.py`` (invariant #1 in
  ``api/alembic/README.md``). Autogenerate never inspects it, so this comment
  cannot surface as drift in ``alembic check`` -- which a comment on any
  ORM-backed table certainly would, as BITB-093 found the hard way.
* Reversing it is writing NULL. No data is involved in either direction.

The ``to_regclass`` guard is load-bearing: CI builds its database from ``r0001``
alone, which creates only the ORM-backed tables. ``sessions`` comes from
``scripts/init.sql`` / ``scripts/migrations/`` and does not exist there, so an
unguarded ``COMMENT ON TABLE sessions`` would fail every CI run. In CI this
revision is a no-op that proves it does not break; production is where it proves
the pipeline.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0002"
down_revision: Union[str, None] = "r0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # plpgsql accepts COMMENT ON directly, so no EXECUTE and no quote escaping.
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.sessions') IS NOT NULL THEN
                COMMENT ON TABLE sessions IS
                    'BITB-089 pipeline probe -- proves CI applies revisions; removed by r0003';
            END IF;
        END
        $$;
        """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.sessions') IS NOT NULL THEN
                COMMENT ON TABLE sessions IS NULL;
            END IF;
        END
        $$;
        """)
