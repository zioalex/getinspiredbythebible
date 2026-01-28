"""
Bible Inspiration Chat API

Main FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from providers import ProviderError
from routes import (
    chat_router,
    church_router,
    feedback_router,
    health_router,
    scripture_router,
)
from scripture import close_db, init_db
from utils.local_only import require_local_access
from utils.logging_config import setup_logging

# Configure logging before anything else
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown tasks.
    """
    # Startup
    logger.info(
        "Starting application",
        extra={
            "app": settings.app_name,
            "version": settings.app_version,
            "debug": settings.debug,
        },
    )
    logger.info(
        "LLM configuration",
        extra={
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
        },
    )
    logger.info(
        "Embedding configuration",
        extra={
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
        },
    )
    logger.info(
        "Email configuration",
        extra={
            "enabled": settings.smtp2go_enabled,
            "api_configured": bool(settings.smtp2go_api_key),
        },
    )

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Database initialization failed", extra={"error": str(e)})

    yield

    # Shutdown
    logger.info("Shutting down application")
    await close_db()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    A conversational AI that helps people find spiritual encouragement
    and relevant scripture based on their life situations.

    ## Features

    - **Chat**: Natural conversation with Bible-grounded responses
    - **Scripture Search**: Semantic search for relevant verses
    - **Verse Lookup**: Get specific verses with context

    ## LLM Providers

    The API supports multiple LLM backends:
    - **Ollama** (default): Self-hosted, local inference
    - **Claude**: Anthropic's Claude API
    - **OpenAI**: Coming soon
    """,
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "https://getinspiredbythebible.ai4you.sh",
        "http://getinspiredbythebible.ai4you.sh",
        # Add production domains here
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Routes ====================

app.include_router(chat_router, prefix="/api/v1")
app.include_router(church_router, prefix="/api/v1")
app.include_router(feedback_router, prefix="/api/v1")
app.include_router(health_router)  # Health endpoints at root level
app.include_router(scripture_router, prefix="/api/v1")


# ==================== Health & Info ====================


@app.get("/", tags=["info"])
async def root():
    """API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/config", tags=["info"])
async def get_config():
    """
    Get current configuration (non-sensitive).

    Useful for debugging and frontend configuration.
    """
    return {
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
        },
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
        },
        "chat": {
            "max_context_verses": settings.max_context_verses,
            "max_conversation_history": settings.max_conversation_history,
        },
    }


@app.get("/debug/embeddings", tags=["debug"], dependencies=[Depends(require_local_access)])
async def debug_embeddings():
    """
    Debug endpoint to check embedding dimensions.

    **Access restricted to local/internal networks only.**

    Compares configured dimensions vs actual database dimensions.
    Useful for diagnosing dimension mismatch errors.
    """
    from sqlalchemy import text

    from providers import get_embedding_provider
    from scripture.database import async_session_factory

    result = {
        "config": {
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "configured_dimensions": settings.embedding_dimensions,
        },
        "provider": {},
        "database": {},
        "match": False,
    }

    # Check provider dimensions
    try:
        provider = get_embedding_provider()
        test_embedding = await provider.embed("test")
        result["provider"] = {
            "name": provider.provider_name,
            "actual_dimensions": len(test_embedding.embedding),
            "healthy": True,
        }
    except Exception as e:
        result["provider"] = {"error": str(e), "healthy": False}

    # Check database embedding dimensions
    try:
        async with async_session_factory() as session:
            # Check if verses table has embeddings and their dimensions
            query = text(
                """
                SELECT
                    COUNT(*) as total_verses,
                    COUNT(embedding) as verses_with_embeddings,
                    CASE WHEN COUNT(embedding) > 0
                        THEN array_length(embedding::real[], 1)
                        ELSE NULL
                    END as embedding_dimensions
                FROM verses
                LIMIT 1
            """
            )
            db_result = await session.execute(query)
            row = db_result.fetchone()

            result["database"] = {
                "total_verses": row[0],
                "verses_with_embeddings": row[1],
                "embedding_dimensions": row[2],
                "connected": True,
            }
    except Exception as e:
        result["database"] = {"error": str(e), "connected": False}

    # Check if dimensions match
    provider_dims = result["provider"].get("actual_dimensions")
    db_dims = result["database"].get("embedding_dimensions")
    config_dims = settings.embedding_dimensions

    result["match"] = (
        provider_dims == db_dims == config_dims if all([provider_dims, db_dims]) else False
    )
    result["diagnosis"] = []

    if provider_dims and provider_dims != config_dims:
        result["diagnosis"].append(
            f"Provider returns {provider_dims} dims but config says {config_dims}"
        )
    if db_dims and db_dims != config_dims:
        result["diagnosis"].append(f"Database has {db_dims} dims but config says {config_dims}")
    if provider_dims and db_dims and provider_dims != db_dims:
        result["diagnosis"].append(
            f"MISMATCH: Provider={provider_dims} dims, Database={db_dims} dims. "
            "You need to regenerate embeddings with the current provider."
        )

    if not result["diagnosis"]:
        result["diagnosis"].append("All dimensions match correctly")

    return result


# ==================== Error Handlers ====================


@app.exception_handler(ProviderError)
async def provider_error_handler(request, exc: ProviderError):
    """Handle LLM provider errors."""
    return JSONResponse(
        status_code=503,
        content={
            "error": "LLM Provider Error",
            "detail": str(exc),
            "hint": "Check if Ollama is running: ollama serve",
        },
    )


if __name__ == "__main__":
    import uvicorn

    # nosec B104: Binding to 0.0.0.0 is intentional for Docker container accessibility
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)  # nosec
