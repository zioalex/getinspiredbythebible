"""
Database connection and session management.
"""

import ssl
from typing import Annotated, AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings


def get_async_database_url() -> tuple[str, dict]:
    """
    Convert database URL to async version and extract SSL settings.

    asyncpg doesn't support sslmode as a URL parameter like psycopg2.
    We need to extract it and pass SSL config via connect_args.

    Returns:
        Tuple of (async_url, connect_args)
    """
    url = settings.database_url
    connect_args: dict = {}

    # Parse the URL to extract and remove sslmode parameter
    parsed = urlparse(url)
    if parsed.query:
        query_params = parse_qs(parsed.query)
        sslmode = query_params.pop("sslmode", [None])[0]

        # Rebuild URL without sslmode
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
