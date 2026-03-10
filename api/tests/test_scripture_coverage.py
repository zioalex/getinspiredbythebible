"""
Tests for scripture repository and search modules.

Coverage targets:
- scripture/repository.py: get_all_books, get_book_by_name, get_book_by_id,
  get_verse, get_verses_in_range, get_chapter_verses, search_verses_text,
  search_verses_semantic, get_passage_by_id, search_passages_semantic,
  get_all_topics, search_topics_semantic, get_stats
- scripture/search.py: ScriptureSearchService.search, get_verse, get_verse_range,
  get_context, text_search, _get_localized_reference
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripture.repository import ScriptureRepository
from scripture.search import (
    PassageResult,
    ScriptureSearchService,
    SearchResults,
    VerseResult,
)

# ==================== Helpers ====================


def _make_mock_session():
    """Create a mock AsyncSession."""
    session = AsyncMock()
    return session


def _make_mock_verse(
    book_name="John",
    chapter=3,
    verse=16,
    text="For God so loved...",
    translation: str | None = "kjv",
):
    """Create a mock Verse object."""
    mock_verse = MagicMock()
    mock_verse.book = MagicMock()
    mock_verse.book.name = book_name
    mock_verse.chapter_number = chapter
    mock_verse.verse_number = verse
    mock_verse.text = text
    mock_verse.translation = translation
    mock_verse.reference = f"{book_name} {chapter}:{verse}"
    mock_verse.embedding = [0.1] * 10
    return mock_verse


def _make_mock_book(name="Genesis", abbreviation="Gen", testament="old", position=1, book_id=1):
    """Create a mock Book object."""
    mock_book = MagicMock()
    mock_book.id = book_id
    mock_book.name = name
    mock_book.abbreviation = abbreviation
    mock_book.testament = testament
    mock_book.position = position
    return mock_book


def _make_mock_passage(
    title="The Lord's Prayer",
    text="Our Father...",
    start_chapter=6,
    start_verse=9,
    end_chapter=6,
    end_verse=13,
    topics="prayer,faith",
):
    """Create a mock Passage object."""
    mock_passage = MagicMock()
    mock_passage.title = title
    mock_passage.text = text
    mock_passage.start_chapter = start_chapter
    mock_passage.start_verse = start_verse
    mock_passage.end_chapter = end_chapter
    mock_passage.end_verse = end_verse
    mock_passage.topics = topics
    mock_passage.book = MagicMock()
    mock_passage.book.name = "Matthew"
    mock_passage.reference = f"Matthew {start_chapter}:{start_verse}-{end_verse}"
    mock_passage.embedding = [0.1] * 10
    return mock_passage


# ==================== Repository Tests ====================


class TestScriptureRepositoryInit:
    """Tests for ScriptureRepository initialization."""

    def test_init(self):
        session = _make_mock_session()
        repo = ScriptureRepository(session)
        assert repo.session is session


class TestGetAllBooks:
    """Tests for ScriptureRepository.get_all_books()."""

    @pytest.mark.asyncio
    async def test_returns_books(self):
        session = _make_mock_session()
        mock_books = [_make_mock_book("Genesis"), _make_mock_book("Exodus", "Exo", "old", 2, 2)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_books
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        books = await repo.get_all_books()

        assert len(books) == 2
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_empty(self):
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        books = await repo.get_all_books()

        assert len(books) == 0


class TestGetBookByName:
    """Tests for ScriptureRepository.get_book_by_name()."""

    @pytest.mark.asyncio
    async def test_found(self):
        session = _make_mock_session()
        mock_book = _make_mock_book("Genesis")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_book
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        book = await repo.get_book_by_name("Genesis")

        assert book is not None
        assert book.name == "Genesis"

    @pytest.mark.asyncio
    async def test_not_found(self):
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        book = await repo.get_book_by_name("NotABook")

        assert book is None

    @pytest.mark.asyncio
    async def test_localized_name(self):
        session = _make_mock_session()
        mock_book = _make_mock_book("Genesis")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_book
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        # "Genesi" is Italian for Genesis - normalize_book_name should handle it
        await repo.get_book_by_name("Genesi")
        session.execute.assert_awaited_once()


class TestGetBookById:
    """Tests for ScriptureRepository.get_book_by_id()."""

    @pytest.mark.asyncio
    async def test_found(self):
        session = _make_mock_session()
        mock_book = _make_mock_book("Genesis")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_book
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        book = await repo.get_book_by_id(1)

        assert book is not None
        assert book.name == "Genesis"

    @pytest.mark.asyncio
    async def test_not_found(self):
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        book = await repo.get_book_by_id(9999)

        assert book is None


class TestGetVerse:
    """Tests for ScriptureRepository.get_verse()."""

    @pytest.mark.asyncio
    async def test_found(self):
        session = _make_mock_session()
        mock_verse = _make_mock_verse()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_verse
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verse = await repo.get_verse("John", 3, 16)

        assert verse is not None
        assert verse.text == "For God so loved..."

    @pytest.mark.asyncio
    async def test_not_found(self):
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verse = await repo.get_verse("NotABook", 1, 1)

        assert verse is None

    @pytest.mark.asyncio
    async def test_with_translation(self):
        session = _make_mock_session()
        mock_verse = _make_mock_verse(translation="ita1927")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_verse
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verse = await repo.get_verse("Giovanni", 3, 16, translation="ita1927")

        assert verse is not None
        assert verse.translation == "ita1927"


class TestGetVersesInRange:
    """Tests for ScriptureRepository.get_verses_in_range()."""

    @pytest.mark.asyncio
    async def test_returns_range(self):
        session = _make_mock_session()
        mock_verses = [
            _make_mock_verse(verse=16),
            _make_mock_verse(verse=17),
            _make_mock_verse(verse=18),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_verses
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verses = await repo.get_verses_in_range("John", 3, 16, 18)

        assert len(verses) == 3

    @pytest.mark.asyncio
    async def test_empty_range(self):
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verses = await repo.get_verses_in_range("NotABook", 1, 1, 5)

        assert len(verses) == 0

    @pytest.mark.asyncio
    async def test_with_translation(self):
        session = _make_mock_session()
        mock_verses = [_make_mock_verse(translation="kjv")]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_verses
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verses = await repo.get_verses_in_range("John", 3, 16, 16, translation="kjv")

        assert len(verses) == 1


class TestGetChapterVerses:
    """Tests for ScriptureRepository.get_chapter_verses()."""

    @pytest.mark.asyncio
    async def test_returns_verses(self):
        session = _make_mock_session()
        mock_verses = [_make_mock_verse(verse=i) for i in range(1, 4)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_verses
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verses = await repo.get_chapter_verses("John", 3)

        assert len(verses) == 3

    @pytest.mark.asyncio
    async def test_empty_chapter(self):
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verses = await repo.get_chapter_verses("NotABook", 1)

        assert len(verses) == 0

    @pytest.mark.asyncio
    async def test_with_translation(self):
        session = _make_mock_session()
        mock_verses = [_make_mock_verse(translation="ita1927")]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_verses
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verses = await repo.get_chapter_verses("Giovanni", 3, translation="ita1927")

        assert len(verses) == 1


class TestSearchVersesText:
    """Tests for ScriptureRepository.search_verses_text()."""

    @pytest.mark.asyncio
    async def test_returns_results(self):
        session = _make_mock_session()
        mock_verses = [_make_mock_verse(text="God so loved")]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_verses
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verses = await repo.search_verses_text("love")

        assert len(verses) == 1

    @pytest.mark.asyncio
    async def test_no_results(self):
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        verses = await repo.search_verses_text("xyznonexistent")

        assert len(verses) == 0


class TestSearchVersesSemantic:
    """Tests for ScriptureRepository.search_verses_semantic()."""

    @pytest.mark.asyncio
    async def test_returns_results(self):
        session = _make_mock_session()
        mock_verse = _make_mock_verse()

        mock_row = MagicMock()
        mock_row.Verse = mock_verse
        mock_row.similarity = 0.85

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        results = await repo.search_verses_semantic([0.1] * 1024, limit=5)

        assert len(results) == 1
        verse, similarity = results[0]
        assert verse == mock_verse
        assert similarity == 0.85

    @pytest.mark.asyncio
    async def test_no_results(self):
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        results = await repo.search_verses_semantic([0.1] * 1024)

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_with_translation_filter(self):
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        await repo.search_verses_semantic([0.1] * 1024, translation="kjv")

        session.execute.assert_awaited_once()


class TestGetPassageById:
    """Tests for ScriptureRepository.get_passage_by_id()."""

    @pytest.mark.asyncio
    async def test_found(self):
        session = _make_mock_session()
        mock_passage = _make_mock_passage()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_passage
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        passage = await repo.get_passage_by_id(1)

        assert passage is not None
        assert passage.title == "The Lord's Prayer"

    @pytest.mark.asyncio
    async def test_not_found(self):
        session = _make_mock_session()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        passage = await repo.get_passage_by_id(9999)

        assert passage is None


class TestSearchPassagesSemantic:
    """Tests for ScriptureRepository.search_passages_semantic()."""

    @pytest.mark.asyncio
    async def test_returns_results(self):
        session = _make_mock_session()
        mock_passage = _make_mock_passage()

        mock_row = MagicMock()
        mock_row.Passage = mock_passage
        mock_row.similarity = 0.75

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        results = await repo.search_passages_semantic([0.1] * 1024)

        assert len(results) == 1
        passage, similarity = results[0]
        assert passage.title == "The Lord's Prayer"
        assert similarity == 0.75


class TestGetAllTopics:
    """Tests for ScriptureRepository.get_all_topics()."""

    @pytest.mark.asyncio
    async def test_returns_topics(self):
        session = _make_mock_session()
        mock_topic = MagicMock()
        mock_topic.name = "Love"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_topic]
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        topics = await repo.get_all_topics()

        assert len(topics) == 1
        assert topics[0].name == "Love"


class TestSearchTopicsSemantic:
    """Tests for ScriptureRepository.search_topics_semantic()."""

    @pytest.mark.asyncio
    async def test_returns_results(self):
        session = _make_mock_session()
        mock_topic = MagicMock()
        mock_topic.name = "Love"

        mock_row = MagicMock()
        mock_row.Topic = mock_topic
        mock_row.similarity = 0.9

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        session.execute = AsyncMock(return_value=mock_result)

        repo = ScriptureRepository(session)
        results = await repo.search_topics_semantic([0.1] * 1024)

        assert len(results) == 1
        topic, similarity = results[0]
        assert topic.name == "Love"
        assert similarity == 0.9


class TestGetStats:
    """Tests for ScriptureRepository.get_stats()."""

    @pytest.mark.asyncio
    async def test_returns_stats(self):
        session = _make_mock_session()

        # Each execute call returns a different count
        counts = [66, 31102, 30000, 150]
        mock_results = []
        for count in counts:
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = count
            mock_results.append(mock_result)

        session.execute = AsyncMock(side_effect=mock_results)

        repo = ScriptureRepository(session)
        stats = await repo.get_stats()

        assert stats["books"] == 66
        assert stats["verses"] == 31102
        assert stats["verses_with_embeddings"] == 30000
        assert stats["passages"] == 150


# ==================== Search Service Tests ====================


def _make_search_service():
    """Create a ScriptureSearchService with mocked dependencies."""
    session = AsyncMock()
    embedding_provider = AsyncMock()
    service = ScriptureSearchService(session, embedding_provider)
    return service, embedding_provider


class TestScriptureSearchServiceInit:
    """Tests for ScriptureSearchService initialization."""

    def test_init(self):
        session = AsyncMock()
        embedding_provider = AsyncMock()
        service = ScriptureSearchService(session, embedding_provider)
        assert service.embedding_provider is embedding_provider
        assert service.repo is not None


class TestGetLocalizedReference:
    """Tests for ScriptureSearchService._get_localized_reference()."""

    def test_english(self):
        service, _ = _make_search_service()
        mock_verse = _make_mock_verse("John", 3, 16, translation="kjv")
        result = service._get_localized_reference(mock_verse)
        assert "3:16" in result

    def test_italian(self):
        service, _ = _make_search_service()
        mock_verse = _make_mock_verse("John", 3, 16, translation="ita1927")
        with patch("scripture.search.get_localized_book_name", return_value="Giovanni"):
            result = service._get_localized_reference(mock_verse)
        assert "Giovanni 3:16" == result


class TestScriptureSearchServiceSearch:
    """Tests for ScriptureSearchService.search()."""

    @pytest.mark.asyncio
    async def test_search_returns_results(self):
        service, embedding = _make_search_service()

        mock_embedding_response = MagicMock()
        mock_embedding_response.embedding = [0.1] * 1024
        embedding.embed = AsyncMock(return_value=mock_embedding_response)

        mock_verse = _make_mock_verse()

        # Mock the repository methods
        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(return_value=[(mock_verse, 0.85)])
        service.repo.search_passages_semantic = AsyncMock(return_value=[])

        results = await service.search("love")

        assert isinstance(results, SearchResults)
        assert results.query == "love"
        assert len(results.verses) == 1
        assert results.verses[0].similarity == 0.85

    @pytest.mark.asyncio
    async def test_search_with_passages(self):
        service, embedding = _make_search_service()

        mock_embedding_response = MagicMock()
        mock_embedding_response.embedding = [0.1] * 1024
        embedding.embed = AsyncMock(return_value=mock_embedding_response)

        mock_passage = _make_mock_passage()

        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(return_value=[])
        service.repo.search_passages_semantic = AsyncMock(return_value=[(mock_passage, 0.7)])

        results = await service.search("prayer")

        assert len(results.passages) == 1
        assert results.passages[0].title == "The Lord's Prayer"
        assert results.passages[0].similarity == 0.7

    @pytest.mark.asyncio
    async def test_search_with_translation_filter(self):
        service, embedding = _make_search_service()

        mock_embedding_response = MagicMock()
        mock_embedding_response.embedding = [0.1] * 1024
        embedding.embed = AsyncMock(return_value=mock_embedding_response)

        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(return_value=[])
        service.repo.search_passages_semantic = AsyncMock(return_value=[])

        await service.search("love", translation="kjv")

        # Verify translation was passed to search
        service.repo.search_verses_semantic.assert_awaited_once()
        call_kwargs = service.repo.search_verses_semantic.call_args
        assert (
            call_kwargs.kwargs.get("translation") == "kjv"
            or call_kwargs[1].get("translation") == "kjv"
        )

    @pytest.mark.asyncio
    async def test_search_passage_with_topics(self):
        service, embedding = _make_search_service()

        mock_embedding_response = MagicMock()
        mock_embedding_response.embedding = [0.1] * 1024
        embedding.embed = AsyncMock(return_value=mock_embedding_response)

        mock_passage = _make_mock_passage(topics="prayer,faith,devotion")

        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(return_value=[])
        service.repo.search_passages_semantic = AsyncMock(return_value=[(mock_passage, 0.8)])

        results = await service.search("prayer")

        assert results.passages[0].topics == ["prayer", "faith", "devotion"]

    @pytest.mark.asyncio
    async def test_search_passage_without_topics(self):
        service, embedding = _make_search_service()

        mock_embedding_response = MagicMock()
        mock_embedding_response.embedding = [0.1] * 1024
        embedding.embed = AsyncMock(return_value=mock_embedding_response)

        mock_passage = _make_mock_passage(topics=None)

        service.repo = AsyncMock()
        service.repo.search_verses_semantic = AsyncMock(return_value=[])
        service.repo.search_passages_semantic = AsyncMock(return_value=[(mock_passage, 0.8)])

        results = await service.search("prayer")

        assert results.passages[0].topics is None


class TestScriptureSearchServiceGetVerse:
    """Tests for ScriptureSearchService.get_verse()."""

    @pytest.mark.asyncio
    async def test_found(self):
        service, _ = _make_search_service()
        mock_verse = _make_mock_verse()

        service.repo = AsyncMock()
        service.repo.get_verse = AsyncMock(return_value=mock_verse)

        result = await service.get_verse("John", 3, 16)

        assert result is not None
        assert isinstance(result, VerseResult)
        assert result.book == "John"
        assert result.chapter == 3
        assert result.verse == 16

    @pytest.mark.asyncio
    async def test_not_found(self):
        service, _ = _make_search_service()

        service.repo = AsyncMock()
        service.repo.get_verse = AsyncMock(return_value=None)

        result = await service.get_verse("NotABook", 1, 1)

        assert result is None

    @pytest.mark.asyncio
    async def test_with_translation(self):
        service, _ = _make_search_service()
        mock_verse = _make_mock_verse(translation="ita1927")

        service.repo = AsyncMock()
        service.repo.get_verse = AsyncMock(return_value=mock_verse)

        result = await service.get_verse("Giovanni", 3, 16, translation="ita1927")

        assert result is not None
        assert result.translation == "ita1927"

    @pytest.mark.asyncio
    async def test_localized_book_synodal(self):
        """get_verse() must populate localized_book for non-English translations."""
        service, _ = _make_search_service()
        mock_verse = _make_mock_verse(book_name="John", translation="synodal")

        service.repo = AsyncMock()
        service.repo.get_verse = AsyncMock(return_value=mock_verse)

        result = await service.get_verse("John", 3, 16, translation="synodal")

        assert result is not None
        assert result.localized_book is not None
        assert result.localized_book == "Иоанн"

    @pytest.mark.asyncio
    async def test_localized_book_kjv_returns_english(self):
        """get_verse() localized_book falls back to English for KJV (no mapping)."""
        service, _ = _make_search_service()
        mock_verse = _make_mock_verse(book_name="John", translation="kjv")

        service.repo = AsyncMock()
        service.repo.get_verse = AsyncMock(return_value=mock_verse)

        result = await service.get_verse("John", 3, 16, translation="kjv")

        assert result is not None
        assert result.localized_book == "John"


class TestScriptureSearchServiceGetVerseRange:
    """Tests for ScriptureSearchService.get_verse_range()."""

    @pytest.mark.asyncio
    async def test_returns_range(self):
        service, _ = _make_search_service()
        mock_verses = [_make_mock_verse(verse=i) for i in range(16, 19)]

        service.repo = AsyncMock()
        service.repo.get_verses_in_range = AsyncMock(return_value=mock_verses)

        results = await service.get_verse_range("John", 3, 16, 18)

        assert len(results) == 3
        assert all(isinstance(r, VerseResult) for r in results)

    @pytest.mark.asyncio
    async def test_empty_range(self):
        service, _ = _make_search_service()

        service.repo = AsyncMock()
        service.repo.get_verses_in_range = AsyncMock(return_value=[])

        results = await service.get_verse_range("NotABook", 1, 1, 5)

        assert results == []

    @pytest.mark.asyncio
    async def test_localized_book_synodal(self):
        """get_verse_range() must populate localized_book for non-English translations."""
        service, _ = _make_search_service()
        mock_verses = [
            _make_mock_verse(book_name="John", verse=i, translation="synodal")
            for i in range(16, 19)
        ]

        service.repo = AsyncMock()
        service.repo.get_verses_in_range = AsyncMock(return_value=mock_verses)

        results = await service.get_verse_range("John", 3, 16, 18, translation="synodal")

        assert len(results) == 3
        assert all(r.localized_book == "Иоанн" for r in results)

    @pytest.mark.asyncio
    async def test_localized_book_kjv_returns_english(self):
        """get_verse_range() localized_book is English for KJV (no mapping)."""
        service, _ = _make_search_service()
        mock_verses = [
            _make_mock_verse(book_name="John", verse=i, translation="kjv") for i in range(1, 3)
        ]

        service.repo = AsyncMock()
        service.repo.get_verses_in_range = AsyncMock(return_value=mock_verses)

        results = await service.get_verse_range("John", 1, 1, 2, translation="kjv")

        assert all(r.localized_book == "John" for r in results)


class TestScriptureSearchServiceGetContext:
    """Tests for ScriptureSearchService.get_context()."""

    @pytest.mark.asyncio
    async def test_returns_context(self):
        service, _ = _make_search_service()
        mock_verses = [_make_mock_verse(verse=i) for i in range(14, 19)]

        service.repo = AsyncMock()
        service.repo.get_verses_in_range = AsyncMock(return_value=mock_verses)

        results = await service.get_context("John", 3, 16, context_size=2)

        assert len(results) == 5
        # Should request verses 14-18 (16-2 to 16+2)
        service.repo.get_verses_in_range.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_context_clamps_to_verse_1(self):
        service, _ = _make_search_service()

        service.repo = AsyncMock()
        service.repo.get_verses_in_range = AsyncMock(return_value=[])

        await service.get_context("Genesis", 1, 1, context_size=3)

        # start should be max(1, 1-3) = 1, end = 1+3 = 4
        call_args = service.repo.get_verses_in_range.call_args
        assert call_args.args[2] == 1  # start_verse (positional)


class TestScriptureSearchServiceTextSearch:
    """Tests for ScriptureSearchService.text_search()."""

    @pytest.mark.asyncio
    async def test_returns_results(self):
        service, _ = _make_search_service()
        mock_verses = [_make_mock_verse(text="God so loved the world")]

        service.repo = AsyncMock()
        service.repo.search_verses_text = AsyncMock(return_value=mock_verses)

        results = await service.text_search("love")

        assert len(results) == 1
        assert isinstance(results[0], VerseResult)

    @pytest.mark.asyncio
    async def test_no_results(self):
        service, _ = _make_search_service()

        service.repo = AsyncMock()
        service.repo.search_verses_text = AsyncMock(return_value=[])

        results = await service.text_search("xyznonexistent")

        assert results == []

    @pytest.mark.asyncio
    async def test_localized_book_synodal(self):
        """text_search() must populate localized_book for non-English translations."""
        service, _ = _make_search_service()
        mock_verse = _make_mock_verse(book_name="John", translation="synodal")

        service.repo = AsyncMock()
        service.repo.search_verses_text = AsyncMock(return_value=[mock_verse])

        results = await service.text_search("возлюбил")

        assert len(results) == 1
        assert results[0].localized_book == "Иоанн"

    @pytest.mark.asyncio
    async def test_localized_book_no_translation_returns_english(self):
        """text_search() localized_book returns English when no translation set."""
        service, _ = _make_search_service()
        mock_verse = _make_mock_verse(book_name="John", translation=None)
        mock_verse.translation = None

        service.repo = AsyncMock()
        service.repo.search_verses_text = AsyncMock(return_value=[mock_verse])

        results = await service.text_search("love")

        assert len(results) == 1
        assert results[0].localized_book == "John"


# ==================== Pydantic Model Tests ====================


class TestVerseResult:
    """Tests for VerseResult Pydantic model."""

    def test_creation(self):
        vr = VerseResult(
            reference="John 3:16",
            text="For God so loved...",
            book="John",
            chapter=3,
            verse=16,
        )
        assert vr.reference == "John 3:16"
        assert vr.similarity is None
        assert vr.translation is None

    def test_with_similarity(self):
        vr = VerseResult(
            reference="John 3:16",
            text="For God so loved...",
            book="John",
            chapter=3,
            verse=16,
            similarity=0.85,
            translation="kjv",
        )
        assert vr.similarity == 0.85
        assert vr.translation == "kjv"


class TestPassageResult:
    """Tests for PassageResult Pydantic model."""

    def test_creation(self):
        pr = PassageResult(
            title="The Lord's Prayer",
            reference="Matthew 6:9-13",
            text="Our Father...",
        )
        assert pr.title == "The Lord's Prayer"
        assert pr.topics is None

    def test_with_topics(self):
        pr = PassageResult(
            title="The Lord's Prayer",
            reference="Matthew 6:9-13",
            text="Our Father...",
            topics=["prayer", "faith"],
        )
        assert pr.topics == ["prayer", "faith"]


class TestSearchResults:
    """Tests for SearchResults Pydantic model."""

    def test_creation(self):
        sr = SearchResults(query="love", verses=[], passages=[])
        assert sr.query == "love"
        assert sr.verses == []
        assert sr.passages == []
