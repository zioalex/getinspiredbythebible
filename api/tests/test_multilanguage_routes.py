"""
Integration tests for multilanguage support in scripture routes and prompts.

Tests cover:
- Bug 1: normalize_book_name() at API boundaries — localized URL book name
          (e.g., "Juan", "Jean") is translated to English before the DB query.
- Bug 2: Source attribution in system prompt is localized (not hardcoded English).
- Bug 3: localized_book field returned in verse and chapter API responses.

All 6 non-English translations are covered:
  Italian (ita1927), German (schlachter), Spanish (valera),
  French (ls1910), Portuguese (almeida), Arabic (arabicsv).
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_verse(english_book: str, translation: str, chapter: int = 3, verse: int = 16):
    """Return a MagicMock that quacks like a Verse ORM object."""
    mock = MagicMock()
    mock.reference = f"{english_book} {chapter}:{verse}"
    mock.text = "Some verse text for testing."
    mock.book.name = english_book
    mock.chapter_number = chapter
    mock.verse_number = verse
    mock.translation = translation
    return mock


# ---------------------------------------------------------------------------
# Bug 1 — normalize_book_name() called at verse endpoint
# ---------------------------------------------------------------------------


class TestNormalizeBookNameAtVerseEndpoint:
    """
    Localized book name in the URL path is normalized to English before the
    DB query. Tests that clicking "Juan 3:16" (Spanish) sends the correct
    English query to ScriptureRepository.get_verse().
    """

    @pytest.mark.parametrize(
        "localized_book, english_book, translation",
        [
            # Italian
            ("Giovanni", "John", "ita1927"),
            ("Genesi", "Genesis", "ita1927"),
            # German
            ("Johannes", "John", "schlachter"),
            ("1. Mose", "Genesis", "schlachter"),
            # Spanish
            ("Juan", "John", "valera"),
            ("Génesis", "Genesis", "valera"),
            # French
            ("Jean", "John", "ls1910"),
            ("Genèse", "Genesis", "ls1910"),
            # Portuguese
            ("João", "John", "almeida"),
            ("Gênesis", "Genesis", "almeida"),
            # Arabic
            ("يوحنا", "John", "arabicsv"),
            ("تكوين", "Genesis", "arabicsv"),
            # English pass-through (must not be double-translated)
            ("John", "John", "kjv"),
            ("Genesis", "Genesis", "kjv"),
        ],
    )
    @pytest.mark.asyncio
    async def test_verse_endpoint_normalizes_book_name(
        self, localized_book, english_book, translation
    ):
        """Localized book name in URL is normalized to English before DB lookup."""
        from routes.scripture import get_verse

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()
        mock_verse = _make_mock_verse(english_book, translation)

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_verse = AsyncMock(return_value=mock_verse)
            mock_repo_cls.return_value = mock_repo

            await get_verse(localized_book, 3, 16, mock_db, mock_embedding, translation)

        # The DB must always receive the English canonical name
        mock_repo.get_verse.assert_awaited_once_with(english_book, 3, 16, translation=translation)


# ---------------------------------------------------------------------------
# Bug 1 — normalize_book_name() called at chapter endpoint
# ---------------------------------------------------------------------------


class TestNormalizeBookNameAtChapterEndpoint:
    """Same normalization requirement for GET /chapter/{book}/{chapter}."""

    @pytest.mark.parametrize(
        "localized_book, english_book, translation",
        [
            ("Giovanni", "John", "ita1927"),
            ("1. Mose", "Genesis", "schlachter"),
            ("Juan", "John", "valera"),
            ("Jean", "John", "ls1910"),
            ("João", "John", "almeida"),
            ("يوحنا", "John", "arabicsv"),
            # English pass-through
            ("John", "John", "kjv"),
        ],
    )
    @pytest.mark.asyncio
    async def test_chapter_endpoint_normalizes_book_name(
        self, localized_book, english_book, translation
    ):
        """Localized book name in URL is normalized to English before DB lookup."""
        from routes.scripture import get_chapter

        mock_db = AsyncMock()
        mock_verse = _make_mock_verse(english_book, translation, chapter=3, verse=1)

        with (
            patch("routes.scripture.ScriptureRepository") as mock_repo_cls,
            patch("routes.scripture.get_localized_book_name", return_value=localized_book),
            patch(
                "routes.scripture.get_translation_info",
                return_value={"name": "Test Translation"},
            ),
        ):
            mock_repo = AsyncMock()
            mock_repo.get_chapter_verses = AsyncMock(return_value=[mock_verse])
            mock_repo_cls.return_value = mock_repo

            await get_chapter(localized_book, 3, mock_db, translation)

        # The DB must always receive the English canonical name
        mock_repo.get_chapter_verses.assert_awaited_once_with(
            english_book, 3, translation=translation
        )


# ---------------------------------------------------------------------------
# Bug 1 — 404 still works with localized name
# ---------------------------------------------------------------------------


class TestNormalizeBookNameNotFoundErrors:
    """After normalization, a 404 is raised when the verse/chapter is missing."""

    @pytest.mark.asyncio
    async def test_verse_not_found_after_normalization(self):
        """A localized book name that normalizes but has no matching verse → 404."""
        from fastapi import HTTPException

        from routes.scripture import get_verse

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_verse = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(HTTPException) as exc_info:
                # "Juan" normalizes to "John", but the mock returns None
                await get_verse("Juan", 99, 99, mock_db, mock_embedding, "valera")

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_chapter_not_found_after_normalization(self):
        """A localized book name that normalizes but has no chapter → 404."""
        from fastapi import HTTPException

        from routes.scripture import get_chapter

        mock_db = AsyncMock()

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_chapter_verses = AsyncMock(return_value=[])
            mock_repo_cls.return_value = mock_repo

            with pytest.raises(HTTPException) as exc_info:
                await get_chapter("Jean", 99, mock_db, "ls1910")

            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Bug 3 — localized_book field in verse endpoint response
# ---------------------------------------------------------------------------


class TestLocalizedBookInVerseResponse:
    """
    GET /verse/{book}/{chapter}/{verse} must return a localized_book field
    with the translation-specific book name.
    """

    @pytest.mark.parametrize(
        "english_book, translation, expected_localized",
        [
            ("John", "ita1927", "Giovanni"),
            ("John", "schlachter", "Johannes"),
            ("John", "valera", "Juan"),
            ("John", "ls1910", "Jean"),
            ("John", "almeida", "João"),
            ("John", "arabicsv", "يوحنا"),
            # English translations keep the English name
            ("John", "kjv", "John"),
            ("John", "web", "John"),
        ],
    )
    @pytest.mark.asyncio
    async def test_localized_book_field_in_response(
        self, english_book, translation, expected_localized
    ):
        """Verse response includes localized_book matching the translation."""
        from routes.scripture import get_verse

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()
        mock_verse = _make_mock_verse(english_book, translation)

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_verse = AsyncMock(return_value=mock_verse)
            mock_repo_cls.return_value = mock_repo

            result = await get_verse(english_book, 3, 16, mock_db, mock_embedding, translation)

        assert "localized_book" in result
        assert result["localized_book"] == expected_localized

    @pytest.mark.asyncio
    async def test_verse_response_includes_all_required_fields(self):
        """Verse API response has reference, text, book, localized_book, chapter, verse."""
        from routes.scripture import get_verse

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()
        mock_verse = _make_mock_verse("John", "valera")

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_verse = AsyncMock(return_value=mock_verse)
            mock_repo_cls.return_value = mock_repo

            result = await get_verse("Juan", 3, 16, mock_db, mock_embedding, "valera")

        for field in ("reference", "text", "book", "localized_book", "chapter", "verse"):
            assert field in result, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Bug 3 — localized_book field in chapter endpoint response
# ---------------------------------------------------------------------------


class TestLocalizedBookInChapterResponse:
    """
    GET /chapter/{book}/{chapter} must return a localized_book field in the
    chapter-level response and in each verse entry.
    """

    @pytest.mark.parametrize(
        "english_book, translation, expected_localized",
        [
            ("John", "ita1927", "Giovanni"),
            ("John", "schlachter", "Johannes"),
            ("John", "valera", "Juan"),
            ("John", "ls1910", "Jean"),
            ("John", "almeida", "João"),
            ("John", "arabicsv", "يوحنا"),
            ("John", "kjv", "John"),
        ],
    )
    @pytest.mark.asyncio
    async def test_chapter_response_localized_book(
        self, english_book, translation, expected_localized
    ):
        """Chapter response has a localized_book field matching the translation."""
        from routes.scripture import get_chapter

        mock_db = AsyncMock()
        mock_verse = _make_mock_verse(english_book, translation, chapter=3, verse=1)

        # ScriptureRepository is mocked; get_localized_book_name uses the real implementation
        with (
            patch("routes.scripture.ScriptureRepository") as mock_repo_cls,
            patch(
                "routes.scripture.get_translation_info",
                return_value={"name": "Test Translation"},
            ),
        ):
            mock_repo = AsyncMock()
            mock_repo.get_chapter_verses = AsyncMock(return_value=[mock_verse])
            mock_repo_cls.return_value = mock_repo

            result = await get_chapter(english_book, 3, mock_db, translation)

        assert result.localized_book == expected_localized

    @pytest.mark.asyncio
    async def test_chapter_verse_entries_have_localized_book(self):
        """Each verse in the chapter response has a localized_book field."""
        from routes.scripture import get_chapter

        mock_db = AsyncMock()
        mock_verse = _make_mock_verse("John", "valera", chapter=3, verse=16)

        with (
            patch("routes.scripture.ScriptureRepository") as mock_repo_cls,
            patch(
                "routes.scripture.get_translation_info",
                return_value={"name": "Reina Valera"},
            ),
        ):
            mock_repo = AsyncMock()
            mock_repo.get_chapter_verses = AsyncMock(return_value=[mock_verse])
            mock_repo_cls.return_value = mock_repo

            result = await get_chapter("John", 3, mock_db, "valera")

        assert len(result.verses) == 1
        verse_entry = result.verses[0]
        assert "localized_book" in verse_entry
        assert verse_entry["localized_book"] == "Juan"


# ---------------------------------------------------------------------------
# Bug 3 — VerseResult model has localized_book field
# ---------------------------------------------------------------------------


class TestVerseResultModel:
    """VerseResult Pydantic model must expose localized_book as an optional field."""

    def test_verse_result_has_localized_book_field(self):
        from scripture.search import VerseResult

        vr = VerseResult(
            reference="John 3:16",
            text="For God so loved the world...",
            book="John",
            localized_book="Juan",
            chapter=3,
            verse=16,
            translation="valera",
        )
        assert vr.localized_book == "Juan"

    def test_verse_result_localized_book_optional(self):
        """localized_book defaults to None (backwards-compatible)."""
        from scripture.search import VerseResult

        vr = VerseResult(
            reference="John 3:16",
            text="For God so loved the world...",
            book="John",
            chapter=3,
            verse=16,
        )
        assert vr.localized_book is None

    @pytest.mark.parametrize(
        "translation, expected_localized",
        [
            ("ita1927", "Giovanni"),
            ("schlachter", "Johannes"),
            ("valera", "Juan"),
            ("ls1910", "Jean"),
            ("almeida", "João"),
            ("arabicsv", "يوحنا"),
            ("kjv", "John"),
        ],
    )
    def test_verse_result_localized_book_values(self, translation, expected_localized):
        """VerseResult accepts correct localized book names for each translation."""
        from scripture.search import VerseResult

        vr = VerseResult(
            reference="John 3:16",
            text="For God so loved the world...",
            book="John",
            localized_book=expected_localized,
            chapter=3,
            verse=16,
            translation=translation,
        )
        assert vr.localized_book == expected_localized


# ---------------------------------------------------------------------------
# Bug 3 — Search results include localized_book
# ---------------------------------------------------------------------------


class TestSearchResultsLocalizedBook:
    """
    GET /scripture/search must include localized_book in each VerseResult
    so the right pane can display the correct localized header.
    """

    @pytest.mark.asyncio
    async def test_search_returns_localized_book_in_verse_results(self):
        """Semantic search results have localized_book for each verse."""
        from routes.scripture import search_scripture
        from scripture.search import SearchResults, VerseResult

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()

        spanish_verse = VerseResult(
            reference="Juan 3:16",
            text="Porque de tal manera amó Dios al mundo...",
            book="John",
            localized_book="Juan",
            chapter=3,
            verse=16,
            translation="valera",
            similarity=0.95,
        )
        mock_results = SearchResults(
            query="amor de Dios",
            verses=[spanish_verse],
            passages=[],
        )

        with patch("routes.scripture.ScriptureSearchService") as mock_service_cls:
            mock_service = AsyncMock()
            mock_service.search = AsyncMock(return_value=mock_results)
            mock_service_cls.return_value = mock_service

            result = await search_scripture(
                q="amor de Dios",
                max_verses=5,
                max_passages=2,
                translation="valera",
                db=mock_db,
                embedding=mock_embedding,
            )

        assert len(result.verses) == 1
        assert result.verses[0].localized_book == "Juan"
        assert result.verses[0].reference == "Juan 3:16"


# ---------------------------------------------------------------------------
# Bug 2 — Localized source attribution in system prompt
# ---------------------------------------------------------------------------


class TestLocalizedSourceAttribution:
    """
    get_system_prompt() must not inject English source-attribution examples
    for non-English languages. Each language gets its own example text.
    """

    @pytest.mark.parametrize(
        "language_code, expected_fragment, not_expected_fragment",
        [
            # Spanish must have Spanish examples
            ("es", "Biblia", "This is from the Bible, specifically"),
            # French must have French examples
            ("fr", "Bible", "This is from the Bible, specifically"),
            # Portuguese must have Portuguese examples
            ("pt", "Bíblia", "This is from the Bible, specifically"),
            # Arabic must have Arabic examples
            ("ar", "الكتاب المقدس", "This is from the Bible, specifically"),
            # Italian must have Italian examples
            ("it", "Bibbia", "This is from the Bible, specifically"),
            # German must have German examples
            ("de", "Bibel", "This is from the Bible, specifically"),
            # English should keep English examples
            ("en", "This is from the Bible, specifically", None),
        ],
    )
    def test_source_attribution_is_localized(
        self, language_code, expected_fragment, not_expected_fragment
    ):
        from chat.prompts import get_system_prompt

        prompt = get_system_prompt(language_code)
        assert (
            expected_fragment in prompt
        ), f"Expected '{expected_fragment}' in {language_code} prompt"
        if not_expected_fragment:
            assert (
                not_expected_fragment not in prompt
            ), f"English phrase '{not_expected_fragment}' must NOT appear in {language_code} prompt"

    def test_unknown_language_falls_back_to_english(self):
        """An unknown language code falls back to English examples."""
        from chat.prompts import get_system_prompt

        prompt = get_system_prompt("zz")  # non-existent locale
        assert "This is from the Bible, specifically" in prompt

    def test_no_language_code_falls_back_to_english(self):
        """None language code falls back to English examples."""
        from chat.prompts import get_system_prompt

        prompt = get_system_prompt(None)
        assert "This is from the Bible, specifically" in prompt


# ---------------------------------------------------------------------------
# Regression — mock-based replacements for the two skipped tests in test_api.py
# ---------------------------------------------------------------------------


class TestVerseEndpointLocalizedBookMocked:
    """
    Mock-based versions of the skipped tests in test_api.py.
    Verifies localized_book is present for all six non-English translations.
    """

    @pytest.mark.parametrize(
        "english_book, translation, expected_localized",
        [
            ("Genesis", "ita1927", "Genesi"),
            ("Genesis", "schlachter", "1. Mose"),
            ("Genesis", "valera", "Génesis"),
            ("Genesis", "ls1910", "Genèse"),
            ("Genesis", "almeida", "Gênesis"),
            ("Genesis", "arabicsv", "تكوين"),
        ],
    )
    @pytest.mark.asyncio
    async def test_verse_endpoint_localized_book_all_translations(
        self, english_book, translation, expected_localized
    ):
        """Verse endpoint returns correct localized_book for all non-English translations."""
        from routes.scripture import get_verse

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()
        mock_verse = _make_mock_verse(english_book, translation, chapter=1, verse=1)

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_verse = AsyncMock(return_value=mock_verse)
            mock_repo_cls.return_value = mock_repo

            result = await get_verse(english_book, 1, 1, mock_db, mock_embedding, translation)

        assert result["localized_book"] == expected_localized
        assert result["book"] == english_book  # canonical name also present


class TestChapterEndpointLocalizedBookMocked:
    """
    Mock-based versions of the skipped chapter tests in test_api.py.
    Verifies localized_book is present for all six non-English translations.
    """

    @pytest.mark.parametrize(
        "english_book, translation, expected_localized",
        [
            ("Genesis", "ita1927", "Genesi"),
            ("Genesis", "schlachter", "1. Mose"),
            ("Genesis", "valera", "Génesis"),
            ("Genesis", "ls1910", "Genèse"),
            ("Genesis", "almeida", "Gênesis"),
            ("Genesis", "arabicsv", "تكوين"),
        ],
    )
    @pytest.mark.asyncio
    async def test_chapter_endpoint_localized_book_all_translations(
        self, english_book, translation, expected_localized
    ):
        """Chapter endpoint returns correct localized_book for all non-English translations."""
        from routes.scripture import get_chapter

        mock_db = AsyncMock()
        mock_verse = _make_mock_verse(english_book, translation, chapter=1, verse=1)

        with (
            patch("routes.scripture.ScriptureRepository") as mock_repo_cls,
            patch(
                "routes.scripture.get_translation_info",
                return_value={"name": "Test Translation"},
            ),
        ):
            mock_repo = AsyncMock()
            mock_repo.get_chapter_verses = AsyncMock(return_value=[mock_verse])
            mock_repo_cls.return_value = mock_repo

            result = await get_chapter(english_book, 1, mock_db, translation)

        assert result.localized_book == expected_localized


# ---------------------------------------------------------------------------
# Edge cases — English input is never double-translated
# ---------------------------------------------------------------------------


class TestEnglishPassThrough:
    """English book names must not be altered by normalize_book_name()."""

    @pytest.mark.parametrize(
        "book, translation",
        [
            ("John", "kjv"),
            ("Genesis", "kjv"),
            ("Revelation", "web"),
            ("1 Corinthians", "kjv"),
        ],
    )
    @pytest.mark.asyncio
    async def test_english_book_unchanged_at_verse_endpoint(self, book, translation):
        """English book names pass through normalize_book_name() unchanged."""
        from routes.scripture import get_verse

        mock_db = AsyncMock()
        mock_embedding = AsyncMock()
        mock_verse = _make_mock_verse(book, translation)

        with patch("routes.scripture.ScriptureRepository") as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_verse = AsyncMock(return_value=mock_verse)
            mock_repo_cls.return_value = mock_repo

            await get_verse(book, 3, 16, mock_db, mock_embedding, translation)

        # The DB must be called with the same name (not modified)
        mock_repo.get_verse.assert_awaited_once_with(book, 3, 16, translation=translation)
