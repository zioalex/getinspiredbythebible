"""
Tests for the request-ID SQL comment tagging in scripture.database.

Verifies that:
- Queries issued during a request get a `/* request_id=... */` comment prefix
- No comment is added when there is no active request ID
- A malicious request ID cannot break out of the SQL comment
"""

from middleware.context import REQUEST_ID_CTX_VAR
from scripture.database import _prepend_request_id_comment


class TestPrependRequestIdComment:
    """Test suite for _prepend_request_id_comment."""

    def test_adds_comment_when_request_id_set(self):
        """A statement is prefixed with the active request ID."""
        token = REQUEST_ID_CTX_VAR.set("test-request-123")
        try:
            result = _prepend_request_id_comment("SELECT 1")
            assert result == "/* request_id=test-request-123 */ SELECT 1"
        finally:
            REQUEST_ID_CTX_VAR.reset(token)

    def test_no_comment_when_request_id_unset(self):
        """The statement is returned unchanged when no request ID is active."""
        result = _prepend_request_id_comment("SELECT 1")
        assert result == "SELECT 1"

    def test_no_comment_when_request_id_empty(self):
        """An explicitly empty request ID is treated as absent."""
        token = REQUEST_ID_CTX_VAR.set("")
        try:
            result = _prepend_request_id_comment("SELECT 1")
            assert result == "SELECT 1"
        finally:
            REQUEST_ID_CTX_VAR.reset(token)

    def test_sanitizes_comment_breakout(self):
        """A request ID containing `*/` cannot terminate the comment early."""
        token = REQUEST_ID_CTX_VAR.set("evil*/ DROP TABLE users; --")
        try:
            result = _prepend_request_id_comment("SELECT 1")
            assert "*/" not in result.split(" */ ", 1)[0]
            assert result.startswith("/* request_id=evil DROP TABLE users; -- */ SELECT 1")
        finally:
            REQUEST_ID_CTX_VAR.reset(token)

    def test_sanitizes_newlines(self):
        """Newlines in the request ID cannot inject additional SQL lines."""
        token = REQUEST_ID_CTX_VAR.set("abc\n--comment")
        try:
            result = _prepend_request_id_comment("SELECT 1")
            assert "\n" not in result
            assert result == "/* request_id=abc --comment */ SELECT 1"
        finally:
            REQUEST_ID_CTX_VAR.reset(token)
