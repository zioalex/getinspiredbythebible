"""
Tests for CachingEmbeddingProvider (BITB-057 Phase 2).

Mirrors the mocking approach used in test_embedding_resilience.py: mock the
wrapped provider's methods directly (no real network calls) and assert on
cache hit/miss/eviction/TTL behaviour and metric increments.
"""

import asyncio

import httpx
import pytest

from config import settings
from providers.base import EmbeddingResponse
from providers.embedding_cache import CachingEmbeddingProvider
from providers.embedding_resilience import ResilientEmbeddingProvider


def _make_settings(**overrides):
    defaults = dict(
        embedding_cache_enabled=True,
        embedding_cache_max_size=1024,
        embedding_cache_ttl_seconds=3600.0,
    )
    defaults.update(overrides)
    return settings.model_copy(update=defaults)


class _FakeProvider:
    """Minimal stand-in for a concrete EmbeddingProvider."""

    def __init__(self):
        self.provider_name = "fake"
        self.dimensions = 4
        self.embed_calls: list[str] = []
        self.embed_batch_calls: list[list[str]] = []
        self.health_check_calls = 0
        self.close_calls = 0

    async def embed(self, text: str) -> EmbeddingResponse:
        self.embed_calls.append(text)
        return _resp(text)

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResponse]:
        self.embed_batch_calls.append(texts)
        return [_resp(t) for t in texts]

    async def health_check(self) -> bool:
        self.health_check_calls += 1
        return True

    async def close(self) -> None:
        self.close_calls += 1


def _resp(text: str) -> EmbeddingResponse:
    # Deterministic per-text vector so distinct texts are distinguishable in assertions.
    return EmbeddingResponse(embedding=[float(len(text))], model="fake", provider="fake")


@pytest.mark.asyncio
async def test_miss_then_hit_calls_wrapped_once():
    wrapped = _FakeProvider()
    provider = CachingEmbeddingProvider(wrapped, _make_settings())

    first = await provider.embed("hello")
    second = await provider.embed("hello")

    assert first.embedding == second.embedding
    assert wrapped.embed_calls == ["hello"]  # only the miss reached the wrapped provider


@pytest.mark.asyncio
async def test_distinct_texts_both_miss():
    wrapped = _FakeProvider()
    provider = CachingEmbeddingProvider(wrapped, _make_settings())

    await provider.embed("hello")
    await provider.embed("world")

    assert wrapped.embed_calls == ["hello", "world"]


@pytest.mark.asyncio
async def test_ttl_expiry_reinvokes_wrapped():
    wrapped = _FakeProvider()
    provider = CachingEmbeddingProvider(wrapped, _make_settings(embedding_cache_ttl_seconds=0.05))

    await provider.embed("hello")
    await asyncio.sleep(0.1)
    await provider.embed("hello")

    assert wrapped.embed_calls == ["hello", "hello"]  # expired entry forced a re-fetch


@pytest.mark.asyncio
async def test_lru_eviction_at_max_size():
    wrapped = _FakeProvider()
    provider = CachingEmbeddingProvider(wrapped, _make_settings(embedding_cache_max_size=2))

    await provider.embed("a")
    await provider.embed("b")
    await provider.embed("c")  # evicts "a" (least recently used)

    await provider.embed("a")  # must miss again - was evicted
    assert wrapped.embed_calls == ["a", "b", "c", "a"]


@pytest.mark.asyncio
async def test_disabled_always_passes_through():
    wrapped = _FakeProvider()
    provider = CachingEmbeddingProvider(wrapped, _make_settings(embedding_cache_enabled=False))

    await provider.embed("hello")
    await provider.embed("hello")

    assert wrapped.embed_calls == ["hello", "hello"]  # cache never consulted


@pytest.mark.asyncio
async def test_embed_batch_never_cached():
    wrapped = _FakeProvider()
    provider = CachingEmbeddingProvider(wrapped, _make_settings())

    await provider.embed_batch(["a", "b"])
    await provider.embed_batch(["a", "b"])

    assert len(wrapped.embed_batch_calls) == 2  # both calls reached the wrapped provider


@pytest.mark.asyncio
async def test_metric_increments_hit_and_miss(monkeypatch):
    from providers import embedding_cache

    calls = []
    monkeypatch.setattr(
        embedding_cache.embedding_cache_counter,
        "add",
        lambda amount, attrs=None: calls.append((amount, attrs)),
    )

    wrapped = _FakeProvider()
    provider = CachingEmbeddingProvider(wrapped, _make_settings())

    await provider.embed("hello")  # miss
    await provider.embed("hello")  # hit

    results = [attrs["result"] for _, attrs in calls]
    assert results == ["miss", "hit"]


@pytest.mark.asyncio
async def test_cache_hit_bypasses_resilient_layer_and_survives_breaker_open():
    """Composition check: CachingEmbeddingProvider(ResilientEmbeddingProvider(fake))."""
    wrapped = _FakeProvider()
    resilient_cfg = settings.model_copy(
        update=dict(
            embedding_request_timeout=0.2,
            embedding_breaker_failure_threshold=1,
            embedding_breaker_cooldown_seconds=30.0,
            embedding_retry_max_attempts=1,
        )
    )
    resilient = ResilientEmbeddingProvider(wrapped, resilient_cfg)
    provider = CachingEmbeddingProvider(resilient, _make_settings())

    # Prime the cache with one successful call.
    await provider.embed("hello")
    assert wrapped.embed_calls == ["hello"]

    # Trip the breaker with a failing call for a different key.
    async def boom(text):
        raise httpx.ConnectError("down")

    wrapped.embed = boom
    with pytest.raises(httpx.ConnectError):
        await provider.embed("other")

    # The cached key still serves from cache without touching the (now-open) breaker.
    result = await provider.embed("hello")
    assert result.embedding == [float(len("hello"))]


def test_provider_name_and_dimensions_delegate():
    wrapped = _FakeProvider()
    provider = CachingEmbeddingProvider(wrapped, _make_settings())

    assert provider.provider_name == "fake"
    assert provider.dimensions == 4


@pytest.mark.asyncio
async def test_health_check_and_close_delegate():
    wrapped = _FakeProvider()
    provider = CachingEmbeddingProvider(wrapped, _make_settings())

    assert await provider.health_check() is True
    assert wrapped.health_check_calls == 1

    await provider.close()
    assert wrapped.close_calls == 1
