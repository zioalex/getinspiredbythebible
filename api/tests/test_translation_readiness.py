"""Tests for the runtime translation-readiness guard.

Covers the readiness predicate (`compute_ready`), the cache accessors, and the
readiness-aware default resolution in `utils.language` — specifically that an
unready language default is skipped in favour of the next ready translation,
while a healthy or unknown default is never changed.
"""

import pytest

from utils import translation_readiness
from utils.language import get_translation_for_language, resolve_translation
from utils.translation_readiness import (
    READY_MIN_EMBED_RATIO,
    READY_MIN_VERSES,
    compute_ready,
    get_ready_translations,
    is_stale,
    set_ready_translations,
)


@pytest.fixture(autouse=True)
def _reset_readiness():
    """Isolate the module-level cache: start and end each test 'unknown'."""
    translation_readiness.reset()
    yield
    translation_readiness.reset()


# ---------------------------------------------------------------------------
# compute_ready predicate
# ---------------------------------------------------------------------------


def _row(code, total, embedded):
    return {"translation": code, "total_verses": total, "verses_with_embeddings": embedded}


def test_full_bible_fully_embedded_is_ready():
    ready = compute_ready([_row("kjv", 31102, 31102)])
    assert ready == {"kjv"}


def test_below_min_verses_not_ready():
    # e.g. a CI-mode load of only 1 Corinthians
    assert compute_ready([_row("kjv", 500, 500)]) == set()


def test_no_embeddings_not_ready():
    assert compute_ready([_row("luther1912", 31102, 0)]) == set()


def test_below_95pct_embedded_not_ready():
    below = int(READY_MIN_VERSES * 0.90)
    assert compute_ready([_row("x", READY_MIN_VERSES, below)]) == set()


def test_95pct_boundary_is_ready():
    at_ratio = int(READY_MIN_VERSES * READY_MIN_EMBED_RATIO)
    assert compute_ready([_row("x", READY_MIN_VERSES, at_ratio)]) == {"x"}
    assert compute_ready([_row("x", READY_MIN_VERSES, at_ratio - 1)]) == set()


def test_never_loaded_translation_absent():
    # A translation with no verses simply doesn't appear in coverage.
    assert "elberfelder1905" not in compute_ready([_row("kjv", 31102, 31102)])


def test_multiple_translations():
    ready = compute_ready(
        [
            _row("kjv", 31102, 31102),
            _row("luther1912", 31102, 31102),
            _row("hindi", 0, 0),
            _row("schlachter", 31102, 100),  # loaded but barely embedded
        ]
    )
    assert ready == {"kjv", "luther1912"}


# ---------------------------------------------------------------------------
# cache accessors
# ---------------------------------------------------------------------------


def test_cache_unknown_by_default():
    assert get_ready_translations() is None
    assert is_stale() is True


def test_set_and_get_snapshot_is_immutable():
    set_ready_translations({"kjv", "web"})
    snap = get_ready_translations()
    assert snap == frozenset({"kjv", "web"})
    assert isinstance(snap, frozenset)
    assert is_stale() is False


# ---------------------------------------------------------------------------
# readiness-aware default resolution (the guard)
# ---------------------------------------------------------------------------


def test_unknown_cache_uses_static_default():
    # No cache populated -> current behaviour: German default = luther1912.
    assert get_translation_for_language("de") == "luther1912"


def test_empty_ready_set_uses_static_default():
    set_ready_translations(set())
    assert get_translation_for_language("de") == "luther1912"


def test_unready_default_falls_back_to_next_ready():
    # Luther not ready, Schlachter ready -> German resolves to Schlachter.
    set_ready_translations({"schlachter"})
    assert get_translation_for_language("de") == "schlachter"


def test_ready_default_is_returned_unchanged():
    # Both ready -> the configured first (luther1912) is kept.
    set_ready_translations({"luther1912", "schlachter"})
    assert get_translation_for_language("de") == "luther1912"


def test_no_language_translation_ready_uses_static_default():
    # Cache populated but none of German's translations are ready.
    set_ready_translations({"kjv"})
    assert get_translation_for_language("de") == "luther1912"


def test_resolve_translation_respects_explicit_preference_even_if_unready():
    # An explicit, valid user choice is honoured regardless of readiness.
    set_ready_translations({"schlachter"})
    assert resolve_translation("luther1912", "de") == "luther1912"


def test_resolve_translation_uses_guard_for_language_default():
    set_ready_translations({"schlachter"})
    assert resolve_translation(None, "de") == "schlachter"
