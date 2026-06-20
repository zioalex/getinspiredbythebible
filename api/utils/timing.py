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

import functools
import time
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

from utils.metrics import chat_stage_duration_histogram

P = ParamSpec("P")
R = TypeVar("R")


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


def timed_stage(
    stage: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Decorator that times an async ``ChatService`` method and records it as ``stage``.

    The wrapped method becomes self-instrumenting: instead of wrapping each call site in
    a ``with`` block, decorate the stage method and it records its own duration into the
    per-request ``self._timings`` dict and the ``chat.stage.duration_ms`` histogram.

    Behaviour:

    * No-op when no timing context is active (``self._timings is None``) — e.g. when the
      method is called outside a chat request — the method still runs normally.
    * Re-entrant: if the same ``stage`` is already being timed by an outer frame, the
      inner call still runs but does not record, so nesting two same-stage methods (e.g.
      the streaming grounding block calling ``_apply_verse_grounding``) yields a single
      measurement owned by the outermost frame.
    * Best-effort: the histogram write is guarded inside ``record_stage`` so telemetry
      can never break a response. The duration is recorded even if the wrapped coroutine
      raises.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            self: Any = args[0]  # decorator is applied to instance methods
            timings = getattr(self, "_timings", None)
            if timings is None:
                return await func(*args, **kwargs)
            active = getattr(self, "_active_stages", None)
            if active is None:
                active = set()
                self._active_stages = active
            if stage in active:
                # Nested same-stage call: run it, but let the outer frame own the timing.
                return await func(*args, **kwargs)
            active.add(stage)
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                active.discard(stage)
                record_stage(
                    timings,
                    stage,
                    (time.perf_counter() - start) * 1000,
                    getattr(self, "_stage_attrs", None),
                )

        return wrapper

    return decorator
