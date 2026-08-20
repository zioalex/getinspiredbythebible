"""
Scripture Repository - Database operations for Bible data.
"""

import asyncio
import time
from typing import Sequence, cast

from opentelemetry.trace import Span
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from middleware.context import REQUEST_ID_CTX_VAR
from utils.book_names import normalize_book_name
from utils.logging_config import get_logger
from utils.metrics import (
    db_query_duration_histogram,
    db_search_duration_histogram,
    db_slow_queries_counter,
)
from utils.telemetry import tracer

from .models import Book, Passage, Topic, Verse

logger = get_logger("scripture.repository")


def _vector_literal(embedding: list[float]) -> str:
    """Format an embedding as a pgvector literal string (e.g. ``[0.1,0.2,...]``)."""
    return f"[{','.join(str(x) for x in embedding)}]"


def _candidate_pool_cte(
    embeddings: list[list[float]],
    params: dict,
    *,
    table: str,
    translation_filter: str,
) -> str:
    """Build the ``candidates`` + ``dedup`` CTEs for an HNSW-backed vector search.

    For each query embedding, pull an ANN candidate pool with the index-friendly
    ``ORDER BY embedding <=> q LIMIT :candidate_pool`` (this is the only shape the
    HNSW index accelerates — a ``WHERE (1 - dist) >= threshold`` filter forces a full
    scan). The per-embedding pools are ``UNION ALL``-ed and deduped by the smallest
    distance (= highest similarity) per row, so multiple embeddings (query expansion)
    widen recall while a single embedding is the plain fast path.

    Mutates ``params`` to add ``emb0..embN``; the caller must also set
    ``candidate_pool``. ``translation_filter`` must reference *unaliased* columns
    because each subquery selects ``FROM <table>`` with no alias.
    """
    subqueries = []
    for i, embedding in enumerate(embeddings):
        key = f"emb{i}"
        params[key] = _vector_literal(embedding)
        subqueries.append(
            f"(SELECT id, embedding <=> CAST(:{key} AS vector) AS dist "
            f"FROM {table} "
            f"WHERE embedding IS NOT NULL {translation_filter} "
            f"ORDER BY embedding <=> CAST(:{key} AS vector) "
            f"LIMIT :candidate_pool)"
        )
    union = " UNION ALL ".join(subqueries)
    return (
        f"candidates AS ({union}), "
        f"dedup AS (SELECT id, MIN(dist) AS dist FROM candidates GROUP BY id)"
    )


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

    if "search" in operation:
        # Semantic search operations
        db_search_duration_histogram.record(
            duration_ms, {"operation": operation, "translation": translation or "all"}
        )
    else:
        # Other DB operations (get_verse, get_chapter, etc.)
        db_query_duration_histogram.record(duration_ms, {"operation": operation})

    # Record slow query counter if threshold exceeded
    if duration_ms > settings.slow_query_threshold_ms:
        db_slow_queries_counter.add(1, {"operation": operation})
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
        return cast(Sequence[Book], result.scalars().all())

    async def get_book_by_name(self, name: str) -> Book | None:
        """Get a book by its name (case-insensitive, supports localized names)."""
        # Normalize localized book names to English
        english_name = normalize_book_name(name)
        result = await self.session.execute(
            select(Book).where(func.lower(Book.name) == english_name.lower())
        )
        return cast(Book | None, result.scalar_one_or_none())

    async def get_book_by_id(self, book_id: int) -> Book | None:
        """Get a book by ID."""
        result = await self.session.execute(select(Book).where(Book.id == book_id))
        return cast(Book | None, result.scalar_one_or_none())

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
            result = await asyncio.wait_for(
                self.session.execute(query),
                timeout=settings.verse_query_timeout_s,
            )
            verse_obj = cast(Verse | None, result.scalar_one_or_none())
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
        return cast(Sequence[Verse], result.scalars().all())

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

        # Order by translation as a stable tiebreaker so that, when no specific
        # translation is requested, the "first" verse is deterministic rather
        # than dependent on the DB's row order.
        query = query.order_by(Verse.translation, Verse.verse_number).options(
            selectinload(Verse.book)
        )

        with tracer.start_as_current_span("db.get_chapter_verses") as span:
            _set_common_span_attrs(span, "get_chapter", translation)
            start = time.perf_counter()
            result = await asyncio.wait_for(
                self.session.execute(query),
                timeout=settings.verse_query_timeout_s,
            )
            verses = cast(Sequence[Verse], result.scalars().all())
            _record_duration(span, start, "get_chapter", len(verses), translation)
            return verses

    async def search_verses_text(self, query: str, limit: int = 20) -> Sequence[Verse]:
        """Full-text search on verse content.

        Uses ``@@`` against ``to_tsvector('simple', text)`` so the planner can use the
        expression GIN index (``idx_verses_fts_simple``, migration 003) instead of the
        leading-wildcard ``ILIKE`` full scan.

        **Deliberately does not use ``verse_tsv``** (BITB-096), unlike the ``ts_rank``
        sites in the hybrid builders below. An expression index already *stores* the
        computed tsvectors, so this lookup was never recomputing anything, and routing
        it through the side table adds a primary-key hop back into ``verses``. Measured
        over 403,856 rows: 0.144 ms via the join against 0.105 ms here. That is also why
        ``idx_verses_fts_simple`` is not being retired -- BITB-095 Phase 2 is cancelled.
        """
        result = await self.session.execute(
            select(Verse)
            .where(
                text("to_tsvector('simple', text) @@ plainto_tsquery('simple', :query)").bindparams(
                    query=query
                )
            )
            .limit(limit)
            .options(selectinload(Verse.book))
        )
        return cast(Sequence[Verse], result.scalars().all())

    async def search_verses_semantic(
        self,
        query_embedding: list[float],
        limit: int = 5,
        similarity_threshold: float = 0.5,
        translation: str | None = None,
        candidate_pool: int | None = None,
    ) -> list[tuple[Verse, float]]:
        """
        Semantic search using vector similarity.

        Index-friendly: pulls an HNSW-backed ANN candidate pool via
        ``_candidate_pool_cte`` (``ORDER BY embedding <=> q LIMIT :candidate_pool``),
        then applies the similarity threshold on the small deduped pool — mirrors
        ``search_verses_hybrid`` minus the keyword-ranking stage.

        Args:
            query_embedding: The embedding vector of the search query
            limit: Maximum results to return
            similarity_threshold: Minimum similarity score (0-1)
            translation: Optional translation code to filter by (e.g., 'kjv', 'ita1927')

        Returns:
            List of (verse, similarity_score) tuples
        """
        translation_filter = ""
        params: dict = {
            "threshold": similarity_threshold,
            "limit": limit,
            "candidate_pool": max(candidate_pool or settings.vector_candidate_pool, limit),
        }

        if translation:
            translation_filter = "AND translation = :translation"
            params["translation"] = translation

        candidate_cte = _candidate_pool_cte(
            [query_embedding], params, table="verses", translation_filter=translation_filter
        )

        sql = f"""
            WITH {candidate_cte}
            SELECT id, (1 - dist) AS similarity
            FROM dedup
            WHERE (1 - dist) >= :threshold
            ORDER BY dist
            LIMIT :limit
        """

        with tracer.start_as_current_span("db.search_verses_semantic") as span:
            _set_common_span_attrs(span, "semantic_search_verses", translation)
            span.set_attribute("db.similarity_threshold", similarity_threshold)
            start = time.perf_counter()
            result = await self.session.execute(text(sql), params)
            id_rows = result.fetchall()

            if not id_rows:
                _record_duration(span, start, "semantic_search_verses", 0, translation)
                return []

            verse_ids = [row[0] for row in id_rows]
            scores = {row[0]: row[1] for row in id_rows}

            verses_result = await self.session.execute(
                select(Verse).where(Verse.id.in_(verse_ids)).options(selectinload(Verse.book))
            )
            verses_by_id = {v.id: v for v in verses_result.scalars().all()}

            rows = [
                (verses_by_id[vid], float(scores[vid])) for vid in verse_ids if vid in verses_by_id
            ]
            _record_duration(span, start, "semantic_search_verses", len(rows), translation)
            return rows

    async def search_verses_hybrid(
        self,
        query_text: str,
        query_embedding: list[float],
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        similarity_threshold: float = 0.35,
        limit: int = 10,
        translation: str | None = None,
        extra_embeddings: list[list[float]] | None = None,
        candidate_pool: int | None = None,
    ) -> list[tuple["Verse", float]]:
        """
        Hybrid search combining semantic similarity and keyword matching.

        ``ts_rank`` reads the persisted tsvector from ``verse_tsv`` rather than
        recomputing ``to_tsvector('simple', v.text)`` for every candidate row
        (BITB-096). Measured over a 200-row candidate pool of 159-character verses:
        2.750 ms recomputed against 0.238 ms stored.

        The join is a ``LEFT JOIN`` with ``COALESCE(..., ''::tsvector)`` on purpose. A
        verse whose ``verse_tsv`` row is missing -- mid-backfill, or if the
        ``verses_tsv_sync`` trigger were ever dropped -- then ranks zero on the keyword
        component instead of disappearing from the results entirely. Degrading a score
        is recoverable; silently losing scripture from a search is not.

        Args:
            query_text: The raw text query (for full-text search)
            query_embedding: The embedding vector of the search query
            semantic_weight: Weight for semantic score (0-1)
            keyword_weight: Weight for keyword score (0-1)
            similarity_threshold: Minimum semantic similarity score (0-1)
            limit: Maximum results to return
            translation: Optional translation code to filter by

        Returns:
            List of (verse, hybrid_score) tuples
        """
        # Normalize weights to ensure they sum to 1
        total_weight = semantic_weight + keyword_weight
        if total_weight > 0:
            semantic_weight /= total_weight
            keyword_weight /= total_weight

        embeddings = [query_embedding, *(extra_embeddings or [])]

        translation_filter = ""
        params: dict = {
            "query_text": query_text,
            "threshold": similarity_threshold,
            "semantic_weight": semantic_weight,
            "keyword_weight": keyword_weight,
            "limit": limit,
            "candidate_pool": max(candidate_pool or settings.vector_candidate_pool, limit),
        }

        if translation:
            translation_filter = "AND translation = :translation"
            params["translation"] = translation

        candidate_cte = _candidate_pool_cte(
            embeddings, params, table="verses", translation_filter=translation_filter
        )

        # Index-friendly + multi-embedding: each embedding pulls an HNSW candidate pool,
        # then threshold + keyword + hybrid-rank run only on the small deduped pool.
        # Parameterized query: only :named binds + internal translation_filter constant.
        sql = f"""
            WITH {candidate_cte},
            ranked AS (
                SELECT
                    d.id,
                    (1 - d.dist) AS semantic_score,
                    ts_rank(
                        COALESCE(vt.text_tsv, CAST('' AS tsvector)),
                        plainto_tsquery('simple', :query_text)
                    ) AS keyword_score_raw
                FROM dedup d
                LEFT JOIN verse_tsv vt ON vt.verse_id = d.id
                WHERE (1 - d.dist) >= :threshold
            ),
            normalized AS (
                SELECT
                    id,
                    semantic_score,
                    keyword_score_raw,
                    CASE
                        WHEN MAX(keyword_score_raw) OVER () > 0
                        THEN keyword_score_raw / MAX(keyword_score_raw) OVER ()
                        ELSE 0.0
                    END AS keyword_score
                FROM ranked
            )
            SELECT
                id,
                (:semantic_weight * semantic_score) +
                (:keyword_weight * keyword_score) AS hybrid_score
            FROM normalized
            ORDER BY hybrid_score DESC
            LIMIT :limit
        """

        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()

        if not rows:
            return []

        verse_ids = [row[0] for row in rows]
        scores = {row[0]: row[1] for row in rows}

        # Fetch full verse objects preserving order
        verses_result = await self.session.execute(
            select(Verse).where(Verse.id.in_(verse_ids)).options(selectinload(Verse.book))
        )
        verses_by_id = {v.id: v for v in verses_result.scalars().all()}

        return [(verses_by_id[vid], float(scores[vid])) for vid in verse_ids if vid in verses_by_id]

    async def search_verses_semantic_boosted(
        self,
        query_embedding: list[float],
        boost_topics: list[str],
        topic_boost_factor: float = 0.2,
        limit: int = 5,
        similarity_threshold: float = 0.35,
        translation: str | None = None,
        extra_embeddings: list[list[float]] | None = None,
        candidate_pool: int | None = None,
    ) -> list[tuple["Verse", float]]:
        """
        Semantic search with optional topic-based score boosting.

        Applies multiplicative boost: final_score = base_score * (1 + factor * matching_topic_count)
        Supports hierarchical topics: child topic also matches parent topic name.

        Args:
            query_embedding: The embedding vector of the search query
            boost_topics: List of topic names to boost (matched against topics.name)
            topic_boost_factor: Boost multiplier per matching topic (default 0.2 = 20%)
            limit: Maximum results to return
            similarity_threshold: Minimum base similarity score
            translation: Optional translation filter

        Returns:
            List of (verse, final_score) tuples ordered by final_score DESC
        """
        embeddings = [query_embedding, *(extra_embeddings or [])]
        translation_filter = ""
        params: dict = {
            "threshold": similarity_threshold,
            "topic_boost_factor": topic_boost_factor,
            "boost_topics": boost_topics,
            "limit": limit,
            "candidate_pool": max(candidate_pool or settings.vector_candidate_pool, limit),
        }

        if translation:
            translation_filter = "AND translation = :translation"
            params["translation"] = translation

        candidate_cte = _candidate_pool_cte(
            embeddings, params, table="verses", translation_filter=translation_filter
        )

        # Parameterized query: only :named binds + internal translation_filter constant (no user SQL).
        sql = f"""
            WITH {candidate_cte},
            base_search AS (
                SELECT id, (1 - dist) AS base_score
                FROM dedup
                WHERE (1 - dist) >= :threshold
            ),
            topic_matches AS (
                SELECT
                    bs.id,
                    bs.base_score,
                    COUNT(DISTINCT vt.topic_id) AS matching_topic_count
                FROM base_search bs
                LEFT JOIN verse_topics vt ON bs.id = vt.verse_id
                LEFT JOIN topics t ON vt.topic_id = t.id
                WHERE t.name = ANY(:boost_topics)
                   OR t.parent_id IN (
                       SELECT id FROM topics WHERE name = ANY(:boost_topics)
                   )
                GROUP BY bs.id, bs.base_score
            ),
            all_verses AS (
                -- Verses with matching topics
                SELECT
                    tm.id,
                    tm.base_score * (1 + (:topic_boost_factor * tm.matching_topic_count)) AS final_score
                FROM topic_matches tm
                UNION ALL
                -- Verses without any matching topics (no boost)
                SELECT
                    bs.id,
                    bs.base_score AS final_score
                FROM base_search bs
                WHERE bs.id NOT IN (SELECT id FROM topic_matches)
            )
            SELECT DISTINCT ON (id) id, final_score
            FROM all_verses
            ORDER BY id, final_score DESC
        """

        # Wrap in outer query to get overall ordering
        outer_sql = f"""
            SELECT id, final_score FROM (
                {sql}
            ) AS deduped
            ORDER BY final_score DESC
            LIMIT :limit
        """

        result = await self.session.execute(text(outer_sql), params)
        rows = result.fetchall()

        if not rows:
            return []

        verse_ids = [row[0] for row in rows]
        scores = {row[0]: row[1] for row in rows}

        verses_result = await self.session.execute(
            select(Verse).where(Verse.id.in_(verse_ids)).options(selectinload(Verse.book))
        )
        verses_by_id = {v.id: v for v in verses_result.scalars().all()}

        return [(verses_by_id[vid], float(scores[vid])) for vid in verse_ids if vid in verses_by_id]

    async def search_verses_hybrid_boosted(
        self,
        query_text: str,
        query_embedding: list[float],
        boost_topics: list[str],
        topic_boost_factor: float = 0.2,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        similarity_threshold: float = 0.35,
        limit: int = 10,
        translation: str | None = None,
        extra_embeddings: list[list[float]] | None = None,
        candidate_pool: int | None = None,
    ) -> list[tuple["Verse", float]]:
        """
        Hybrid search with topic-based score boosting.

        Combines semantic + keyword scores, then applies topic boost.
        Formula: final_score = hybrid_score * (1 + factor * matching_topic_count)

        Like ``search_verses_hybrid``, ``ts_rank`` here reads the persisted tsvector
        from ``verse_tsv`` via a ``LEFT JOIN`` rather than recomputing it per candidate
        row (BITB-096). See that method for the measurements and for why the join is
        outer.
        """
        # Normalize weights
        total_weight = semantic_weight + keyword_weight
        if total_weight > 0:
            semantic_weight /= total_weight
            keyword_weight /= total_weight

        embeddings = [query_embedding, *(extra_embeddings or [])]
        translation_filter = ""
        params: dict = {
            "query_text": query_text,
            "threshold": similarity_threshold,
            "semantic_weight": semantic_weight,
            "keyword_weight": keyword_weight,
            "topic_boost_factor": topic_boost_factor,
            "boost_topics": boost_topics,
            "limit": limit,
            "candidate_pool": max(candidate_pool or settings.vector_candidate_pool, limit),
        }

        if translation:
            translation_filter = "AND translation = :translation"
            params["translation"] = translation

        candidate_cte = _candidate_pool_cte(
            embeddings, params, table="verses", translation_filter=translation_filter
        )

        # Parameterized query: only :named binds + internal translation_filter constant (no user SQL).
        sql = f"""
            WITH {candidate_cte},
            ranked AS (
                SELECT
                    d.id,
                    (1 - d.dist) AS semantic_score,
                    ts_rank(
                        COALESCE(vt.text_tsv, CAST('' AS tsvector)),
                        plainto_tsquery('simple', :query_text)
                    ) AS keyword_score_raw
                FROM dedup d
                LEFT JOIN verse_tsv vt ON vt.verse_id = d.id
                WHERE (1 - d.dist) >= :threshold
            ),
            normalized AS (
                SELECT
                    id,
                    semantic_score,
                    CASE
                        WHEN MAX(keyword_score_raw) OVER () > 0
                        THEN keyword_score_raw / MAX(keyword_score_raw) OVER ()
                        ELSE 0.0
                    END AS keyword_score
                FROM ranked
            ),
            hybrid_scored AS (
                SELECT
                    id,
                    (:semantic_weight * semantic_score) +
                    (:keyword_weight * keyword_score) AS hybrid_score
                FROM normalized
            ),
            topic_matches AS (
                SELECT
                    hs.id,
                    hs.hybrid_score,
                    COUNT(DISTINCT vt.topic_id) AS matching_topic_count
                FROM hybrid_scored hs
                LEFT JOIN verse_topics vt ON hs.id = vt.verse_id
                LEFT JOIN topics t ON vt.topic_id = t.id
                WHERE t.name = ANY(:boost_topics)
                   OR t.parent_id IN (
                       SELECT id FROM topics WHERE name = ANY(:boost_topics)
                   )
                GROUP BY hs.id, hs.hybrid_score
            ),
            all_verses AS (
                SELECT
                    tm.id,
                    tm.hybrid_score * (1 + (:topic_boost_factor * tm.matching_topic_count)) AS final_score
                FROM topic_matches tm
                UNION ALL
                SELECT
                    hs.id,
                    hs.hybrid_score AS final_score
                FROM hybrid_scored hs
                WHERE hs.id NOT IN (SELECT id FROM topic_matches)
            )
            SELECT DISTINCT ON (id) id, final_score
            FROM all_verses
            ORDER BY id, final_score DESC
        """

        outer_sql = f"""
            SELECT id, final_score FROM (
                {sql}
            ) AS deduped
            ORDER BY final_score DESC
            LIMIT :limit
        """

        result = await self.session.execute(text(outer_sql), params)
        rows = result.fetchall()

        if not rows:
            return []

        verse_ids = [row[0] for row in rows]
        scores = {row[0]: row[1] for row in rows}

        verses_result = await self.session.execute(
            select(Verse).where(Verse.id.in_(verse_ids)).options(selectinload(Verse.book))
        )
        verses_by_id = {v.id: v for v in verses_result.scalars().all()}

        return [(verses_by_id[vid], float(scores[vid])) for vid in verse_ids if vid in verses_by_id]

    # ==================== Passages ====================

    async def get_passage_by_id(self, passage_id: int) -> Passage | None:
        """Get a passage by ID."""
        result = await self.session.execute(
            select(Passage).where(Passage.id == passage_id).options(selectinload(Passage.book))
        )
        return cast(Passage | None, result.scalar_one_or_none())

    async def search_passages_semantic(
        self,
        query_embedding: list[float],
        limit: int = 3,
        similarity_threshold: float = 0.5,
        candidate_pool: int | None = None,
    ) -> list[tuple[Passage, float]]:
        """Semantic search on passages.

        Index-friendly: mirrors ``search_passages_hybrid`` minus the keyword-ranking
        stage — HNSW candidate pool via ``_candidate_pool_cte``, then threshold filter
        on the small deduped pool.
        """
        params: dict = {
            "threshold": similarity_threshold,
            "limit": limit,
            "candidate_pool": max(candidate_pool or settings.vector_candidate_pool, limit),
        }
        candidate_cte = _candidate_pool_cte(
            [query_embedding], params, table="passages", translation_filter=""
        )

        sql = f"""
            WITH {candidate_cte}
            SELECT id, (1 - dist) AS similarity
            FROM dedup
            WHERE (1 - dist) >= :threshold
            ORDER BY dist
            LIMIT :limit
        """

        with tracer.start_as_current_span("db.search_passages_semantic") as span:
            _set_common_span_attrs(span, "semantic_search_passages", None)
            span.set_attribute("db.similarity_threshold", similarity_threshold)
            start = time.perf_counter()
            result = await self.session.execute(text(sql), params)
            id_rows = result.fetchall()

            if not id_rows:
                _record_duration(span, start, "semantic_search_passages", 0, None)
                return []

            passage_ids = [row[0] for row in id_rows]
            scores = {row[0]: row[1] for row in id_rows}

            passages_result = await self.session.execute(
                select(Passage)
                .where(Passage.id.in_(passage_ids))
                .options(selectinload(Passage.book))
            )
            passages_by_id = {p.id: p for p in passages_result.scalars().all()}

            rows = [
                (passages_by_id[pid], float(scores[pid]))
                for pid in passage_ids
                if pid in passages_by_id
            ]
            _record_duration(span, start, "semantic_search_passages", len(rows), None)
            return rows

    async def search_passages_hybrid(
        self,
        query_text: str,
        query_embedding: list[float],
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3,
        similarity_threshold: float = 0.35,
        limit: int = 3,
        candidate_pool: int | None = None,
    ) -> list[tuple["Passage", float]]:
        """
        Hybrid search on passages combining semantic similarity and keyword matching.

        Args:
            query_text: The raw text query (for full-text search)
            query_embedding: The embedding vector of the search query
            semantic_weight: Weight for semantic score (0-1)
            keyword_weight: Weight for keyword score (0-1)
            similarity_threshold: Minimum semantic similarity score (0-1)
            limit: Maximum results to return

        Returns:
            List of (passage, hybrid_score) tuples
        """
        # Normalize weights to ensure they sum to 1
        total_weight = semantic_weight + keyword_weight
        if total_weight > 0:
            semantic_weight /= total_weight
            keyword_weight /= total_weight

        params: dict = {
            "query_text": query_text,
            "threshold": similarity_threshold,
            "semantic_weight": semantic_weight,
            "keyword_weight": keyword_weight,
            "limit": limit,
            "candidate_pool": max(candidate_pool or settings.vector_candidate_pool, limit),
        }

        candidate_cte = _candidate_pool_cte(
            [query_embedding], params, table="passages", translation_filter=""
        )

        # Index-friendly: HNSW candidate pool, then threshold + keyword + hybrid-rank.
        sql = f"""
            WITH {candidate_cte},
            ranked AS (
                SELECT
                    d.id,
                    (1 - d.dist) AS semantic_score,
                    ts_rank(
                        to_tsvector('simple', p.text),
                        plainto_tsquery('simple', :query_text)
                    ) AS keyword_score_raw
                FROM dedup d
                JOIN passages p ON p.id = d.id
                WHERE (1 - d.dist) >= :threshold
            ),
            normalized AS (
                SELECT
                    id,
                    semantic_score,
                    keyword_score_raw,
                    CASE
                        WHEN MAX(keyword_score_raw) OVER () > 0
                        THEN keyword_score_raw / MAX(keyword_score_raw) OVER ()
                        ELSE 0.0
                    END AS keyword_score
                FROM ranked
            )
            SELECT
                id,
                (:semantic_weight * semantic_score) +
                (:keyword_weight * keyword_score) AS hybrid_score
            FROM normalized
            ORDER BY hybrid_score DESC
            LIMIT :limit
        """

        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()

        if not rows:
            return []

        passage_ids = [row[0] for row in rows]
        scores = {row[0]: row[1] for row in rows}

        passages_result = await self.session.execute(
            select(Passage).where(Passage.id.in_(passage_ids)).options(selectinload(Passage.book))
        )
        passages_by_id = {p.id: p for p in passages_result.scalars().all()}

        return [
            (passages_by_id[pid], float(scores[pid]))
            for pid in passage_ids
            if pid in passages_by_id
        ]

    # ==================== Topics ====================

    async def get_all_topics(self) -> Sequence[Topic]:
        """Get all topics."""
        result = await self.session.execute(select(Topic).order_by(Topic.name))
        return cast(Sequence[Topic], result.scalars().all())

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

    async def get_translation_coverage(self) -> list[dict]:
        """Per-translation verse/embedding coverage (BITB-054).

        Reuses the diagnostic SQL documented in ``NEXT_STEPS.md``
        (``SELECT translation, COUNT(*), COUNT(embedding) FROM verses GROUP BY
        translation``) so a missing or partially-loaded translation is
        queryable instead of requiring a manual psql session.

        Returns:
            One dict per translation: ``{"translation", "total_verses",
            "verses_with_embeddings"}``. A translation with zero rows in
            ``verses`` (never loaded) simply does not appear.
        """
        result = await self.session.execute(
            select(
                Verse.translation,
                func.count(Verse.id),
                func.count(Verse.embedding),
            ).group_by(Verse.translation)
        )
        return [
            {
                "translation": translation,
                "total_verses": total_verses,
                "verses_with_embeddings": verses_with_embeddings,
            }
            for translation, total_verses, verses_with_embeddings in result.all()
        ]
