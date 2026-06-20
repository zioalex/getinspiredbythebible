"""
Tests for the per-stage chat timing helper (utils.timing).

These verify that stage durations are written into the per-request ``timings``
dict (the source of the ``chat_stage_timings`` log line) and recorded into the
``chat.stage.duration_ms`` OpenTelemetry histogram, and that recording is
best-effort (a telemetry failure must never propagate into a chat response).
"""

from unittest.mock import patch

from utils import timing
from utils.metrics import chat_stage_duration_histogram
from utils.timing import record_stage, stage_timer


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


class TestStageTimer:
    def test_times_block_and_records(self):
        timings: dict[str, float] = {}
        # Patch perf_counter so the measured duration is deterministic.
        with patch.object(timing.time, "perf_counter", side_effect=[1.0, 1.25]):
            with patch.object(chat_stage_duration_histogram, "record") as mock_record:
                with stage_timer(timings, "search", {"stream": False}):
                    pass

        assert timings == {"search": 250.0}
        mock_record.assert_called_once_with(250.0, {"stage": "search", "stream": False})

    def test_records_even_when_block_raises(self):
        timings: dict[str, float] = {}
        with patch.object(timing.time, "perf_counter", side_effect=[2.0, 2.1]):
            try:
                with stage_timer(timings, "grounding"):
                    raise ValueError("inner failure")
            except ValueError:
                pass

        # finally-clause still records the partial duration.
        assert "grounding" in timings
        assert timings["grounding"] == 100.0
