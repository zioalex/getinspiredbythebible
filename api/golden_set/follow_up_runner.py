"""Live runner for the follow-up chip golden set (BITB-178).

Sends curated cases to a running backend (streaming endpoint by default, the
same one the apps use), evaluates the chips with ``follow_up_evaluators`` and
renders reports. All HTTP goes through an injected ``httpx.Client`` and an
injected ``sleep`` so the logic is unit-testable with ``httpx.MockTransport``.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from golden_set.follow_up_evaluators import (
    CheckResult,
    build_score,
    check_follow_ups,
    check_multi_turn,
)
from golden_set.models import AutomatedScore, GoldenSetCase

Mode = Literal["stream", "json"]

SCENARIOS = ("expected", "verse-citing", "suppressed", "multi-turn")
STREAM_PATH = "/api/v1/chat/stream"
JSON_PATH = "/api/v1/chat"
RETRY_STATUSES = frozenset({429, 503})
MAX_RETRIES = 3
DEFAULT_RETRY_AFTER = 10.0
EXCERPT_LEN = 200

EXPECTED_BEHAVIOUR = {
    "expected": "2-3 chips appear, in the answer's language, each short and a natural next question.",
    "verse-citing": (
        "2-3 chips appear; any verse reference in a chip is also cited in the answer."
    ),
    "suppressed": "No chips at all (crisis / help-seeking or off-topic).",
    "multi-turn": "Tap the first chip: turn 2 gets valid chips, not the tapped question again.",
}

CRISIS_NOTE = (
    "Crisis cases depend on the configured content-safety provider: a crisis case that shows "
    "chips usually points at the safety configuration, not at the chips feature."
)
FLAG_HINT = "CHAT_FOLLOW_UPS_ENABLED is probably off on this backend."


class BackendUnreachableError(Exception):
    """The backend could not be contacted at all (connection refused, DNS, timeout)."""


class BackendError(Exception):
    """The backend answered, but not with a usable chat response."""


class TurnOutcome(BaseModel):
    """What one chat request returned."""

    answer: str = ""
    follow_ups: list[str] = []


class FollowUpCaseResult(BaseModel):
    """Result of running one golden-set case against the backend."""

    case_id: str
    language: str
    scenario: str
    chips: list[list[str]] = []
    answer_excerpt: str = ""
    score: AutomatedScore | None = None
    elapsed_ms: int = 0
    error: str | None = None

    @property
    def passed(self) -> bool:
        """True when the case ran without error and every check passed."""
        return self.error is None and self.score is not None and self.score.passed


def scenario_of(case: GoldenSetCase) -> str:
    """Return the scenario tag (one of ``SCENARIOS``) carried by a case."""
    for tag in case.tags:
        if tag in SCENARIOS:
            return tag
    return "unknown"


def language_of(case: GoldenSetCase) -> str:
    """Language code of a case (input language, falling back to the expectation)."""
    return case.input.language or case.expectations.response_language


def _retry_delay(response: httpx.Response) -> float:
    raw = response.headers.get("Retry-After", "")
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_RETRY_AFTER


def _parse_sse(lines: Any) -> TurnOutcome:
    """Fold SSE ``data:`` lines into the final answer and chips."""
    parts: list[str] = []
    corrected: str | None = None
    follow_ups: list[str] = []
    for line in lines:
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if payload == "[DONE]":
            break
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "content":
            parts.append(event.get("content", ""))
        elif kind == "error":
            raise BackendError(f"stream error: {event.get('error', 'unknown error')}")
        elif kind == "completion":
            corrected = event.get("corrected_message")
            follow_ups = list(event.get("follow_ups") or [])
    answer = corrected if corrected is not None else "".join(parts)
    return TurnOutcome(answer=answer, follow_ups=follow_ups)


def _send_stream(client: httpx.Client, body: dict[str, Any]) -> tuple[int, TurnOutcome, float]:
    with client.stream("POST", STREAM_PATH, json=body) as response:
        if response.status_code != 200:
            response.read()
            return response.status_code, TurnOutcome(), _retry_delay(response)
        return 200, _parse_sse(response.iter_lines()), 0.0


def _send_json(client: httpx.Client, body: dict[str, Any]) -> tuple[int, TurnOutcome, float]:
    response = client.post(JSON_PATH, json=body)
    if response.status_code != 200:
        return response.status_code, TurnOutcome(), _retry_delay(response)
    data = response.json()
    return (
        200,
        TurnOutcome(answer=data.get("message", ""), follow_ups=list(data.get("follow_ups") or [])),
        0.0,
    )


def send_turn(
    client: httpx.Client,
    mode: Mode,
    body: dict[str, Any],
    sleep: Callable[[float], None] = time.sleep,
) -> TurnOutcome:
    """POST one chat turn, retrying 429/503 up to ``MAX_RETRIES`` times."""
    sender = _send_stream if mode == "stream" else _send_json
    for attempt in range(MAX_RETRIES + 1):
        try:
            status, outcome, delay = sender(client, body)
        except httpx.TransportError as exc:
            raise BackendUnreachableError(f"{type(exc).__name__}: {exc}") from exc
        if status == 200:
            return outcome
        if status in RETRY_STATUSES and attempt < MAX_RETRIES:
            sleep(delay)
            continue
        raise BackendError(f"HTTP {status}")
    raise BackendError("retries exhausted")  # pragma: no cover


def _request_body(
    case: GoldenSetCase, message: str, history: list[dict[str, str]], session_id: str
) -> dict[str, Any]:
    return {
        "message": message,
        "conversation_history": history,
        "include_search": case.input.include_search,
        "preferred_translation": case.input.preferred_translation,
        "language": case.input.language,
        "session_id": session_id,
    }


def _tap_checks(
    client: httpx.Client,
    mode: Mode,
    case: GoldenSetCase,
    turn1: TurnOutcome,
    session_id: str,
    sleep: Callable[[float], None],
) -> tuple[list[CheckResult], TurnOutcome | None]:
    """Turn 2 of a multi-turn case: tap the first chip and evaluate the reply."""
    if not turn1.follow_ups:
        return [("follow_up_tap", False, "no chip to tap")], None
    tapped = turn1.follow_ups[0]
    history = [
        {"role": "user", "content": case.input.message},
        {"role": "assistant", "content": turn1.answer},
    ]
    turn2 = send_turn(client, mode, _request_body(case, tapped, history, session_id), sleep)
    expectations = case.expectations.model_copy(update={"follow_ups": "expected"})
    checks = check_follow_ups(turn2.follow_ups, turn2.answer, expectations)
    checks += check_multi_turn(turn1.follow_ups, tapped, turn2.follow_ups)
    return [(f"turn2_{name}", ok, detail) for name, ok, detail in checks], turn2


def _evaluate(
    client: httpx.Client,
    mode: Mode,
    case: GoldenSetCase,
    session_id: str,
    sleep: Callable[[float], None],
) -> tuple[AutomatedScore, list[list[str]], str]:
    turn1 = send_turn(client, mode, _request_body(case, case.input.message, [], session_id), sleep)
    checks = check_follow_ups(turn1.follow_ups, turn1.answer, case.expectations)
    chips = [turn1.follow_ups]
    if case.input.tap_follow_up:
        checks = [(f"turn1_{name}", ok, detail) for name, ok, detail in checks]
        extra, turn2 = _tap_checks(client, mode, case, turn1, session_id, sleep)
        checks += extra
        if turn2 is not None:
            chips.append(turn2.follow_ups)
    return build_score(checks), chips, turn1.answer


def run_case(
    client: httpx.Client,
    case: GoldenSetCase,
    *,
    mode: Mode = "stream",
    sleep: Callable[[float], None] = time.sleep,
) -> FollowUpCaseResult:
    """Run one case against the backend and evaluate it.

    ``BackendError`` is captured on the result; ``BackendUnreachableError`` propagates
    so the CLI can exit with a clear message.
    """
    result = FollowUpCaseResult(
        case_id=case.id, language=language_of(case), scenario=scenario_of(case)
    )
    session_id = "fu-eval-" + uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        score, chips, answer = _evaluate(client, mode, case, session_id, sleep)
        result.score, result.chips, result.answer_excerpt = score, chips, answer[:EXCERPT_LEN]
    except BackendError as exc:
        result.error = str(exc)
    result.elapsed_ms = int((time.perf_counter() - start) * 1000)
    return result


def _tally(results: list[FollowUpCaseResult], key: Callable[[FollowUpCaseResult], str]) -> dict:
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "passed": 0})
    for r in results:
        buckets[key(r)]["total"] += 1
        buckets[key(r)]["passed"] += int(r.passed)
    return dict(sorted(buckets.items()))


def summarize(results: list[FollowUpCaseResult]) -> dict[str, Any]:
    """Totals overall, per language and per scenario, plus diagnostic hints."""
    expected = [r for r in results if r.scenario == "expected"]
    all_empty = bool(expected) and all(not (r.chips and r.chips[0]) for r in expected)
    return {
        "total": len(results),
        "passed": sum(r.passed for r in results),
        "failed": sum(not r.passed for r in results),
        "by_language": _tally(results, lambda r: r.language),
        "by_scenario": _tally(results, lambda r: r.scenario),
        "hint": FLAG_HINT if all_empty else None,
        "note": CRISIS_NOTE,
    }


def _case_line(r: FollowUpCaseResult) -> str:
    status = "PASS" if r.passed else "FAIL"
    line = f"[{status}] {r.case_id} ({r.scenario}) {r.elapsed_ms}ms chips={r.chips}"
    if r.error:
        return f"{line}\n       error: {r.error}"
    if r.score and not r.score.passed:
        failures = [f"{n}: {r.score.details[n]['detail']}" for n in r.score.failed_checks]
        return line + "".join(f"\n       {f}" for f in failures)
    return line


def _tally_lines(title: str, tally: dict) -> list[str]:
    lines = [f"{title}:"]
    lines += [f"  {k:<14} {v['passed']}/{v['total']}" for k, v in tally.items()]
    return lines


def render_text_report(results: list[FollowUpCaseResult]) -> str:
    """Human-readable per-case, per-language and per-scenario report."""
    summary = summarize(results)
    lines = [_case_line(r) for r in results]
    lines += [""] + _tally_lines("By language", summary["by_language"])
    lines += [""] + _tally_lines("By scenario", summary["by_scenario"])
    lines += ["", f"Total: {summary['passed']}/{summary['total']} passed"]
    if summary["hint"]:
        lines.append(f"HINT: {summary['hint']}")
    lines.append(f"Note: {summary['note']}")
    return "\n".join(lines)


def render_json(results: list[FollowUpCaseResult]) -> str:
    """Machine-readable results plus the summary."""
    payload = {
        "summary": summarize(results),
        "results": [r.model_dump() | {"passed": r.passed} for r in results],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_checklist(cases: list[GoldenSetCase]) -> str:
    """Markdown checklist for manual on-device testing, grouped by language."""
    by_lang: dict[str, list[GoldenSetCase]] = defaultdict(list)
    for case in cases:
        by_lang[language_of(case)].append(case)
    lines = ["# Follow-up chips manual checklist (BITB-178)", ""]
    for lang, lang_cases in by_lang.items():
        lines += [f"## {lang}", ""]
        for case in lang_cases:
            scenario = scenario_of(case)
            lines.append(f'- [ ] **{case.id}** ({scenario}) — "{case.input.message}"')
            lines.append(f"  - Expected: {EXPECTED_BEHAVIOUR.get(scenario, 'see story')}")
        lines.append("")
    return "\n".join(lines)
