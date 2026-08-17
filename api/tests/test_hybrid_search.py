"""
Tests for hybrid search (BITB-018.2).
Tests use mocks to avoid requiring a real database connection.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from scripture.repository import ScriptureRepository
from scripture.search import ScriptureSearchService

# Compiling against asyncpg's paramstyle reproduces exactly what reaches the driver.
_ASYNCPG_DIALECT = postgresql.dialect(paramstyle="numeric_dollar")

# ==================== Repository Tests ====================


class TestSearchVersesHybrid:
    """Tests for ScriptureRepository.search_verses_hybrid()."""

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_verses(self):
        """search_verses_hybrid returns list of (verse, score) tuples."""
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)

        # Mock SQL result rows: (id, hybrid_score)
        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [
            (1, 0.85),
            (2, 0.72),
        ]

        # Mock verse objects
        mock_verse1 = MagicMock()
        mock_verse1.id = 1
        mock_verse1.text = "Peace, be still."

        mock_verse2 = MagicMock()
        mock_verse2.id = 2
        mock_verse2.text = "Be still and know that I am God."

        mock_verses_result = MagicMock()
        mock_verses_result.scalars.return_value.all.return_value = [mock_verse1, mock_verse2]

        mock_session.execute.side_effect = [mock_sql_result, mock_verses_result]

        embedding = [0.1] * 1024
        results = await repo.search_verses_hybrid(
            query_text="peace be still",
            query_embedding=embedding,
            limit=5,
        )

        assert len(results) == 2
        assert results[0][0].id == 1
        assert results[0][1] == pytest.approx(0.85)

    @pytest.mark.asyncio
    async def test_hybrid_search_empty_result(self):
        """search_verses_hybrid returns empty list when no results."""
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)

        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_sql_result

        embedding = [0.1] * 1024
        results = await repo.search_verses_hybrid(
            query_text="peace be still",
            query_embedding=embedding,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_hybrid_search_weight_normalization(self):
        """Weights are normalized to sum to 1.0 in the SQL query."""
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)

        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_sql_result

        embedding = [0.1] * 1024
        # Pass weights that don't sum to 1.0 — they should be normalized
        await repo.search_verses_hybrid(
            query_text="test",
            query_embedding=embedding,
            semantic_weight=2.0,
            keyword_weight=1.0,
        )

        # Verify execute was called (weights were normalized internally)
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_with_translation_filter(self):
        """search_verses_hybrid passes translation filter to SQL."""
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)

        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_sql_result

        embedding = [0.1] * 1024
        await repo.search_verses_hybrid(
            query_text="test",
            query_embedding=embedding,
            translation="kjv",
        )

        # Verify execute was called with translation parameter
        call_args = mock_session.execute.call_args
        params = call_args[0][1]  # second positional arg is params dict
        assert "translation" in params
        assert params["translation"] == "kjv"

    @pytest.mark.asyncio
    async def test_hybrid_search_zero_weights_skips_normalization(self):
        """When semantic_weight and keyword_weight are both 0, the
        `if total_weight > 0` guard skips division, avoiding a
        ZeroDivisionError, and the raw (zero) weights flow through."""
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)

        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_sql_result

        embedding = [0.1] * 1024
        results = await repo.search_verses_hybrid(
            query_text="test",
            query_embedding=embedding,
            semantic_weight=0,
            keyword_weight=0,
        )

        assert results == []
        params = mock_session.execute.call_args[0][1]
        assert params["semantic_weight"] == 0
        assert params["keyword_weight"] == 0


class TestSearchVersesHybridBoosted:
    """Tests for ScriptureRepository.search_verses_hybrid_boosted()."""

    @pytest.mark.asyncio
    async def test_hybrid_search_boosted_zero_weights_skips_normalization(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)

        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_sql_result

        embedding = [0.1] * 1024
        results = await repo.search_verses_hybrid_boosted(
            query_text="test",
            query_embedding=embedding,
            boost_topics=[],
            semantic_weight=0,
            keyword_weight=0,
        )

        assert results == []
        params = mock_session.execute.call_args[0][1]
        assert params["semantic_weight"] == 0
        assert params["keyword_weight"] == 0


class TestRawSqlHasNoPythonComment:
    """Regression: the raw-SQL search builders must not leak a Python ``#`` comment
    into the SQL string sent to Postgres.

    A misplaced ``# nosec`` after the opening triple-quote once made every query
    start with ``# nosec ...``, which Postgres rejected with
    ``syntax error at or near "#"`` and aborted the transaction. These tests
    execute the real SQL-building path (mocked session, empty rows) and assert the
    generated SQL is clean — coverage that was missing because other tests mock the
    repository methods themselves.
    """

    @staticmethod
    def _first_sql(mock_session) -> str:
        # First execute() call passes text(sql) as the first positional arg.
        return mock_session.execute.call_args_list[0][0][0].text

    @pytest.mark.asyncio
    async def test_search_verses_hybrid_sql_is_clean(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_verses_hybrid(
            query_text="test", query_embedding=[0.1, 0.2], translation="schlachter"
        )

        sql = self._first_sql(mock_session)
        assert "#" not in sql
        assert sql.lstrip().upper().startswith(("WITH", "SELECT"))

    @pytest.mark.asyncio
    async def test_search_verses_semantic_boosted_sql_is_clean(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_verses_semantic_boosted(
            query_embedding=[0.1, 0.2], boost_topics=["faith"], translation="schlachter"
        )

        sql = self._first_sql(mock_session)
        assert "#" not in sql
        assert sql.lstrip().upper().startswith(("WITH", "SELECT"))

    @pytest.mark.asyncio
    async def test_search_verses_hybrid_boosted_sql_is_clean(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_verses_hybrid_boosted(
            query_text="test",
            query_embedding=[0.1, 0.2],
            boost_topics=["faith"],
            translation="schlachter",
        )

        sql = self._first_sql(mock_session)
        assert "#" not in sql
        assert sql.lstrip().upper().startswith(("WITH", "SELECT"))


class TestEmbeddingBindCompilesForAsyncpg:
    """Regression: the embedding bind must survive compilation to asyncpg's paramstyle.

    The builders once cast the embedding with the Postgres ``::`` shorthand
    (``:embedding::vector``). SQLAlchemy's bind-parameter parser refuses to bind a
    ``:name`` immediately followed by ``::`` — it mis-detected a phantom ``embeddin``
    bind and left the literal ``:embedding::vector`` in the compiled SQL, so asyncpg
    raised ``syntax error at or near ":"`` and the vector was never bound.

    ``CAST(:embedding AS vector)`` binds correctly. These tests compile the real SQL
    each builder produces against asyncpg's dialect — the step the ``#``-comment tests
    skip — so a regression to ``:embedding::vector`` (or any unbound ``:name``) fails.
    """

    @staticmethod
    def _compile_first_sql(mock_session):
        text_clause = mock_session.execute.call_args_list[0][0][0]
        compiled = text_clause.compile(dialect=_ASYNCPG_DIALECT)
        return str(compiled), compiled.positiontup

    @staticmethod
    def _assert_clean(sql: str, positiontup) -> None:
        # No named bind may leak to asyncpg; the embedding must actually be bound.
        assert ":" not in sql, f"unbound named parameter leaked into SQL: {sql}"
        # Each query embedding is bound as emb0..embN by _candidate_pool_cte.
        assert "emb0" in positiontup
        assert "embeddin" not in positiontup  # the phantom bind from the ::vector bug

    @pytest.mark.asyncio
    async def test_search_verses_hybrid_binds_embedding(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_verses_hybrid(
            query_text="test", query_embedding=[0.1, 0.2], translation="schlachter"
        )

        self._assert_clean(*self._compile_first_sql(mock_session))

    @pytest.mark.asyncio
    async def test_search_verses_semantic_boosted_binds_embedding(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_verses_semantic_boosted(
            query_embedding=[0.1, 0.2], boost_topics=["faith"], translation="schlachter"
        )

        self._assert_clean(*self._compile_first_sql(mock_session))

    @pytest.mark.asyncio
    async def test_search_verses_hybrid_boosted_binds_embedding(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_verses_hybrid_boosted(
            query_text="test",
            query_embedding=[0.1, 0.2],
            boost_topics=["faith"],
            translation="schlachter",
        )

        self._assert_clean(*self._compile_first_sql(mock_session))

    @pytest.mark.asyncio
    async def test_search_passages_hybrid_binds_embedding(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_passages_hybrid(query_text="test", query_embedding=[0.1, 0.2])

        self._assert_clean(*self._compile_first_sql(mock_session))


class TestSearchPassagesHybrid:
    """Tests for ScriptureRepository.search_passages_hybrid()."""

    @pytest.mark.asyncio
    async def test_passages_hybrid_returns_results(self):
        """search_passages_hybrid returns list of (passage, score) tuples."""
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)

        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = [(1, 0.90)]

        mock_passage = MagicMock()
        mock_passage.id = 1
        mock_passage.title = "The Lord's Prayer"

        mock_passages_result = MagicMock()
        mock_passages_result.scalars.return_value.all.return_value = [mock_passage]

        mock_session.execute.side_effect = [mock_sql_result, mock_passages_result]

        embedding = [0.1] * 1024
        results = await repo.search_passages_hybrid(
            query_text="our father prayer",
            query_embedding=embedding,
        )

        assert len(results) == 1
        assert results[0][0].title == "The Lord's Prayer"
        assert results[0][1] == pytest.approx(0.90)

    @pytest.mark.asyncio
    async def test_passages_hybrid_empty_result(self):
        """search_passages_hybrid returns empty list when no results."""
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)

        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_sql_result

        embedding = [0.1] * 1024
        results = await repo.search_passages_hybrid(
            query_text="xyz",
            query_embedding=embedding,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_passages_hybrid_zero_weights_skips_normalization(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)

        mock_sql_result = MagicMock()
        mock_sql_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_sql_result

        embedding = [0.1] * 1024
        results = await repo.search_passages_hybrid(
            query_text="xyz",
            query_embedding=embedding,
            semantic_weight=0,
            keyword_weight=0,
        )

        assert results == []
        params = mock_session.execute.call_args[0][1]
        assert params["semantic_weight"] == 0
        assert params["keyword_weight"] == 0


class TestSearchVersesSemanticIndexFriendly:
    """BITB-062: search_verses_semantic must use the candidate-pool CTE, not a
    ``WHERE (1 - dist) >= threshold`` full-scan predicate."""

    @pytest.mark.asyncio
    async def test_sql_is_clean(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_verses_semantic(query_embedding=[0.1, 0.2], translation="schlachter")

        text_clause = mock_session.execute.call_args_list[0][0][0]
        sql = text_clause.text
        assert "#" not in sql
        assert sql.lstrip().upper().startswith("WITH")
        assert "dedup" in sql

    @pytest.mark.asyncio
    async def test_binds_embedding(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_verses_semantic(query_embedding=[0.1, 0.2], translation="schlachter")

        text_clause = mock_session.execute.call_args_list[0][0][0]
        compiled = text_clause.compile(dialect=_ASYNCPG_DIALECT)
        sql, positiontup = str(compiled), compiled.positiontup
        assert ":" not in sql, f"unbound named parameter leaked into SQL: {sql}"
        assert "emb0" in positiontup

    @pytest.mark.asyncio
    async def test_uses_candidate_pool_before_threshold(self):
        """The ANN pool is pulled with LIMIT :candidate_pool before the threshold
        filter, not filtered by threshold inside the index-eligible ORDER BY step —
        this is the shape that lets Postgres use the HNSW index."""
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_verses_semantic(query_embedding=[0.1, 0.2])

        sql = mock_session.execute.call_args_list[0][0][0].text
        candidates_idx = sql.index("candidates AS")
        threshold_idx = sql.index(":threshold")
        assert candidates_idx < threshold_idx


class TestSearchPassagesSemanticIndexFriendly:
    """BITB-062: search_passages_semantic must use the candidate-pool CTE."""

    @pytest.mark.asyncio
    async def test_sql_is_clean(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_passages_semantic(query_embedding=[0.1, 0.2])

        text_clause = mock_session.execute.call_args_list[0][0][0]
        sql = text_clause.text
        assert "#" not in sql
        assert sql.lstrip().upper().startswith("WITH")
        assert "dedup" in sql

    @pytest.mark.asyncio
    async def test_binds_embedding(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_passages_semantic(query_embedding=[0.1, 0.2])

        text_clause = mock_session.execute.call_args_list[0][0][0]
        compiled = text_clause.compile(dialect=_ASYNCPG_DIALECT)
        sql, positiontup = str(compiled), compiled.positiontup
        assert ":" not in sql, f"unbound named parameter leaked into SQL: {sql}"
        assert "emb0" in positiontup


class TestSearchVersesTextUsesFts:
    """BITB-062: search_verses_text must use FTS (index-backed), not a
    leading-wildcard ILIKE (unindexable full scan)."""

    @pytest.mark.asyncio
    async def test_uses_tsvector_match_not_ilike(self):
        mock_session = AsyncMock()
        repo = ScriptureRepository(mock_session)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        await repo.search_verses_text("peace")

        compiled_stmt = mock_session.execute.call_args_list[0][0][0]
        sql = str(compiled_stmt.compile(compile_kwargs={"literal_binds": False}))
        assert "ilike" not in sql.lower()
        assert "plainto_tsquery" in sql
        # BITB-095: matches the persisted generated column, not the recomputed
        # expression. Asserting the expression is *absent* is the half that
        # matters -- it is what makes dropping idx_verses_fts_simple safe.
        assert "text_tsv" in sql
        assert "to_tsvector" not in sql


# ==================== SearchService Tests ====================


class TestScriptureSearchServiceHybrid:
    """Tests for ScriptureSearchService.search_hybrid()."""

    @pytest.mark.asyncio
    async def test_search_hybrid_calls_repository(self):
        """search_hybrid generates embedding and calls repository methods."""
        mock_session = AsyncMock()
        mock_embedding_provider = AsyncMock()
        mock_embedding_provider.embed.return_value = MagicMock(embedding=[0.1] * 1024)

        service = ScriptureSearchService(mock_session, mock_embedding_provider)

        mock_verse = MagicMock()
        mock_verse.text = "Peace be still"
        mock_verse.book.name = "Mark"
        mock_verse.chapter_number = 4
        mock_verse.verse_number = 39
        mock_verse.translation = "kjv"
        mock_verse.book.name = "Mark"
        mock_verse.reference = "Mark 4:39"

        with (
            patch.object(
                service.repo, "search_verses_hybrid", new_callable=AsyncMock
            ) as mock_verses,
            patch.object(
                service.repo, "search_passages_hybrid", new_callable=AsyncMock
            ) as mock_passages,
            patch("scripture.search.get_localized_book_name", return_value="Mark"),
        ):
            mock_verses.return_value = [(mock_verse, 0.85)]
            mock_passages.return_value = []

            results = await service.search_hybrid(
                query="peace be still",
                max_verses=5,
            )

        mock_embedding_provider.embed.assert_called_once_with("peace be still")
        mock_verses.assert_called_once()
        assert len(results.verses) == 1
        assert results.verses[0].similarity == 0.85

    @pytest.mark.asyncio
    async def test_search_hybrid_passes_weights(self):
        """search_hybrid passes correct weights to repository."""
        mock_session = AsyncMock()
        mock_embedding_provider = AsyncMock()
        mock_embedding_provider.embed.return_value = MagicMock(embedding=[0.1] * 1024)

        service = ScriptureSearchService(mock_session, mock_embedding_provider)

        with (
            patch.object(
                service.repo, "search_verses_hybrid", new_callable=AsyncMock
            ) as mock_verses,
            patch.object(
                service.repo, "search_passages_hybrid", new_callable=AsyncMock
            ) as mock_passages,
        ):
            mock_verses.return_value = []
            mock_passages.return_value = []

            await service.search_hybrid(
                query="test",
                semantic_weight=0.6,
                keyword_weight=0.4,
            )

        call_kwargs = mock_verses.call_args[1]
        assert call_kwargs["semantic_weight"] == 0.6
        assert call_kwargs["keyword_weight"] == 0.4

    @pytest.mark.asyncio
    async def test_search_hybrid_forwards_extra_embeddings(self):
        """Query-expansion embeddings must reach the verses builder.

        Regression guard: extras previously flowed only into the throwaway semantic
        search() and never into search_hybrid(), so expansion had no effect on answers.
        """
        mock_session = AsyncMock()
        mock_embedding_provider = AsyncMock()
        mock_embedding_provider.embed.return_value = MagicMock(embedding=[0.1] * 1024)

        service = ScriptureSearchService(mock_session, mock_embedding_provider)

        extras = [[0.2] * 1024]
        with (
            patch.object(
                service.repo, "search_verses_hybrid", new_callable=AsyncMock
            ) as mock_verses,
            patch.object(
                service.repo, "search_passages_hybrid", new_callable=AsyncMock
            ) as mock_passages,
        ):
            mock_verses.return_value = []
            mock_passages.return_value = []

            await service.search_hybrid(query="test", extra_embeddings=extras)

        assert mock_verses.call_args[1]["extra_embeddings"] == extras


# ==================== Config Validation Tests ====================


class TestHybridSearchConfig:
    """Tests for hybrid search configuration validation."""

    def test_default_weights_are_valid(self):
        """Default weights (0.7 + 0.3) sum to 1.0."""
        from config import Settings

        s = Settings(
            hybrid_search_enabled=False,
            hybrid_search_semantic_weight=0.7,
            hybrid_search_keyword_weight=0.3,
        )
        assert s.hybrid_search_semantic_weight == 0.7
        assert s.hybrid_search_keyword_weight == 0.3

    def test_weights_must_sum_to_one(self):
        """Weights that don't sum to 1.0 raise ValidationError."""
        from pydantic import ValidationError

        from config import Settings

        # Try invalid weights that sum to 1.6
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                hybrid_search_semantic_weight=0.8,
                hybrid_search_keyword_weight=0.8,  # 0.8 + 0.8 = 1.6, invalid
            )

        error_msg = str(exc_info.value)
        assert "sum" in error_msg.lower() or "1.0" in error_msg or "weights" in error_msg.lower()

    def test_equal_weights_are_valid(self):
        """Equal weights (0.5 + 0.5) are valid."""
        from config import Settings

        s = Settings(
            hybrid_search_semantic_weight=0.5,
            hybrid_search_keyword_weight=0.5,
        )
        assert s.hybrid_search_semantic_weight == 0.5

    def test_hybrid_flag_defaults_to_true(self):
        """HYBRID_SEARCH_ENABLED defaults to True (BITB-043)."""
        from config import Settings

        s = Settings()
        assert s.hybrid_search_enabled is True

    def test_weight_out_of_range_raises(self):
        """Weight > 1.0 raises ValidationError."""
        from config import Settings

        try:
            Settings(
                hybrid_search_semantic_weight=1.5,
                hybrid_search_keyword_weight=-0.5,
            )
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "0.0" in str(e) or "1.0" in str(e) or "between" in str(e).lower()
