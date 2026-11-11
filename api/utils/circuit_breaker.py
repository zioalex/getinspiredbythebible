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

    Opt-in refinements (defaults preserve the behaviour above exactly):

    - ``single_probe=True``: only ONE caller is admitted as the half-open probe
      (it holds a lease); every other caller is short-circuited until the probe
      records an outcome. The lease expires after ``probe_timeout_seconds``
      (default: ``cooldown_seconds``) so a probe whose outcome is never recorded
      (cancellation, unexpected exception) cannot wedge the breaker.
    - ``max_cooldown_seconds``: each consecutive re-open from HALF_OPEN doubles
      the effective cooldown (``base * 2**n``), capped at this value;
      ``record_success`` resets it to the base ``cooldown_seconds``.
      With ``single_probe=True`` only a failure while a probe lease is active counts as
      a failed probe: a stale failure from a call admitted before the breaker opened
      (HALF_OPEN with no lease) re-opens the breaker but does not escalate the backoff.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        cooldown_seconds: float = 30.0,
        single_probe: bool = False,
        probe_timeout_seconds: float | None = None,
        max_cooldown_seconds: float | None = None,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.single_probe = single_probe
        self.probe_timeout_seconds = (
            probe_timeout_seconds if probe_timeout_seconds is not None else cooldown_seconds
        )
        self.max_cooldown_seconds = max_cooldown_seconds
        self._reopen_count = 0
        self._probe_started_at: float | None = None
        self._state = _State.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float = 0.0
        self._lock = Lock()

    @property
    def state(self) -> str:
        return self._state.value

    @property
    def current_cooldown_seconds(self) -> float:
        """Effective cooldown for the current open window (base, or backed-off)."""
        if self.max_cooldown_seconds is None:
            return self.cooldown_seconds
        backed_off = self.cooldown_seconds * (2**self._reopen_count)
        return min(backed_off, max(self.max_cooldown_seconds, self.cooldown_seconds))

    def is_open(self) -> bool:
        """Return True if the call should be short-circuited."""
        with self._lock:
            now = time.monotonic()
            if self._state == _State.OPEN:
                if now - self._opened_at >= self.current_cooldown_seconds:
                    self._transition(_State.HALF_OPEN)
                    if self.single_probe:
                        self._probe_started_at = now
                    return False
                return True
            if self._state == _State.HALF_OPEN and self.single_probe:
                if (
                    self._probe_started_at is None
                    or now - self._probe_started_at >= self.probe_timeout_seconds
                ):
                    # No live lease (never granted, or the probe vanished): this
                    # caller becomes the new probe.
                    self._probe_started_at = now
                    return False
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            if self._state != _State.CLOSED:
                self._transition(_State.CLOSED)
            self._consecutive_failures = 0
            self._reopen_count = 0
            self._probe_started_at = None

    def record_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._state == _State.HALF_OPEN:
                lease_live = (
                    self._probe_started_at is not None
                    and time.monotonic() - self._probe_started_at < self.probe_timeout_seconds
                )
                if not self.single_probe or lease_live:
                    self._reopen_count += 1
                self._open()
            elif self._consecutive_failures >= self.failure_threshold:
                self._open()

    def _open(self) -> None:
        self._opened_at = time.monotonic()
        self._probe_started_at = None
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
        circuit_breaker_state_counter.add(1, {"breaker": self.name, "to_state": new_state.value})
        self._state = new_state
