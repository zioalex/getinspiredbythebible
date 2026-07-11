"""Runtime readiness cache for Bible translations.

A translation is "ready" only when it has a full set of verses AND embeddings in
the vector DB, so semantic search actually works for it. Default resolution
(``utils.language``) consults this cache so a language's default is never a
translation that has not finished loading/embedding yet: an unready default is
skipped in favour of the next ready translation for that language, and the guard
self-heals once seeding completes (the cache is refreshed periodically).

This module is intentionally dependency-free (stdlib only). It must NOT import
``utils.language`` or ``scripture`` — ``scripture.coverage`` imports
``utils.language`` and ``utils.language`` imports this module, so importing
either here would create a cycle. The async DB refresh lives in
``scripture.coverage.refresh_ready_translations`` and writes into this cache.
"""

from __future__ import annotations

import threading
import time

# "Ready" matches the loader's ✅ READY definition (scripts/load_bible.py
# print_status_report): a full Bible of verses, nearly all of them embedded.
READY_MIN_VERSES = 30_000
READY_MIN_EMBED_RATIO = 0.95

# How long a cached ready-set is considered fresh. The background refresh in
# api/main.py re-populates on this cadence, so a newly-seeded translation
# becomes usable without a redeploy.
READY_TTL_SECONDS = 300.0

_lock = threading.Lock()
# None => unknown / never populated (callers must fall back to the static
# default, NOT treat every translation as unready).
_ready: frozenset[str] | None = None
_fetched_at: float = 0.0


def compute_ready(coverage: list[dict]) -> set[str]:
    """Return the translation codes that are fully loaded + embedded.

    Args:
        coverage: rows as returned by
            ``ScriptureRepository.get_translation_coverage()`` — dicts with
            ``"translation"``, ``"total_verses"``, ``"verses_with_embeddings"``.
    """
    ready: set[str] = set()
    for row in coverage:
        total = row.get("total_verses") or 0
        embedded = row.get("verses_with_embeddings") or 0
        if total >= READY_MIN_VERSES and embedded >= READY_MIN_EMBED_RATIO * total:
            ready.add(row["translation"])
    return ready


def set_ready_translations(codes: set[str]) -> None:
    """Atomically publish a new ready-set snapshot (immutable, so readers never
    observe a partially-updated set)."""
    global _ready, _fetched_at
    snapshot = frozenset(codes)
    with _lock:
        _ready = snapshot
        _fetched_at = time.monotonic()


def get_ready_translations() -> frozenset[str] | None:
    """Return the cached ready-set, or ``None`` if it has never been populated.

    ``None`` means "unknown" — callers should use their configured default
    rather than assuming nothing is ready.
    """
    return _ready


def is_stale() -> bool:
    """True if the cache is unpopulated or older than ``READY_TTL_SECONDS``."""
    if _ready is None:
        return True
    return (time.monotonic() - _fetched_at) >= READY_TTL_SECONDS


def reset() -> None:
    """Clear the cache. Test helper — resets module state to 'unknown'."""
    global _ready, _fetched_at
    with _lock:
        _ready = None
        _fetched_at = 0.0
