"""make translations.created_at timezone-aware (BITB-127)

Revision ID: r0007
Revises: r0006
Create Date: 2026-10-06 00:00:00.000000

Converts ``translations.created_at`` from ``timestamp without time zone`` to
``timestamp with time zone`` so it matches every other ``created_at`` column.
Existing values were always written as UTC (``CURRENT_TIMESTAMP`` /
``datetime.utcnow()``), so the ``USING created_at AT TIME ZONE 'UTC'`` clause
reinterprets each stored value as the same instant -- no zone shift.

Lock / rewrite assessment (docs/MIGRATION_GUIDELINES.md):

* ``ALTER COLUMN ... TYPE`` takes ``ACCESS EXCLUSIVE`` on ``translations``
  only. ``verses`` has its foreign key on ``translations.code``, and the
  column being altered is not part of it, so ``verses`` is not locked.
* ``translations`` holds ~13 rows (one per bundled Bible translation). The
  production row count is unconfirmed: run ``SELECT count(*) FROM
  translations`` before applying.
* Only ``scripts/init.sql`` and the data loaders write this column; no
  request-path code does.
* Because of the ``AT TIME ZONE`` ``USING`` clause, PostgreSQL performs a
  full table rewrite. Plan for it; at this size it is sub-second.
* The column has no indexes, so there is no index rebuild.
* The table is not in the banned-table list for risky DDL.
* ``lock_timeout`` is set so a queued ACCESS EXCLUSIVE request cannot stall
  readers behind it indefinitely.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0007"
down_revision: str | None = "r0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _set_timeouts() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '10min'")


def upgrade() -> None:
    _set_timeouts()
    op.alter_column(
        "translations",
        "created_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    _set_timeouts()
    op.alter_column(
        "translations",
        "created_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
