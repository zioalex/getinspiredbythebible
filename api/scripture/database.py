"""
Database connection and session management.
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator, Annotated
from fastapi import Depends

from config import settings


def get_async_database_url() -> str:
    """Convert database URL to async version."""
    url = settings.database_url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# Create async engine
engine = create_async_engine(
    get_async_database_url(),
    poolclass=NullPool,  # Better for async
    echo=settings.debug
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


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
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()
