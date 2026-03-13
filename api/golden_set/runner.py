"""Golden set test runner.

Supports two modes:
- mock: Uses canned responses for CI/structural validation (no external deps)
- live: Uses real ChatService with actual LLM/embedding providers
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from golden_set.evaluators import run_all_checks
from golden_set.loader import load_test_cases
from golden_set.models import CaseResult, EvalRun, GoldenSetCase

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from providers.base import EmbeddingProvider, LLMProvider

RESULTS_DIR = Path(__file__).parent / "results"

# Canned mock responses by category for structural validation
MOCK_RESPONSES: dict[str, str] = {
    "encouragement": (
        "I hear that you're going through a difficult time, and those feelings "
        "are completely valid. Many people experience seasons of struggle.\n\n"
        "Scripture offers us comfort in Philippians 4:6-7: 'Do not be anxious "
        "about anything, but in everything by prayer and supplication, with "
        "thanksgiving, let your requests be made known to God.' Also, "
        "Psalm 34:18 reminds us: 'The Lord is close to the brokenhearted.'\n\n"
        "You are not alone in this."
    ),
    "verse_lookup": (
        "This is from the Bible. The passage you're asking about is found in "
        "the Gospel of John.\n\n"
        "John 3:16 says: 'For God so loved the world, that he gave his only "
        "begotten Son, that whosoever believeth in him should not perish, but "
        "have everlasting life.'\n\n"
        "This verse is one of the most well-known in all of Scripture. It "
        "summarizes the core message of the Christian gospel: God's love for "
        "humanity led to the sacrifice of Jesus, and through faith in him, "
        "people can receive eternal life.\n\n"
        "The context is a conversation between Jesus and Nicodemus, a Pharisee "
        "who came to Jesus at night to ask about spiritual matters."
    ),
    "prayer_lookup": (
        "This prayer is NOT from the Bible. It is a traditional Catholic prayer "
        "that developed during the medieval period.\n\n"
        "The Hail Mary combines elements from Luke 1:28 (the angel Gabriel's "
        "greeting) and Luke 1:42 (Elizabeth's blessing), but the prayer itself "
        "was composed by the Church.\n\n"
        "If you are looking for a prayer to use for devotion, you might consider "
        "the Lord's Prayer (Matthew 6:9-13), which Jesus himself taught."
    ),
    "theological": (
        "This is a profound question that Scripture addresses from multiple "
        "angles. In Romans 8:28 we read: 'And we know that in all things God "
        "works for the good of those who love him.'\n\n"
        "The book of Job also wrestles deeply with this question. In Psalm 46:1 "
        "we are reminded: 'God is our refuge and strength, a very present help "
        "in trouble.'\n\n"
        "While Scripture doesn't give us a simple answer, it consistently points "
        "us to a God who is present in our suffering."
    ),
    "multilingual": (
        "Capisco che stai attraversando un momento difficile, e i tuoi "
        "sentimenti sono completamente validi.\n\n"
        "La Bibbia ci offre conforto in Filippesi 4:6-7: 'Non angustiatevi "
        "di nulla, ma in ogni cosa fate conoscere le vostre richieste a Dio.'\n\n"
        "Il Salmo 34:18 ci ricorda: 'Il Signore e' vicino a quelli che hanno "
        "il cuore spezzato.'"
    ),
    "edge_cases": (
        "I understand you need help. The Bible offers guidance for many "
        "situations. In Psalm 46:1, we read: 'God is our refuge and strength, "
        "a very present help in trouble.'\n\n"
        "Whatever you're going through, know that you don't have to face "
        "it alone."
    ),
}


def _get_mock_response(case: GoldenSetCase) -> str:
    """Get a canned mock response for a test case based on its category."""
    return MOCK_RESPONSES.get(case.category, MOCK_RESPONSES["encouragement"])


async def run_mock(
    cases: list[GoldenSetCase] | None = None,
) -> EvalRun:
    """Run golden set in mock mode with canned responses.

    This mode validates evaluator logic and YAML schema without
    requiring any external services.
    """
    if cases is None:
        cases = load_test_cases()

    run_id = str(uuid.uuid4())[:8]
    results: list[CaseResult] = []

    for case in cases:
        response_text = _get_mock_response(case)

        automated_score = run_all_checks(response_text, case.expectations, case.input.message)

        results.append(
            CaseResult(
                run_id=run_id,
                case_id=case.id,
                timestamp=datetime.now(timezone.utc),
                provider="mock",
                model="mock-v1",
                input_message=case.input.message,
                actual_response=response_text,
                scripture_context=None,
                automated_score=automated_score,
                response_time_ms=0,
            )
        )

    return EvalRun(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc),
        provider="mock",
        model="mock-v1",
        mode="mock",
        results=results,
    )


async def run_live(
    db_session: "AsyncSession",  # noqa: F821 - imported at runtime
    llm_provider: "LLMProvider",  # noqa: F821
    embedding_provider: "EmbeddingProvider",  # noqa: F821
    cases: list[GoldenSetCase] | None = None,
    category: str | None = None,
) -> EvalRun:
    """Run golden set in live mode against real services.

    Args:
        db_session: Active database session.
        llm_provider: Configured LLM provider.
        embedding_provider: Configured embedding provider.
        cases: Optional specific cases to run (defaults to all).
        category: Optional category filter.

    Returns:
        EvalRun with results from all executed cases.
    """
    from chat.service import ChatRequest, ChatService, ConversationMessage

    if cases is None:
        cases = load_test_cases()

    if category:
        cases = [c for c in cases if c.category == category]

    service = ChatService(db_session, llm_provider, embedding_provider)
    run_id = str(uuid.uuid4())[:8]
    results: list[CaseResult] = []

    for case in cases:
        # Build conversation history
        history = [ConversationMessage(**msg) for msg in case.input.conversation_history]

        request = ChatRequest(
            message=case.input.message,
            conversation_history=history,
            include_search=case.input.include_search,
            preferred_translation=case.input.preferred_translation,
        )

        start_time = time.time()
        try:
            chat_response = await service.chat(request)
            elapsed_ms = int((time.time() - start_time) * 1000)

            scripture_ctx = None
            if chat_response.scripture_context:
                scripture_ctx = chat_response.scripture_context.model_dump()

            automated_score = run_all_checks(
                chat_response.message, case.expectations, case.input.message
            )

            results.append(
                CaseResult(
                    run_id=run_id,
                    case_id=case.id,
                    timestamp=datetime.now(timezone.utc),
                    provider=chat_response.provider,
                    model=chat_response.model,
                    input_message=case.input.message,
                    actual_response=chat_response.message,
                    scripture_context=scripture_ctx,
                    automated_score=automated_score,
                    response_time_ms=elapsed_ms,
                )
            )
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            results.append(
                CaseResult(
                    run_id=run_id,
                    case_id=case.id,
                    timestamp=datetime.now(timezone.utc),
                    provider=llm_provider.provider_name,
                    model="error",
                    input_message=case.input.message,
                    actual_response=f"ERROR: {type(e).__name__}: {e}",
                    automated_score=run_all_checks("", case.expectations),
                    response_time_ms=elapsed_ms,
                )
            )

    provider_name = results[0].provider if results else "unknown"
    model_name = results[0].model if results else "unknown"

    return EvalRun(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc),
        provider=provider_name,
        model=model_name,
        mode="live",
        results=results,
    )


def save_run(run: EvalRun, directory: Path | None = None) -> Path:
    """Save an EvalRun to a JSON file.

    Args:
        run: The evaluation run to save.
        directory: Directory to save to (defaults to golden_set/results/).

    Returns:
        Path to the saved file.
    """
    directory = directory or RESULTS_DIR
    directory.mkdir(parents=True, exist_ok=True)

    filename = f"{run.run_id}_{run.mode}_{run.provider}.json"
    file_path = directory / filename

    with open(file_path, "w") as f:
        json.dump(run.model_dump(mode="json"), f, indent=2, default=str)

    return file_path


def load_run(file_path: Path) -> EvalRun:
    """Load an EvalRun from a JSON file."""
    with open(file_path) as f:
        data = json.load(f)
    return EvalRun(**data)


def list_runs(directory: Path | None = None) -> list[Path]:
    """List all saved run files, newest first."""
    directory = directory or RESULTS_DIR
    if not directory.exists():
        return []
    return sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def get_latest_run(directory: Path | None = None) -> EvalRun | None:
    """Load the most recent saved run."""
    runs = list_runs(directory)
    if not runs:
        return None
    return load_run(runs[0])


def print_summary(run: EvalRun) -> None:
    """Print a summary of an evaluation run to stdout."""
    total = len(run.results)
    passed = sum(1 for r in run.results if r.automated_score.passed)
    failed = total - passed

    print(f"\n{'=' * 60}")
    print(f"Golden Set Run: {run.run_id}")
    print(f"Mode: {run.mode} | Provider: {run.provider} | Model: {run.model}")
    print(f"Date: {run.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 60}")
    print(f"Total: {total} | Passed: {passed} | Failed: {failed}")

    if total > 0:
        rate = passed / total * 100
        print(f"Pass rate: {rate:.1f}%")

    if failed > 0:
        print(f"\n{'─' * 60}")
        print("Failed cases:")
        for r in run.results:
            if not r.automated_score.passed:
                print(f"  {r.case_id}: {r.automated_score.failed_checks}")

    print(f"{'=' * 60}\n")
