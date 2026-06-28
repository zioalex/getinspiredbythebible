"""
Vox Quieta API

Main FastAPI application entry point.
"""

import os
import traceback as _traceback
from contextlib import asynccontextmanager

# Configure Azure Monitor (Application Insights) as early as possible.
# This ensures that all subsequent imports that might create meters/tracers
# are correctly bound to the Azure Monitor provider.
_appinsights_conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
_appinsights_initialized: bool = False
if _appinsights_conn:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=_appinsights_conn,
            # Scope to our app logger so Azure SDK internal logs are not exported
            logger_name="bible_app",
        )
        _appinsights_initialized = True
        # Note: We can't use our logger yet as it hasn't been set up
        print("Application Insights telemetry initialized")
    except Exception as e:
        # Print full traceback so container logs capture the root cause
        print(f"WARNING: Failed to configure Application Insights: {e}")
        print(_traceback.format_exc())

from fastapi import Depends, FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from config import settings  # noqa: E402
from middleware.access_audit import AccessAuditMiddleware  # noqa: E402
from middleware.correlation_id import CorrelationIDMiddleware  # noqa: E402
from providers import ProviderError, get_embedding_provider, get_llm_provider  # noqa: E402
from routes import (  # noqa: E402
    admin_router,
    chat_router,
    church_router,
    feedback_router,
    health_router,
    scripture_router,
)
from scripture import close_db, init_db  # noqa: E402
from utils.local_only import require_local_access  # noqa: E402
from utils.logging_config import get_logger, setup_logging  # noqa: E402
from utils.metrics import meter as _metrics_meter  # noqa: F401, E402

# Configure logging before anything else
setup_logging()
logger = get_logger(__name__)


async def _purge_blocked_samples_at_startup() -> None:
    """Best-effort TTL sweep for blocked-message samples on app start."""
    try:
        from feedback.blocked_samples import purge_expired_blocked_samples

        deleted = await purge_expired_blocked_samples()
        if deleted:
            logger.info("Purged expired blocked-message samples", extra={"deleted": deleted})
    except Exception as e:
        logger.warning("Blocked-sample purge failed at startup: %s", e)


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
    # Get the actual model being used based on provider
    if settings.llm_provider == "openrouter":
        llm_model = settings.openrouter_model
    else:
        llm_model = settings.llm_model

    logger.info(
        "LLM configuration",
        extra={
            "provider": settings.llm_provider,
            "model": llm_model,
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
    logger.info(
        "Security configuration",
        extra={
            "rate_limit_enabled": settings.rate_limit_enabled,
            "rate_limit_per_minute": settings.rate_limit_requests_per_minute,
            "content_filter_enabled": settings.content_filter_enabled,
            "max_message_length": settings.max_message_length,
        },
    )

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Database initialization failed", extra={"error": str(e)})

    await _purge_blocked_samples_at_startup()

    yield

    # Shutdown
    logger.info("Shutting down application")
    await close_db()

    # Close provider HTTP clients
    try:
        logger.info("Cleaning up LLM provider")
        await get_llm_provider().close()
        logger.info("LLM provider cleanup complete")
    except Exception as e:
        logger.warning("Failed to clean up LLM provider: %s", e)

    try:
        logger.info("Cleaning up embedding provider")
        await get_embedding_provider().close()
        logger.info("Embedding provider cleanup complete")
    except Exception as e:
        logger.warning("Failed to clean up embedding provider: %s", e)

    logger.info("Provider cleanup complete")

    # Flush OpenTelemetry telemetry before container shuts down.
    # Without this, the batch exporter may lose pending spans/logs/metrics
    # when the container scales to zero.
    if _appinsights_initialized:
        try:
            logger.info("Flushing telemetry before shutdown...")
            from opentelemetry import metrics, trace  # type: ignore[attr-defined]
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.trace import TracerProvider

            # Flush traces
            tp = trace.get_tracer_provider()
            if isinstance(tp, TracerProvider):
                tp.force_flush(timeout_millis=5000)

            # Flush metrics
            mp = metrics.get_meter_provider()
            if isinstance(mp, MeterProvider):
                mp.force_flush(timeout_millis=5000)

            logger.info("Telemetry flush complete")
        except Exception as e:
            logger.debug("Failed to flush telemetry: %s", e)


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


def _get_cors_origins() -> list[str]:
    """Build list of allowed CORS origins from settings."""
    # Always allow localhost for development
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        # Production domain (configurable via PRODUCTION_FRONTEND_URL env var)
        settings.production_frontend_url,
    ]
    # Add custom origins from environment variable (comma-separated)
    if settings.cors_origins:
        custom_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        origins.extend(custom_origins)
    return origins


# Explicitly instrument the FastAPI app for Application Insights request tracing.
# configure_azure_monitor() replaces fastapi.FastAPI with an instrumented subclass,
# but our `from fastapi import FastAPI` already bound the original class. So the app
# created above is uninstrumented. instrument_app() adds the ASGI tracing middleware
# directly, giving us server requests, response times, and dependency tracking.
if _appinsights_initialized:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI request tracing instrumented")
    except Exception as e:
        logger.warning("Failed to instrument FastAPI app: %s", e)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Correlation ID middleware for request tracing
# Added after CORS (executes before CORS in request chain due to middleware stack)
app.add_middleware(CorrelationIDMiddleware)

# Access audit middleware for monitoring unofficial API access
# Added last = executes first (outermost), sees all requests before other middleware
app.add_middleware(AccessAuditMiddleware)


# ==================== Routes ====================

app.include_router(chat_router, prefix="/api/v1")
app.include_router(church_router, prefix="/api/v1")
app.include_router(feedback_router, prefix="/api/v1")
app.include_router(health_router)  # Health endpoints at root level
app.include_router(scripture_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")  # internal probe-gated endpoints


# ==================== Health & Info ====================


@app.get("/", tags=["info"])
async def root():
    """API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "commit": settings.git_sha,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/config", tags=["info"])
async def get_config():
    """
    Get current configuration (non-sensitive).

    Useful for debugging and frontend configuration.
    """
    # Get the actual model being used based on provider
    if settings.llm_provider == "openrouter":
        llm_model = settings.openrouter_model
    else:
        llm_model = settings.llm_model

    return {
        "version": {
            "app_version": settings.app_version,
            "commit": settings.git_sha,
        },
        "telemetry": {
            "appinsights_configured": bool(_appinsights_conn),
            "appinsights_initialized": _appinsights_initialized,
        },
        "llm": {
            "provider": settings.llm_provider,
            "model": llm_model,
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
        "security": {
            "turnstile_enabled": settings.turnstile_enabled,
            "turnstile_site_key": (
                settings.turnstile_site_key if settings.turnstile_enabled else None
            ),
        },
    }


@app.post("/api/v1/client-errors", include_in_schema=False)
async def report_client_error(request: Request):
    """Receive client-side error reports (Turnstile failures, etc.)."""
    body = await request.json()
    client_ip = request.headers.get(
        "CF-Connecting-IP",
        request.headers.get(
            "X-Forwarded-For", request.client.host if request.client else "unknown"
        ),
    )
    logger.warning(
        "Client error report: %s — %s",
        body.get("type", "unknown"),
        body.get("detail", ""),
        extra={
            "error_type": body.get("type"),
            "error_detail": body.get("detail"),
            "user_agent": request.headers.get("user-agent"),
            "ip": client_ip,
        },
    )
    return {"status": "ok"}


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
            query = text("""
                SELECT
                    COUNT(*) as total_verses,
                    COUNT(embedding) as verses_with_embeddings,
                    CASE WHEN COUNT(embedding) > 0
                        THEN array_length(embedding::real[], 1)
                        ELSE NULL
                    END as embedding_dimensions
                FROM verses
                LIMIT 1
            """)
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
