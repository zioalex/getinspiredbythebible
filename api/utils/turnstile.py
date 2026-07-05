"""
Cloudflare Turnstile verification for bot protection.

Turnstile is an invisible CAPTCHA alternative that runs silently in the browser.
It provides bot protection without user friction.

Setup:
1. Create a Turnstile widget at https://dash.cloudflare.com/?to=/:account/turnstile
2. Set TURNSTILE_ENABLED=true in your .env
3. Set TURNSTILE_SECRET_KEY to your server-side secret
4. Set TURNSTILE_SITE_KEY to your client-side key (for frontend)

Test keys for development:
- Secret: 1x0000000000000000000000000000000AA (always passes)
- Secret: 2x0000000000000000000000000000000AA (always fails)
- Secret: 3x0000000000000000000000000000000AA (forces interactive challenge)
- Site key: 1x00000000000000000000AA (always passes, invisible)
"""

import logging
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request

from config import settings
from utils.circuit_breaker import CircuitBreaker
from utils.metrics import turnstile_fail_open_counter

from .monitor_probe import is_monitor_probe

logger = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def _classify_transient_error(e: Exception) -> str:
    """Categorize a siteverify transient failure for the fail-open metric label."""
    if isinstance(e, httpx.TimeoutException):
        return "timeout"
    if isinstance(e, httpx.HTTPStatusError):
        status = getattr(e.response, "status_code", None)
        return f"http_{status}" if status else "http_error"
    if isinstance(e, httpx.HTTPError):
        return type(e).__name__.lower()
    return type(e).__name__.lower()


class TurnstileVerifier:
    """Verifies Cloudflare Turnstile tokens."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self._client: httpx.AsyncClient | None = None
        # Trip after 5 consecutive siteverify failures; cooldown 30s. While
        # open, verify() fails CLOSED without hitting the network. Isolated
        # blips (breaker still closed) fail OPEN but emit
        # turnstile_fail_open_counter so the bypass is observable/alertable.
        self._breaker = CircuitBreaker(
            name="turnstile",
            failure_threshold=5,
            cooldown_seconds=30.0,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def verify(self, token: str, remote_ip: str | None = None) -> tuple[bool, str | None]:
        """
        Verify a Turnstile token with Cloudflare.

        Args:
            token: The turnstile response token from the frontend
            remote_ip: Optional client IP for additional validation

        Returns:
            Tuple of (success, error_message)
        """
        if not token:
            return False, "Missing Turnstile token"

        # Breaker open → siteverify is persistently failing → fail CLOSED
        # without re-hitting the network (no per-request timeout paid).
        if self._breaker.is_open():
            logger.error("Turnstile siteverify circuit open — failing closed")
            return False, "Verification temporarily unavailable"

        try:
            client = await self._get_client()

            payload = {
                "secret": self.secret_key,
                "response": token,
            }
            if remote_ip:
                payload["remoteip"] = remote_ip

            response = await client.post(TURNSTILE_VERIFY_URL, data=payload)
            response.raise_for_status()

            result = response.json()

            # siteverify answered → endpoint healthy regardless of token verdict.
            self._breaker.record_success()

            if result.get("success"):
                logger.debug(
                    "Turnstile verification successful",
                    extra={"hostname": result.get("hostname")},
                )
                return True, None
            else:
                error_codes = result.get("error-codes", [])
                error_msg = ", ".join(error_codes) if error_codes else "Verification failed"
                logger.warning(
                    "Turnstile verification failed",
                    extra={"error_codes": error_codes, "remote_ip": remote_ip},
                )
                return False, error_msg  # explicit rejection → fail CLOSED

        except Exception as e:
            return self._handle_transient_error(e, remote_ip)

    def _handle_transient_error(
        self, e: Exception, remote_ip: str | None
    ) -> tuple[bool, str | None]:
        """Handle a siteverify network/transport failure: record it against the
        breaker, then fail open (isolated blip) or closed (persistent outage)."""
        reason = _classify_transient_error(e)
        self._breaker.record_failure()
        if self._breaker.is_open():
            # This failure tripped the breaker (or it re-opened) → persistent
            # outage → fail CLOSED.
            logger.error(
                "Turnstile siteverify persistently failing (%s) — failing closed",
                reason,
                extra={"error": str(e), "remote_ip": remote_ip},
            )
            return False, "Verification temporarily unavailable"
        # Isolated blip, breaker still closed → fail OPEN, but make it observable.
        turnstile_fail_open_counter.add(1, {"reason": reason})
        logger.warning(
            "Turnstile siteverify %s — failing open (breaker closed)",
            reason,
            extra={"error": str(e), "remote_ip": remote_ip},
        )
        return True, None

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Global verifier instance
_verifier: TurnstileVerifier | None = None


def get_turnstile_verifier() -> TurnstileVerifier | None:
    """Get or create the global Turnstile verifier instance."""
    global _verifier
    if not settings.turnstile_enabled or not settings.turnstile_secret_key:
        return None
    if _verifier is None:
        _verifier = TurnstileVerifier(settings.turnstile_secret_key)
    return _verifier


def _should_skip_path(path: str) -> bool:
    """Check if the path should skip Turnstile verification.

    Uses prefix matching so that e.g. "/health" also covers
    "/health/live" and "/health/ready".
    """
    skip_paths = [p.strip() for p in settings.turnstile_skip_paths.split(",") if p.strip()]
    return any(path == sp or path.startswith(sp + "/") for sp in skip_paths)


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check CF-Connecting-IP (Cloudflare)
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return str(cf_ip).strip()

    # Check X-Forwarded-For header
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return str(forwarded).split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return str(real_ip).strip()

    # Fallback to direct client IP
    if request.client:
        return str(request.client.host)

    return "unknown"


async def require_turnstile(request: Request) -> None:
    """
    FastAPI dependency to require Turnstile verification.

    The frontend must send the token in the X-Turnstile-Token header.

    Raises HTTPException 403 if verification fails.
    """
    # Skip if Turnstile is disabled
    if not settings.turnstile_enabled:
        return

    # Skip certain paths (health probes, docs, root)
    if _should_skip_path(request.url.path):
        return

    # Skip CORS preflight and HEAD requests (harmless, no side effects)
    if request.method in ("HEAD", "OPTIONS"):
        return

    # Authorized synthetic monitor probe — bypass.
    if is_monitor_probe(request):
        logger.info(
            "Monitor probe — bypassing Turnstile",
            extra={"path": request.url.path},
        )
        return

    verifier = get_turnstile_verifier()
    if not verifier:
        return  # No verifier configured

    # Get token from header
    token = request.headers.get("X-Turnstile-Token")

    if not token:
        logger.warning(
            "Missing Turnstile token",
            extra={"path": request.url.path, "ip": _get_client_ip(request)},
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Bot verification required",
                "message": "Please complete the security check",
                "code": "TURNSTILE_REQUIRED",
            },
        )

    # Verify the token
    client_ip = _get_client_ip(request)
    success, error = await verifier.verify(token, client_ip)

    if not success:
        logger.warning(
            "Turnstile verification failed",
            extra={"path": request.url.path, "ip": client_ip, "error": error},
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Bot verification failed",
                "message": error or "Verification failed",
                "code": "TURNSTILE_FAILED",
            },
        )


# Type alias for dependency injection
TurnstileDep = Annotated[None, Depends(require_turnstile)]
