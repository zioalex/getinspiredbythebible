"""add search_eval_ro read-only role for the nightly search-eval harness (BITB-101)

Revision ID: r0005
Revises: r0004
Create Date: 2026-08-26 00:00:00.000000

The nightly ``eval-prod`` job in ``.github/workflows/search-eval-full.yml``
previously authenticated as the Postgres **admin** role -- the same
credentials ``run-migrations`` uses to run DDL -- even though it only ever
issues ``SELECT``s. That made "read-only" a property of what the harness
happened to execute, not something the database enforced.

This revision creates ``search_eval_ro``: a login role that can only read
the three tables the harness actually queries (traced through
``api/search_eval/runner.py`` -> ``ScriptureSearchService.search()`` /
``search_hybrid()`` -> ``ScriptureRepository.search_verses_semantic()`` /
``search_verses_hybrid()``: ``verses``, ``books`` via
``selectinload(Verse.book)``, and ``verse_tsv`` via the hybrid path's
``LEFT JOIN``), with ``default_transaction_read_only = on`` so a write
attempt fails at the database, not by convention.

This project has no ``postgresql`` Terraform provider -- only ``azurerm``
and ``random`` (see ``deployment/main.tf``) -- and no existing precedent
for Terraform-managed Postgres roles or grants. All schema/role-level DDL
here goes through Alembic instead, which already runs with admin
credentials during deploy under a gated ``environment: production`` job
(``run-migrations`` in ``.github/workflows/azure-deploy.yml``). Provisioning
this role as a migration is therefore a deliberate deviation from the
Terraform approach the BITB-101 story doc originally sketched, in favor of
the mechanism this codebase actually uses for DDL.

Lock level / duration at production scale: every statement here is
catalog-only (``CREATE ROLE``, ``GRANT``, ``ALTER ROLE ... SET``) -- no
statement acquires a table-level lock stronger than the implicit
``ACCESS SHARE`` that ``GRANT`` briefly takes on each named table, and none
of it scales with table size (403,856 rows on ``verses`` is irrelevant here,
unlike r0004). Expected duration: low milliseconds, dominated by network
round-trips, not data volume.

This role has **no password** after this revision runs. Setting one is a
manual operator step (out of scope for a committed migration, which must
never contain a production credential): after this deploys,

    ALTER ROLE search_eval_ro WITH PASSWORD '<generated>';

run once by hand against production, with that value stored as the
``SEARCH_EVAL_DB_PASSWORD`` secret in a new ``search-eval`` GitHub
environment (not a bare repo secret) -- see the workflow change in the same
PR. Until that password is set, the role exists but cannot authenticate,
which is safe (fails closed, not open).

Idempotent throughout: role creation is guarded by a ``pg_roles`` existence
check (``CREATE ROLE`` has no native ``IF NOT EXISTS``); every ``GRANT`` and
``ALTER ROLE ... SET`` is naturally idempotent.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r0005"
down_revision: Union[str, None] = "r0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_NAME = "search_eval_ro"
READ_TABLES = ("verses", "books", "verse_tsv")


def _set_timeouts() -> None:
    """Bound this migration from inside the database (BITB-100 rule).

    ``SET LOCAL`` scopes both to Alembic's transaction, so nothing leaks into
    the session afterwards.
    """
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("SET LOCAL statement_timeout = '10min'")


def upgrade() -> None:
    _set_timeouts()

    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '{ROLE_NAME}') THEN
                CREATE ROLE {ROLE_NAME} LOGIN;
            END IF;
        END
        $$
        """)

    op.execute(f"""
        DO $$
        BEGIN
            EXECUTE format('GRANT CONNECT ON DATABASE %I TO {ROLE_NAME}', current_database());
        END
        $$
        """)

    op.execute(f"GRANT USAGE ON SCHEMA public TO {ROLE_NAME}")
    op.execute(f"GRANT SELECT ON {', '.join(READ_TABLES)} TO {ROLE_NAME}")

    # The load-bearing line: makes "read-only" a property the database
    # enforces, not the harness's own behaviour.
    op.execute(f"ALTER ROLE {ROLE_NAME} SET default_transaction_read_only = on")
    op.execute(f"ALTER ROLE {ROLE_NAME} SET statement_timeout = '60s'")
    op.execute(f"ALTER ROLE {ROLE_NAME} SET idle_in_transaction_session_timeout = '60s'")


def downgrade() -> None:
    _set_timeouts()

    op.execute(f"REVOKE SELECT ON {', '.join(READ_TABLES)} FROM {ROLE_NAME}")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {ROLE_NAME}")
    op.execute(f"""
        DO $$
        BEGIN
            EXECUTE format('REVOKE CONNECT ON DATABASE %I FROM {ROLE_NAME}', current_database());
        END
        $$
        """)
    op.execute(f"ALTER ROLE {ROLE_NAME} RESET default_transaction_read_only")
    op.execute(f"ALTER ROLE {ROLE_NAME} RESET statement_timeout")
    op.execute(f"ALTER ROLE {ROLE_NAME} RESET idle_in_transaction_session_timeout")
    op.execute(f"DROP ROLE IF EXISTS {ROLE_NAME}")
