"""
Scripture Search Service - Combines semantic search with scripture data.
"""

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from providers import EmbeddingProvider
from utils.book_names import get_localized_book_name

from .repository import ScriptureRepository


class VerseResult(BaseModel):
    """Search result for a verse."""

    reference: str
    text: str
    book: str
    chapter: int
    verse: int
    translation: str | None = None
    similarity: float | None = None

    class Config:
        from_attributes = True


class PassageResult(BaseModel):
    """Search result for a passage."""

    title: str
    reference: str
    text: str
    topics: list[str] | None = None
    similarity: float | None = None

    class Config:
        from_attributes = True


class SearchResults(BaseModel):
    """Combined search results."""

    query: str
    verses: list[VerseResult]
    passages: list[PassageResult]


class ScriptureSearchService:
    """
    Service for searching scripture using semantic similarity.

    Combines embedding generation with database queries for
    intelligent scripture discovery.
    """

    def __init__(self, session: AsyncSession, embedding_provider: EmbeddingProvider):
        self.repo = ScriptureRepository(session)
        self.embedding_provider = embedding_provider

    def _get_localized_reference(self, verse) -> str:
        """Get verse reference with localized book name based on translation."""
        localized_book = get_localized_book_name(verse.book.name, verse.translation)
        return f"{localized_book} {verse.chapter_number}:{verse.verse_number}"

    async def search(
        self,
        query: str,
        max_verses: int = 5,
        max_passages: int = 2,
        similarity_threshold: float = 0.4,
        translation: str | None = None,
    ) -> SearchResults:
        """
        Search for relevant scripture based on a natural language query.

        Args:
            query: Natural language query (e.g., "I'm feeling anxious")
            max_verses: Maximum number of verses to return
            max_passages: Maximum number of passages to return
            similarity_threshold: Minimum similarity score (0-1)
            translation: Optional translation code to filter by (e.g., 'kjv', 'ita1927')

        Returns:
            SearchResults with matching verses and passages
        """
        # Generate embedding for the query
        embedding_response = await self.embedding_provider.embed(query)
        query_embedding = embedding_response.embedding

        # Search verses
        verse_results = await self.repo.search_verses_semantic(
            query_embedding=query_embedding,
            limit=max_verses,
            similarity_threshold=similarity_threshold,
            translation=translation,
        )

        verses = [
            VerseResult(
                reference=self._get_localized_reference(verse),
                text=verse.text,
                book=verse.book.name,
                chapter=verse.chapter_number,
                verse=verse.verse_number,
                translation=verse.translation,
                similarity=round(similarity, 3),
            )
            for verse, similarity in verse_results
        ]

        # Search passages
        passage_results = await self.repo.search_passages_semantic(
            query_embedding=query_embedding,
            limit=max_passages,
            similarity_threshold=similarity_threshold,
        )

        passages = [
            PassageResult(
                title=passage.title,
                reference=passage.reference,
                text=passage.text,
                topics=passage.topics.split(",") if passage.topics else None,
                similarity=round(similarity, 3),
            )
            for passage, similarity in passage_results
        ]

        return SearchResults(query=query, verses=verses, passages=passages)

    async def get_verse(self, book: str, chapter: int, verse: int) -> VerseResult | None:
        """Get a specific verse by reference."""
        result = await self.repo.get_verse(book, chapter, verse)
        if not result:
            return None

        return VerseResult(
            reference=result.reference,
            text=result.text,
            book=result.book.name,
            chapter=result.chapter_number,
            verse=result.verse_number,
        )

    async def get_verse_range(
        self, book: str, chapter: int, start_verse: int, end_verse: int
    ) -> list[VerseResult]:
        """Get a range of verses."""
        results = await self.repo.get_verses_in_range(book, chapter, start_verse, end_verse)

        return [
            VerseResult(
                reference=v.reference,
                text=v.text,
                book=v.book.name,
                chapter=v.chapter_number,
                verse=v.verse_number,
            )
            for v in results
        ]

    async def get_context(
        self, book: str, chapter: int, verse: int, context_size: int = 2
    ) -> list[VerseResult]:
        """
        Get a verse with surrounding context.

        Args:
            book: Book name
            chapter: Chapter number
            verse: Verse number
            context_size: Number of verses before and after

        Returns:
            List of verses including context
        """
        start = max(1, verse - context_size)
        end = verse + context_size

        return await self.get_verse_range(book, chapter, start, end)

    async def text_search(self, query: str, limit: int = 20) -> list[VerseResult]:
        """Simple text-based search."""
        results = await self.repo.search_verses_text(query, limit)

        return [
            VerseResult(
                reference=v.reference,
                text=v.text,
                book=v.book.name,
                chapter=v.chapter_number,
                verse=v.verse_number,
            )
            for v in results
        ]
