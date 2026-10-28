"""add tts_event_daily aggregate table (BITB-247)

Revision ID: r0008
Revises: r0007
Create Date: 2026-10-27 00:00:00.000000

Creates ``tts_event_daily (day, event, locale, platform, browser, os, count)``,
the daily aggregate of read-aloud client events behind the weekly report's
"Read aloud" section. The six dimension columns form the primary key so the
endpoint can increment atomically with ``INSERT ... ON CONFLICT DO UPDATE SET
count = count + 1``. All dimensions are bounded enums (no text, user agent, IP
or identifiers).

Lock / rewrite assessment (docs/MIGRATION_GUIDELINES.md):

* ``CREATE TABLE`` on a brand-new table takes no lock on any existing table and
  rewrites nothing. It is catalog work only: sub-second at any scale. There is
  no foreign key, so no existing table (``verses`` etc.) is touched.
* The table starts empty; growth is bounded (days x events x locales x
  platform/browser/os enums), at most a few thousand rows per day.
* Backward-compatible (Rule #7, expand/contract): nothing in the currently
  deployed app reads or writes this table. The new endpoint code tolerates the
  table being absent (the upsert is logged and swallowed; the weekly report
  falls back to an empty section), so the order of migration vs. deploy is safe.
* ``lock_timeout`` is set so the statement can never queue behind a long
  transaction and stall other sessions; ``IF NOT EXISTS`` / ``IF EXISTS`` keep
  it idempotent.
* ``downgrade()`` drops the table; the data is a non-critical telemetry aggregate.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0008"
down_revision: str | None = "r0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _set_timeouts() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '30s'")


def upgrade() -> None:
    _set_timeouts()
    op.create_table(
        "tts_event_daily",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("browser", sa.String(length=16), nullable=False),
        sa.Column("os", sa.String(length=16), nullable=False),
        sa.Column("count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint(
            "day", "event", "locale", "platform", "browser", "os", name="tts_event_daily_pkey"
        ),
        if_not_exists=True,
    )


def downgrade() -> None:
    _set_timeouts()
    op.drop_table("tts_event_daily", if_exists=True)
