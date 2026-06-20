"""
Per-stage timing for the chat pipeline.

Each stage is recorded in two places:

* a per-request ``timings`` dict, so the orchestrator can emit a single
  ``chat_stage_timings`` log line ("intent=3100 retrieval=8200 generation=...")
  that is instantly readable in the backend logs; and
* the ``chat.stage.duration_ms`` OpenTelemetry histogram, so the same data drives
  Application Insights dashboards and alerts.

Recording is best-effort: instrumentation must never break a chat response, so the
histogram write is guarded.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from utils.metrics import chat_stage_duration_histogram


def record_stage(
    timings: dict[str, float],
    stage: str,
    elapsed_ms: float,
    base_attributes: dict | None = None,
) -> None:
    """Record one stage's duration into ``timings`` and the OTel histogram."""
    timings[stage] = round(elapsed_ms, 1)
    attrs: dict = {"stage": stage}
    if base_attributes:
        attrs.update(base_attributes)
    try:
        chat_stage_duration_histogram.record(elapsed_ms, attrs)
    except Exception:  # pragma: no cover - telemetry must never break a response
        pass


@contextmanager
def stage_timer(
    timings: dict[str, float],
    stage: str,
    base_attributes: dict | None = None,
) -> Iterator[None]:
    """Time the wrapped block and record it as ``stage``.

    Works across ``await`` because the awaited code runs inside the ``with`` body::

        with stage_timer(timings, "intent", attrs):
            intent = await self._detect_intent(...)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        record_stage(timings, stage, (time.perf_counter() - start) * 1000, base_attributes)
