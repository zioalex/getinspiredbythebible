"""remove the pipeline probe comment (BITB-089)

Revision ID: r0003
Revises: r0002
Create Date: 2026-08-15 17:30:00.000000

Reverses ``r0002``, which set a table comment on ``sessions`` purely to prove
that a committed revision reaches production through the deploy pipeline. It
did: production reports ``r0002 (head)``, the comment is present in
``pg_description``, and ``alembic check`` against production is clean.

This revision is the "then drop it" half of BITB-089's acceptance criterion,
and it doubles as the more interesting proof -- ``r0002`` showed the pipeline
can apply a revision to a freshly *stamped* database, whereas this one shows it
advances an existing chain, ``r0002 -> r0003``.

The ``to_regclass`` guard is kept for the same reason as in ``r0002``: CI builds
its database from the ORM-backed tables only, so ``sessions`` -- created by
``scripts/init.sql`` / ``scripts/migrations/`` -- does not exist there, and an
unguarded ``COMMENT ON`` would fail every CI run.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0003"
down_revision: Union[str, None] = "r0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF to_regclass('public.sessions') IS NOT NULL THEN
                COMMENT ON TABLE sessions IS NULL;
            END IF;
        END
        $$;
        """)


def downgrade() -> None:
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
