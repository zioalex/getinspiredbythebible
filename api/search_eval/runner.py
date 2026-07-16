"""Retrieval-evaluation runner (BITB-051 P3).

Runs golden-set queries through the *real* search pipeline under different
named configurations (semantic vs. hybrid, with/without query expansion), so
the harness measures actual ranking behaviour instead of a reimplementation
of it. Read-only: never writes to the database.

Standalone bootstrap (session + providers) mirrors
``scripts/migrations/run_migrations.py`` — this module can run outside the
FastAPI app via ``scripts/run_search_eval.py --run``.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from chat.service import ChatService
from config import settings
from providers import EmbeddingProvider, LLMProvider
from providers.factory import create_embedding_provider, create_llm_provider
from scripture.database import async_session_factory
from scripture.search import ScriptureSearchService
from utils.language import resolve_translation
from utils.logging_config import get_logger

from .metrics import false_positives_at_k, mrr, precision_at_k, recall_at_k
from .models import GoldenCase
from .normalize import parse_verse_key

logger = get_logger(__name__)

EmbedFn = Callable[[str], Awaitable[list[float]]]


@dataclass(frozen=True)
class EvalConfig:
    """One named search configuration to evaluate."""

    name: str
    use_hybrid: bool
    use_expansion: bool
    use_topic_boost: bool = False
    similarity_threshold: float = 0.35
    semantic_weight: float = settings.hybrid_search_semantic_weight
    keyword_weight: float = settings.hybrid_search_keyword_weight
    max_verses: int = max(settings.max_context_verses, 10)


# Named registry consumed by the CLI's --config flag. ``topic_boosted`` is a
# documented no-op (falls back to plain hybrid search + a warning) until
# BITB-044 populates verse_topics — kept here so the CLI can name it and the
# report can explain why its numbers equal ``hybrid``'s.
EVAL_CONFIGS: dict[str, EvalConfig] = {
    "baseline_semantic": EvalConfig("baseline_semantic", use_hybrid=False, use_expansion=False),
    "expansion_semantic": EvalConfig("expansion_semantic", use_hybrid=False, use_expansion=True),
    "hybrid": EvalConfig("hybrid", use_hybrid=True, use_expansion=False),
    "hybrid_expansion": EvalConfig("hybrid_expansion", use_hybrid=True, use_expansion=True),
    "topic_boosted": EvalConfig(
        "topic_boosted", use_hybrid=True, use_expansion=False, use_topic_boost=True
    ),
}

DEFAULT_AB: tuple[str, str] = ("baseline_semantic", "expansion_semantic")


class Expander(Protocol):
    """Expands a query into a thematically related search query."""

    async def expand(self, query: str, language: str) -> str: ...


class ChatServiceExpander:
    """Adapts ``ChatService._expand_query`` to the ``Expander`` protocol."""

    def __init__(self, chat_service: ChatService) -> None:
        self._chat_service = chat_service

    async def expand(self, query: str, language: str) -> str:
        return await self._chat_service._expand_query(query, language)


@dataclass
class QueryResult:
    """The scored outcome of running one golden-set case through one config."""

    case_id: str
    language: str
    config: str
    retrieved: list[str]
    precision_at_5: float
    recall_at_10: float
    mrr: float
    false_positives_at_5: int
    expansion_used: bool = False
    expansion_latency_ms: float | None = None
    error: str | None = None


@dataclass
class RunResult:
    """All per-query results from one evaluation run, across all configs."""

    configs: list[str]
    query_results: list[QueryResult]


async def run_query(
    case: GoldenCase,
    config: EvalConfig,
    *,
    search_service: ScriptureSearchService,
    embed: EmbedFn,
    expander: Expander | None,
) -> QueryResult:
    """Run one golden-set case through ``config`` and score the retrieval.

    Fail-open: any exception is caught and returned as a zero-scored error
    result so one bad query never aborts the whole run.
    """
    try:
        query_embedding = await embed(case.query)

        extra_embeddings: list[list[float]] | None = None
        expansion_used = False
        expansion_latency_ms: float | None = None
        if config.use_expansion:
            if expander is None:
                raise ValueError(f"config {config.name!r} requires an expander")
            start = time.monotonic()
            expanded = await expander.expand(case.query, case.language)
            expansion_latency_ms = (time.monotonic() - start) * 1000
            if expanded != case.query:
                extra_embeddings = [await embed(expanded)]
                expansion_used = True

        if config.use_topic_boost:
            logger.warning(
                "topic_boosted eval config is a no-op until BITB-044 populates "
                "verse_topics; falling back to non-boosted search",
                extra={"config": config.name},
            )

        translation = resolve_translation(case.translation, case.language)

        if config.use_hybrid:
            results = await search_service.search_hybrid(
                query=case.query,
                max_verses=config.max_verses,
                max_passages=0,
                similarity_threshold=config.similarity_threshold,
                translation=translation,
                semantic_weight=config.semantic_weight,
                keyword_weight=config.keyword_weight,
                extra_embeddings=extra_embeddings,
                query_embedding=query_embedding,
            )
        else:
            results = await search_service.search(
                query=case.query,
                max_verses=config.max_verses,
                max_passages=0,
                similarity_threshold=config.similarity_threshold,
                translation=translation,
                extra_embeddings=extra_embeddings,
                query_embedding=query_embedding,
            )

        retrieved_keys = [
            key for v in results.verses if (key := parse_verse_key(v.reference)) is not None
        ]
        relevant = case.relevant_matchers()
        irrelevant = case.irrelevant_matchers()

        return QueryResult(
            case_id=case.id,
            language=case.language,
            config=config.name,
            retrieved=[v.reference for v in results.verses],
            precision_at_5=precision_at_k(retrieved_keys, relevant, 5),
            recall_at_10=recall_at_k(retrieved_keys, relevant, 10),
            mrr=mrr(retrieved_keys, relevant),
            false_positives_at_5=false_positives_at_k(retrieved_keys, irrelevant, 5),
            expansion_used=expansion_used,
            expansion_latency_ms=expansion_latency_ms,
        )
    except Exception as exc:  # noqa: BLE001 - fail-open per query, log and continue
        logger.warning(
            "search-eval query failed, scoring as zero (fail-open)",
            extra={"case_id": case.id, "config": config.name, "error": str(exc)},
        )
        return QueryResult(
            case_id=case.id,
            language=case.language,
            config=config.name,
            retrieved=[],
            precision_at_5=0.0,
            recall_at_10=0.0,
            mrr=0.0,
            false_positives_at_5=0,
            error=str(exc),
        )


async def run_config(
    cases: list[GoldenCase],
    config: EvalConfig,
    *,
    search_service: ScriptureSearchService,
    embed: EmbedFn,
    expander: Expander | None,
) -> list[QueryResult]:
    """Run every case in ``cases`` through one config, in order."""
    return [
        await run_query(case, config, search_service=search_service, embed=embed, expander=expander)
        for case in cases
    ]


async def run_eval(
    cases: list[GoldenCase],
    config_names: Sequence[str],
    *,
    session=None,
    embedding_provider: EmbeddingProvider | None = None,
    llm_provider: LLMProvider | None = None,
) -> RunResult:
    """Run ``cases`` through every named config in ``config_names``.

    When ``session``/``embedding_provider``/``llm_provider`` are not supplied,
    bootstraps them standalone (outside the FastAPI app), the same pattern
    ``scripts/migrations/run_migrations.py`` uses. Read-only — no commits are
    ever made on the session.
    """
    configs = [EVAL_CONFIGS[name] for name in config_names]

    owns_session = session is None
    if session is None:
        session = async_session_factory()
    if embedding_provider is None:
        embedding_provider = create_embedding_provider(settings)
    if llm_provider is None and any(c.use_expansion for c in configs):
        llm_provider = create_llm_provider(settings)

    try:
        search_service = ScriptureSearchService(session, embedding_provider)

        async def embed(text: str) -> list[float]:
            response = await embedding_provider.embed(text)
            return response.embedding

        expander: Expander | None = None
        if llm_provider is not None:
            chat_service = ChatService(session, llm_provider, embedding_provider)
            expander = ChatServiceExpander(chat_service)

        query_results: list[QueryResult] = []
        for config in configs:
            query_results.extend(
                await run_config(
                    cases,
                    config,
                    search_service=search_service,
                    embed=embed,
                    expander=expander,
                )
            )

        return RunResult(configs=[c.name for c in configs], query_results=query_results)
    finally:
        if owns_session:
            await session.close()
