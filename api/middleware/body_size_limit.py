"""
Request body size guard (BITB-296).

A pure ASGI middleware (NOT ``BaseHTTPMiddleware``) that rejects any HTTP request whose
body exceeds ``settings.max_request_body_bytes`` with ``413`` and
``{"detail": {"error": "request_too_large"}}``.

- ``Content-Length`` is checked first, so an honest oversized request is rejected without
  reading a single body byte or calling the app.
- Bodies without (or lying about) ``Content-Length`` -- e.g. chunked uploads -- are bounded
  by counting bytes as the app pulls them through ``receive``.
- ``send`` is passed through untouched, so streaming (SSE) responses are never buffered.
"""

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from config import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)

_BODY = json.dumps({"detail": {"error": "request_too_large"}}).encode()


class _BodyTooLargeError(Exception):
    """Raised from the wrapped ``receive`` to abort the app once the cap is exceeded."""


def _declared_length(scope: Scope) -> int | None:
    """Return the parsed Content-Length, or None if absent/malformed."""
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None  # malformed -> fall through to byte counting
    return None


async def _send_413(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(_BODY)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": _BODY})


class _RequestGuard:
    """Per-request state: counts received bytes and tracks the response lifecycle."""

    def __init__(self, scope: Scope, receive: Receive, send: Send, limit: int) -> None:
        self.scope = scope
        self._receive = receive
        self._send = send
        self.limit = limit
        self.received = 0
        self.response_started = False
        self.rejected = False

    async def receive(self) -> Message:
        message = await self._receive()
        if message["type"] != "http.request":
            return message
        self.received += len(message.get("body", b""))
        if self.received <= self.limit:
            return message
        if self.response_started:
            # Too late for a 413; just stop feeding the body.
            return {"type": "http.disconnect"}
        logger.warning(
            "Request body rejected: streamed %d bytes exceeds limit=%d (path=%s)",
            self.received,
            self.limit,
            self.scope.get("path"),
        )
        self.rejected = True
        await _send_413(self._send)
        raise _BodyTooLargeError

    async def send(self, message: Message) -> None:
        if self.rejected:
            return  # 413 already sent; swallow anything the app still emits
        if message["type"] == "http.response.start":
            self.response_started = True
        await self._send(message)


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int | None = None) -> None:
        self.app = app
        self.max_bytes = max_bytes

    def _limit(self) -> int:
        return self.max_bytes if self.max_bytes is not None else settings.max_request_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self._limit()
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            logger.warning(
                "Request body rejected: content-length=%d exceeds limit=%d (path=%s)",
                declared,
                limit,
                scope.get("path"),
            )
            await _send_413(send)
            return

        guard = _RequestGuard(scope, receive, send, limit)
        try:
            await self.app(scope, guard.receive, guard.send)
        except _BodyTooLargeError:
            pass
        except Exception:
            # The app may wrap our exception (e.g. via error handlers); if we already
            # answered 413, don't surface a second failure.
            if not guard.rejected:
                raise


__all__ = ["BodySizeLimitMiddleware"]
