"""grant search_eval_ro access to topic-boosting tables (BITB-104)

Revision ID: r0006
Revises: r0005
Create Date: 2026-09-05 00:00:00.000000

The topic-boosted eval path reads ``topics`` and ``verse_topics`` in addition
to the tables granted by r0005. ``verse_topics`` is still created by the
legacy migration chain, so the grant is guarded for clean Alembic-only test
databases where that table is intentionally absent.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0006"
down_revision: str | None = "r0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_NAME = "search_eval_ro"
READ_TABLES = ("topics", "verse_topics")


def _set_timeouts() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '10min'")


def _change_privileges(action: str) -> None:
    for table in READ_TABLES:
        op.execute(f"""
            DO $$
            BEGIN
                IF to_regclass('public.{table}') IS NOT NULL THEN
                    {action} SELECT ON TABLE public.{table} {"TO" if action == "GRANT" else "FROM"} {ROLE_NAME};
                END IF;
            END
            $$
            """)


def upgrade() -> None:
    _set_timeouts()
    _change_privileges("GRANT")


def downgrade() -> None:
    _set_timeouts()
    _change_privileges("REVOKE")
