"""
Tests for the email service (SMTP2GO HTTP API).
"""

import asyncio
import html
import inspect
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from utils.email_service import EXPORT_HOWTO_URL


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


_SECRET_USER_MESSAGE = "SECRET-QUESTION-xyzzy why am I suffering"
_SECRET_REPLY = "SECRET-AI-REPLY-plugh the answer is"
_SECRET_COMMENT = "SECRET-COMMENT-fnord it was unhelpful"
_SECRET_CONTACT_MESSAGE = "SECRET-CONTACT-MESSAGE-quux I need pastoral help"
_SECRET_EMAIL = "secret.sender@example.org"
_FB_UUID = "3f2b1c9e-8a4d-4e0b-9c1a-5d6e7f8a9b0c"
_PROD_URL = (
    "postgresql+asyncpg://bible@bible-app-db-mb0172.postgres.database.azure.com:5432/bibledb"
    "?ssl=require"
)


def _mock_settings(mock_settings, database_url=_PROD_URL):
    mock_settings.smtp2go_enabled = True
    mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
    mock_settings.smtp2go_sender_email = "sender@example.com"
    mock_settings.smtp2go_sender_name = "Test Sender"
    mock_settings.contact_notification_email = "admin@example.com"
    mock_settings.feedback_text_retention_days = 30
    mock_settings.contact_retention_days = 90
    mock_settings.database_url = database_url


async def _send(method, database_url=_PROD_URL, **kwargs):
    """Call ``EmailService.<method>`` and return the SMTP2GO payload it posted."""
    with patch("utils.email_service.settings") as mock_settings:
        _mock_settings(mock_settings, database_url)
        from utils.email_service import EmailService

        service = EmailService()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"succeeded": 1}}
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await getattr(service, method)(**kwargs)
            assert result is True
            mock_post.assert_called_once()
            return mock_post.call_args[1]["json"]


_CREATED = datetime(2026, 11, 16, 9, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
class TestSendContactNotification:
    """send_contact_notification: identifiers only (BITB-329)."""

    async def test_contact_notification_has_identifiers_and_howto(self):
        payload = await _send(
            "send_contact_notification",
            subject_type="bug",
            contact_id=42,
            has_reply_email=True,
            created_at=_CREATED,
        )
        assert payload["to"] == ["admin@example.com"]
        assert "Bug" in payload["subject"]
        for body in (payload["text_body"], payload["html_body"]):
            assert "42" in body
            assert 'make export-feedback ARGS="--contacts --id 42"' in html.unescape(body)
            # created 2026-11-16 + 90 days
            assert "2027-02-14" in body
            assert EXPORT_HOWTO_URL in body
        assert "Reply email left: yes" in payload["text_body"]

    async def test_contact_notification_has_no_reply_to_and_no_text(self):
        payload = await _send(
            "send_contact_notification",
            subject_type="feature",
            contact_id=7,
            has_reply_email=True,
            created_at=_CREATED,
        )
        assert "custom_headers" not in payload
        blob = json.dumps(payload)
        for secret in (_SECRET_CONTACT_MESSAGE, _SECRET_EMAIL, "Mozilla"):
            assert secret not in blob

    async def test_contact_notification_signature_cannot_carry_text(self):
        """The removed parameters are gone: passing them is a TypeError, not a leak."""
        from utils.email_service import EmailService

        params = inspect.signature(EmailService.send_contact_notification).parameters
        assert set(params) == {
            "self",
            "subject_type",
            "contact_id",
            "has_reply_email",
            "created_at",
        }


@pytest.mark.asyncio
class TestSendFeedbackNotification:
    """send_feedback_notification: identifiers only (BITB-329)."""

    async def test_negative_feedback_sends(self):
        payload = await _send(
            "send_feedback_notification",
            rating="negative",
            message_id=_FB_UUID,
            has_comment=True,
            reason="inaccurate",
            created_at=_CREATED,
        )
        assert "Negative" in payload["subject"]

    async def test_positive_feedback_renders_positive(self):
        payload = await _send(
            "send_feedback_notification",
            rating="positive",
            message_id=_FB_UUID,
            has_comment=True,
            created_at=_CREATED,
        )
        assert "Positive" in payload["subject"]

    async def test_feedback_bodies_never_contain_user_text(self):
        payload = await _send(
            "send_feedback_notification",
            rating="negative",
            message_id=_FB_UUID,
            has_comment=True,
            verses_cited=["John 3:16"],
            model_used="claude-test",
            response_time_ms=1234,
            reason="inaccurate",
            created_at=_CREATED,
        )
        assert "custom_headers" not in payload
        blob = json.dumps(payload)
        for secret in (_SECRET_USER_MESSAGE, _SECRET_REPLY, _SECRET_COMMENT):
            assert secret not in blob
        # identifiers kept
        for body in (payload["text_body"], payload["html_body"]):
            assert _FB_UUID in body
            assert "inaccurate" in body
            assert "claude-test" in body
            assert "1234" in body
            assert "John 3:16" in body
        assert "Comment left: yes" in payload["text_body"]

    async def test_feedback_howto_commands_are_exact_for_this_item(self):
        payload = await _send(
            "send_feedback_notification",
            rating="negative",
            message_id=_FB_UUID,
            created_at=_CREATED,
        )
        text = payload["text_body"]
        for line in (
            "make az-pg-add-ip",
            "export PGPASSWORD='<database admin password>'",
            'export DATABASE_URL="$(make -s db-server-url SERVER=bible-app-db-mb0172)"',
            f'make export-feedback ARGS="--message-id {_FB_UUID}"',
            "make az-pg-remove-ip RULE=bible-app-db-mb0172",
        ):
            assert line in text
            assert line in html.unescape(payload["html_body"])
        # created 2026-11-16 + 30 days
        assert "Text available until 2026-12-16" in text
        assert EXPORT_HOWTO_URL in text and EXPORT_HOWTO_URL in payload["html_body"]
        assert "<server>" not in text

    async def test_unknown_server_prints_placeholder_and_hint(self):
        payload = await _send(
            "send_feedback_notification",
            database_url="postgresql://u:p@localhost:5432/db",
            rating="negative",
            message_id=_FB_UUID,
            created_at=_CREATED,
        )
        text = payload["text_body"]
        assert "SERVER=<server>" in text
        assert "RULE=<server>" in text
        assert "make db-server-url" in text and "terraform.tfvars" in text

    async def test_non_uuid_message_id_never_reaches_a_shell_command(self):
        hostile = "x'; rm -rf / #"
        payload = await _send(
            "send_feedback_notification",
            rating="negative",
            message_id=hostile,
            created_at=_CREATED,
        )
        assert 'ARGS="--message-id' not in payload["text_body"]
        assert hostile not in payload["html_body"]  # HTML-escaped in the table
        assert html.escape(hostile) in payload["html_body"]

    async def test_user_controlled_fields_are_html_escaped(self):
        payload = await _send(
            "send_feedback_notification",
            rating="negative",
            message_id=_FB_UUID,
            reason="<script>alert(1)</script>",
            model_used="<b>m</b>",
            verses_cited=["<i>x</i>"],
            created_at=_CREATED,
        )
        body = payload["html_body"]
        assert "<script>" not in body and "<b>m</b>" not in body and "<i>x</i>" not in body
        assert "&lt;script&gt;" in body

    async def test_signature_cannot_carry_text(self):
        from utils.email_service import EmailService

        params = set(inspect.signature(EmailService.send_feedback_notification).parameters)
        assert not params & {"comment", "user_message", "assistant_response", "reply_to"}


class TestProdServerName:
    def test_derived_from_azure_host(self):
        with patch("utils.email_service.settings") as s:
            s.database_url = _PROD_URL
            from utils.email_service import _prod_server_name

            assert _prod_server_name() == "bible-app-db-mb0172"

    @pytest.mark.parametrize(
        "url",
        [
            "postgresql://u:p@localhost/db",
            "postgresql://u:p@evil.example.com/db",
            "postgresql://u:p@x.postgres.database.azure.com.evil.com/db",
        ],
    )
    def test_none_for_other_hosts(self, url):
        with patch("utils.email_service.settings") as s:
            s.database_url = url
            from utils.email_service import _prod_server_name

            assert _prod_server_name() is None
