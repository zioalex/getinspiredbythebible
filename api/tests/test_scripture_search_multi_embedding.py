"""
Tests for ScriptureSearchService multi-embedding search (BITB-018.1).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from scripture.search import ScriptureSearchService, SearchResults


def _make_mock_verse(
    verse_id: int,
    book: str = "John",
    chapter: int = 3,
    verse: int = 16,
    text: str = "For God so loved...",
    translation: str = "kjv",
):
    """Create a mock Verse object with an id."""
    mock_verse = MagicMock()
    mock_verse.id = verse_id
    mock_verse.book = MagicMock()
    mock_verse.book.name = book
    mock_verse.chapter_number = chapter
    mock_verse.verse_number = verse
    mock_verse.text = text
    mock_verse.translation = translation
    mock_verse.reference = f"{book} {chapter}:{verse}"
    mock_verse.embedding = [0.1] * 1024
    return mock_verse


def _make_search_service():
    """Create a ScriptureSearchService with mocked dependencies."""
    session = AsyncMock()
    embedding_provider = AsyncMock()
    service = ScriptureSearchService(session, embedding_provider)
    return service, embedding_provider


class TestSearchVersesWithEmbeddings:
    """Tests for ScriptureSearchService._search_verses_with_embeddings()."""

    @pytest.mark.asyncio
    async def test_single_embedding_delegates_to_repo(self):
        """Single embedding should call repo.search_verses_semantic once."""
        service, _ = _make_search_service()
        mock_verse = _make_mock_verse(1)

        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(return_value=[(mock_verse, 0.85)])

        result = await service._search_verses_with_embeddings(
            query_embeddings=[[0.1] * 1024],
            max_verses=5,
            similarity_threshold=0.35,
            translation=None,
        )

        assert len(result) == 1
        service.repo.search_verses_semantic.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_embeddings_merge_results(self):
        """Multiple embeddings should merge results from all searches."""
        service, _ = _make_search_service()
        verse1 = _make_mock_verse(1, text="Verse from query 1")
        verse2 = _make_mock_verse(2, text="Verse from query 2")

        service.repo = AsyncMock()
        # First call returns verse1, second call returns verse2
        service.repo.search_verses_semantic = AsyncMock(
            side_effect=[
                [(verse1, 0.80)],
                [(verse2, 0.75)],
            ]
        )

        result = await service._search_verses_with_embeddings(
            query_embeddings=[[0.1] * 1024, [0.2] * 1024],
            max_verses=5,
            similarity_threshold=0.35,
            translation=None,
        )

        assert len(result) == 2
        assert service.repo.search_verses_semantic.call_count == 2

    @pytest.mark.asyncio
    async def test_deduplication_keeps_max_similarity(self):
        """Deduplication should keep the highest similarity score for duplicate verses."""
        service, _ = _make_search_service()
        # Same verse ID returned from both searches with different similarity
        verse_low = _make_mock_verse(42, text="Same verse lower score")
        verse_high = _make_mock_verse(42, text="Same verse higher score")

        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(
            side_effect=[
                [(verse_low, 0.60)],  # First query: verse 42 at 0.60
                [(verse_high, 0.85)],  # Second query: same verse 42 at 0.85
            ]
        )

        result = await service._search_verses_with_embeddings(
            query_embeddings=[[0.1] * 1024, [0.2] * 1024],
            max_verses=5,
            similarity_threshold=0.35,
            translation=None,
        )

        # Should deduplicate — only 1 result
        assert len(result) == 1
        # Should keep the highest similarity (0.85)
        _, similarity = result[0]
        assert similarity == 0.85

    @pytest.mark.asyncio
    async def test_results_sorted_by_similarity_descending(self):
        """Results should be sorted by similarity descending."""
        service, _ = _make_search_service()
        verse_a = _make_mock_verse(1)
        verse_b = _make_mock_verse(2)
        verse_c = _make_mock_verse(3)

        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(
            side_effect=[
                [(verse_a, 0.70), (verse_b, 0.50)],
                [(verse_c, 0.90), (verse_b, 0.55)],  # verse_b appears again with higher score
            ]
        )

        result = await service._search_verses_with_embeddings(
            query_embeddings=[[0.1] * 1024, [0.2] * 1024],
            max_verses=5,
            similarity_threshold=0.35,
            translation=None,
        )

        # verse_c (0.90) > verse_a (0.70) > verse_b (0.55)
        assert len(result) == 3
        similarities = [s for _, s in result]
        assert similarities == sorted(similarities, reverse=True)

    @pytest.mark.asyncio
    async def test_respects_max_verses_limit(self):
        """Result count should not exceed max_verses."""
        service, _ = _make_search_service()
        verses = [_make_mock_verse(i) for i in range(1, 8)]  # 7 unique verses

        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(
            side_effect=[
                [(v, 0.8 - i * 0.05) for i, v in enumerate(verses[:4])],
                [(v, 0.7 - i * 0.05) for i, v in enumerate(verses[3:])],  # verse 4 overlaps
            ]
        )

        result = await service._search_verses_with_embeddings(
            query_embeddings=[[0.1] * 1024, [0.2] * 1024],
            max_verses=5,  # limit to 5
            similarity_threshold=0.35,
            translation=None,
        )

        assert len(result) <= 5


class TestSearchWithExtraEmbeddings:
    """Tests for ScriptureSearchService.search() with extra_embeddings parameter."""

    @pytest.mark.asyncio
    async def test_search_without_extra_embeddings_unchanged(self):
        """search() without extra_embeddings should work exactly as before."""
        service, embedding = _make_search_service()

        mock_embedding_response = MagicMock()
        mock_embedding_response.embedding = [0.1] * 1024
        embedding.embed = AsyncMock(return_value=mock_embedding_response)

        mock_verse = _make_mock_verse(1)
        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(return_value=[(mock_verse, 0.85)])
        service.repo.search_passages_semantic = AsyncMock(return_value=[])

        results = await service.search("I feel anxious")

        assert isinstance(results, SearchResults)
        assert len(results.verses) == 1

    @pytest.mark.asyncio
    async def test_search_with_extra_embeddings_uses_multi_search(self):
        """search() with extra_embeddings should pass both to _search_verses_with_embeddings."""
        service, embedding = _make_search_service()

        mock_embedding_response = MagicMock()
        mock_embedding_response.embedding = [0.1] * 1024
        embedding.embed = AsyncMock(return_value=mock_embedding_response)

        verse1 = _make_mock_verse(1, text="Original query verse")
        verse2 = _make_mock_verse(2, text="Expanded query verse")

        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(
            side_effect=[
                [(verse1, 0.80)],  # original embedding search
                [(verse2, 0.75)],  # expanded embedding search
            ]
        )
        service.repo.search_passages_semantic = AsyncMock(return_value=[])

        extra_embedding = [0.2] * 1024
        results = await service.search(
            "I am anxious",
            extra_embeddings=[extra_embedding],
        )

        # Should have results from both searches
        assert len(results.verses) == 2

    @pytest.mark.asyncio
    async def test_search_deduplicates_across_embeddings(self):
        """search() should deduplicate verses found by multiple embeddings."""
        service, embedding = _make_search_service()

        mock_embedding_response = MagicMock()
        mock_embedding_response.embedding = [0.1] * 1024
        embedding.embed = AsyncMock(return_value=mock_embedding_response)

        # Same verse found by both embeddings
        verse_same = _make_mock_verse(99)

        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(
            side_effect=[
                [(verse_same, 0.70)],
                [(verse_same, 0.85)],  # same verse, higher similarity
            ]
        )
        service.repo.search_passages_semantic = AsyncMock(return_value=[])

        results = await service.search(
            "peace",
            extra_embeddings=[[0.2] * 1024],
        )

        # Should be deduplicated to 1
        assert len(results.verses) == 1
        assert results.verses[0].similarity == 0.85  # Should keep max


class TestQueryExpansionIntegration:
    """Integration test cases for query expansion themes."""

    def test_expansion_test_cases_fixture_exists(self, tmp_path):
        """Verify test cases fixture structure is valid."""
        # This tests the fixture file format
        import json
        import os

        fixture_path = os.path.join(
            os.path.dirname(__file__), "fixtures", "query_expansion_test_cases.json"
        )
        assert os.path.exists(fixture_path), f"Fixture file not found: {fixture_path}"

        with open(fixture_path) as f:
            data = json.load(f)

        assert "test_cases" in data
        assert len(data["test_cases"]) >= 5

        for case in data["test_cases"]:
            assert "query" in case
            assert "language" in case
            assert "expected_themes" in case
            assert len(case["expected_themes"]) >= 2
