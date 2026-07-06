"""
Tests for the per-stage chat timing helpers (utils.timing).

These verify that stage durations are written into the per-request ``timings`` dict
(the source of the ``chat_stage_timings`` log line) and recorded into the
``chat.stage.duration_ms`` OpenTelemetry histogram, that recording is best-effort (a
telemetry failure must never propagate into a chat response), and that the
``@timed_stage`` decorator times the methods it wraps without double-counting nested
same-stage calls.
"""

from unittest.mock import patch

import pytest

from utils import timing
from utils.metrics import chat_stage_duration_histogram
from utils.timing import format_timings, record_stage, timed_stage


class TestRecordStage:
    def test_writes_into_timings_and_rounds(self):
        timings: dict[str, float] = {}
        with patch.object(chat_stage_duration_histogram, "record") as mock_record:
            record_stage(timings, "intent", 3100.456, {"stream": True, "provider": "openrouter"})

        assert timings == {"intent": 3100.5}
        mock_record.assert_called_once_with(
            3100.456, {"stage": "intent", "stream": True, "provider": "openrouter"}
        )

    def test_works_without_base_attributes(self):
        timings: dict[str, float] = {}
        with patch.object(chat_stage_duration_histogram, "record") as mock_record:
            record_stage(timings, "retrieval", 42.0)

        assert timings == {"retrieval": 42.0}
        mock_record.assert_called_once_with(42.0, {"stage": "retrieval"})

    def test_telemetry_failure_is_swallowed(self):
        """A histogram error must not break the response; the dict is still written."""
        timings: dict[str, float] = {}
        with patch.object(
            chat_stage_duration_histogram, "record", side_effect=RuntimeError("boom")
        ):
            record_stage(timings, "generation", 10.0)

        assert timings == {"generation": 10.0}


class TestFormatTimings:
    def test_renders_compact_key_value_string(self):
        timings = {"intent": 3100.5, "retrieval": 8200.1, "total": 11500.0}
        assert format_timings(timings) == "intent=3100.5 retrieval=8200.1 total=11500.0"

    def test_empty_timings_is_empty_string(self):
        assert format_timings({}) == ""


class _FakeService:
    """Minimal stand-in exposing the attributes ``@timed_stage`` reads off ``self``."""

    def __init__(self, timings: dict[str, float] | None):
        self._timings = timings
        self._stage_attrs = {"stream": False}
        self._active_stages: set[str] = set()

    @timed_stage("intent")
    async def detect(self, value):
        return value

    @timed_stage("grounding")
    async def boom(self):
        raise ValueError("inner failure")

    @timed_stage("grounding")
    async def outer(self):
        # Nested same-stage call: the inner decorated method must not double-record.
        return await self.inner()

    @timed_stage("grounding")
    async def inner(self):
        return "ok"


class TestTimedStage:
    async def test_records_into_timings_and_histogram(self):
        svc = _FakeService(timings={})
        # Patch perf_counter so the measured duration is deterministic.
        with patch.object(timing.time, "perf_counter", side_effect=[1.0, 1.25]):
            with patch.object(chat_stage_duration_histogram, "record") as mock_record:
                result = await svc.detect("hello")

        assert result == "hello"
        assert svc._timings == {"intent": 250.0}
        mock_record.assert_called_once_with(250.0, {"stage": "intent", "stream": False})

    async def test_noop_when_no_timing_context(self):
        """Called outside a chat request (``_timings is None``) → run, record nothing."""
        svc = _FakeService(timings=None)
        with patch.object(chat_stage_duration_histogram, "record") as mock_record:
            result = await svc.detect("hello")

        assert result == "hello"
        assert svc._timings is None
        mock_record.assert_not_called()

    async def test_records_even_when_method_raises(self):
        svc = _FakeService(timings={})
        with patch.object(timing.time, "perf_counter", side_effect=[2.0, 2.1]):
            with pytest.raises(ValueError):
                await svc.boom()

        # finally-clause still records the partial duration.
        assert svc._timings == {"grounding": 100.0}

    async def test_nested_same_stage_records_once(self):
        svc = _FakeService(timings={})
        with patch.object(chat_stage_duration_histogram, "record") as mock_record:
            result = await svc.outer()

        assert result == "ok"
        # Only the outermost frame owns the "grounding" measurement.
        assert list(svc._timings.keys()) == ["grounding"]
        mock_record.assert_called_once()
        assert mock_record.call_args.args[1]["stage"] == "grounding"
