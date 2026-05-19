"""
Minimal in-process circuit breaker for external API call paths.

Built for two callers — OpenRouter and Llama Guard — to short-circuit
requests when a dependency is known-down, so we skip the per-request timeout
instead of paying it on every call during an outage.
"""

from __future__ import annotations

import time
from enum import Enum
from threading import Lock

from utils.logging_config import get_logger
from utils.metrics import circuit_breaker_state_counter

logger = get_logger(__name__)


class CircuitOpenError(Exception):
    """Raised by callers when a breaker is open and the call is short-circuited."""


class _State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Failure-count based breaker.

    - CLOSED: calls flow through; consecutive failures increment a counter.
    - OPEN: after `failure_threshold` consecutive failures, calls are
      short-circuited via `is_open()` until `cooldown_seconds` elapses.
    - HALF_OPEN: the next call is allowed through as a probe; success closes
      the breaker, failure re-opens it.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._state = _State.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float = 0.0
        self._lock = Lock()

    @property
    def state(self) -> str:
        return self._state.value

    def is_open(self) -> bool:
        """Return True if the call should be short-circuited."""
        with self._lock:
            if self._state == _State.OPEN:
                if time.monotonic() - self._opened_at >= self.cooldown_seconds:
                    self._transition(_State.HALF_OPEN)
                    return False
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            if self._state != _State.CLOSED:
                self._transition(_State.CLOSED)
            self._consecutive_failures = 0

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._state == _State.HALF_OPEN:
                self._open()
            elif self._consecutive_failures >= self.failure_threshold:
                self._open()

    def _open(self) -> None:
        self._opened_at = time.monotonic()
        self._transition(_State.OPEN)

    def _transition(self, new_state: _State) -> None:
        if new_state == self._state:
            return
        logger.info(
            "Circuit breaker %s: %s -> %s (consecutive_failures=%d)",
            self.name,
            self._state.value,
            new_state.value,
            self._consecutive_failures,
        )
        circuit_breaker_state_counter.add(
            1, {"breaker": self.name, "to_state": new_state.value}
        )
        self._state = new_state
