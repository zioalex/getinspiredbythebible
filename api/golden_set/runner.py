"""Run golden set cases and record results (BITB-177).

Two modes:

- ``run_mock``: no API. Every case gets a fixed placeholder answer, which exercises the
  loading / scoring / saving pipeline (the checks themselves are expected to fail).
- ``run_live``: POSTs each case, including its conversation history, language and
  translation, to a running API's ``/api/v1/chat`` and scores the real answer with the
  automated checks. Meant for a local or dev API where Turnstile is off, or for production
  through the server-to-server probe header (``X-Monitor-Probe-Secret``); a 403 is reported
  as "blocked", distinct from a model failure.

String checks are a floor, not a proof of correct exegesis; read the saved responses.
"""

import asyncio
import os
import sys
import time
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

import httpx

from golden_set.evaluators import run_all_checks
from golden_set.models import AutomatedScore, CaseResult, EvalRun, GoldenSetCase

RESULTS_DIR = Path(__file__).parent / "results"
CHAT_PATH = "/api/v1/chat"
# Same header name as utils.monitor_probe.PROBE_HEADER. Repeated here (not imported) because
# importing utils.monitor_probe pulls config.settings, which a CLI run should not need.
PROBE_HEADER = "X-Monitor-Probe-Secret"  # noqa: S105 - header name, not a secret
PROBE_SECRET_ENV = "GOLDEN_SET_PROBE_SECRET"  # noqa: S105 - env var name, not a secret
MOCK_RESPONSE = "[mock response] No API was called; this only exercises the runner pipeline."

# failed_checks markers for results that never reached the automated checks.
BLOCKED = "blocked"
HTTP_ERROR = "http_error"
REQUEST_ERROR = "request_error"
_TRANSPORT_FAILURES = {BLOCKED, HTTP_ERROR, REQUEST_ERROR}


def _new_run_id(mode: str) -> str:
    return f"{mode}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"


def _score_response(case: GoldenSetCase, response: str) -> AutomatedScore:
    return run_all_checks(response, case.expectations, case.input.message)


def _failed_score(marker: str, detail: str) -> AutomatedScore:
    return AutomatedScore(
        passed=False,
        total_checks=1,
        passed_checks=0,
        failed_checks=[marker],
        details={marker: detail},
    )


def build_payload(case: GoldenSetCase) -> dict:
    """Build the ``ChatRequest`` JSON body for a case (history, language, translation)."""
    payload: dict = {
        "message": case.input.message,
        "conversation_history": case.input.conversation_history,
        "include_search": case.input.include_search,
    }
    if case.input.preferred_translation:
        payload["preferred_translation"] = case.input.preferred_translation
    if case.input.language:
        payload["language"] = case.input.language
    return payload


def run_mock(cases: list[GoldenSetCase]) -> EvalRun:
    """Run every case against a placeholder answer (no API, no network)."""
    run_id = _new_run_id("mock")
    now = datetime.now(timezone.utc)
    results = [
        CaseResult(
            run_id=run_id,
            case_id=case.id,
            timestamp=now,
            provider="mock",
            model="mock",
            input_message=case.input.message,
            actual_response=MOCK_RESPONSE,
            automated_score=_score_response(case, MOCK_RESPONSE),
        )
        for case in cases
    ]
    return EvalRun(
        run_id=run_id,
        timestamp=now,
        provider="mock",
        model="mock",
        mode="mock",
        results=results,
        metadata={"case_count": len(cases)},
    )


async def _live_one(
    client: httpx.AsyncClient,
    url: str,
    case: GoldenSetCase,
    run_id: str,
    timeout: float,
    headers: dict[str, str] | None,
) -> CaseResult:
    """Send one case and turn the outcome (answer, HTTP error or transport error) into a result."""
    started = time.monotonic()
    provider = model = "unknown"
    response_text = ""
    scripture_context: dict | None = None
    try:
        resp = await client.post(url, json=build_payload(case), headers=headers, timeout=timeout)
    except httpx.HTTPError as e:
        # Exception class only, not its message: the request carries the probe header and a
        # message may echo request details.
        score = _failed_score(REQUEST_ERROR, type(e).__name__)
    else:
        if resp.status_code == 200:
            try:
                body = resp.json()
                response_text = body.get("message") or ""
                provider = body.get("provider") or provider
                model = body.get("model") or model
                scripture_context = body.get("scripture_context")
                score = _score_response(case, response_text)
            except ValueError as e:
                score = _failed_score(HTTP_ERROR, f"HTTP 200 with an unreadable body: {e}")
        elif resp.status_code == 403:
            score = _failed_score(BLOCKED, "blocked (Turnstile / edge): HTTP 403")
        else:
            score = _failed_score(HTTP_ERROR, f"HTTP {resp.status_code}")
    return CaseResult(
        run_id=run_id,
        case_id=case.id,
        timestamp=datetime.now(timezone.utc),
        provider=provider,
        model=model,
        input_message=case.input.message,
        actual_response=response_text,
        scripture_context=scripture_context,
        automated_score=score,
        response_time_ms=int((time.monotonic() - started) * 1000),
    )


async def run_live(
    cases: list[GoldenSetCase],
    base_url: str,
    timeout: float = 120.0,
    delay: float = 0.0,
    client: httpx.AsyncClient | None = None,
    headers: dict[str, str] | None = None,
) -> EvalRun:
    """Send every case to ``{base_url}/api/v1/chat`` and score the answers.

    Args:
        cases: Cases to run, in order (sequential, so ``delay`` is a real pause).
        base_url: API root, e.g. ``http://localhost:8000``.
        timeout: Per-request timeout in seconds.
        delay: Seconds to sleep between requests (be kind to rate limits).
        client: Optional ``httpx.AsyncClient`` (tests inject a mocked transport).
        headers: Extra request headers, e.g. the probe header from ``probe_headers_from_env``.
            Their values are never stored in the returned run.
    """
    run_id = _new_run_id("live")
    url = base_url.rstrip("/") + CHAT_PATH
    owns_client = client is None
    http = client or httpx.AsyncClient()
    results: list[CaseResult] = []
    try:
        for i, case in enumerate(cases):
            if i and delay > 0:
                await asyncio.sleep(delay)
            results.append(await _live_one(http, url, case, run_id, timeout, headers))
    finally:
        if owns_client:
            await http.aclose()

    answered = [r for r in results if r.provider != "unknown"]
    return EvalRun(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc),
        provider=answered[0].provider if answered else "unknown",
        model=answered[0].model if answered else "unknown",
        mode="live",
        results=results,
        metadata={
            "base_url": base_url,
            "case_count": len(cases),
            "timeout": timeout,
            "probe_header_sent": bool(headers and PROBE_HEADER in headers),
        },
    )


def probe_headers_from_env(environ: Mapping[str, str] | None = None) -> dict[str, str] | None:
    """Build the probe header from ``GOLDEN_SET_PROBE_SECRET``; None when unset or empty.

    The secret is read from the environment only (never argv, so it cannot show up in a
    process list) and is not printed or saved anywhere by this module.
    """
    env = os.environ if environ is None else environ
    secret = env.get(PROBE_SECRET_ENV, "")
    return {PROBE_HEADER: secret} if secret else None


def has_scorable_answer(run: EvalRun) -> bool:
    """True when at least one case reached the automated checks (not blocked / errored)."""
    return any(_failure_kind(r) is None for r in run.results)


def save_run(run: EvalRun, path: Path | None = None) -> Path:
    """Write a run as JSON. Defaults to ``golden_set/results/<run_id>.json`` (gitignored)."""
    target = path or RESULTS_DIR / f"{run.run_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    return target


def load_run(path: Path) -> EvalRun:
    """Load a run saved by ``save_run``."""
    return EvalRun.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _failure_kind(result: CaseResult) -> str | None:
    """Return the transport marker when the case never produced a scorable answer."""
    for marker in result.automated_score.failed_checks:
        if marker in _TRANSPORT_FAILURES:
            return marker
    return None


def summarize(run: EvalRun) -> dict:
    """Counts used by ``print_summary`` and the CLI's ``--fail-under`` gate.

    ``pass_rate`` is passed / total, so blocked and errored cases count against it.
    """
    total = len(run.results)
    blocked = sum(1 for r in run.results if _failure_kind(r) == BLOCKED)
    errored = sum(1 for r in run.results if _failure_kind(r) in (HTTP_ERROR, REQUEST_ERROR))
    passed = sum(1 for r in run.results if r.automated_score.passed)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed - blocked - errored,
        "blocked": blocked,
        "errored": errored,
        "pass_rate": (passed / total) if total else 0.0,
    }


def print_summary(run: EvalRun, out: TextIO | None = None) -> None:
    """Print a human-readable summary: totals, then one line per non-passing case."""
    out = out or sys.stdout
    s = summarize(run)
    print(f"Golden set run {run.run_id} ({run.mode}; {run.provider}/{run.model})", file=out)
    print(
        f"  {s['passed']}/{s['total']} passed ({s['pass_rate']:.0%}); "
        f"{s['failed']} failed checks, {s['blocked']} blocked, {s['errored']} errored",
        file=out,
    )
    if s["blocked"]:
        print(
            "  Blocked = HTTP 403 (Turnstile / edge). Point --base-url at a local or dev API "
            "with Turnstile off; blocked cases say nothing about the model.",
            file=out,
        )
    for r in run.results:
        if r.automated_score.passed:
            continue
        kind = _failure_kind(r)
        label = kind.upper() if kind else "FAIL"
        detail = (
            r.automated_score.details.get(kind, "")
            if kind
            else ", ".join(r.automated_score.failed_checks)
        )
        print(f"  [{label}] {r.case_id}: {detail}", file=out)
