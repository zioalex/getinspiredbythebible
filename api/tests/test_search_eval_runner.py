"""Tests for the retrieval-eval runner (BITB-051 P3).

Drives ``run_query``/``run_config`` with injected fakes — no database, no
network, no provider credentials — so orchestration and metric assembly are
covered in the standard (blocking) backend-tests CI job. The genuine live A/B
run against real search + Azure embeddings is a manual/maintainer step (see
docs/SEARCH_EVAL_HOWTO.md) or lands via P4 CI, not this test file.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from scripture.search import SearchResults, VerseResult
from search_eval.models import GoldenCase
from search_eval.runner import (
    EVAL_CONFIGS,
    ChatServiceExpander,
    EvalConfig,
    run_config,
    run_query,
)


def _verse(reference: str) -> VerseResult:
    return VerseResult(
        reference=reference, text="...", book=reference.split()[0], chapter=1, verse=1
    )


def _fake_search_service(*, hybrid_refs=None, semantic_refs=None):
    """A fake exposing only .search / .search_hybrid, recording call kwargs."""
    service = AsyncMock()
    service.search = AsyncMock(
        return_value=SearchResults(
            query="q", verses=[_verse(r) for r in (semantic_refs or [])], passages=[]
        )
    )
    service.search_hybrid = AsyncMock(
        return_value=SearchResults(
            query="q", verses=[_verse(r) for r in (hybrid_refs or [])], passages=[]
        )
    )
    return service


async def _fake_embed(text: str) -> list[float]:
    return [0.1, 0.2, 0.3]


class _FakeExpander:
    def __init__(self, expanded: str):
        self._expanded = expanded
        self.calls: list[tuple[str, str]] = []

    async def expand(self, query: str, language: str) -> str:
        self.calls.append((query, language))
        return self._expanded


def _case(**overrides: Any) -> GoldenCase:
    defaults: dict[str, Any] = dict(
        id="c1", query="I'm anxious", language="en", relevant_refs=["John 3:16"]
    )
    defaults.update(overrides)
    return GoldenCase(**defaults)


class TestDispatch:
    @pytest.mark.asyncio
    async def test_semantic_config_calls_search(self):
        service = _fake_search_service(semantic_refs=["John 3:16"])
        result = await run_query(
            _case(),
            EVAL_CONFIGS["baseline_semantic"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        service.search.assert_awaited_once()
        service.search_hybrid.assert_not_awaited()
        assert result.retrieved == ["John 3:16"]
        assert result.precision_at_5 == pytest.approx(0.2)
        assert result.error is None

    @pytest.mark.asyncio
    async def test_hybrid_config_calls_search_hybrid(self):
        service = _fake_search_service(hybrid_refs=["John 3:16"])
        result = await run_query(
            _case(),
            EVAL_CONFIGS["hybrid"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        service.search_hybrid.assert_awaited_once()
        service.search.assert_not_awaited()
        assert result.retrieved == ["John 3:16"]

    @pytest.mark.asyncio
    async def test_translation_override_bypasses_resolve_translation(self):
        """BITB-107 (live-verified against eval-smoke): resolve_translation()'s
        readiness-aware language default silently resolves to a translation a
        standalone-CLI corpus never loaded, always returning zero rows. When
        translation_override is given, it must be used verbatim instead."""
        service = _fake_search_service(semantic_refs=[])
        await run_query(
            _case(language="en"),
            EVAL_CONFIGS["baseline_semantic"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
            translation_override="kjv",
        )
        _, kwargs = service.search.call_args
        # Without the override, English resolves to "web" (see
        # utils.language.LANGUAGE_TO_TRANSLATION) -- the override must win.
        assert kwargs["translation"] == "kjv"

    @pytest.mark.asyncio
    async def test_no_translation_override_uses_resolve_translation(self):
        """Without an override, behaviour is unchanged: English resolves to
        the language default ("web"), not the override path."""
        service = _fake_search_service(semantic_refs=[])
        await run_query(
            _case(language="en"),
            EVAL_CONFIGS["baseline_semantic"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        _, kwargs = service.search.call_args
        assert kwargs["translation"] == "web"

    @pytest.mark.asyncio
    async def test_max_verses_at_least_ten(self):
        service = _fake_search_service(semantic_refs=[])
        await run_query(
            _case(),
            EVAL_CONFIGS["baseline_semantic"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        _, kwargs = service.search.call_args
        assert kwargs["max_verses"] >= 10


class TestExpansion:
    @pytest.mark.asyncio
    async def test_expansion_changes_query_adds_extra_embedding(self):
        service = _fake_search_service(semantic_refs=["John 3:16"])
        expander = _FakeExpander("anxiety peace trust God")
        result = await run_query(
            _case(),
            EVAL_CONFIGS["expansion_semantic"],
            search_service=service,
            embed=_fake_embed,
            expander=expander,
        )
        assert expander.calls == [("I'm anxious", "en")]
        _, kwargs = service.search.call_args
        assert kwargs["extra_embeddings"] is not None
        assert len(kwargs["extra_embeddings"]) == 1
        assert result.expansion_used is True
        assert result.expansion_latency_ms is not None

    @pytest.mark.asyncio
    async def test_expansion_no_change_skips_extra_embedding(self):
        service = _fake_search_service(semantic_refs=[])
        expander = _FakeExpander("I'm anxious")  # unchanged (fail-open fallback)
        result = await run_query(
            _case(),
            EVAL_CONFIGS["expansion_semantic"],
            search_service=service,
            embed=_fake_embed,
            expander=expander,
        )
        _, kwargs = service.search.call_args
        assert kwargs["extra_embeddings"] is None
        assert result.expansion_used is False

    @pytest.mark.asyncio
    async def test_expansion_config_without_expander_errors_fail_open(self):
        service = _fake_search_service(semantic_refs=[])
        result = await run_query(
            _case(),
            EVAL_CONFIGS["expansion_semantic"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        assert result.error is not None
        assert result.precision_at_5 == 0.0


class TestTopicBoosted:
    @pytest.mark.asyncio
    async def test_topic_boosted_falls_back_to_hybrid_and_warns(self, caplog):
        service = _fake_search_service(hybrid_refs=["John 3:16"])
        result = await run_query(
            _case(),
            EVAL_CONFIGS["topic_boosted"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        service.search_hybrid.assert_awaited_once()
        assert result.retrieved == ["John 3:16"]
        assert any("topic_boosted" in record.message for record in caplog.records)


class TestFailOpen:
    @pytest.mark.asyncio
    async def test_search_error_scores_zero_and_records_error(self):
        service = _fake_search_service()
        service.search = AsyncMock(side_effect=RuntimeError("db unreachable"))
        result = await run_query(
            _case(),
            EVAL_CONFIGS["baseline_semantic"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        # BITB-107: the recorded error is rendered via _describe_exception,
        # which includes the exception's type name alongside its message
        # (rather than bare str(exc)) so a chained cause is never silently
        # dropped -- see test_error_records_full_exception_chain below.
        assert result.error == "RuntimeError: db unreachable"
        assert result.precision_at_5 == 0.0
        assert result.recall_at_10 == 0.0
        assert result.mrr == 0.0
        assert result.retrieved == []

    @pytest.mark.asyncio
    async def test_error_records_full_exception_chain(self):
        """BITB-107: openai.APIConnectionError's __str__() is a fixed,
        uninformative constant ("Connection error.") -- the real cause lives
        on __cause__/__context__, which bare str(exc) discarded. Guard
        against that regression: the recorded error string must carry both
        the outer and the inner exception's class name and message."""

        class InnerError(Exception):
            pass

        class OuterError(Exception):
            pass

        async def raising_search(**kwargs):
            try:
                raise InnerError("illegal header value")
            except InnerError as inner:
                raise OuterError("Connection error.") from inner

        service = _fake_search_service()
        service.search = AsyncMock(side_effect=raising_search)
        result = await run_query(
            _case(),
            EVAL_CONFIGS["baseline_semantic"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        assert result.error is not None
        assert "OuterError" in result.error
        assert "Connection error." in result.error
        assert "InnerError" in result.error
        assert "illegal header value" in result.error

    @pytest.mark.asyncio
    async def test_one_bad_case_does_not_abort_the_config_run(self):
        service = _fake_search_service(semantic_refs=["John 3:16"])
        good = _case(id="good")
        bad = _case(id="bad")
        call_count = {"n": 0}

        async def flaky_search(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("boom")
            return SearchResults(query="q", verses=[_verse("John 3:16")], passages=[])

        service.search = AsyncMock(side_effect=flaky_search)
        results = await run_config(
            [bad, good],
            EVAL_CONFIGS["baseline_semantic"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        assert len(results) == 2
        assert results[0].error is not None
        assert results[1].error is None


class TestChatServiceExpander:
    @pytest.mark.asyncio
    async def test_delegates_to_expand_query(self):
        chat_service = AsyncMock()
        chat_service._expand_query = AsyncMock(return_value="expanded text")
        expander = ChatServiceExpander(chat_service)
        result = await expander.expand("original", "en")
        assert result == "expanded text"
        chat_service._expand_query.assert_awaited_once_with("original", "en")


class TestEvalConfigs:
    def test_default_ab_pair_present(self):
        from search_eval.runner import DEFAULT_AB

        assert DEFAULT_AB == ("baseline_semantic", "expansion_semantic")
        assert set(DEFAULT_AB).issubset(EVAL_CONFIGS)

    def test_topic_boosted_is_hybrid_flagged(self):
        config = EVAL_CONFIGS["topic_boosted"]
        assert isinstance(config, EvalConfig)
        assert config.use_topic_boost is True
        assert config.use_hybrid is True
