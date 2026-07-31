"""Alembic environment script.

Run from ``api/`` (``alembic upgrade head`` etc. -- see ``api/alembic/README.md``
and ``docs/MIGRATION_GUIDELINES.md``). ``alembic.ini`` sets
``prepend_sys_path = .`` so the imports below resolve exactly like they do for
the app itself.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from feedback.models import Base as FeedbackBase
from scripture.database import get_async_database_url
from scripture.models import Base as ScriptureBase

# this is the Alembic Config object, which provides access to values within
# the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Both ORM bases this project defines. Autogenerate diffs the union of these
# against the live database.
target_metadata = [ScriptureBase.metadata, FeedbackBase.metadata]

# Tables Alembic is allowed to know about. Five tables in the real database --
# sessions, verse_topics, rate_limit_hits, rate_limit_sessions, schema_migrations
# -- were created by the hand-rolled scripts/migrations/ system and scripts/init.sql
# and have no SQLAlchemy ORM model (see docs/MIGRATION_GUIDELINES.md and
# scripts/migrations/README.md). Without this allowlist, autogenerate would see
# those tables as "not in target_metadata" and emit `op.drop_table(...)` for every
# one of them on the very first `revision --autogenerate`. This is intentional
# scope-limiting, not a bug: those tables stay owned by the legacy system until a
# future story explicitly migrates them into Alembic.
_OWNED_TABLES = set(ScriptureBase.metadata.tables) | set(FeedbackBase.metadata.tables)


def include_name(name, type_, parent_names):
    """Restrict autogenerate to objects Alembic actually owns.

    Schemas: only the default (unnamed) schema -- this project doesn't use
    Postgres schemas beyond ``public``.
    Tables: only tables backed by an ORM model (see ``_OWNED_TABLES`` above).
    Everything else (columns, indexes, etc.) defers to ``include_object``.
    """
    if type_ == "schema":
        return name is None
    if type_ == "table":
        return name in _OWNED_TABLES
    return True


def include_object(object_, name, type_, reflected, compare_to):
    """Ignore raw-SQL-created indexes that have no ORM-side definition.

    Indexes such as ``idx_verses_fts_english``/``idx_verses_fts_simple``
    (``scripts/migrations/003_add_fulltext_index.sql``), the passage FTS
    equivalents, and the per-translation partial HNSW indexes
    ``idx_verse_emb_hnsw_<translation>`` (``scripts/migrations/007_partial_hnsw_verse_indexes.py``)
    exist in the database but were never declared on any model, so Alembic
    would otherwise propose dropping them on every autogenerate. ``reflected
    and compare_to is None`` is exactly "this index was found in the database
    but has no corresponding object in target_metadata" -- i.e. an index this
    migration system doesn't own.
    """
    if type_ == "index" and reflected and compare_to is None:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine, though an
    Engine is acceptable here as well. By skipping the Engine creation we
    don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the script
    output, so this mode is used to produce a reviewable ``.sql`` file (e.g.
    for a DBA-reviewed, zero-downtime deploy) instead of connecting to a
    database directly: ``alembic upgrade head --sql``.
    """
    url, _connect_args = get_async_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
        include_object=include_object,
        # Column type comparison is intentionally off -- see the comment in
        # run_migrations_online() below for the full rationale (applies
        # identically here).
        compare_type=False,
        compare_server_default=True,
        # Alembic's own bookkeeping table stays at the default name
        # ("alembic_version"), deliberately distinct from the hand-rolled
        # scripts/migrations/ system's "schema_migrations" table (see
        # scripts/migrations/run_migrations.py). The two systems coexist
        # without collision during the transition described in
        # docs/MIGRATION_GUIDELINES.md.
        version_table="alembic_version",
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_name=include_name,
        include_object=include_object,
        # Vector(settings.embedding_dimensions) (api/scripture/models.py) is
        # environment-dependent: 1024 for the ollama-backed local/CI default,
        # 1536 for azure_openai in prod (see api/config.py). If compare_type
        # were on, autogenerate/`alembic check` would flag a Vector(1024) vs
        # Vector(1536) "drift" purely because two environments run different
        # embedding providers -- not because anyone changed the schema. Turning
        # column-type comparison off avoids that false-positive drift flapping
        # the CI gate; structural (table/column/index presence) comparison is
        # unaffected.
        compare_type=False,
        compare_server_default=True,
        version_table="alembic_version",
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an Engine and associate a connection with the context.

    Uses ``NullPool`` deliberately: this is a one-shot CLI invocation (revision
    generation, upgrade, downgrade, check), not the long-lived app process, so
    there is nothing to gain from pooling and no reason to hold a connection
    open past this single run.
    """
    url, connect_args = get_async_database_url()
    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine and associate a connection
    with the context.
    """
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
