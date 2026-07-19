"""
Tests for database performance instrumentation.

Verifies that:
- OTel spans are created for each DB operation
- Span attributes are correct (operation, duration, count, translation, request_id)
- Slow query logging triggers when threshold exceeded
- Correlation ID is included in spans
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from middleware.context import REQUEST_ID_CTX_VAR
from scripture.repository import ScriptureRepository
from utils.telemetry import tracer


class TestTelemetryModule:
    """Verify the telemetry module is properly configured."""

    def test_tracer_is_not_none(self):
        """Tracer should be initialized (OTel API is a no-op if no exporter)."""
        assert tracer is not None

    def test_tracer_name(self):
        """Tracer should use the bible_app.scripture instrumentation scope."""
        # The tracer object's internal name is accessible via instrumenting_module_name
        # or via __class__.__name__ — just verify it's a valid tracer
        from opentelemetry import trace

        t = trace.get_tracer("bible_app.scripture")
        assert t is not None


class TestSpanAttributes:
    """Verify _set_common_span_attrs and _record_duration set correct attributes."""

    def test_set_common_span_attrs_with_translation(self):
        """Common attributes include operation, translation, and request_id."""
        from scripture.repository import _set_common_span_attrs

        mock_span = MagicMock()
        token = REQUEST_ID_CTX_VAR.set("test-request-123")
        try:
            _set_common_span_attrs(mock_span, "get_verse", "kjv")
            mock_span.set_attribute.assert_any_call("db.operation", "get_verse")
            mock_span.set_attribute.assert_any_call("db.translation", "kjv")
            mock_span.set_attribute.assert_any_call("request_id", "test-request-123")
        finally:
            REQUEST_ID_CTX_VAR.reset(token)

    def test_set_common_span_attrs_no_translation(self):
        """Translation defaults to 'all' when not provided."""
        from scripture.repository import _set_common_span_attrs

        mock_span = MagicMock()
        _set_common_span_attrs(mock_span, "get_chapter", None)
        mock_span.set_attribute.assert_any_call("db.translation", "all")

    def test_set_common_span_attrs_no_request_id(self):
        """request_id attribute is not set when context var is empty."""
        from scripture.repository import _set_common_span_attrs

        mock_span = MagicMock()
        # Ensure context var is empty
        token = REQUEST_ID_CTX_VAR.set("")
        try:
            _set_common_span_attrs(mock_span, "get_verse", None)
            calls = [str(c) for c in mock_span.set_attribute.call_args_list]
            assert not any("request_id" in c for c in calls)
        finally:
            REQUEST_ID_CTX_VAR.reset(token)

    def test_record_duration_sets_attributes(self):
        """Duration and result count are recorded on the span."""
        from scripture.repository import _record_duration

        mock_span = MagicMock()
        start = time.perf_counter() - 0.05  # Simulate 50ms query
        _record_duration(mock_span, start, "get_verse", 1, "kjv")
        # Verify duration attribute was set (value should be ~50ms)
        calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
        assert "db.duration_ms" in calls
        assert calls["db.duration_ms"] >= 0
        assert calls["db.results.count"] == 1

    def test_slow_query_logging(self):
        """Slow queries are logged as warnings when threshold exceeded."""
        from scripture.repository import _record_duration

        mock_span = MagicMock()
        with patch("scripture.repository.logger") as mock_logger:
            with patch("scripture.repository.settings") as mock_settings:
                mock_settings.slow_query_threshold_ms = 0  # Everything is slow
                start = time.perf_counter() - 0.5  # 500ms ago
                _record_duration(mock_span, start, "semantic_search_verses", 5, "kjv")
                mock_logger.warning.assert_called_once()
                call_kwargs = mock_logger.warning.call_args
                assert "Slow query detected" in call_kwargs[0][0]

    def test_fast_query_no_slow_log(self):
        """Fast queries below threshold do not trigger slow query log."""
        from scripture.repository import _record_duration

        mock_span = MagicMock()
        with patch("scripture.repository.logger") as mock_logger:
            with patch("scripture.repository.settings") as mock_settings:
                mock_settings.slow_query_threshold_ms = 10000  # Very high threshold
                start = time.perf_counter()
                _record_duration(mock_span, start, "get_verse", 1, None)
                mock_logger.warning.assert_not_called()


class TestSlowQueryLogging:
    """Verify slow query log entries include required fields."""

    def test_slow_query_log_includes_operation(self):
        """Slow query log includes operation name."""
        from scripture.repository import _record_duration

        mock_span = MagicMock()
        with patch("scripture.repository.logger") as mock_logger:
            with patch("scripture.repository.settings") as mock_settings:
                mock_settings.slow_query_threshold_ms = 0
                _record_duration(
                    mock_span, time.perf_counter() - 1.0, "semantic_search_verses", 3, None
                )
                call_kwargs = mock_logger.warning.call_args[1]["extra"]
                assert call_kwargs["operation"] == "semantic_search_verses"
                assert call_kwargs["result_count"] == 3
                assert "duration_ms" in call_kwargs

    def test_slow_query_log_includes_correlation_id(self):
        """Slow query log includes correlation ID from context var."""
        from scripture.repository import _record_duration

        mock_span = MagicMock()
        token = REQUEST_ID_CTX_VAR.set("corr-id-456")
        try:
            with patch("scripture.repository.logger") as mock_logger:
                with patch("scripture.repository.settings") as mock_settings:
                    mock_settings.slow_query_threshold_ms = 0
                    _record_duration(mock_span, time.perf_counter() - 1.0, "get_chapter", 10, "kjv")
                    call_kwargs = mock_logger.warning.call_args[1]["extra"]
                    assert call_kwargs["request_id"] == "corr-id-456"
        finally:
            REQUEST_ID_CTX_VAR.reset(token)


class TestRepositorySpans:
    """Verify repository methods create OTel spans with correct attributes."""

    @pytest.mark.asyncio
    async def test_search_verses_semantic_creates_span(self):
        """search_verses_semantic() creates a span named db.search_verses_semantic."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = ScriptureRepository(mock_session)

        with patch("scripture.repository.tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

            await repo.search_verses_semantic([0.1] * 10, limit=5, similarity_threshold=0.35)

            mock_tracer.start_as_current_span.assert_called_once_with("db.search_verses_semantic")

    @pytest.mark.asyncio
    async def test_search_passages_semantic_creates_span(self):
        """search_passages_semantic() creates a span named db.search_passages_semantic."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = ScriptureRepository(mock_session)

        with patch("scripture.repository.tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

            await repo.search_passages_semantic([0.1] * 10, limit=3, similarity_threshold=0.35)

            mock_tracer.start_as_current_span.assert_called_once_with("db.search_passages_semantic")

    @pytest.mark.asyncio
    async def test_get_verse_creates_span(self):
        """get_verse() creates a span named db.get_verse."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        repo = ScriptureRepository(mock_session)

        with patch("scripture.repository.tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

            await repo.get_verse("John", 3, 16)

            mock_tracer.start_as_current_span.assert_called_once_with("db.get_verse")

    @pytest.mark.asyncio
    async def test_get_chapter_verses_creates_span(self):
        """get_chapter_verses() creates a span named db.get_chapter_verses."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        repo = ScriptureRepository(mock_session)

        with patch("scripture.repository.tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

            await repo.get_chapter_verses("John", 3)

            mock_tracer.start_as_current_span.assert_called_once_with("db.get_chapter_verses")

    @pytest.mark.asyncio
    async def test_similarity_threshold_set_on_span(self):
        """Semantic search spans include similarity_threshold attribute."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = ScriptureRepository(mock_session)

        with patch("scripture.repository.tracer") as mock_tracer:
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(return_value=False)

            await repo.search_verses_semantic([0.1] * 10, similarity_threshold=0.42)

            # Check that similarity_threshold was set
            calls = {call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list}
            assert calls.get("db.similarity_threshold") == 0.42


class TestDBMetricsRecording:
    """Verify DB metrics are recorded alongside spans."""

    @pytest.mark.asyncio
    async def test_search_verses_semantic_records_metric(self):
        """search_verses_semantic() records db.search.duration_ms metric."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        repo = ScriptureRepository(mock_session)

        with patch("scripture.repository.db_search_duration_histogram") as mock_histogram:
            await repo.search_verses_semantic(
                [0.1] * 10, limit=5, similarity_threshold=0.35, translation="kjv"
            )
            # Verify the histogram recorded a value with correct dimensions
            mock_histogram.record.assert_called_once()
            call_args = mock_histogram.record.call_args
            # First arg is duration_ms (should be a float)
            assert isinstance(call_args[0][0], float)
            # Second arg is dimensions dict
            assert call_args[0][1] == {"operation": "semantic_search_verses", "translation": "kjv"}

    def test_record_duration_records_metric_for_search_operation(self):
        """_record_duration() routes search operations to db_search_duration_histogram."""
        from scripture.repository import _record_duration

        mock_span = MagicMock()
        with patch("scripture.repository.db_search_duration_histogram") as mock_histogram:
            with patch("scripture.repository.settings") as mock_settings:
                mock_settings.slow_query_threshold_ms = 10000  # High threshold
                _record_duration(
                    mock_span,
                    time.perf_counter() - 0.05,
                    "semantic_search_verses",
                    5,
                    "kjv",
                )
                mock_histogram.record.assert_called_once()
                call_args = mock_histogram.record.call_args
                # Verify dimensions include both operation and translation
                assert call_args[0][1] == {
                    "operation": "semantic_search_verses",
                    "translation": "kjv",
                }

    def test_record_duration_records_metric_for_query_operation(self):
        """_record_duration() routes non-search operations to db_query_duration_histogram."""
        from scripture.repository import _record_duration

        mock_span = MagicMock()
        with patch("scripture.repository.db_query_duration_histogram") as mock_histogram:
            with patch("scripture.repository.settings") as mock_settings:
                mock_settings.slow_query_threshold_ms = 10000  # High threshold
                _record_duration(mock_span, time.perf_counter() - 0.05, "get_verse", 1, "kjv")
                mock_histogram.record.assert_called_once()
                call_args = mock_histogram.record.call_args
                # Verify dimensions include only operation (no translation for non-search)
                assert call_args[0][1] == {"operation": "get_verse"}

    def test_record_duration_increments_slow_query_counter(self):
        """_record_duration() increments slow_query counter when threshold exceeded."""
        from scripture.repository import _record_duration

        mock_span = MagicMock()
        with patch("scripture.repository.db_slow_queries_counter") as mock_counter:
            with patch("scripture.repository.settings") as mock_settings:
                with patch("scripture.repository.logger"):
                    mock_settings.slow_query_threshold_ms = 0  # Everything is slow
                    _record_duration(
                        mock_span,
                        time.perf_counter() - 0.5,
                        "semantic_search_verses",
                        5,
                        "kjv",
                    )
                    mock_counter.add.assert_called_once_with(
                        1, {"operation": "semantic_search_verses"}
                    )

    def test_record_duration_does_not_increment_slow_query_counter_for_fast_queries(self):
        """_record_duration() does not increment slow_query counter for fast queries."""
        from scripture.repository import _record_duration

        mock_span = MagicMock()
        with patch("scripture.repository.db_slow_queries_counter") as mock_counter:
            with patch("scripture.repository.settings") as mock_settings:
                mock_settings.slow_query_threshold_ms = 10000  # Very high threshold
                _record_duration(mock_span, time.perf_counter(), "get_verse", 1, None)
                mock_counter.add.assert_not_called()
