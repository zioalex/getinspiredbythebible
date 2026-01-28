"""
Tests for the email service (SMTP2GO HTTP API).
"""

from unittest.mock import MagicMock, patch

import httpx


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


class TestSendEmail:
    """Test send_email method."""

    def test_send_email_when_disabled_returns_false(self):
        """Test that send_email returns False when disabled."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = False
            mock_settings.smtp2go_api_key = "test-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "test@example.com"
            mock_settings.smtp2go_sender_name = "Test"

            from utils.email_service import EmailService

            service = EmailService()
            result = service.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                body_text="Test body",
            )

            assert result is False

    def test_send_email_when_api_key_missing_returns_false(self):
        """Test that send_email returns False when API key is missing."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = None
            mock_settings.smtp2go_sender_email = "test@example.com"
            mock_settings.smtp2go_sender_name = "Test"

            from utils.email_service import EmailService

            service = EmailService()
            result = service.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                body_text="Test body",
            )

            assert result is False

    def test_send_email_successful_api_call(self):
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

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                    body_html="<p>Test body</p>",
                )

                assert result is True
                mock_client_instance.post.assert_called_once()
                call_args = mock_client_instance.post.call_args
                payload = call_args[1]["json"]
                assert payload["api_key"] == "test-api-key"  # pragma: allowlist secret
                assert payload["to"] == ["recipient@example.com"]
                assert payload["subject"] == "Test Subject"
                assert payload["text_body"] == "Test body"
                assert payload["html_body"] == "<p>Test body</p>"

    def test_send_email_with_reply_to(self):
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

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                    reply_to="user@example.com",
                )

                assert result is True
                call_args = mock_client_instance.post.call_args
                payload = call_args[1]["json"]
                assert payload["custom_headers"] == [
                    {"header": "Reply-To", "value": "user@example.com"}
                ]

    def test_send_email_handles_api_failure(self):
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

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                )

                assert result is False

    def test_send_email_handles_api_success_with_zero_succeeded(self):
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

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                )

                assert result is False

    def test_send_email_handles_timeout(self):
        """Test handling of timeout exception."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"

            from utils.email_service import EmailService

            service = EmailService()

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.side_effect = httpx.TimeoutException("Timeout")
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                )

                assert result is False

    def test_send_email_handles_http_error(self):
        """Test handling of HTTP errors."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"

            from utils.email_service import EmailService

            service = EmailService()

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.side_effect = httpx.HTTPError("Connection failed")
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = service.send_email(
                    to_email="recipient@example.com",
                    subject="Test Subject",
                    body_text="Test body",
                )

                assert result is False


class TestSendContactNotification:
    """Test send_contact_notification method."""

    def test_send_contact_notification_formats_correctly(self):
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

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = service.send_contact_notification(
                    subject_type="bug",
                    message="Found a bug in the app",
                    reply_email="user@example.com",
                    user_agent="Mozilla/5.0",
                )

                assert result is True
                call_args = mock_client_instance.post.call_args
                payload = call_args[1]["json"]
                assert payload["to"] == ["admin@example.com"]
                assert "Bug" in payload["subject"]
                assert "Found a bug" in payload["text_body"]
                assert "user@example.com" in payload["text_body"]

    def test_send_contact_notification_sets_reply_to(self):
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

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                service.send_contact_notification(
                    subject_type="feature",
                    message="Please add dark mode",
                    reply_email="user@example.com",
                )

                call_args = mock_client_instance.post.call_args
                payload = call_args[1]["json"]
                assert payload["custom_headers"] == [
                    {"header": "Reply-To", "value": "user@example.com"}
                ]


class TestSendFeedbackNotification:
    """Test send_feedback_notification method."""

    def test_feedback_notification_only_sends_for_negative(self):
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

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = service.send_feedback_notification(
                    rating="negative",
                    comment="Not helpful",
                    user_message="What is the meaning of life?",
                    assistant_response="The meaning of life is...",
                )

                assert result is True
                mock_client_instance.post.assert_called_once()

    def test_feedback_notification_skips_positive(self):
        """Test that notification is skipped for positive feedback."""
        with patch("utils.email_service.settings") as mock_settings:
            mock_settings.smtp2go_enabled = True
            mock_settings.smtp2go_api_key = "test-api-key"  # pragma: allowlist secret
            mock_settings.smtp2go_sender_email = "sender@example.com"
            mock_settings.smtp2go_sender_name = "Test Sender"
            mock_settings.contact_notification_email = "admin@example.com"

            from utils.email_service import EmailService

            service = EmailService()

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = service.send_feedback_notification(
                    rating="positive",
                    comment="Great answer!",
                    user_message="What is love?",
                    assistant_response="Love is...",
                )

                # Should return True (success) but not send email
                assert result is True
                mock_client_instance.post.assert_not_called()

    def test_feedback_notification_truncates_long_messages(self):
        """Test that long messages are truncated to 500 chars."""
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

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                service.send_feedback_notification(
                    rating="negative",
                    comment="Bad response",
                    user_message=long_message,
                    assistant_response=long_message,
                )

                call_args = mock_client_instance.post.call_args
                payload = call_args[1]["json"]
                # Check that the text body contains truncated messages
                # Should have "A" * 500 + "..."
                assert "A" * 500 in payload["text_body"]
                assert "..." in payload["text_body"]

    def test_feedback_notification_handles_no_comment(self):
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

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = service.send_feedback_notification(
                    rating="negative",
                    comment=None,
                    user_message="Question",
                    assistant_response="Answer",
                )

                assert result is True
                call_args = mock_client_instance.post.call_args
                payload = call_args[1]["json"]
                assert "No comment provided" in payload["text_body"]
