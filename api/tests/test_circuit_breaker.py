"""Tests for utils.circuit_breaker (BITB-289 single-probe + backoff, default mode unchanged)."""

from unittest.mock import patch

import pytest

from utils.circuit_breaker import CircuitBreaker


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock():
    c = Clock()
    with patch("utils.circuit_breaker.time.monotonic", side_effect=c):
        yield c


def _trip(b: CircuitBreaker) -> None:
    for _ in range(b.failure_threshold):
        b.record_failure()


def test_default_half_open_admits_every_caller(clock):
    b = CircuitBreaker("t", failure_threshold=2, cooldown_seconds=30)
    _trip(b)
    assert b.is_open() is True
    clock.t += 30
    assert b.is_open() is False
    assert b.state == "half_open"
    assert b.is_open() is False
    assert b.is_open() is False


def test_default_cooldown_fixed_across_reopens(clock):
    b = CircuitBreaker("t", failure_threshold=2, cooldown_seconds=30)
    _trip(b)
    for _ in range(3):
        clock.t += 30
        assert b.is_open() is False
        b.record_failure()
        assert b.current_cooldown_seconds == 30
    clock.t += 29
    assert b.is_open() is True
    clock.t += 1
    assert b.is_open() is False


def test_single_probe_only_first_caller_admitted(clock):
    b = CircuitBreaker("t", failure_threshold=2, cooldown_seconds=10, single_probe=True)
    _trip(b)
    clock.t += 10
    assert b.is_open() is False  # probe
    assert b.is_open() is True
    assert b.is_open() is True


def test_single_probe_success_closes(clock):
    b = CircuitBreaker("t", failure_threshold=2, cooldown_seconds=10, single_probe=True)
    _trip(b)
    clock.t += 10
    assert b.is_open() is False
    b.record_success()
    assert b.state == "closed"
    assert b.is_open() is False
    assert b.is_open() is False


def test_single_probe_failure_reopens_and_clears_lease(clock):
    b = CircuitBreaker("t", failure_threshold=2, cooldown_seconds=10, single_probe=True)
    _trip(b)
    clock.t += 10
    assert b.is_open() is False
    b.record_failure()
    assert b.state == "open"
    assert b.is_open() is True
    clock.t += 10
    assert b.is_open() is False  # a fresh probe after the new cooldown


def test_single_probe_lease_expires(clock):
    b = CircuitBreaker(
        "t", failure_threshold=2, cooldown_seconds=10, single_probe=True, probe_timeout_seconds=5
    )
    _trip(b)
    clock.t += 10
    assert b.is_open() is False  # probe never reports back
    clock.t += 4
    assert b.is_open() is True
    clock.t += 1
    assert b.is_open() is False  # lease expired -> new probe
    assert b.is_open() is True


def test_probe_timeout_defaults_to_cooldown(clock):
    b = CircuitBreaker("t", failure_threshold=1, cooldown_seconds=10, single_probe=True)
    assert b.probe_timeout_seconds == 10


def test_backoff_doubles_up_to_cap_and_resets_on_success(clock):
    b = CircuitBreaker(
        "t",
        failure_threshold=1,
        cooldown_seconds=10,
        max_cooldown_seconds=60,
        single_probe=True,
    )
    assert b.current_cooldown_seconds == 10
    b.record_failure()  # trip
    seen = []
    for _ in range(5):
        clock.t += b.current_cooldown_seconds
        assert b.is_open() is False
        b.record_failure()
        seen.append(b.current_cooldown_seconds)
    assert seen == [20, 40, 60, 60, 60]
    # not yet elapsed -> still open
    clock.t += 59
    assert b.is_open() is True
    clock.t += 1
    assert b.is_open() is False
    b.record_success()
    assert b.current_cooldown_seconds == 10


def test_closed_failures_do_not_back_off(clock):
    b = CircuitBreaker("t", failure_threshold=3, cooldown_seconds=10, max_cooldown_seconds=60)
    _trip(b)
    assert b.current_cooldown_seconds == 10


def test_stale_failure_without_live_lease_does_not_escalate_backoff(clock):
    b = CircuitBreaker(
        "t",
        failure_threshold=1,
        cooldown_seconds=10,
        max_cooldown_seconds=60,
        single_probe=True,
        probe_timeout_seconds=5,
    )
    b.record_failure()  # trip
    clock.t += 10
    assert b.is_open() is False  # probe lease granted
    clock.t += 6  # lease expired, probe never reported
    b.record_failure()  # stale/late failure, no live lease
    assert b.state == "open"
    assert b.current_cooldown_seconds == 10


def test_probe_failure_with_live_lease_escalates_backoff(clock):
    b = CircuitBreaker(
        "t", failure_threshold=1, cooldown_seconds=10, max_cooldown_seconds=60, single_probe=True
    )
    b.record_failure()
    clock.t += 10
    assert b.is_open() is False
    b.record_failure()
    assert b.current_cooldown_seconds == 20
