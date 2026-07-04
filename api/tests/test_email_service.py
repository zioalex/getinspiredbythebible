"""
Tests for the email service (SMTP2GO HTTP API).
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestEmailServiceInitialization:
    """Test EmailService initialization."""

    def test_service_initializes_with_settings(self):
        """Test that EmailService reads settings on initialization."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "test@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"

            from utils.email_service import EmailService

            service = EmailService()

            assert service.enabled is True
            assert service.api_key == "test-api-key"  # pragma: allowlist secret
            assert service.sender_email == "test@example.com"
            assert service.sender_name == "Test Sender"


class TestNoSyncHttpxClient:
    """Regression guard for BITB-060: no sync httpx.Client reachable from async code."""

    def test_no_sync_httpx_client_in_api_source(self):
        """No `httpx.Client(` call should exist outside tests/ — it blocks the event loop."""
        from pathlib import Path

        api_root = Path(__file__).parent.parent
        offenders = []
        for path in api_root.rglob("*.py"):
            if "tests" in path.relative_to(api_root).parts:
                continue
            if path.name == "test_email_service.py":
                continue
            text = path.read_text()
            if "httpx.Client(" in text:
                offenders.append(str(path.relative_to(api_root)))

        assert not offenders, (
            f"Found sync httpx.Client( usage reachable from async code: {offenders}. "
            "Use httpx.AsyncClient instead — a sync client call blocks the event loop "
            "(see BITB-060)."
        )


@pytest.mark.asyncio
class TestSendEmail:
    """Test send_email method."""

    async def test_send_email_when_disabled_returns_false(self):
        """Test that send_email returns False when disabled."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = False
            mock_settings.smtp2go_api_key = "test-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "test@example.com"
            mock_settings.smtp2go_sender_name = "Test"

            from utils.email_service import EmailService

            service = EmailService()
            result = await service.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                body_text="Test body",
            )

            assert result is False

    async def test_send_email_when_api_key_missing_returns_false(self):
        """Test that send_email returns False when API key is missing."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = None
            mock_settings.smtp2go_sender_email = "test@example.com"
            mock_settings.smtp2go_sender_name = "Test"

            from utils.email_service import EmailService

            service = EmailService()
            result = await service.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                body_text="Test body",
            )

            assert result is False

    async def test_send_email_successful_api_call(self):
        """Test successful email sending via API."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"succeeded": 1}}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                result = await service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                    body_html="<p>Test body</p>",
                )

                assert result is True
                mock_post.assert_called_once()
                call_args = mock_post.call_args
                payload = call_args[1]["json"]
                assert payload["api_key"] == "test-api-key"  # pragma: allowlist secret
                assert payload["to"] == ["recipient@example.com"]
                assert payload["subject"] == "Test Subject"
                assert payload["text_body"] == "Test body"
                assert payload["html_body"] == "<p>Test body</p>"

    async def test_send_email_with_reply_to(self):
        """Test email sending with reply-to header."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"succeeded": 1}}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                result = await service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                    reply_to="user@example.com",
                )

                assert result is True
                call_args = mock_post.call_args
                payload = call_args[1]["json"]
                assert payload["custom_headers"] == [
                    {"header": "Reply-To", "value": "user@example.com"}
                ]

    async def test_send_email_handles_api_failure(self):
        """Test handling of non-200 API response."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Bad Request"

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                result = await service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                )

                assert result is False

    async def test_send_email_handles_api_success_with_zero_succeeded(self):
        """Test handling when API returns 200 but succeeded=0."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"succeeded": 0, "failed": 1}}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                result = await service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                )

                assert result is False

    async def test_send_email_handles_timeout(self):
        """Test handling of timeout exception."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"

            from utils.email_service import EmailService

            service = EmailService()

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = httpx.TimeoutException("Timeout")

                result = await service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                )

                assert result is False

    async def test_send_email_handles_http_error(self):
        """Test handling of HTTP errors."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"

            from utils.email_service import EmailService

            service = EmailService()

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = httpx.HTTPError("Connection failed")

                result = await service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                )

                assert result is False

    async def test_slow_email_does_not_block_event_loop(self):
        """A slow SMTP2GO response must not stall other concurrent coroutines.

        Regression test for BITB-060: send_email used to run on a synchronous
        httpx.Client, which froze the entire event loop — including in-flight
        chat SSE streams — for as long as the call took.
        """
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"succeeded": 1}}

            async def slow_post(*args, **kwargs):
                await asyncio.sleep(0.3)
                return mock_response

            sentinel_ticks = []

            async def fast_sentinel():
                for _ in range(10):
                    await asyncio.sleep(0.03)
                    sentinel_ticks.append(time.monotonic())

            with patch("httpx.AsyncClient.post", new=slow_post):
                start = time.monotonic()
                _, _ = await asyncio.gather(
                    service.send_email(
                        to_email="recipient@example.com",
                        subject="Test Subject",
                        body_text="Test body",
                    ),
                    fast_sentinel(),
                )
                elapsed = time.monotonic() - start

            # The event loop kept running the sentinel while the "slow" email
            # send was in flight — its ticks are spread across the whole
            # window, not bunched up after the email call returns.
            assert len(sentinel_ticks) == 10
            assert sentinel_ticks[0] - start < 0.3
            assert elapsed < 0.6  # concurrent, not serialized (0.3 + 10*0.03)


@pytest.mark.asyncio
class TestSendContactNotification:
    """Test send_contact_notification method."""

    async def test_send_contact_notification_formats_correctly(self):
        """Test that contact notification is formatted correctly."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"
            mock_settings.contact_notification_email = "admin@example.com"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"succeeded": 1}}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                result = await service.send_contact_notification(
                    subject_type="bug",
                    message="Found a bug in the app",
                    reply_email="user@example.com",
                    user_agent="Mozilla/5.0",
                )

                assert result is True
                call_args = mock_post.call_args
                payload = call_args[1]["json"]
                assert payload["to"] == ["admin@example.com"]
                assert "Bug" in payload["subject"]
                assert "Found a bug" in payload["text_body"]
                assert "user@example.com" in payload["text_body"]

    async def test_send_contact_notification_sets_reply_to(self):
        """Test that reply-to is set when email is provided."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"
            mock_settings.contact_notification_email = "admin@example.com"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"succeeded": 1}}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                await service.send_contact_notification(
                    subject_type="feature",
                    message="Please add dark mode",
                    reply_email="user@example.com",
                )

                call_args = mock_post.call_args
                payload = call_args[1]["json"]
                assert payload["custom_headers"] == [
                    {"header": "Reply-To", "value": "user@example.com"}
                ]


@pytest.mark.asyncio
class TestSendFeedbackNotification:
    """Test send_feedback_notification method."""

    async def test_feedback_notification_only_sends_for_negative(self):
        """Test that notification is only sent for negative feedback."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"
            mock_settings.contact_notification_email = "admin@example.com"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"succeeded": 1}}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                result = await service.send_feedback_notification(
                    rating="negative",
                    comment="Not helpful",
                    user_message="What is the meaning of life?",
                    assistant_response="The meaning of life is...",
                )

                assert result is True
                mock_post.assert_called_once()

    async def test_feedback_notification_renders_positive(self):
        """Positive feedback now renders and sends; gating moved to the route.

        ``send_feedback_notification`` renders whatever rating it is given —
        the decision of *when* to notify (negative, or positive with a comment)
        lives in the route. So a direct call for positive feedback sends.
        """
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"
            mock_settings.contact_notification_email = "admin@example.com"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"succeeded": 1}}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                result = await service.send_feedback_notification(
                    rating="positive",
                    comment="Great answer!",
                    user_message="What is love?",
                    assistant_response="Love is...",
                )

                assert result is True
                mock_post.assert_called_once()
                payload = mock_post.call_args[1]["json"]
                assert "Positive" in payload["subject"]

    async def test_feedback_notification_includes_full_messages(self):
        """Long messages are sent in full — no 500-char truncation."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"
            mock_settings.contact_notification_email = "admin@example.com"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"succeeded": 1}}

            long_message = "A" * 600  # 600 character message

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                await service.send_feedback_notification(
                    rating="negative",
                    comment="Bad response",
                    user_message=long_message,
                    assistant_response=long_message,
                )

                call_args = mock_post.call_args
                payload = call_args[1]["json"]
                # The full 600-char message is present, untruncated.
                assert "A" * 600 in payload["text_body"]
                assert "..." not in payload["text_body"]

    async def test_feedback_notification_handles_no_comment(self):
        """Test feedback notification with no comment."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"
            mock_settings.contact_notification_email = "admin@example.com"

            from utils.email_service import EmailService

            service = EmailService()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": {"succeeded": 1}}

            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_response

                result = await service.send_feedback_notification(
                    rating="negative",
                    comment=None,
                    user_message="Question",
                    assistant_response="Answer",
                )

                assert result is True
                call_args = mock_post.call_args
                payload = call_args[1]["json"]
                assert "No comment provided" in payload["text_body"]
