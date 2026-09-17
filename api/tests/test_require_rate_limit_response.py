"""
BITB-118: the actual HTTP 429 response shape of `require_rate_limit()`.

`test_rate_limiter.py`, `test_security.py`, and `test_utils_coverage.py` all
test `RateLimiter.check_rate_limit()` directly and assert on the returned
`(allowed, reason)` tuple, but none of them exercise the FastAPI dependency
that turns a denial into an `HTTPException` — so a change to that response's
shape (e.g. adding the numeric `limit` field for the session-lifetime case)
had no test to catch a regression. This file closes that gap.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings  # noqa: E402
from utils.security import require_rate_limit  # noqa: E402


class _FakeRequest:
    """Minimal stand-in for a Starlette Request, matching the one already
    used for `check_content_filter` in test_security.py."""

    def __init__(self, body: dict):
        self.method = "POST"
        self.headers: dict[str, str] = {}
        self.client = None
        self._body = body

    async def json(self):
        return self._body


def _stub_rate_limiter(allowed: bool, reason: str):
    limiter = AsyncMock()
    limiter.check_rate_limit = AsyncMock(return_value=(allowed, reason))
    return limiter


class TestRequireRateLimitResponse:
    """Asserts the exact 429 `detail` dict shape for each denial reason."""

    @pytest.mark.asyncio
    async def test_session_lifetime_limit_includes_numeric_limit(self):
        request = _FakeRequest({"session_id": "abc123"})
        with (
            patch("utils.security.settings.rate_limit_enabled", True),
            patch(
                "utils.security.get_rate_limiter",
                return_value=_stub_rate_limiter(False, "Session lifetime limit exceeded"),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await require_rate_limit(request)  # type: ignore[arg-type]

        assert exc_info.value.status_code == 429
        detail = exc_info.value.detail
        assert detail["error"] == "session_lifetime_limit"
        assert detail["retry_after"] is None
        assert detail["limit"] == settings.rate_limit_session_max_requests

    @pytest.mark.asyncio
    async def test_per_minute_session_limit_has_no_numeric_limit(self):
        """Guards against the lifetime-only `limit` field leaking into the
        generic per-minute/session branch, which has a different meaning
        (a rolling window, not a lifetime cap)."""
        request = _FakeRequest({"session_id": "abc123"})
        with (
            patch("utils.security.settings.rate_limit_enabled", True),
            patch(
                "utils.security.get_rate_limiter",
                return_value=_stub_rate_limiter(False, "Session rate limit exceeded"),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await require_rate_limit(request)  # type: ignore[arg-type]

        assert exc_info.value.status_code == 429
        detail = exc_info.value.detail
        assert detail == {"error": "Rate limit exceeded", "retry_after": 60}

    @pytest.mark.asyncio
    async def test_ip_limit_has_no_numeric_limit(self):
        request = _FakeRequest({"session_id": "abc123"})
        with (
            patch("utils.security.settings.rate_limit_enabled", True),
            patch(
                "utils.security.get_rate_limiter",
                return_value=_stub_rate_limiter(False, "IP rate limit exceeded"),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await require_rate_limit(request)  # type: ignore[arg-type]

        assert exc_info.value.status_code == 429
        detail = exc_info.value.detail
        assert detail == {"error": "Rate limit exceeded", "retry_after": 60}

    @pytest.mark.asyncio
    async def test_rate_limiting_disabled_short_circuits(self):
        request = _FakeRequest({"session_id": "abc123"})
        with (
            patch("utils.security.settings.rate_limit_enabled", False),
            patch(
                "utils.security.get_rate_limiter",
                return_value=_stub_rate_limiter(False, "Session lifetime limit exceeded"),
            ) as mock_get_limiter,
        ):
            result = await require_rate_limit(request)  # type: ignore[arg-type]

        assert result is None
        mock_get_limiter.assert_not_called()
