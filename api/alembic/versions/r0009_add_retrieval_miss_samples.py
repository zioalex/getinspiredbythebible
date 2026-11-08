"""add retrieval_miss_samples table (BITB-256)

Revision ID: r0009
Revises: r0008
Create Date: 2026-11-03 00:00:00.000000

Creates ``retrieval_miss_samples``: privacy-safe records of chat turns where
scripture retrieval was empty, weak, or the reply cited verses outside the
retrieved context. Holds only derived signals (topic ids, sanitized expansion
keywords, verse references + scores, language, translation, a hashed session id);
no column holds user or model text. Deduplicated by ``signature_sha256`` with a
``hit_count``; ``expires_at`` is fixed at first insert and purged by the app.

Lock / rewrite assessment (docs/MIGRATION_GUIDELINES.md):

* ``CREATE TABLE`` on a brand-new table takes no lock on any existing table and
  rewrites nothing. Catalog work only: sub-second at any scale. No foreign keys,
  so no existing table is touched. The indexes are created on the empty new table,
  so they need no ``CONCURRENTLY``.
* The table starts empty; growth is bounded by the dedup signature
  (reasons x intent x language x translation x topic set x retrieval
  mode x embedding model) and the 90-day purge.
* Backward-compatible (Rule #7, expand/contract): nothing in the currently deployed
  app reads or writes this table. The capture code is flag-gated
  (``RETRIEVAL_MISS_CAPTURE_ENABLED``, default off) and swallows write errors, so
  migration vs. deploy order is safe.
* ``lock_timeout`` is set so the statement can never queue behind a long
  transaction; ``IF NOT EXISTS`` / ``IF EXISTS`` keep it idempotent.
* ``downgrade()`` drops the table; the data is non-critical diagnostics.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0009"
down_revision: str | None = "r0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _set_timeouts() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '30s'")


def upgrade() -> None:
    _set_timeouts()
    op.create_table(
        "retrieval_miss_samples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reasons", postgresql.ARRAY(sa.String(length=24)), nullable=False),
        sa.Column("intent", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("translation", sa.String(length=20), nullable=False),
        sa.Column("topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("expansion_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("top_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("top_score", sa.Float(), nullable=True),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column(
            "cited_outside_pool",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("retrieval_mode", sa.String(length=24), nullable=False),
        sa.Column("embedding_provider", sa.String(length=32), nullable=False),
        sa.Column("embedding_model", sa.String(length=100), nullable=False),
        sa.Column("session_id_hash", sa.String(length=64), nullable=True),
        sa.Column("signature_sha256", sa.String(length=64), nullable=False),
        sa.Column("hit_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_retrieval_miss_samples_expires_at"),
        "retrieval_miss_samples",
        ["expires_at"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        op.f("ix_retrieval_miss_samples_signature_sha256"),
        "retrieval_miss_samples",
        ["signature_sha256"],
        unique=True,
        if_not_exists=True,
    )
    op.create_index(
        "ix_retrieval_miss_samples_lang_created",
        "retrieval_miss_samples",
        ["language", "created_at"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    _set_timeouts()
    op.drop_table("retrieval_miss_samples", if_exists=True)
