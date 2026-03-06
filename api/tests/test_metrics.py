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

    def test_new_llm_metrics_defined(self):
        """Ensure all new LLM performance metrics are initialized."""
        from utils.metrics import (
            llm_fallback_counter,
            llm_rate_limit_counter,
            llm_tokens_per_second_histogram,
            llm_total_duration_histogram,
            llm_ttft_histogram,
        )

        assert llm_ttft_histogram is not None
        assert llm_total_duration_histogram is not None
        assert llm_fallback_counter is not None
        assert llm_rate_limit_counter is not None
        assert llm_tokens_per_second_histogram is not None

    def test_new_db_metrics_defined(self):
        """Ensure all new database performance metrics are initialized."""
        from utils.metrics import (
            db_query_duration_histogram,
            db_search_duration_histogram,
            db_slow_queries_counter,
        )

        assert db_search_duration_histogram is not None
        assert db_query_duration_histogram is not None
        assert db_slow_queries_counter is not None

    def test_llm_metrics_recording(self):
        """Test recording LLM performance metrics."""
        from utils.metrics import (
            llm_fallback_counter,
            llm_rate_limit_counter,
            llm_tokens_per_second_histogram,
            llm_total_duration_histogram,
            llm_ttft_histogram,
        )

        with patch.object(llm_ttft_histogram, "record") as mock_record:
            llm_ttft_histogram.record(42.5, {"provider": "openrouter", "model": "test"})
            mock_record.assert_called_once_with(42.5, {"provider": "openrouter", "model": "test"})

        with patch.object(llm_total_duration_histogram, "record") as mock_record:
            llm_total_duration_histogram.record(1200.0, {"provider": "claude", "model": "test"})
            mock_record.assert_called_once_with(1200.0, {"provider": "claude", "model": "test"})

        with patch.object(llm_tokens_per_second_histogram, "record") as mock_record:
            llm_tokens_per_second_histogram.record(35.0, {"provider": "ollama", "model": "test"})
            mock_record.assert_called_once_with(35.0, {"provider": "ollama", "model": "test"})

        with patch.object(llm_fallback_counter, "add") as mock_add:
            llm_fallback_counter.add(1, {"provider": "openrouter", "model": "fallback-model"})
            mock_add.assert_called_once_with(
                1, {"provider": "openrouter", "model": "fallback-model"}
            )

        with patch.object(llm_rate_limit_counter, "add") as mock_add:
            llm_rate_limit_counter.add(1, {"provider": "openrouter"})
            mock_add.assert_called_once_with(1, {"provider": "openrouter"})

    def test_db_metrics_recording(self):
        """Test recording database performance metrics."""
        from utils.metrics import (
            db_query_duration_histogram,
            db_search_duration_histogram,
            db_slow_queries_counter,
        )

        with patch.object(db_search_duration_histogram, "record") as mock_record:
            db_search_duration_histogram.record(85.2)
            mock_record.assert_called_once_with(85.2)

        with patch.object(db_query_duration_histogram, "record") as mock_record:
            db_query_duration_histogram.record(12.3)
            mock_record.assert_called_once_with(12.3)

        with patch.object(db_slow_queries_counter, "add") as mock_add:
            db_slow_queries_counter.add(1)
            mock_add.assert_called_once_with(1)
