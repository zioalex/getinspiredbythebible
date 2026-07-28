"""
Security tests for anti-abuse protection.

Tests:
- Input validation (length, whitespace, format)
- Rate limiting (per-IP, per-session, lifetime)
- Content filtering (profanity, spam, URLs)
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from chat.service import ChatRequest
from config import settings
from main import app
from utils.rate_limiter import RateLimiter
from utils.security import ContentFilter, ViolationType


class TestInputValidation:
    """Tests for ChatRequest input validation."""

    def test_valid_message(self):
        """Accept valid message within length limit."""
        request = ChatRequest(message="How can I find peace?")
        assert request.message == "How can I find peace?"

    def test_message_whitespace_stripped(self):
        """Whitespace should be stripped from message."""
        request = ChatRequest(message="  Hello world  ")
        assert request.message == "Hello world"

    def test_empty_message_rejected(self):
        """Empty message should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="")
        assert "min_length" in str(exc_info.value).lower() or "at least 1" in str(exc_info.value)

    def test_whitespace_only_message_rejected(self):
        """Whitespace-only message should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="   ")
        assert "empty" in str(exc_info.value).lower() or "whitespace" in str(exc_info.value).lower()

    def test_message_too_long_rejected(self):
        """Message exceeding max length should be rejected."""
        limit = settings.max_message_length
        long_message = "a" * (limit + 1)
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message=long_message)
        assert "max_length" in str(exc_info.value).lower() or str(limit) in str(exc_info.value)

    def test_message_at_max_length_accepted(self):
        """Message at exactly max length should be accepted."""
        limit = settings.max_message_length
        exact_message = "a" * limit
        request = ChatRequest(message=exact_message)
        assert len(request.message) == limit

    def test_max_message_length_is_500(self):
        """BITB-075: the configured default limit must be 500, not the old
        300 (web/Android) or 200 (production terraform) values that used to
        disagree with each other."""
        assert settings.max_message_length == 500

    def test_500_char_message_accepted(self):
        """BITB-075: a 500-character message must be accepted end-to-end."""
        message_500 = "a" * 500
        request = ChatRequest(message=message_500)
        assert len(request.message) == 500

    def test_501_char_message_rejected_with_422(self):
        """BITB-075: a message one character over the 500 limit must be
        rejected by the API with HTTP 422 (not just at the Pydantic-model
        level). Uses varied, realistic text (not a repeated character) so the
        content filter's spam check doesn't mask the length rejection."""
        client = TestClient(app)
        sentence = "This is a realistic sentence about finding peace and hope. "
        long_message = (sentence * ((501 // len(sentence)) + 1))[:501]
        assert len(long_message) == 501

        response = client.post(
            "/api/v1/chat",
            json={"message": long_message},
        )
        assert response.status_code == 422

    def test_valid_session_id(self):
        """Accept valid session ID format."""
        request = ChatRequest(message="Hello", session_id="abc123-xyz_456")
        assert request.session_id == "abc123-xyz_456"

    def test_invalid_session_id_rejected(self):
        """Session ID with invalid characters should be rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="Hello", session_id="abc!@#$%")
        assert "pattern" in str(exc_info.value).lower() or "session" in str(exc_info.value).lower()

    def test_session_id_too_long_rejected(self):
        """Session ID exceeding max length should be rejected."""
        long_id = "a" * 65  # Max is 64
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest(message="Hello", session_id=long_id)
        assert "max_length" in str(exc_info.value).lower() or "64" in str(exc_info.value)


class TestRateLimiter:
    """Tests for rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        """Requests under the limit should be allowed."""
        limiter = RateLimiter(backend="memory", requests_per_minute=5)
        for _ in range(5):
            allowed, reason = await limiter.check_rate_limit("192.168.1.1")
            assert allowed is True
            assert reason is None

    @pytest.mark.asyncio
    async def test_blocks_requests_over_ip_limit(self):
        """Requests over the IP limit should be blocked."""
        limiter = RateLimiter(backend="memory", requests_per_minute=3)

        # First 3 should pass
        for _ in range(3):
            allowed, _ = await limiter.check_rate_limit("192.168.1.1")
            assert allowed is True

        # 4th should fail
        allowed, reason = await limiter.check_rate_limit("192.168.1.1")
        assert allowed is False
        assert "IP" in reason

    @pytest.mark.asyncio
    async def test_different_ips_have_separate_limits(self):
        """Different IPs should have separate rate limits."""
        limiter = RateLimiter(backend="memory", requests_per_minute=2)

        # Max out first IP
        await limiter.check_rate_limit("192.168.1.1")
        await limiter.check_rate_limit("192.168.1.1")
        allowed, _ = await limiter.check_rate_limit("192.168.1.1")
        assert allowed is False

        # Second IP should still be allowed
        allowed, _ = await limiter.check_rate_limit("192.168.1.2")
        assert allowed is True

    @pytest.mark.asyncio
    async def test_session_rate_limit(self):
        """Per-session rate limit should be enforced."""
        limiter = RateLimiter(
            backend="memory",
            requests_per_minute=10,  # High IP limit
            session_requests_per_minute=2,  # Low session limit
        )

        # Session should hit limit before IP
        await limiter.check_rate_limit("192.168.1.1", "session-1")
        await limiter.check_rate_limit("192.168.1.1", "session-1")
        allowed, reason = await limiter.check_rate_limit("192.168.1.1", "session-1")
        assert allowed is False
        assert "session" in reason.lower()

    @pytest.mark.asyncio
    async def test_session_lifetime_limit(self):
        """Session lifetime limit should be enforced."""
        limiter = RateLimiter(
            backend="memory",
            requests_per_minute=100,
            session_requests_per_minute=100,
            session_max_requests=5,  # Low lifetime limit
        )

        # Use up lifetime limit
        for _ in range(5):
            allowed, _ = await limiter.check_rate_limit("192.168.1.1", "session-1")
            assert allowed is True

        # Should be blocked by lifetime limit
        allowed, reason = await limiter.check_rate_limit("192.168.1.1", "session-1")
        assert allowed is False
        assert "lifetime" in reason.lower()

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Stats should reflect tracked IPs and sessions."""
        limiter = RateLimiter(backend="memory")
        await limiter.check_rate_limit("192.168.1.1")
        await limiter.check_rate_limit("192.168.1.2", "session-1")

        stats = limiter.get_stats()
        assert stats["tracked_ips"] == 2
        assert stats["tracked_sessions"] == 1


class TestContentFilter:
    """Tests for content filtering."""

    def test_allows_clean_content(self):
        """Clean content should be allowed."""
        filter = ContentFilter()
        allowed, violation, reason = filter.check("How can I find peace in difficult times?")
        assert allowed is True
        assert violation is None

    def test_blocks_profanity(self):
        """Profanity should be blocked."""
        filter = ContentFilter()
        with patch("utils.security.settings") as mock_settings:
            mock_settings.content_filter_enabled = True
            mock_settings.content_filter_block_profanity = True
            mock_settings.content_filter_block_spam = False
            mock_settings.content_filter_max_urls = 1

            allowed, violation, reason = filter.check("This is a damn test")
            assert allowed is False
            assert violation == ViolationType.PROFANITY
            assert "inappropriate" in reason.lower()

    def test_blocks_urls(self):
        """URLs should be blocked when configured."""
        filter = ContentFilter()
        with patch("utils.security.settings") as mock_settings:
            mock_settings.content_filter_enabled = True
            mock_settings.content_filter_block_profanity = False
            mock_settings.content_filter_max_urls = 0

            # Test various URL formats
            test_urls = [
                "Check out https://example.com",
                "Visit www.example.com for more",
                "Go to http://test.org",
            ]
            for msg in test_urls:
                allowed, violation, _ = filter.check(msg)
                assert allowed is False, f"Should block: {msg}"
                assert violation == ViolationType.URL_DETECTED

    @pytest.mark.parametrize(
        "message",
        [
            # The exact reported false positive: a German Bible reference written
            # "<chapter>.<Book>" with no space looks like the domain "1.timotheus".
            "1.Timotheus 2,1-2 ist eine der Bibel-Stellen in der wir zum "
            "Grundsätzlichsten aufgefordert sind",
            "2.Mose 20",
            "1.Korinther 13",
            "3.Johannes 4",
            "Lies 1.Petrus 5,7",
        ],
    )
    def test_allows_bible_references(self, message):
        """German Bible references must not be mistaken for URLs.

        Regression for the reported false positive where "1.Timotheus 2,1-2 ..."
        was rejected with HTTP 400 content_blocked because "1.Timotheus" matched
        the bare-domain URL pattern.
        """
        filter = ContentFilter()
        with patch("utils.security.settings") as mock_settings:
            mock_settings.content_filter_enabled = True
            mock_settings.content_filter_block_profanity = False
            mock_settings.content_filter_block_spam = False
            mock_settings.content_filter_max_urls = 0

            allowed, violation, _ = filter.check(message)
            assert allowed is True, f"Should NOT block Bible reference: {message!r}"
            assert violation is None

    @pytest.mark.parametrize(
        "message",
        [
            # Scheme / www URLs (first alternative) — unchanged behavior.
            "Check out https://example.com",
            "Visit www.example.com for more",
            "Go to http://test.org",
            # Bare domains (second alternative) — still caught via a real TLD.
            "buy cheap meds at cheapmeds.ru",
            "go to spam.com now",
        ],
    )
    def test_blocks_real_urls_and_bare_domains(self, message):
        """Genuine URLs and bare domains must still be blocked after the fix."""
        filter = ContentFilter()
        with patch("utils.security.settings") as mock_settings:
            mock_settings.content_filter_enabled = True
            mock_settings.content_filter_block_profanity = False
            mock_settings.content_filter_block_spam = False
            mock_settings.content_filter_max_urls = 0

            allowed, violation, _ = filter.check(message)
            assert allowed is False, f"Should block URL/domain: {message!r}"
            assert violation == ViolationType.URL_DETECTED

    def test_blocks_repeated_chars(self):
        """Excessive repeated characters should be blocked."""
        filter = ContentFilter()
        with patch("utils.security.settings") as mock_settings:
            mock_settings.content_filter_enabled = True
            mock_settings.content_filter_block_profanity = False
            mock_settings.content_filter_block_spam = True
            mock_settings.content_filter_max_repeated_chars = 5
            mock_settings.content_filter_max_urls = 1

            # 6 or more repeated chars should be blocked
            allowed, violation, _ = filter.check("Hellooooooo there")
            assert allowed is False
            assert violation == ViolationType.REPEATED_CHARS

    def test_allows_reasonable_repetition(self):
        """Reasonable character repetition should be allowed."""
        filter = ContentFilter()
        with patch("utils.security.settings") as mock_settings:
            mock_settings.content_filter_enabled = True
            mock_settings.content_filter_block_profanity = False
            mock_settings.content_filter_block_spam = True
            mock_settings.content_filter_max_repeated_chars = 5
            mock_settings.content_filter_max_urls = 1

            # 5 or fewer repeated chars should be allowed
            allowed, _, _ = filter.check("Helloo there")
            assert allowed is True

    @pytest.mark.parametrize(
        "message",
        [
            # The exact message from the reported false positive (ellipsis "......").
            "mi manca tanto la....... Anna la mia Amica",
            # Bare punctuation runs that natural messages contain.
            ".......",
            "!!!!!!!!",
            "???????",
            "--------",
            # Accented (Unicode) text with an ellipsis must still be allowed.
            "perché........ non lo so",
        ],
    )
    def test_allows_repeated_punctuation(self, message):
        """Repeated punctuation/whitespace (ellipses, !!!, ???) must not be spam.

        Regression for the reported false positive where "mi manca tanto la......."
        was rejected with HTTP 400 content_blocked because of the trailing dots.
        """
        filter = ContentFilter()
        with patch("utils.security.settings") as mock_settings:
            mock_settings.content_filter_enabled = True
            mock_settings.content_filter_block_profanity = False
            mock_settings.content_filter_block_spam = True
            mock_settings.content_filter_max_repeated_chars = 5
            mock_settings.content_filter_max_urls = 1

            allowed, violation, _ = filter.check(message)
            assert allowed is True, f"Should NOT block punctuation: {message!r}"
            assert violation is None

    @pytest.mark.parametrize(
        "message",
        [
            "Hellooooooo there",  # existing case — stretched word
            "soooooooo",
            "aaaaaaaa",
            "1111111",  # repeated digits are word chars, still spammy
        ],
    )
    def test_blocks_stretched_words(self, message):
        """Stretched *word* characters (letters/digits) must still be blocked."""
        filter = ContentFilter()
        with patch("utils.security.settings") as mock_settings:
            mock_settings.content_filter_enabled = True
            mock_settings.content_filter_block_profanity = False
            mock_settings.content_filter_block_spam = True
            mock_settings.content_filter_max_repeated_chars = 5
            mock_settings.content_filter_max_urls = 1

            allowed, violation, _ = filter.check(message)
            assert allowed is False, f"Should block stretched word: {message!r}"
            assert violation == ViolationType.REPEATED_CHARS

    def test_disabled_filter_allows_all(self):
        """Disabled filter should allow all content."""
        filter = ContentFilter()
        with patch("utils.security.settings") as mock_settings:
            mock_settings.content_filter_enabled = False

            allowed, _, _ = filter.check("Any content including bad words and https://urls.com")
            assert allowed is True


class TestSecurityIntegration:
    """Integration tests for security features with the API."""

    def test_message_too_long_returns_422(self):
        """API should return 422 for messages over limit."""
        client = TestClient(app)
        # Use realistic text to avoid content filter triggering on repeated chars.
        # Repeat enough times to exceed the configured limit (BITB-075: 500),
        # rather than a fixed repeat count that would stop exceeding the limit
        # whenever the limit is raised.
        phrase = "This is a test message that is too long "
        repeats = (settings.max_message_length // len(phrase)) + 2
        long_message = phrase * repeats

        response = client.post("/api/v1/chat", json={"message": long_message})
        assert response.status_code == 422

    def test_empty_message_returns_422(self):
        """API should return 422 for empty messages."""
        client = TestClient(app)

        response = client.post("/api/v1/chat", json={"message": ""})
        assert response.status_code == 422

    def test_invalid_session_id_returns_422(self):
        """API should return 422 for invalid session ID format."""
        client = TestClient(app)

        response = client.post(
            "/api/v1/chat",
            json={"message": "Hello", "session_id": "invalid!@#"},
        )
        assert response.status_code == 422


class _FakeRequest:
    """Minimal stand-in for a Starlette Request for the content-filter dependency."""

    def __init__(self, body: dict):
        self.method = "POST"
        self.headers: dict[str, str] = {}
        self.client = None
        self._body = body

    async def json(self):
        return self._body


class TestContentFilterDependency:
    """End-to-end tests for the check_content_filter FastAPI dependency.

    Exercises the real HTTP 400 `content_blocked` path that rejected the reported
    message, without invoking the LLM.
    """

    @pytest.mark.asyncio
    async def test_ellipsis_message_not_blocked(self):
        """The reported ellipsis message must pass the content-filter dependency."""
        from utils.security import check_content_filter

        request = _FakeRequest({"message": "mi manca tanto la....... Anna la mia Amica"})
        # Must NOT raise HTTPException(400, content_blocked).
        await check_content_filter(request)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_bible_reference_not_blocked(self):
        """The reported German Bible-reference message must pass the dependency."""
        from utils.security import check_content_filter

        request = _FakeRequest(
            {
                "message": "1.Timotheus 2,1-2 ist eine der Bibel-Stellen in der wir "
                "zum Grundsätzlichsten, was wir tun sollen, aufgefordert sind. "
                "Gib mir alle Bibel-Stellen die in ähnlicher Weise reden"
            }
        )
        # Must NOT raise HTTPException(400, content_blocked).
        await check_content_filter(request)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_stretched_word_still_blocked(self):
        """A stretched word still trips the dependency with HTTP 400 content_blocked."""
        from fastapi import HTTPException

        from utils.security import check_content_filter

        request = _FakeRequest({"message": "Hellooooooo there"})
        with pytest.raises(HTTPException) as exc_info:
            await check_content_filter(request)  # type: ignore[arg-type]
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "content_blocked"
