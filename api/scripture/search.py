"""
Scripture Search Service - Combines semantic search with scripture data.
"""

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from providers import EmbeddingProvider
from utils.book_names import get_localized_book_name
from utils.logging_config import get_logger

from .repository import ScriptureRepository

logger = get_logger(__name__)


class VerseResult(BaseModel):
    """Search result for a verse."""

    reference: str
    text: str
    book: str
    localized_book: str | None = None
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

    async def _search_verses_with_embeddings(
        self,
        query_embeddings: list[list[float]],
        max_verses: int,
        similarity_threshold: float,
        translation: str | None,
    ) -> list[tuple]:  # list of (verse, similarity) tuples
        """Search verses using one or more query embeddings, merge and deduplicate results."""
        if len(query_embeddings) == 1:
            return await self.repo.search_verses_semantic(
                query_embedding=query_embeddings[0],
                limit=max_verses,
                similarity_threshold=similarity_threshold,
                translation=translation,
            )

        # Multiple embeddings: search each, merge with max similarity deduplication
        all_results: dict[int, tuple] = {}  # verse_id -> (verse, similarity)
        for embedding in query_embeddings:
            results = await self.repo.search_verses_semantic(
                query_embedding=embedding,
                limit=max_verses * 2,  # fetch more to ensure good coverage
                similarity_threshold=similarity_threshold,
                translation=translation,
            )
            for verse, similarity in results:
                vid = verse.id
                if vid not in all_results or similarity > all_results[vid][1]:
                    all_results[vid] = (verse, similarity)

        # Sort by similarity descending, return top max_verses
        merged = sorted(all_results.values(), key=lambda x: x[1], reverse=True)
        return merged[:max_verses]

    async def search(
        self,
        query: str,
        max_verses: int = 5,
        max_passages: int = 2,
        similarity_threshold: float = 0.4,
        translation: str | None = None,
        extra_embeddings: list[list[float]] | None = None,  # NEW: for query expansion
    ) -> SearchResults:
        """
        Search for relevant scripture based on a natural language query.

        Args:
            query: Natural language query (e.g., "I'm feeling anxious")
            max_verses: Maximum number of verses to return
            max_passages: Maximum number of passages to return
            similarity_threshold: Minimum similarity score (0-1)
            translation: Optional translation code to filter by (e.g., 'kjv', 'ita1927')
            extra_embeddings: Optional additional embeddings for multi-embedding search

        Returns:
            SearchResults with matching verses and passages
        """
        # Generate embedding for the query
        embedding_response = await self.embedding_provider.embed(query)
        query_embedding = embedding_response.embedding

        # Build list of embeddings (original + any expansion embeddings)
        query_embeddings = [query_embedding]
        if extra_embeddings:
            query_embeddings.extend(extra_embeddings)

        # Search verses using single or multi-embedding search
        verse_results = await self._search_verses_with_embeddings(
            query_embeddings=query_embeddings,
            max_verses=max_verses,
            similarity_threshold=similarity_threshold,
            translation=translation,
        )

        if extra_embeddings:
            logger.info(
                "Multi-embedding search completed",
                extra={
                    "num_embeddings": len(query_embeddings),
                    "total_results": len(verse_results),
                },
            )

        verses = [
            VerseResult(
                reference=verse.reference,  # always English: "John 3:16"
                text=verse.text,
                book=verse.book.name,
                localized_book=get_localized_book_name(verse.book.name, verse.translation),
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

    async def search_hybrid(
        self,
        query: str,
        max_verses: int = 5,
        max_passages: int = 2,
        similarity_threshold: float = 0.35,
        translation: str | None = None,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ) -> SearchResults:
        """
        Hybrid search combining semantic similarity and keyword matching.

        Args:
            query: Natural language query
            max_verses: Maximum number of verses to return
            max_passages: Maximum number of passages to return
            similarity_threshold: Minimum semantic similarity score (0-1)
            translation: Optional translation code to filter by
            semantic_weight: Weight for semantic score (0.0-1.0)
            keyword_weight: Weight for keyword score (0.0-1.0)

        Returns:
            SearchResults with matching verses and passages
        """
        # Generate embedding for the query
        embedding_response = await self.embedding_provider.embed(query)
        query_embedding = embedding_response.embedding

        # Hybrid search verses
        verse_results = await self.repo.search_verses_hybrid(
            query_text=query,
            query_embedding=query_embedding,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
            similarity_threshold=similarity_threshold,
            limit=max_verses,
            translation=translation,
        )

        logger.info(
            "Hybrid search completed",
            extra={
                "query": query[:100],
                "verses_found": len(verse_results),
                "semantic_weight": semantic_weight,
                "keyword_weight": keyword_weight,
            },
        )

        verses = [
            VerseResult(
                reference=self._get_localized_reference(verse),
                text=verse.text,
                book=verse.book.name,
                localized_book=get_localized_book_name(verse.book.name, verse.translation),
                chapter=verse.chapter_number,
                verse=verse.verse_number,
                translation=verse.translation,
                similarity=round(score, 3),
            )
            for verse, score in verse_results
        ]

        # Hybrid search passages
        passage_results = await self.repo.search_passages_hybrid(
            query_text=query,
            query_embedding=query_embedding,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
            similarity_threshold=similarity_threshold,
            limit=max_passages,
        )

        passages = [
            PassageResult(
                title=passage.title,
                reference=passage.reference,
                text=passage.text,
                topics=passage.topics.split(",") if passage.topics else None,
                similarity=round(score, 3),
            )
            for passage, score in passage_results
        ]

        return SearchResults(query=query, verses=verses, passages=passages)

    async def get_verse(
        self, book: str, chapter: int, verse: int, translation: str | None = None
    ) -> VerseResult | None:
        """Get a specific verse by reference, optionally filtered by translation."""
        result = await self.repo.get_verse(book, chapter, verse, translation)
        if not result:
            return None

        return VerseResult(
            reference=result.reference,
            text=result.text,
            book=result.book.name,
            localized_book=get_localized_book_name(result.book.name, result.translation),
            chapter=result.chapter_number,
            verse=result.verse_number,
            translation=result.translation,
        )

    async def get_verse_range(
        self,
        book: str,
        chapter: int,
        start_verse: int,
        end_verse: int,
        translation: str | None = None,
    ) -> list[VerseResult]:
        """Get a range of verses, optionally filtered by translation."""
        results = await self.repo.get_verses_in_range(
            book, chapter, start_verse, end_verse, translation
        )

        return [
            VerseResult(
                reference=v.reference,
                text=v.text,
                book=v.book.name,
                localized_book=get_localized_book_name(v.book.name, v.translation),
                chapter=v.chapter_number,
                verse=v.verse_number,
                translation=v.translation,
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
                localized_book=get_localized_book_name(
                    v.book.name, getattr(v, "translation", None)
                ),
                chapter=v.chapter_number,
                verse=v.verse_number,
            )
            for v in results
        ]
