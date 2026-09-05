"""Tests for the retrieval-eval runner (BITB-051 P3).

Drives ``run_query``/``run_config`` with injected fakes — no database, no
network, no provider credentials — so orchestration and metric assembly are
covered in the standard (blocking) backend-tests CI job. The genuine live A/B
run against real search + Azure embeddings is a manual/maintainer step (see
docs/SEARCH_EVAL_HOWTO.md) or lands via P4 CI, not this test file.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, call

import pytest

from chat.topics import detect_topics
from config import settings
from scripture.search import SearchResults, VerseResult
from search_eval.models import GoldenCase
from search_eval.runner import (
    EVAL_CONFIGS,
    ChatServiceExpander,
    EmptyVerseTopicsError,
    EvalConfig,
    resolve_configs,
    run_config,
    run_query,
)


def _verse(reference: str) -> VerseResult:
    return VerseResult(
        reference=reference, text="...", book=reference.split()[0], chapter=1, verse=1
    )


def _fake_search_service(
    *, hybrid_refs=None, semantic_refs=None, boosted_refs=None, has_verse_topics=True
):
    """A fake exposing .search/.search_hybrid/.search_boosted/.search_hybrid_boosted
    and .has_verse_topics, recording call kwargs."""
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
    service.search_boosted = AsyncMock(
        return_value=SearchResults(
            query="q", verses=[_verse(r) for r in (boosted_refs or [])], passages=[]
        )
    )
    service.search_hybrid_boosted = AsyncMock(
        return_value=SearchResults(
            query="q", verses=[_verse(r) for r in (boosted_refs or [])], passages=[]
        )
    )
    service.has_verse_topics = AsyncMock(return_value=has_verse_topics)
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
    async def test_topic_boosted_calls_hybrid_boosted_with_detected_topics(self):
        service = _fake_search_service(boosted_refs=["Psalm 23:1"])
        result = await run_query(
            _case(query="I'm anxious"),
            EVAL_CONFIGS["topic_boosted"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        service.search_hybrid_boosted.assert_awaited_once()
        service.search_hybrid.assert_not_awaited()
        _, kwargs = service.search_hybrid_boosted.call_args
        assert kwargs["boost_topics"] == detect_topics("I'm anxious") == ["anxiety"]
        assert kwargs["topic_boost_factor"] == settings.topic_boost_factor
        assert kwargs["max_passages"] == 0
        assert result.retrieved == ["Psalm 23:1"]
        assert result.topic_boost_applied is True
        assert result.boost_topics == ["anxiety"]

    @pytest.mark.asyncio
    async def test_boosted_ranking_differs_from_unboosted(self):
        """AC: a boosted query ranks a topically-tagged verse differently from
        the unboosted query (the failure this story closes: a boosted config
        silently reporting the same numbers as unboosted)."""
        case = _case(query="I'm anxious", relevant_refs=["Psalm 23:1"])
        hybrid_service = _fake_search_service(hybrid_refs=["Genesis 1:1", "Psalm 23:1"])
        boosted_service = _fake_search_service(boosted_refs=["Psalm 23:1", "Genesis 1:1"])

        hybrid_result = await run_query(
            case,
            EVAL_CONFIGS["hybrid"],
            search_service=hybrid_service,
            embed=_fake_embed,
            expander=None,
        )
        boosted_result = await run_query(
            case,
            EVAL_CONFIGS["topic_boosted"],
            search_service=boosted_service,
            embed=_fake_embed,
            expander=None,
        )

        assert hybrid_result.retrieved != boosted_result.retrieved
        assert hybrid_result.mrr == pytest.approx(0.5)
        assert boosted_result.mrr == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_no_op_warning_is_gone(self, caplog):
        service = _fake_search_service(boosted_refs=["Psalm 23:1"])
        await run_query(
            _case(query="I'm anxious"),
            EVAL_CONFIGS["topic_boosted"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        assert not any(
            "no-op" in record.message or "falls back to non-boosted" in record.message
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_untagged_query_falls_back_to_plain_hybrid(self):
        query = "What does Genesis chapter one verse one say"
        assert detect_topics(query) == []
        service = _fake_search_service(hybrid_refs=["Genesis 1:1"])
        result = await run_query(
            _case(query=query),
            EVAL_CONFIGS["topic_boosted"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        service.search_hybrid.assert_awaited_once()
        service.search_hybrid_boosted.assert_not_awaited()
        assert result.topic_boost_applied is False
        assert result.error is None

    @pytest.mark.asyncio
    async def test_semantic_topic_boost_calls_search_boosted(self):
        config = EvalConfig(
            "semantic_boosted",
            use_hybrid=False,
            use_expansion=False,
            use_topic_boost=True,
        )
        service = _fake_search_service(boosted_refs=["Psalm 23:1"])
        result = await run_query(
            _case(query="I'm anxious"),
            config,
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        service.search_boosted.assert_awaited_once()
        service.search.assert_not_awaited()
        assert result.retrieved == ["Psalm 23:1"]

    @pytest.mark.asyncio
    async def test_empty_verse_topics_raises_before_any_query(self):
        service = _fake_search_service(has_verse_topics=False)
        with pytest.raises(EmptyVerseTopicsError, match="populate_verse_topics"):
            await run_config(
                [_case(query="I'm anxious")],
                EVAL_CONFIGS["topic_boosted"],
                search_service=service,
                embed=_fake_embed,
                expander=None,
            )
        service.search_hybrid_boosted.assert_not_awaited()
        service.search_hybrid.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_verse_topics_is_ignored_for_unboosted_configs(self):
        service = _fake_search_service(hybrid_refs=["John 3:16"], has_verse_topics=False)
        results = await run_config(
            [_case()],
            EVAL_CONFIGS["hybrid"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        assert len(results) == 1
        assert results[0].error is None
        service.has_verse_topics.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_verse_topics_probe_runs_once_per_config(self):
        service = _fake_search_service(boosted_refs=["Psalm 23:1"])
        cases = [_case(id=f"c{i}", query="I'm anxious") for i in range(3)]
        await run_config(
            cases,
            EVAL_CONFIGS["topic_boosted"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        assert service.has_verse_topics.await_count == 1
        service.has_verse_topics.assert_awaited_once_with("web")

    @pytest.mark.asyncio
    async def test_verse_topics_probe_uses_translation_override(self):
        service = _fake_search_service(boosted_refs=["Psalm 23:1"])
        await run_config(
            [_case(query="I'm anxious")],
            EVAL_CONFIGS["topic_boosted"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
            translation_override="kjv",
        )
        service.has_verse_topics.assert_awaited_once_with("kjv")

    @pytest.mark.asyncio
    async def test_verse_topics_probe_checks_every_topic_bearing_translation(self):
        service = _fake_search_service(boosted_refs=["Psalm 23:1"])
        service.has_verse_topics.side_effect = lambda translation: translation != "ita1927"
        cases = [
            _case(id="en", query="I'm anxious", language="en"),
            _case(id="it", query="Sono ansioso", language="it"),
            _case(id="neutral", query="What does John 3:16 say", language="de"),
        ]

        with pytest.raises(EmptyVerseTopicsError, match="ita1927"):
            await run_config(
                cases,
                EVAL_CONFIGS["topic_boosted"],
                search_service=service,
                embed=_fake_embed,
                expander=None,
            )

        assert service.has_verse_topics.await_args_list == [
            call("ita1927"),
            call("web"),
        ]
        service.search_hybrid_boosted.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_verse_topics_probe_skips_neutral_case_translations(self):
        service = _fake_search_service(hybrid_refs=["John 3:16"], has_verse_topics=False)
        await run_config(
            [_case(query="What does John 3:16 say", language="de")],
            EVAL_CONFIGS["topic_boosted"],
            search_service=service,
            embed=_fake_embed,
            expander=None,
        )
        service.has_verse_topics.assert_not_awaited()


class TestTopicBoostSweep:
    def test_no_factors_is_identity(self):
        configs = resolve_configs(["hybrid", "topic_boosted"])
        assert [c.name for c in configs] == ["hybrid", "topic_boosted"]
        assert configs[1].topic_boost_factor == settings.topic_boost_factor

    def test_sweep_expands_boosted_config_per_factor(self):
        configs = resolve_configs(["topic_boosted"], topic_boost_factors=[0.0, 0.2, 0.5])
        assert [c.name for c in configs] == [
            "topic_boosted@0",
            "topic_boosted@0.2",
            "topic_boosted@0.5",
        ]
        assert [c.topic_boost_factor for c in configs] == [0.0, 0.2, 0.5]
        base = EVAL_CONFIGS["topic_boosted"]
        for c in configs:
            assert c.use_hybrid == base.use_hybrid
            assert c.use_topic_boost == base.use_topic_boost

    def test_sweep_never_duplicates_non_boosted_configs(self):
        configs = resolve_configs(["hybrid", "topic_boosted"], topic_boost_factors=[0.1, 0.3])
        names = [c.name for c in configs]
        assert names == ["hybrid", "topic_boosted@0.1", "topic_boosted@0.3"]


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
        assert config.topic_boost_factor == settings.topic_boost_factor
