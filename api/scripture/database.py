"""
Database connection and session management.
"""

import logging
import ssl
from typing import Annotated, AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import Depends
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from middleware.context import REQUEST_ID_CTX_VAR

logger = logging.getLogger(__name__)


def get_async_database_url() -> tuple[str, dict]:
    """
    Convert database URL to async version and extract SSL settings.

    asyncpg doesn't support sslmode as a URL parameter like psycopg2.
    We need to extract it and pass SSL config via connect_args.

    Both spellings are handled: ``?sslmode=require`` (libpq/psycopg2 form) and
    ``?ssl=require`` (the form `.github/workflows/azure-deploy.yml` builds for
    the migration job). Leaving either in the URL makes asyncpg fail at connect
    time with ``parameter 'ssl' cannot be changed now``, so both are stripped
    here and turned into a real SSL context on ``connect_args`` -- matching
    ``scripts/migrations/utils.py::get_migration_connection_params()``, which
    has always stripped both.

    Returns:
        Tuple of (async_url, connect_args)
    """
    url = settings.database_url
    connect_args: dict = {}

    # Parse the URL to extract and remove the SSL parameters
    parsed = urlparse(url)
    if parsed.query:
        query_params = parse_qs(parsed.query)
        # Pop both unconditionally -- neither may survive into the DSN handed to
        # asyncpg. `sslmode` wins when both are present; they are the same
        # libpq-style value set.
        sslmode = query_params.pop("sslmode", [None])[0]
        ssl_param = query_params.pop("ssl", [None])[0]
        sslmode = sslmode or ssl_param

        # Rebuild URL without the SSL parameters
        new_query = urlencode(query_params, doseq=True) if query_params else ""
        url = urlunparse(parsed._replace(query=new_query))

        # Configure SSL for asyncpg based on sslmode
        if sslmode in ("require", "verify-ca", "verify-full"):
            # Create SSL context for secure connection
            ssl_context = ssl.create_default_context()
            if sslmode == "require":
                # Don't verify certificate (like psycopg2's sslmode=require)
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ssl_context

    # Convert to async driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return url, connect_args


# Get async URL and connection args
_async_url, _connect_args = get_async_database_url()

# Bound every query at the driver and the server so a slow/hung backend fails fast
# and *visibly* instead of tying up a pooled connection until db_pool_timeout.
#   - command_timeout (asyncpg, client side): the request coroutine raises promptly,
#     so the fail-open guard logs it, emits scripture.pipeline.errors and retries once.
#   - statement_timeout (server side, ms, set a little lower): Postgres cancels the
#     runaway query itself, so even a wedged client socket cannot hold a backend open.
# Both sit well above normal request latency, so they only trip on genuine stalls.
_connect_args.setdefault("command_timeout", settings.db_command_timeout)
_server_settings = _connect_args.setdefault("server_settings", {})
_server_settings.setdefault("statement_timeout", str(settings.db_statement_timeout_ms))

# Create async engine.
#
# Use SQLAlchemy's default async pool (AsyncAdaptedQueuePool) rather than NullPool.
# NullPool opens a fresh connection per request: under concurrent multilingual load
# that means repeated connect/TLS handshakes and an unbounded number of backends
# hitting a small burstable Postgres. A bounded QueuePool reuses warm connections and
# caps concurrent backends (pool_size + max_overflow) well under the server's
# max_connections. pool_pre_ping validates a connection before use (handles Azure idle
# drops); pool_recycle proactively retires long-lived connections.
engine = create_async_engine(
    _async_url,
    echo=settings.debug,
    connect_args=_connect_args,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    pool_pre_ping=True,
)


@event.listens_for(engine.sync_engine, "connect")
def _apply_session_hnsw_ef_search(dbapi_connection, connection_record):
    """Apply ``hnsw.ef_search`` on every new pooled connection.

    This is the runtime source of truth for the HNSW exploration depth. The
    database-level ``ALTER DATABASE ... SET hnsw.ef_search`` (migration 007)
    requires DB-owner/superuser privileges that the Azure Flexible Server
    application role does not have, so it cannot be relied upon. Setting the GUC
    at the *session* level needs no special privilege (any role may ``SET`` a
    namespaced custom GUC) and the value persists for the life of the pooled,
    reused connection.

    The listener fires inside SQLAlchemy's asyncio greenlet, so the synchronous
    DBAPI cursor facade transparently awaits the underlying asyncpg call. A
    failure here would break every connection, so it is logged and swallowed:
    falling back to the server default degrades recall but keeps the app up
    (``config`` already enforces ``hnsw_ef_search >= vector_candidate_pool``).
    """
    try:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f"SET hnsw.ef_search = {int(settings.hnsw_ef_search)}")
        finally:
            cursor.close()
    except Exception:  # noqa: BLE001 - never let this take down a connection
        logger.warning("Failed to set hnsw.ef_search on new connection", exc_info=True)


def _prepend_request_id_comment(statement: str) -> str:
    """Prefix ``statement`` with a ``/* request_id=... */`` SQL comment.

    Lets a slow or stuck query be matched back to the request that issued it
    via ``pg_stat_activity``/server logs. The id may come from a client-supplied
    ``X-Request-ID`` header (see ``CorrelationIDMiddleware``), so it is
    sanitized to prevent breaking out of the comment.
    """
    request_id = REQUEST_ID_CTX_VAR.get("")
    if not request_id:
        return statement
    safe_id = request_id.replace("*/", "").replace("\n", " ")
    return f"/* request_id={safe_id} */ {statement}"


@event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
def _tag_query_with_request_id(conn, cursor, statement, parameters, context, executemany):
    # Note: making every statement string unique defeats asyncpg's prepared-statement
    # cache (keyed on SQL text), trading a per-query re-parse for traceability. Given
    # this app's read-mostly, low-QPS load, shipping as-is; revisit if profiling shows
    # a regression.
    return _prepend_request_id_comment(statement), parameters


# Session factory
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session.

    Usage:
        @app.get("/items")
        async def get_items(db: DbSession):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type alias for dependency injection
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def init_db():
    """Initialize database tables."""
    from feedback.models import Base as FeedbackBase

    from .models import Base as ScriptureBase

    async with engine.begin() as conn:
        # Create pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create all tables from both models
        await conn.run_sync(ScriptureBase.metadata.create_all)
        await conn.run_sync(FeedbackBase.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()
