"""
Scripture Repository - Database operations for Bible data.
"""

import time
from typing import Sequence

from opentelemetry.trace import Span
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from middleware.context import REQUEST_ID_CTX_VAR
from utils.book_names import normalize_book_name
from utils.logging_config import get_logger
from utils.telemetry import tracer

from .models import Book, Passage, Topic, Verse

logger = get_logger("scripture.repository")


def _set_common_span_attrs(span: Span, operation: str, translation: str | None) -> None:
    """Set standard span attributes common to all DB operations."""
    span.set_attribute("db.operation", operation)
    span.set_attribute("db.translation", translation or "all")
    request_id = REQUEST_ID_CTX_VAR.get("")
    if request_id:
        span.set_attribute("request_id", request_id)


def _record_duration(
    span: Span,
    start: float,
    operation: str,
    result_count: int,
    translation: str | None,
) -> None:
    """Record query duration on the span and emit slow query log if threshold exceeded."""
    duration_ms = (time.perf_counter() - start) * 1000
    span.set_attribute("db.duration_ms", round(duration_ms, 2))
    span.set_attribute("db.results.count", result_count)

    from utils.metrics import (
        db_query_duration_histogram,
        db_search_duration_histogram,
        db_slow_queries_counter,
    )

    if "semantic_search" in operation:
        db_search_duration_histogram.record(duration_ms)
    else:
        db_query_duration_histogram.record(duration_ms)

    if duration_ms > settings.slow_query_threshold_ms:
        db_slow_queries_counter.add(1)
        request_id = REQUEST_ID_CTX_VAR.get("")
        logger.warning(
            "Slow query detected",
            extra={
                "operation": operation,
                "duration_ms": round(duration_ms, 2),
                "result_count": result_count,
                "translation": translation or "all",
                "request_id": request_id or "none",
                "threshold_ms": settings.slow_query_threshold_ms,
            },
        )


class ScriptureRepository:
    """
    Repository for scripture database operations.

    Provides methods for querying Bible verses, books, and passages.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ==================== Books ====================

    async def get_all_books(self) -> Sequence[Book]:
        """Get all books in order."""
        result = await self.session.execute(select(Book).order_by(Book.position))
        return result.scalars().all()

    async def get_book_by_name(self, name: str) -> Book | None:
        """Get a book by its name (case-insensitive, supports localized names)."""
        # Normalize localized book names to English
        english_name = normalize_book_name(name)
        result = await self.session.execute(
            select(Book).where(func.lower(Book.name) == english_name.lower())
        )
        return result.scalar_one_or_none()

    async def get_book_by_id(self, book_id: int) -> Book | None:
        """Get a book by ID."""
        result = await self.session.execute(select(Book).where(Book.id == book_id))
        return result.scalar_one_or_none()

    # ==================== Verses ====================

    async def get_verse(
        self, book_name: str, chapter: int, verse: int, translation: str | None = None
    ) -> Verse | None:
        """Get a specific verse by reference, optionally filtered by translation."""
        # Normalize localized book names to English
        english_name = normalize_book_name(book_name)
        query = (
            select(Verse)
            .join(Book)
            .where(
                func.lower(Book.name) == english_name.lower(),
                Verse.chapter_number == chapter,
                Verse.verse_number == verse,
            )
        )

        if translation:
            query = query.where(Verse.translation == translation)

        query = query.options(selectinload(Verse.book))

        with tracer.start_as_current_span("db.get_verse") as span:
            _set_common_span_attrs(span, "get_verse", translation)
            start = time.perf_counter()
            result = await self.session.execute(query)
            verse_obj = result.scalar_one_or_none()
            _record_duration(span, start, "get_verse", 1 if verse_obj else 0, translation)
            return verse_obj

    async def get_verses_in_range(
        self,
        book_name: str,
        chapter: int,
        start_verse: int,
        end_verse: int,
        translation: str | None = None,
    ) -> Sequence[Verse]:
        """Get verses in a range (e.g., John 3:16-21), optionally filtered by translation."""
        # Normalize localized book names to English
        english_name = normalize_book_name(book_name)
        query = (
            select(Verse)
            .join(Book)
            .where(
                func.lower(Book.name) == english_name.lower(),
                Verse.chapter_number == chapter,
                Verse.verse_number >= start_verse,
                Verse.verse_number <= end_verse,
            )
        )

        if translation:
            query = query.where(Verse.translation == translation)

        query = query.order_by(Verse.verse_number).options(selectinload(Verse.book))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_chapter_verses(
        self, book_name: str, chapter: int, translation: str | None = None
    ) -> Sequence[Verse]:
        """Get all verses in a chapter, optionally filtered by translation."""
        # Normalize localized book names to English
        english_name = normalize_book_name(book_name)
        query = (
            select(Verse)
            .join(Book)
            .where(func.lower(Book.name) == english_name.lower(), Verse.chapter_number == chapter)
        )

        if translation:
            query = query.where(Verse.translation == translation)

        query = query.order_by(Verse.verse_number).options(selectinload(Verse.book))

        with tracer.start_as_current_span("db.get_chapter_verses") as span:
            _set_common_span_attrs(span, "get_chapter", translation)
            start = time.perf_counter()
            result = await self.session.execute(query)
            verses = result.scalars().all()
            _record_duration(span, start, "get_chapter", len(verses), translation)
            return verses

    async def search_verses_text(self, query: str, limit: int = 20) -> Sequence[Verse]:
        """Full-text search on verse content."""
        result = await self.session.execute(
            select(Verse)
            .where(Verse.text.ilike(f"%{query}%"))
            .limit(limit)
            .options(selectinload(Verse.book))
        )
        return result.scalars().all()

    async def search_verses_semantic(
        self,
        query_embedding: list[float],
        limit: int = 5,
        similarity_threshold: float = 0.5,
        translation: str | None = None,
    ) -> list[tuple[Verse, float]]:
        """
        Semantic search using vector similarity.

        Args:
            query_embedding: The embedding vector of the search query
            limit: Maximum results to return
            similarity_threshold: Minimum similarity score (0-1)
            translation: Optional translation code to filter by (e.g., 'kjv', 'ita1927')

        Returns:
            List of (verse, similarity_score) tuples
        """
        # Using pgvector's cosine distance (1 - cosine_similarity)
        # So we convert to similarity: 1 - distance
        query = (
            select(
                Verse, (1 - Verse.embedding.cosine_distance(query_embedding)).label("similarity")
            )
            .where(Verse.embedding.isnot(None))
            .where((1 - Verse.embedding.cosine_distance(query_embedding)) >= similarity_threshold)
        )

        if translation:
            query = query.where(Verse.translation == translation)

        query = (
            query.order_by(Verse.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .options(selectinload(Verse.book))
        )

        with tracer.start_as_current_span("db.search_verses_semantic") as span:
            _set_common_span_attrs(span, "semantic_search_verses", translation)
            span.set_attribute("db.similarity_threshold", similarity_threshold)
            start = time.perf_counter()
            result = await self.session.execute(query)
            rows = [(row.Verse, row.similarity) for row in result.all()]
            _record_duration(span, start, "semantic_search_verses", len(rows), translation)
            return rows

    # ==================== Passages ====================

    async def get_passage_by_id(self, passage_id: int) -> Passage | None:
        """Get a passage by ID."""
        result = await self.session.execute(
            select(Passage).where(Passage.id == passage_id).options(selectinload(Passage.book))
        )
        return result.scalar_one_or_none()

    async def search_passages_semantic(
        self, query_embedding: list[float], limit: int = 3, similarity_threshold: float = 0.5
    ) -> list[tuple[Passage, float]]:
        """Semantic search on passages."""
        with tracer.start_as_current_span("db.search_passages_semantic") as span:
            _set_common_span_attrs(span, "semantic_search_passages", None)
            span.set_attribute("db.similarity_threshold", similarity_threshold)
            start = time.perf_counter()
            result = await self.session.execute(
                select(
                    Passage,
                    (1 - Passage.embedding.cosine_distance(query_embedding)).label("similarity"),
                )
                .where(Passage.embedding.isnot(None))
                .where(
                    (1 - Passage.embedding.cosine_distance(query_embedding)) >= similarity_threshold
                )
                .order_by(Passage.embedding.cosine_distance(query_embedding))
                .limit(limit)
                .options(selectinload(Passage.book))
            )
            rows = [(row.Passage, row.similarity) for row in result.all()]
            _record_duration(span, start, "semantic_search_passages", len(rows), None)
            return rows

    # ==================== Topics ====================

    async def get_all_topics(self) -> Sequence[Topic]:
        """Get all topics."""
        result = await self.session.execute(select(Topic).order_by(Topic.name))
        return result.scalars().all()

    async def search_topics_semantic(
        self, query_embedding: list[float], limit: int = 5
    ) -> list[tuple[Topic, float]]:
        """Find topics related to a query."""
        result = await self.session.execute(
            select(
                Topic, (1 - Topic.embedding.cosine_distance(query_embedding)).label("similarity")
            )
            .where(Topic.embedding.isnot(None))
            .order_by(Topic.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        return [(row.Topic, row.similarity) for row in result.all()]

    # ==================== Stats ====================

    async def get_stats(self) -> dict:
        """Get database statistics."""
        books_count = await self.session.execute(select(func.count(Book.id)))
        verses_count = await self.session.execute(select(func.count(Verse.id)))
        embedded_count = await self.session.execute(
            select(func.count(Verse.id)).where(Verse.embedding.isnot(None))
        )
        passages_count = await self.session.execute(select(func.count(Passage.id)))

        return {
            "books": books_count.scalar_one(),
            "verses": verses_count.scalar_one(),
            "verses_with_embeddings": embedded_count.scalar_one(),
            "passages": passages_count.scalar_one(),
        }
