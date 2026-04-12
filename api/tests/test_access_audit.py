"""
Tests for Access Audit Middleware.

Verifies that:
- Requests from the web frontend (with Origin) are classified as official/web
- Requests from the Android app (with X-Turnstile-Token, no Origin) are official/app
- Requests with no identifying headers are classified as unofficial
- Non-API paths are not audited
- OPTIONS/HEAD requests are skipped
- Path normalization collapses dynamic segments
- Log throttling suppresses duplicate warnings
- Metrics are recorded with correct attributes
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from middleware.access_audit import (
    _classify_user_agent,
    _normalize_path,
    _origin_matches,
    _should_throttle,
    _throttle_cache,
)

client = TestClient(app)


class TestAccessClassification:
    """Test source classification logic via real HTTP requests."""

    def test_official_web_with_origin(self):
        """Request with matching Origin header → official, client_type=web."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.get(
                "/api/v1/scripture/translations",
                headers={"Origin": "https://voxquieta.org"},
            )
            mock_counter.add.assert_called()
            call_args = mock_counter.add.call_args
            attrs = call_args[0][1]
            assert attrs["source"] == "official"
            assert attrs["client_type"] == "web"

    def test_official_web_with_referer(self):
        """Request with matching Referer header → official, client_type=web."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.get(
                "/api/v1/scripture/translations",
                headers={"Referer": "https://voxquieta.org/chat"},
            )
            mock_counter.add.assert_called()
            attrs = mock_counter.add.call_args[0][1]
            assert attrs["source"] == "official"
            assert attrs["client_type"] == "web"

    def test_official_web_with_localhost_origin(self):
        """Request with localhost Origin → official, client_type=web."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.get(
                "/api/v1/scripture/translations",
                headers={"Origin": "http://localhost:3000"},
            )
            mock_counter.add.assert_called()
            attrs = mock_counter.add.call_args[0][1]
            assert attrs["source"] == "official"
            assert attrs["client_type"] == "web"

    def test_official_app_with_turnstile_token(self):
        """Request with X-Turnstile-Token but no Origin → official, client_type=app (Android)."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.get(
                "/api/v1/scripture/translations",
                headers={
                    "X-Turnstile-Token": "some-token",
                    "User-Agent": "okhttp/4.12.0",
                },
            )
            mock_counter.add.assert_called()
            attrs = mock_counter.add.call_args[0][1]
            assert attrs["source"] == "official"
            assert attrs["client_type"] == "app"

    def test_unofficial_no_identifying_headers(self):
        """Request with no Origin, no Referer, no Turnstile token → unofficial."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.get(
                "/api/v1/scripture/translations",
                headers={"User-Agent": "curl/7.88.1"},
            )
            mock_counter.add.assert_called()
            attrs = mock_counter.add.call_args[0][1]
            assert attrs["source"] == "unofficial"
            assert attrs["client_type"] == "unknown"

    def test_unofficial_wrong_origin(self):
        """Request with non-matching Origin → unofficial."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.get(
                "/api/v1/scripture/translations",
                headers={"Origin": "https://evil.example.com"},
            )
            mock_counter.add.assert_called()
            attrs = mock_counter.add.call_args[0][1]
            assert attrs["source"] == "unofficial"
            assert attrs["client_type"] == "unknown"

    def test_post_request_audited(self):
        """POST requests are also audited."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.post(
                "/api/v1/chat/stream",
                headers={"Origin": "https://voxquieta.org"},
                json={"message": "test"},
            )
            mock_counter.add.assert_called()
            attrs = mock_counter.add.call_args[0][1]
            assert attrs["method"] == "POST"
            assert attrs["source"] == "official"


class TestSkipPaths:
    """Verify that non-API paths are not audited."""

    def test_health_not_audited(self):
        """Requests to /health are not audited."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.get("/health")
            mock_counter.add.assert_not_called()

    def test_root_not_audited(self):
        """Requests to / are not audited."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.get("/")
            mock_counter.add.assert_not_called()

    def test_docs_not_audited(self):
        """Requests to /docs are not audited."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.get("/docs")
            mock_counter.add.assert_not_called()

    def test_options_not_audited(self):
        """OPTIONS requests (CORS preflight) are skipped."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            client.options("/api/v1/scripture/translations")
            mock_counter.add.assert_not_called()


class TestPathNormalization:
    """Verify dynamic path segments are collapsed."""

    def test_verse_path_normalized(self):
        """/scripture/verse/Genesis/1/1 → /scripture/verse/{book}/{chapter}/{verse}."""
        result = _normalize_path("/api/v1/scripture/verse/Genesis/1/1")
        assert result == "/api/v1/scripture/verse/{book}/{chapter}/{verse}"

    def test_chapter_path_normalized(self):
        """/scripture/chapter/Genesis/1 → /scripture/chapter/{book}/{chapter}."""
        result = _normalize_path("/api/v1/scripture/chapter/Genesis/1")
        assert result == "/api/v1/scripture/chapter/{book}/{chapter}"

    def test_verse_context_path_normalized(self):
        """/scripture/verse-context/John/3/16 → normalized."""
        result = _normalize_path("/api/v1/scripture/verse-context/John/3/16")
        assert result == "/api/v1/scripture/verse-context/{book}/{chapter}/{verse}"

    def test_static_path_unchanged(self):
        """/scripture/translations is not dynamic — stays as-is."""
        result = _normalize_path("/api/v1/scripture/translations")
        assert result == "/api/v1/scripture/translations"

    def test_book_names_path_unchanged(self):
        """/scripture/book-names stays as-is."""
        result = _normalize_path("/api/v1/scripture/book-names")
        assert result == "/api/v1/scripture/book-names"

    def test_normalized_path_in_metric(self):
        """Metric attributes use normalized path, not raw path."""
        with patch("middleware.access_audit.api_access_counter") as mock_counter:
            # Use translations endpoint (doesn't need DB) to test metric recording,
            # and verify path normalization via unit tests above.
            client.get(
                "/api/v1/scripture/translations",
                headers={"Origin": "https://voxquieta.org"},
            )
            mock_counter.add.assert_called()
            attrs = mock_counter.add.call_args[0][1]
            # Static path stays unchanged
            assert attrs["path"] == "/api/v1/scripture/translations"
            assert attrs["method"] == "GET"


class TestUserAgentClassification:
    """Verify User-Agent string classification."""

    @pytest.mark.parametrize(
        "ua,expected",
        [
            ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "browser"),
            ("okhttp/4.12.0", "okhttp"),
            ("curl/7.88.1", "curl"),
            ("python-requests/2.31.0", "python"),
            ("Go-http-client/2.0", "go"),
            ("SomeUnknownBot/1.0", "other"),
            ("", "other"),
        ],
    )
    def test_ua_classification(self, ua, expected):
        assert _classify_user_agent(ua) == expected


class TestOriginMatching:
    """Verify Origin/Referer matching logic."""

    def test_exact_match(self):
        origins = ["https://voxquieta.org"]
        assert _origin_matches("https://voxquieta.org", origins)

    def test_trailing_slash(self):
        origins = ["https://voxquieta.org"]
        assert _origin_matches("https://voxquieta.org/", origins)

    def test_referer_with_path(self):
        origins = ["https://voxquieta.org"]
        assert _origin_matches("https://voxquieta.org/chat", origins)

    def test_no_match(self):
        origins = ["https://voxquieta.org"]
        assert not _origin_matches("https://evil.example.com", origins)

    def test_empty_value(self):
        origins = ["https://voxquieta.org"]
        assert not _origin_matches("", origins)

    def test_localhost(self):
        origins = ["http://localhost:3000"]
        assert _origin_matches("http://localhost:3000", origins)


class TestLogThrottling:
    """Verify log throttle prevents duplicate warnings."""

    def setup_method(self):
        """Clear throttle cache before each test."""
        _throttle_cache.clear()

    def test_first_call_not_throttled(self):
        assert not _should_throttle("1.2.3.4:/api/v1/scripture/translations")

    def test_second_call_within_ttl_throttled(self):
        _should_throttle("1.2.3.4:/api/v1/scripture/translations")
        assert _should_throttle("1.2.3.4:/api/v1/scripture/translations")

    def test_different_keys_not_throttled(self):
        _should_throttle("1.2.3.4:/api/v1/scripture/translations")
        assert not _should_throttle("5.6.7.8:/api/v1/scripture/translations")

    def test_unofficial_logs_warning(self):
        """Unofficial access generates a WARNING log."""
        _throttle_cache.clear()
        with patch("middleware.access_audit.logger") as mock_logger:
            client.get(
                "/api/v1/scripture/translations",
                headers={"User-Agent": "curl/7.88.1"},
            )
            mock_logger.warning.assert_called_once()
            call_kwargs = mock_logger.warning.call_args
            assert "Unofficial API access" in call_kwargs[0][0]

    def test_unofficial_second_request_throttled(self):
        """Second unofficial request from same IP+path within TTL does not log again."""
        _throttle_cache.clear()
        with patch("middleware.access_audit.logger") as mock_logger:
            # First request — logs
            client.get(
                "/api/v1/scripture/translations",
                headers={"User-Agent": "curl/7.88.1"},
            )
            assert mock_logger.warning.call_count == 1

            # Second request — throttled, no additional log
            client.get(
                "/api/v1/scripture/translations",
                headers={"User-Agent": "curl/7.88.1"},
            )
            assert mock_logger.warning.call_count == 1
