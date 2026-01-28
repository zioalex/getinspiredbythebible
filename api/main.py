"""
Bible Inspiration Chat API

Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from providers import ProviderError, check_providers_health
from routes import chat_router, church_router, feedback_router, scripture_router
from scripture import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown tasks.
    """
    # Startup
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    print(f"📖 LLM Provider: {settings.llm_provider} ({settings.llm_model})")
    print(f"🔍 Embedding Provider: {settings.embedding_provider} ({settings.embedding_model})")

    # Initialize database
    try:
        await init_db()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

    yield

    # Shutdown
    print("👋 Shutting down...")
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


@app.get("/health", tags=["health"])
async def health_check():
    """
    Check API and provider health.

    Returns status of all system components.
    """
    try:
        provider_health = await check_providers_health()

        all_healthy = all(p["healthy"] for p in provider_health.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "providers": provider_health,
            "config": {
                "llm_provider": settings.llm_provider,
                "llm_model": settings.llm_model,
                "embedding_provider": settings.embedding_provider,
                "embedding_model": settings.embedding_model,
            },
        }
    except ProviderError as e:
        return JSONResponse(status_code=503, content={"status": "unhealthy", "error": str(e)})


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
