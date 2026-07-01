"""
Health check routes for monitoring and orchestration.

Provides:
- /health - Comprehensive health check with component status
- /health/live - Liveness probe (is the process running?)
- /health/ready - Readiness probe (can we serve requests?)
"""

import asyncio
import resource
import time
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from config import settings
from providers import ProviderError, get_embedding_provider, get_llm_provider
from scripture.database import async_session_factory
from utils.local_only import require_local_access
from utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    status: str  # "healthy", "unhealthy", "degraded"
    latency_ms: float | None = None
    error: str | None = None
    details: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    """Complete health check response."""

    status: str  # "healthy", "unhealthy", "degraded"
    version: str
    components: dict[str, ComponentHealth]
    memory: dict[str, Any]


async def check_database_health(timeout: float | None = None) -> ComponentHealth:
    """Check database connectivity and measure latency.

    ``timeout`` defaults to ``settings.health_check_timeout`` (the comprehensive
    ``/health`` budget). The readiness probe passes a shorter value so it answers
    within the platform probe deadline instead of hanging up to the full budget.
    """
    timeout = settings.health_check_timeout if timeout is None else timeout
    start = time.perf_counter()
    try:
        async with async_session_factory() as session:
            result = await asyncio.wait_for(
                session.execute(text("SELECT 1")),
                timeout=timeout,
            )
            result.scalar()
            latency_ms = (time.perf_counter() - start) * 1000
            return ComponentHealth(
                status="healthy",
                latency_ms=round(latency_ms, 2),
            )
    except asyncio.TimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000
        # Log so a stalled DB is visible to the log-scan even though the platform
        # readiness probe gives up (and stays silent) before this returns.
        logger.warning(
            f"Database health check timed out after {timeout}s (elapsed {latency_ms:.0f}ms)"
        )
        return ComponentHealth(
            status="unhealthy",
            error=f"Database check timed out after {timeout}s",
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.warning(f"Database health check failed: {e}")
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e),
        )


async def check_llm_health() -> ComponentHealth:
    """Check LLM provider connectivity."""
    start = time.perf_counter()
    try:
        provider = get_llm_provider()
        healthy = await asyncio.wait_for(
            provider.health_check(),
            timeout=settings.health_check_timeout,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status="healthy" if healthy else "unhealthy",
            latency_ms=round(latency_ms, 2),
            details={"provider": provider.provider_name},
        )
    except asyncio.TimeoutError:
        logger.warning(
            f"LLM health check timed out after {settings.health_check_timeout}s "
            f"(provider={settings.llm_provider})"
        )
        return ComponentHealth(
            status="unhealthy",
            error=f"LLM check timed out after {settings.health_check_timeout}s",
            details={"provider": settings.llm_provider},
        )
    except ProviderError as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e),
            details={"provider": settings.llm_provider},
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.warning(f"LLM health check failed: {e}")
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e),
            details={"provider": settings.llm_provider},
        )


async def check_embedding_health() -> ComponentHealth:
    """Check embedding provider connectivity with a test embedding."""
    start = time.perf_counter()
    try:
        provider = get_embedding_provider()
        # Generate a small test embedding
        result = await asyncio.wait_for(
            provider.embed("health check"),
            timeout=settings.health_check_timeout,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status="healthy",
            latency_ms=round(latency_ms, 2),
            details={
                "provider": provider.provider_name,
                "dimensions": len(result.embedding),
            },
        )
    except asyncio.TimeoutError:
        logger.warning(
            f"Embedding health check timed out after {settings.health_check_timeout}s "
            f"(provider={settings.embedding_provider})"
        )
        return ComponentHealth(
            status="unhealthy",
            error=f"Embedding check timed out after {settings.health_check_timeout}s",
            details={"provider": settings.embedding_provider},
        )
    except ProviderError as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e),
            details={"provider": settings.embedding_provider},
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        logger.warning(f"Embedding health check failed: {e}")
        return ComponentHealth(
            status="unhealthy",
            latency_ms=round(latency_ms, 2),
            error=str(e),
            details={"provider": settings.embedding_provider},
        )


def get_memory_info() -> dict[str, Any]:
    """Get current memory usage information."""
    try:
        # Get memory usage from resource module (works on Unix)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # maxrss is in kilobytes on Linux, bytes on macOS
        used_mb = usage.ru_maxrss / 1024  # Convert to MB (Linux)

        return {
            "used_mb": round(used_mb, 2),
            "limit_mb": settings.memory_warning_threshold_mb,
            "percent": round((used_mb / settings.memory_warning_threshold_mb) * 100, 1),
            "warning": used_mb > settings.memory_warning_threshold_mb,
        }
    except Exception as e:
        logger.warning(f"Could not get memory info: {e}")
        return {"error": str(e)}


@router.get("", response_model=HealthResponse, dependencies=[Depends(require_local_access)])
async def health_check():
    """
    Comprehensive health check with component-level status.

    **Access restricted to local/internal networks only.**

    Checks:
    - Database connectivity and latency
    - LLM provider availability
    - Embedding provider availability
    - Memory usage

    Returns:
    - status: "healthy" if all components healthy
    - status: "degraded" if some components unhealthy but app can still serve requests
    - status: "unhealthy" if critical components are down
    """
    # Run all health checks concurrently
    db_health, llm_health, embedding_health = await asyncio.gather(
        check_database_health(),
        check_llm_health(),
        check_embedding_health(),
    )

    components = {
        "database": db_health,
        "llm": llm_health,
        "embedding": embedding_health,
    }

    memory = get_memory_info()

    # Determine overall status
    # Database is critical - if it's down, we're unhealthy
    # LLM/Embedding degraded means we can still serve some requests
    if db_health.status == "unhealthy":
        overall_status = "unhealthy"
    elif llm_health.status == "unhealthy" or embedding_health.status == "unhealthy":
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    response = HealthResponse(
        status=overall_status,
        version=settings.app_version,
        components=components,
        memory=memory,
    )

    # Return 503 if unhealthy for load balancer integration
    if overall_status == "unhealthy":
        return JSONResponse(status_code=503, content=response.model_dump())

    return response


@router.get("/live")
async def liveness_probe():
    """
    Liveness probe for Kubernetes/orchestration.

    Returns 200 if the process is running and can handle requests.
    This is a fast check that always succeeds if the app has started.

    Use this for restart decisions - if this fails, restart the container.
    """
    return {"status": "alive"}


@router.get("/ready")
async def readiness_probe():
    """
    Readiness probe for Kubernetes/orchestration.

    Returns 200 if the app can serve requests, 503 only when the database —
    the dependency that actually gates request serving — is unavailable.

    Intentionally cheap: it checks ONLY the database, with a short timeout
    (`settings.readiness_check_timeout`) that stays under the platform probe
    deadline (`deployment/main.tf` readiness_probe.timeout). The LLM and
    embedding providers are deliberately NOT probed here. Calling those external
    APIs on every scrape (~every 10s) made readiness exceed the probe deadline
    whenever a free-tier upstream was slow, flapping the pod for weeks while it
    was otherwise serving fine. Their health is covered by the comprehensive
    `/health` endpoint and by the LLM/embedding fallback metric alerts;
    single-dependency inference degradation still serves (degraded) responses
    and must not bounce the pod.
    """
    db_health = await check_database_health(timeout=settings.readiness_check_timeout)

    dependencies = {"database": db_health.status}

    if db_health.status == "unhealthy":
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "database_unavailable",
                "dependencies": dependencies,
                "error": db_health.error,
            },
        )

    return {
        "status": "ready",
        "database_latency_ms": db_health.latency_ms,
        "dependencies": dependencies,
    }
