"""
In-process cache for the embedding call path (BITB-057 Phase 2).

Wraps any concrete EmbeddingProvider (typically ResilientEmbeddingProvider) so
repeated `embed()` calls for the same text are served from memory instead of
paying another round-trip to the embedding provider. There is no Redis (or any
other shared cache) anywhere in this stack — see providers/embedding_resilience.py
and the BITB-057 story notes — so this is intentionally in-process only; a hit
on one replica does not help another.

Composed as the OUTERMOST layer over ResilientEmbeddingProvider (see
factory.py::create_embedding_provider): a cache hit must not consult the
circuit breaker or pay the request timeout, and usefully still serves while
the breaker is open during a sustained outage.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict

from config import Settings
from utils.logging_config import get_logger
from utils.metrics import embedding_cache_counter

from .base import EmbeddingProvider, EmbeddingResponse

logger = get_logger(__name__)

__all__ = ["CachingEmbeddingProvider"]


class _LruTtlCache:
    """Small in-process LRU cache with per-entry TTL, guarded by a lock.

    Mirrors utils/circuit_breaker.py's self-contained, Lock-guarded style
    rather than adding a caching dependency for ~30 lines of logic.
    """

    def __init__(self, max_size: int, ttl_seconds: float):
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._entries: OrderedDict[str, tuple[float, EmbeddingResponse]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> EmbeddingResponse | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() >= expires_at:
                del self._entries[key]
                return None
            # Refresh recency for LRU eviction.
            self._entries.move_to_end(key)
            return value

    def put(self, key: str, value: EmbeddingResponse) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic() + self._ttl_seconds, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_size:
                self._entries.popitem(last=False)


class CachingEmbeddingProvider(EmbeddingProvider):
    """
    Caches `embed()` results for the wrapped provider, keyed on the exact
    query text (namespaced by provider name + dimensions so a config change
    can't serve a stale-shaped vector).

    `embed_batch()` is never cached — batch calls are bulk ingestion with low
    repeat value and would otherwise bloat the cache with one-off vectors.
    """

    def __init__(self, wrapped: EmbeddingProvider, settings: Settings):
        self._wrapped = wrapped
        self._settings = settings
        self._cache = _LruTtlCache(
            max_size=settings.embedding_cache_max_size,
            ttl_seconds=settings.embedding_cache_ttl_seconds,
        )

    @property
    def provider_name(self) -> str:
        return self._wrapped.provider_name

    @property
    def dimensions(self) -> int:
        return self._wrapped.dimensions

    def _cache_key(self, text: str) -> str:
        # Exact bytes, not normalized — a different string must never hit a
        # cached vector for another string.
        return f"{self._wrapped.provider_name}:{self._wrapped.dimensions}:{text}"

    async def embed(self, text: str) -> EmbeddingResponse:
        if not self._settings.embedding_cache_enabled:
            return await self._wrapped.embed(text)

        key = self._cache_key(text)
        cached = self._cache.get(key)
        if cached is not None:
            embedding_cache_counter.add(1, {"result": "hit"})
            return cached

        embedding_cache_counter.add(1, {"result": "miss"})
        result = await self._wrapped.embed(text)
        self._cache.put(key, result)
        return result

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResponse]:
        """Never cached — see class docstring."""
        return await self._wrapped.embed_batch(texts)

    async def health_check(self) -> bool:
        """Delegate health checks to the wrapped provider (not cache-gated)."""
        return await self._wrapped.health_check()

    async def close(self) -> None:
        """Close the wrapped provider's resources."""
        await self._wrapped.close()
