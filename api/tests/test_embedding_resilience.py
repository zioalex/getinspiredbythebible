"""
Tests for ResilientEmbeddingProvider (BITB-057 Phase 2).

Mirrors the mocking approach used in test_llama_guard.py's timeout/error tests:
mock the wrapped provider's methods directly (no real network calls) and assert
on breaker/retry/metric behaviour.
"""

import asyncio
from unittest.mock import AsyncMock

import httpx
import pytest

from config import settings
from providers.base import EmbeddingResponse
from providers.embedding_resilience import CircuitOpenError, ResilientEmbeddingProvider


def _make_settings(**overrides):
    """Settings with fast retry/timeout knobs so tests don't sleep for real."""
    defaults = dict(
        embedding_request_timeout=0.2,
        embedding_breaker_failure_threshold=2,
        embedding_breaker_cooldown_seconds=30.0,
        embedding_retry_max_attempts=2,
        embedding_retry_base_delay_seconds=0.01,
    )
    defaults.update(overrides)
    return settings.model_copy(update=defaults)


class _FakeProvider:
    """Minimal stand-in for a concrete EmbeddingProvider."""

    def __init__(self):
        self.provider_name = "fake"
        self.dimensions = 4
        self.embed = AsyncMock()
        self.embed_batch = AsyncMock()
        self.health_check = AsyncMock(return_value=True)
        self.close = AsyncMock()


def _resp(vec=None):
    return EmbeddingResponse(embedding=vec or [0.1, 0.2, 0.3, 0.4], model="fake", provider="fake")


@pytest.mark.asyncio
async def test_embed_success_passthrough():
    wrapped = _FakeProvider()
    wrapped.embed.return_value = _resp()
    provider = ResilientEmbeddingProvider(wrapped, _make_settings())

    result = await provider.embed("hello")

    assert result.embedding == [0.1, 0.2, 0.3, 0.4]
    wrapped.embed.assert_awaited_once_with("hello")


@pytest.mark.asyncio
async def test_circuit_open_short_circuits_immediately():
    wrapped = _FakeProvider()
    wrapped.embed.side_effect = httpx.ConnectError("boom")
    cfg = _make_settings(embedding_breaker_failure_threshold=1, embedding_retry_max_attempts=1)
    provider = ResilientEmbeddingProvider(wrapped, cfg)

    # First call trips the breaker (threshold=1, single attempt).
    with pytest.raises(httpx.ConnectError):
        await provider.embed("first")
    assert wrapped.embed.await_count == 1

    # Second call should short-circuit without calling the wrapped provider.
    with pytest.raises(CircuitOpenError):
        await provider.embed("second")
    assert wrapped.embed.await_count == 1  # unchanged — no new call made


@pytest.mark.asyncio
async def test_timeout_then_successful_retry():
    wrapped = _FakeProvider()

    call_count = 0

    async def slow_then_fast(text):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await asyncio.sleep(1.0)  # exceeds the 0.2s timeout
        return _resp()

    wrapped.embed.side_effect = slow_then_fast
    provider = ResilientEmbeddingProvider(wrapped, _make_settings())

    result = await provider.embed("hello")

    assert result.embedding == [0.1, 0.2, 0.3, 0.4]
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_exhaustion_raises():
    wrapped = _FakeProvider()
    wrapped.embed.side_effect = httpx.ConnectError("still down")
    cfg = _make_settings(embedding_retry_max_attempts=2, embedding_breaker_failure_threshold=5)
    provider = ResilientEmbeddingProvider(wrapped, cfg)

    with pytest.raises(httpx.ConnectError):
        await provider.embed("hello")

    assert wrapped.embed.await_count == 2  # both attempts used


@pytest.mark.asyncio
async def test_non_transient_error_raises_without_retry():
    wrapped = _FakeProvider()
    wrapped.embed.side_effect = ValueError("bad input")
    cfg = _make_settings(embedding_retry_max_attempts=3, embedding_breaker_failure_threshold=5)
    provider = ResilientEmbeddingProvider(wrapped, cfg)

    with pytest.raises(ValueError):
        await provider.embed("hello")

    assert wrapped.embed.await_count == 1  # no retry for non-transient errors


@pytest.mark.asyncio
async def test_metric_increments_on_timeout(monkeypatch):
    from providers import embedding_resilience

    calls = []
    monkeypatch.setattr(
        embedding_resilience.embedding_fallback_counter,
        "add",
        lambda amount, attrs=None: calls.append((amount, attrs)),
    )

    wrapped = _FakeProvider()

    async def always_slow(text):
        await asyncio.sleep(1.0)

    wrapped.embed.side_effect = always_slow
    cfg = _make_settings(embedding_retry_max_attempts=2, embedding_breaker_failure_threshold=5)
    provider = ResilientEmbeddingProvider(wrapped, cfg)

    with pytest.raises(asyncio.TimeoutError):
        await provider.embed("hello")

    reasons = [attrs["reason"] for _, attrs in calls]
    assert reasons.count("timeout") == 2


@pytest.mark.asyncio
async def test_metric_increments_on_circuit_open(monkeypatch):
    from providers import embedding_resilience

    calls = []
    monkeypatch.setattr(
        embedding_resilience.embedding_fallback_counter,
        "add",
        lambda amount, attrs=None: calls.append((amount, attrs)),
    )

    wrapped = _FakeProvider()
    wrapped.embed.side_effect = httpx.ConnectError("boom")
    cfg = _make_settings(embedding_breaker_failure_threshold=1, embedding_retry_max_attempts=1)
    provider = ResilientEmbeddingProvider(wrapped, cfg)

    with pytest.raises(httpx.ConnectError):
        await provider.embed("first")
    with pytest.raises(CircuitOpenError):
        await provider.embed("second")

    reasons = [attrs["reason"] for _, attrs in calls]
    assert "breaker_open" in reasons


@pytest.mark.asyncio
async def test_embed_batch_wraps_whole_call_not_per_item():
    wrapped = _FakeProvider()
    wrapped.embed_batch.side_effect = httpx.ConnectError("down")
    cfg = _make_settings(embedding_retry_max_attempts=2, embedding_breaker_failure_threshold=5)
    provider = ResilientEmbeddingProvider(wrapped, cfg)

    with pytest.raises(httpx.ConnectError):
        await provider.embed_batch(["a", "b", "c"])

    # Retried as a whole batch call, not once per item: 2 attempts total.
    assert wrapped.embed_batch.await_count == 2


@pytest.mark.asyncio
async def test_health_check_not_breaker_gated():
    wrapped = _FakeProvider()
    wrapped.health_check.return_value = True
    cfg = _make_settings(embedding_breaker_failure_threshold=1, embedding_retry_max_attempts=1)
    provider = ResilientEmbeddingProvider(wrapped, cfg)

    # Trip the breaker via a failed embed() call.
    wrapped.embed.side_effect = httpx.ConnectError("boom")
    with pytest.raises(httpx.ConnectError):
        await provider.embed("x")

    # health_check() is not gated by the breaker.
    assert await provider.health_check() is True
    wrapped.health_check.assert_awaited_once()


def test_provider_name_and_dimensions_delegate():
    wrapped = _FakeProvider()
    provider = ResilientEmbeddingProvider(wrapped, _make_settings())

    assert provider.provider_name == "fake"
    assert provider.dimensions == 4
