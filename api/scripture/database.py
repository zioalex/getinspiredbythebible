"""
Database connection and session management.
"""

import ssl
from typing import Annotated, AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

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

# Create async engine
engine = create_async_engine(
    _async_url,
    poolclass=NullPool,  # Better for async
    echo=settings.debug,
    connect_args=_connect_args,
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
    from .models import Base

    async with engine.begin() as conn:
        # Create pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()
