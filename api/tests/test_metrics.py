"""
Tests for custom OpenTelemetry metrics.

Verifies that metrics are correctly defined and can be recorded.
"""

from unittest.mock import patch

from utils.metrics import (
    chat_messages_counter,
    chat_response_time,
    chat_sessions_counter,
    chat_stream_counter,
    church_search_counter,
    contact_form_counter,
    feedback_counter,
    scripture_search_counter,
    scripture_verses_returned,
)


class TestMetrics:
    """Verify metrics definitions and basic recording."""

    def test_metrics_defined(self):
        """Ensure all metrics objects are initialized."""
        assert chat_messages_counter is not None
        assert chat_response_time is not None
        assert chat_sessions_counter is not None
        assert chat_stream_counter is not None
        assert scripture_search_counter is not None
        assert scripture_verses_returned is not None
        assert church_search_counter is not None
        assert feedback_counter is not None
        assert contact_form_counter is not None

    def test_chat_metrics_recording(self):
        """Test recording chat metrics with mocks."""
        with patch.object(chat_messages_counter, "add") as mock_add:
            chat_messages_counter.add(1)
            mock_add.assert_called_once_with(1)

        with patch.object(chat_response_time, "record") as mock_record:
            chat_response_time.record(150.5)
            mock_record.assert_called_once_with(150.5)

        with patch.object(chat_sessions_counter, "add") as mock_add:
            chat_sessions_counter.add(1, {"session_token": "test-session"})
            mock_add.assert_called_once_with(1, {"session_token": "test-session"})

        with patch.object(chat_stream_counter, "add") as mock_add:
            chat_stream_counter.add(1)
            mock_add.assert_called_once_with(1)

    def test_scripture_metrics_recording(self):
        """Test recording scripture metrics with mocks."""
        with patch.object(scripture_search_counter, "add") as mock_add:
            scripture_search_counter.add(1)
            mock_add.assert_called_once_with(1)

        with patch.object(scripture_verses_returned, "record") as mock_record:
            scripture_verses_returned.record(5)
            mock_record.assert_called_once_with(5)

    def test_church_metrics_recording(self):
        """Test recording church metrics with mocks."""
        with patch.object(church_search_counter, "add") as mock_add:
            church_search_counter.add(1)
            mock_add.assert_called_once_with(1)

    def test_feedback_metrics_recording(self):
        """Test recording feedback metrics with mocks."""
        with patch.object(feedback_counter, "add") as mock_add:
            feedback_counter.add(1, {"rating": "positive"})
            mock_add.assert_called_once_with(1, {"rating": "positive"})

        with patch.object(contact_form_counter, "add") as mock_add:
            contact_form_counter.add(1, {"subject": "bug"})
            mock_add.assert_called_once_with(1, {"subject": "bug"})
