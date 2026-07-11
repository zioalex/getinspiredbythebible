"""
Access Audit Middleware for monitoring unofficial API access.

Classifies every /api/ request as "official" (from web frontend or Android app)
or "unofficial" (direct curl, scripts, unknown clients).  Records an
OpenTelemetry counter metric and logs a WARNING for unofficial access.

This middleware never blocks requests — it is observability-only.
"""

import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from config import settings
from utils.logging_config import get_logger
from utils.metrics import api_access_counter, preflight_errors_counter
from utils.turnstile import _get_client_ip

logger = get_logger(__name__)

# ── Path normalization patterns ──────────────────────────────────────────
# Collapse dynamic segments to keep metric cardinality low.
_PATH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"/api/v1/scripture/verse/[^/]+/\d+/\d+"),
        "/api/v1/scripture/verse/{book}/{chapter}/{verse}",
    ),
    (
        re.compile(r"/api/v1/scripture/chapter/[^/]+/\d+"),
        "/api/v1/scripture/chapter/{book}/{chapter}",
    ),
    (
        re.compile(r"/api/v1/scripture/verse-context/[^/]+/\d+/\d+"),
        "/api/v1/scripture/verse-context/{book}/{chapter}/{verse}",
    ),
]

# ── User-Agent classification ────────────────────────────────────────────
_UA_PATTERNS: list[tuple[str, str]] = [
    ("okhttp", "okhttp"),
    ("mozilla", "browser"),
    ("chrome", "browser"),
    ("safari", "browser"),
    ("firefox", "browser"),
    ("edge", "browser"),
    ("curl", "curl"),
    ("python", "python"),
    ("httpx", "python"),
    ("wget", "wget"),
    ("go-http-client", "go"),
    ("java", "java"),
]

# ── Log throttle: avoid flooding logs for the same IP+path ───────────────
_THROTTLE_TTL_SECONDS = 60
_throttle_cache: dict[str, float] = {}
_MAX_THROTTLE_ENTRIES = 10_000


def _normalize_path(path: str) -> str:
    """Collapse dynamic path segments for metric cardinality control."""
    for pattern, replacement in _PATH_PATTERNS:
        if pattern.search(path):
            return replacement
    return path


def _classify_user_agent(ua: str) -> str:
    """Return a short label for the User-Agent family."""
    ua_lower = ua.lower()
    for fragment, label in _UA_PATTERNS:
        if fragment in ua_lower:
            return label
    return "other"


def _get_allowed_origins() -> list[str]:
    """Build the set of allowed origins (mirrors _get_cors_origins in main.py)."""
    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        settings.production_frontend_url,
    ]
    if settings.cors_origins:
        custom = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
        origins.extend(custom)
    return origins


def _origin_matches(header_value: str, allowed: list[str]) -> bool:
    """Check if Origin or Referer header matches an allowed origin."""
    if not header_value:
        return False
    # Origin is an exact match; Referer starts with the origin.
    value = header_value.rstrip("/")
    for origin in allowed:
        origin_stripped = origin.rstrip("/")
        if value == origin_stripped or value.startswith(origin_stripped + "/"):
            return True
    return False


def _should_throttle(key: str) -> bool:
    """Return True if we already logged this key within the TTL window."""
    now = time.monotonic()
    # Periodic eviction to prevent unbounded growth
    if len(_throttle_cache) > _MAX_THROTTLE_ENTRIES:
        expired = [k for k, ts in _throttle_cache.items() if now - ts > _THROTTLE_TTL_SECONDS]
        for k in expired:
            del _throttle_cache[k]
    last = _throttle_cache.get(key)
    if last is not None and now - last < _THROTTLE_TTL_SECONDS:
        return True
    _throttle_cache[key] = now
    return False


class AccessAuditMiddleware(BaseHTTPMiddleware):
    """
    Observability middleware that classifies API requests as official or
    unofficial and records OpenTelemetry metrics.

    Official sources:
    - Web frontend: Origin/Referer matches an allowed CORS origin
    - Android app: X-Turnstile-Token header present (sent on all requests)

    Never blocks requests.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        path = request.url.path

        # Only audit /api/ paths
        if not path.startswith("/api/"):
            return await call_next(request)

        # Skip preflight and HEAD from the official/unofficial classification,
        # but still observe OPTIONS 5xx: a browser CORS preflight that returns
        # 5xx is a browser-only outage (the _IncludedRouter incident) that no
        # other signal here catches. Count it, then pass the real response
        # through untouched so CORS handling is unaffected.
        if request.method in ("OPTIONS", "HEAD"):
            response = await call_next(request)
            if request.method == "OPTIONS" and response.status_code >= 500:
                normalized = _normalize_path(path)
                preflight_errors_counter.add(
                    1, {"status": str(response.status_code), "path": normalized}
                )
                logger.warning(
                    "CORS preflight returned %s — browser-only failure signature",
                    response.status_code,
                    extra={
                        "path": path,
                        "normalized_path": normalized,
                        "status_code": response.status_code,
                    },
                )
            return response

        # ── Classify ─────────────────────────────────────────────────
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")
        has_turnstile = bool(request.headers.get("X-Turnstile-Token"))
        allowed_origins = _get_allowed_origins()

        origin_match = _origin_matches(origin, allowed_origins) or _origin_matches(
            referer, allowed_origins
        )

        if origin_match:
            source = "official"
            client_type = "web"
        elif has_turnstile:
            source = "official"
            client_type = "app"
        else:
            source = "unofficial"
            client_type = "unknown"

        # ── Record metric ────────────────────────────────────────────
        normalized_path = _normalize_path(path)
        ua_class = _classify_user_agent(request.headers.get("user-agent", ""))

        api_access_counter.add(
            1,
            {
                "source": source,
                "method": request.method,
                "path": normalized_path,
                "client_type": client_type,
            },
        )

        # ── Log unofficial access (throttled) ────────────────────────
        if source == "unofficial":
            client_ip = _get_client_ip(request)
            throttle_key = f"{client_ip}:{normalized_path}"
            if not _should_throttle(throttle_key):
                logger.warning(
                    "Unofficial API access detected",
                    extra={
                        "path": path,
                        "normalized_path": normalized_path,
                        "method": request.method,
                        "client_ip": client_ip,
                        "user_agent": request.headers.get("user-agent", ""),
                        "ua_class": ua_class,
                    },
                )

        return await call_next(request)
