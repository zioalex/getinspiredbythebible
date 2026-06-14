"""Tests for the retrieval-eval metric + normalization core (BITB-043).

Pure functions, no database — runs in the standard backend-tests CI job.
"""

import pytest

from search_eval.metrics import mrr, precision_at_k, recall_at_k
from search_eval.models import GoldenCase
from search_eval.normalize import (
    RefMatcher,
    VerseKey,
    canonical_book,
    normalize_reference,
    parse_verse_key,
)

# ==================== Normalization ====================


class TestCanonicalBook:
    def test_psalm_singular_to_plural(self):
        assert canonical_book("Psalm") == "Psalms"
        assert canonical_book("Psalms") == "Psalms"

    def test_song_variants(self):
        assert canonical_book("Song of Songs") == "Song of Solomon"
        assert canonical_book("Song of Solomon") == "Song of Solomon"

    def test_revelation_variant(self):
        assert canonical_book("Revelations") == "Revelation"
        assert canonical_book("Revelation") == "Revelation"

    def test_localized_to_english(self):
        # Italian "Giovanni" -> "John" via utils.book_names
        assert canonical_book("Giovanni") == "John"

    def test_numbered_book_unchanged(self):
        assert canonical_book("1 Corinthians") == "1 Corinthians"

    def test_unknown_book_passthrough(self):
        assert canonical_book("Nonexistent") == "Nonexistent"


class TestNormalizeReference:
    def test_exact_verse(self):
        m = normalize_reference("Matthew 6:34")
        assert m == RefMatcher("Matthew", 6, frozenset({34}))

    def test_range_expands_inclusive(self):
        m = normalize_reference("Philippians 4:6-7")
        assert m == RefMatcher("Philippians", 4, frozenset({6, 7}))

    def test_chapter_only_is_wildcard(self):
        m = normalize_reference("Psalm 23")
        assert m == RefMatcher("Psalms", 23, None)

    def test_numbered_book_with_range(self):
        m = normalize_reference("1 Corinthians 13:4-7")
        assert m == RefMatcher("1 Corinthians", 13, frozenset({4, 5, 6, 7}))

    def test_reversed_range_is_normalized(self):
        m = normalize_reference("John 3:7-5")
        assert m == RefMatcher("John", 3, frozenset({5, 6, 7}))

    def test_whitespace_tolerant(self):
        assert normalize_reference("  John 3:16  ") == RefMatcher("John", 3, frozenset({16}))

    @pytest.mark.parametrize("bad", ["", "not a ref", "John", "12345", None])
    def test_unparseable_returns_none(self, bad):
        assert normalize_reference(bad) is None


class TestParseVerseKey:
    def test_single_verse(self):
        assert parse_verse_key("John 3:16") == VerseKey("John", 3, 16)

    def test_localized_book(self):
        assert parse_verse_key("Giovanni 3:16") == VerseKey("John", 3, 16)

    def test_range_takes_start(self):
        assert parse_verse_key("Philippians 4:6-7") == VerseKey("Philippians", 4, 6)

    def test_chapter_only_returns_none(self):
        assert parse_verse_key("Psalm 23") is None

    def test_garbage_returns_none(self):
        assert parse_verse_key("xyz") is None


class TestMatcher:
    def test_exact_matches_only_that_verse(self):
        m = RefMatcher("John", 3, frozenset({16}))
        assert m.matches(VerseKey("John", 3, 16))
        assert not m.matches(VerseKey("John", 3, 17))

    def test_chapter_only_matches_any_verse(self):
        m = RefMatcher("Psalms", 23, None)
        assert m.matches(VerseKey("Psalms", 23, 1))
        assert m.matches(VerseKey("Psalms", 23, 6))
        assert not m.matches(VerseKey("Psalms", 24, 1))

    def test_wrong_book_never_matches(self):
        m = RefMatcher("John", 3, None)
        assert not m.matches(VerseKey("Mark", 3, 16))


# ==================== Metrics ====================

# Shared ground truth: Matthew 6:34, Philippians 4:6-7 (range), Psalm 23 (chapter)
RELEVANT = [
    normalize_reference("Matthew 6:34"),
    normalize_reference("Philippians 4:6-7"),
    normalize_reference("Psalm 23"),
]


def _keys(*refs: str) -> list[VerseKey]:
    return [parse_verse_key(r) for r in refs]


class TestPrecisionAtK:
    def test_all_top5_relevant(self):
        ranked = _keys(
            "Matthew 6:34",
            "Philippians 4:6",
            "Philippians 4:7",
            "Psalms 23:1",
            "Psalms 23:4",
        )
        assert precision_at_k(ranked, RELEVANT, 5) == 1.0

    def test_no_hits(self):
        ranked = _keys("Genesis 1:1", "Exodus 2:2", "Leviticus 3:3")
        assert precision_at_k(ranked, RELEVANT, 5) == 0.0

    def test_partial_uses_k_denominator(self):
        # 2 relevant of top-5 slots -> 0.4 even though only 2 retrieved
        ranked = _keys("Matthew 6:34", "Psalms 23:2")
        assert precision_at_k(ranked, RELEVANT, 5) == pytest.approx(0.4)

    def test_range_member_counts_as_hit(self):
        ranked = _keys("Philippians 4:7")  # within the 6-7 range
        assert precision_at_k(ranked, RELEVANT, 1) == 1.0

    def test_k_zero_is_zero(self):
        assert precision_at_k(_keys("Matthew 6:34"), RELEVANT, 0) == 0.0


class TestRecallAtK:
    def test_all_matchers_covered(self):
        ranked = _keys("Matthew 6:34", "Philippians 4:6", "Psalms 23:1")
        assert recall_at_k(ranked, RELEVANT, 10) == 1.0

    def test_one_of_three(self):
        ranked = _keys("Matthew 6:34", "Genesis 1:1")
        assert recall_at_k(ranked, RELEVANT, 10) == pytest.approx(1 / 3)

    def test_chapter_matcher_covered_by_any_verse(self):
        ranked = _keys("Psalms 23:6")
        assert recall_at_k(ranked, RELEVANT, 10) == pytest.approx(1 / 3)

    def test_window_excludes_late_hits(self):
        # Only the 11th result is relevant -> not counted at k=10
        ranked = _keys(*[f"Genesis 1:{i}" for i in range(1, 11)]) + _keys("Matthew 6:34")
        assert recall_at_k(ranked, RELEVANT, 10) == 0.0

    def test_no_relevant_is_zero(self):
        assert recall_at_k(_keys("Matthew 6:34"), [], 10) == 0.0


class TestMRR:
    def test_first_position(self):
        assert mrr(_keys("Matthew 6:34", "Genesis 1:1"), RELEVANT) == 1.0

    def test_third_position(self):
        ranked = _keys("Genesis 1:1", "Exodus 2:2", "Psalms 23:1")
        assert mrr(ranked, RELEVANT) == pytest.approx(1 / 3)

    def test_no_hit_is_zero(self):
        assert mrr(_keys("Genesis 1:1", "Exodus 2:2"), RELEVANT) == 0.0

    def test_empty_retrieved_is_zero(self):
        assert mrr([], RELEVANT) == 0.0


# ==================== GoldenCase model ====================


class TestGoldenCase:
    def test_minimal_valid_case(self):
        case = GoldenCase(id="x", query="q", relevant_refs=["John 3:16"])
        assert case.language == "en"
        assert case.translation is None
        assert case.tags == []

    def test_relevant_matchers(self):
        case = GoldenCase(
            id="x",
            query="q",
            relevant_refs=["Matthew 6:34", "Philippians 4:6-7", "Psalm 23"],
        )
        assert case.relevant_matchers() == RELEVANT

    def test_rejects_empty_relevant_refs(self):
        with pytest.raises(Exception):
            GoldenCase(id="x", query="q", relevant_refs=[])

    def test_rejects_unparseable_ref(self):
        with pytest.raises(Exception):
            GoldenCase(id="x", query="q", relevant_refs=["not a reference"])
