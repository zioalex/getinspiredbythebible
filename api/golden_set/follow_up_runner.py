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
DEFAULT_RETRY_AFTER = 60.0  # matches the backend's own hint for per-minute limits
DEFAULT_UPSTREAM_RETRY_AFTER = 10.0
MAX_UPSTREAM_RETRIES = 1
ERROR_BODY_LEN = 200
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
    """The backend could not be contacted at all (connection refused, DNS, connect timeout)."""


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
    kind: str | None = None
    chips: list[list[str]] = []
    answer_excerpt: str = ""
    score: AutomatedScore | None = None
    expects_chips: bool = False
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


def kind_of(case: GoldenSetCase) -> str | None:
    """Crisis / off-topic kind of a suppressed case (``crisis-ml``, ``crisis-keyword``, ...)."""
    for kind in ("crisis-ml", "crisis-keyword", "off-topic"):
        if kind in case.tags:
            return kind
    return None


def language_of(case: GoldenSetCase) -> str:
    """Language code of a case (input language, falling back to the expectation)."""
    return case.input.language or case.expectations.response_language


class _RetryableError(Exception):
    """Internal: a failure worth retrying after ``delay`` seconds."""

    def __init__(self, delay: float, reason: str, kind: str) -> None:
        super().__init__(reason)
        self.delay = delay
        self.reason = reason
        self.kind = kind  # "http" (429/503) or "upstream" (stream error event)


def _error_detail(response: httpx.Response) -> dict[str, Any]:
    """The ``detail`` object of an error body, or ``{}`` when absent / not an object."""
    try:
        body = response.json()
    except ValueError:
        return {}
    detail = body.get("detail") if isinstance(body, dict) else None
    return detail if isinstance(detail, dict) else {}


def _retry_delay(response: httpx.Response) -> float:
    """Retry-After header, else ``detail.retry_after`` from the body, else the default."""
    for raw in (response.headers.get("Retry-After"), _error_detail(response).get("retry_after")):
        try:
            return max(0.0, float(raw))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    return DEFAULT_RETRY_AFTER


def _http_failure_reason(response: httpx.Response) -> str:
    detail = _error_detail(response)
    text = str(detail["error"]) if "error" in detail else response.text[:ERROR_BODY_LEN]
    return f"HTTP {response.status_code}: {text}".rstrip(": ")


def _raise_for_status(response: httpx.Response) -> None:
    """Turn a non-200 response into ``_RetryableError`` or ``BackendError``."""
    reason = _http_failure_reason(response)
    if _error_detail(response).get("error") == "session_lifetime_limit":
        raise BackendError(f"{reason} (session request cap reached; use a fresh session)")
    if response.status_code in RETRY_STATUSES:
        raise _RetryableError(_retry_delay(response), reason, "http")
    raise BackendError(reason)


def _raise_stream_error(event: dict[str, Any]) -> None:
    code = event.get("error_code")
    reason = f"stream error [{code}]: {event.get('error', 'unknown error')}"
    if code == "upstream_unavailable":
        try:
            delay = max(0.0, float(event.get("retry_after")))
        except (TypeError, ValueError):
            delay = DEFAULT_UPSTREAM_RETRY_AFTER
        raise _RetryableError(delay, reason, "upstream")
    raise BackendError(reason)


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
            _raise_stream_error(event)
        elif kind == "completion":
            corrected = event.get("corrected_message")
            follow_ups = list(event.get("follow_ups") or [])
    answer = corrected if corrected is not None else "".join(parts)
    return TurnOutcome(answer=answer, follow_ups=follow_ups)


def _send_stream(client: httpx.Client, body: dict[str, Any]) -> TurnOutcome:
    with client.stream("POST", STREAM_PATH, json=body) as response:
        if response.status_code != 200:
            response.read()
            _raise_for_status(response)
        return _parse_sse(response.iter_lines())


def _send_json(client: httpx.Client, body: dict[str, Any]) -> TurnOutcome:
    response = client.post(JSON_PATH, json=body)
    if response.status_code != 200:
        _raise_for_status(response)
    try:
        data = response.json()
    except ValueError as exc:
        raise BackendError(f"invalid JSON response: {response.text[:ERROR_BODY_LEN]}") from exc
    if not isinstance(data, dict):
        raise BackendError(f"invalid JSON response: {response.text[:ERROR_BODY_LEN]}")
    return TurnOutcome(
        answer=data.get("message", ""), follow_ups=list(data.get("follow_ups") or [])
    )


def _transport_failure(client: httpx.Client, exc: httpx.TransportError) -> Exception:
    """Map a transport error: only "cannot connect" is unreachable; the rest is per-case."""
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
        return BackendUnreachableError(f"{type(exc).__name__}: {exc}")
    if isinstance(exc, httpx.TimeoutException):
        seconds = client.timeout.read
        return BackendError(f"timeout after {seconds:g}s" if seconds else "timeout")
    return BackendError(f"connection dropped: {type(exc).__name__}: {exc}")


def send_turn(
    client: httpx.Client,
    mode: Mode,
    body: dict[str, Any],
    sleep: Callable[[float], None] = time.sleep,
) -> TurnOutcome:
    """POST one chat turn.

    429/503 are retried up to ``MAX_RETRIES`` times and a stream
    ``upstream_unavailable`` error once, each after the server's hinted delay.
    """
    sender = _send_stream if mode == "stream" else _send_json
    limits = {"http": MAX_RETRIES, "upstream": MAX_UPSTREAM_RETRIES}
    used = {"http": 0, "upstream": 0}
    while True:
        try:
            return sender(client, body)
        except httpx.TransportError as exc:
            raise _transport_failure(client, exc) from exc
        except _RetryableError as retry:
            if used[retry.kind] >= limits[retry.kind]:
                raise BackendError(retry.reason) from retry
            used[retry.kind] += 1
            sleep(retry.delay)


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
        *case.input.conversation_history,
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
    result: FollowUpCaseResult,
) -> AutomatedScore:
    """Run the turn(s); fills ``result.chips`` / excerpt as it goes so a turn-2 error keeps turn 1."""
    turn1 = send_turn(
        client,
        mode,
        _request_body(case, case.input.message, list(case.input.conversation_history), session_id),
        sleep,
    )
    result.chips = [turn1.follow_ups]
    result.answer_excerpt = turn1.answer[:EXCERPT_LEN]
    checks = check_follow_ups(turn1.follow_ups, turn1.answer, case.expectations)
    if case.input.tap_follow_up:
        checks = [(f"turn1_{name}", ok, detail) for name, ok, detail in checks]
        extra, turn2 = _tap_checks(client, mode, case, turn1, session_id, sleep)
        checks += extra
        if turn2 is not None:
            result.chips.append(turn2.follow_ups)
    return build_score(checks)


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
        case_id=case.id,
        language=language_of(case),
        scenario=scenario_of(case),
        kind=kind_of(case),
        expects_chips=case.expectations.follow_ups == "expected",
    )
    session_id = "fu-eval-" + uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        result.score = _evaluate(client, mode, case, session_id, sleep, result)
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


CRISIS_ML_BUCKET = "crisis-ml (needs classifier)"
CRISIS_ML_HINT = (
    "only crisis-ml cases failed: an ML content-safety classifier is probably not configured "
    "on this backend"
)
KIND_LABELS = {"crisis-ml": "crisis-ml: needs ML safety classifier"}


def _bucket(r: FollowUpCaseResult) -> str:
    return CRISIS_ML_BUCKET if r.kind == "crisis-ml" else r.scenario


def _label(scenario: str, kind: str | None) -> str:
    """Scenario plus crisis kind, e.g. ``suppressed · crisis-ml: needs ML safety classifier``."""
    return f"{scenario} · {KIND_LABELS.get(kind or '', kind)}" if kind else scenario


def summarize(results: list[FollowUpCaseResult], planned: int | None = None) -> dict[str, Any]:
    """Totals overall, per language and per scenario, plus diagnostic hints.

    ``planned`` is how many cases the run set out to execute; when fewer results
    exist (the backend went away mid-run) the summary is flagged ``incomplete`` so
    a saved partial report can't be mistaken for a clean, complete run.
    """
    planned = len(results) if planned is None else planned
    expected = [r for r in results if r.expects_chips and r.error is None]
    all_empty = bool(expected) and all(not (r.chips and r.chips[0]) for r in expected)
    failures = [r for r in results if not r.passed]
    # Only a crisis-ml case that actually *answered* (no transport/HTTP error) and
    # still failed says anything about the safety classifier.
    only_ml = bool(failures) and all(r.kind == "crisis-ml" and r.error is None for r in failures)
    crisis_ml = [r for r in results if r.kind == "crisis-ml"]
    return {
        "total": len(results),
        "planned": planned,
        "incomplete": len(results) < planned,
        "passed": sum(r.passed for r in results),
        "failed": sum(not r.passed for r in results),
        "by_language": _tally(results, lambda r: r.language),
        "by_scenario": _tally(results, _bucket),
        "crisis_ml": {"total": len(crisis_ml), "passed": sum(r.passed for r in crisis_ml)},
        "hint": FLAG_HINT if all_empty else None,
        "crisis_ml_hint": CRISIS_ML_HINT if only_ml else None,
        "note": CRISIS_NOTE,
    }


def _case_line(r: FollowUpCaseResult) -> str:
    status = "PASS" if r.passed else "FAIL"
    line = f"[{status}] {r.case_id} ({_label(r.scenario, r.kind)}) {r.elapsed_ms}ms chips={r.chips}"
    if r.error:
        return f"{line}\n       error: {r.error}"
    if r.score and not r.score.passed:
        failures = [f"{n}: {r.score.details[n]['detail']}" for n in r.score.failed_checks]
        return line + "".join(f"\n       {f}" for f in failures)
    return line


def _tally_lines(title: str, tally: dict) -> list[str]:
    width = max((len(k) for k in tally), default=0)
    lines = [f"{title}:"]
    lines += [f"  {k:<{width}} {v['passed']}/{v['total']}" for k, v in tally.items()]
    return lines


def render_text_report(results: list[FollowUpCaseResult], planned: int | None = None) -> str:
    """Human-readable per-case, per-language and per-scenario report."""
    summary = summarize(results, planned)
    lines = [_case_line(r) for r in results]
    lines += [""] + _tally_lines("By language", summary["by_language"])
    lines += [""] + _tally_lines("By scenario", summary["by_scenario"])
    lines += ["", f"Total: {summary['passed']}/{summary['total']} passed"]
    if summary["incomplete"]:
        lines.append(
            f"INCOMPLETE: backend went away after {summary['total']}/{summary['planned']} cases"
        )
    if summary["hint"]:
        lines.append(f"HINT: {summary['hint']}")
    if summary["crisis_ml_hint"]:
        lines.append(f"HINT: {summary['crisis_ml_hint']}")
    lines.append(f"Note: {summary['note']}")
    return "\n".join(lines)


def render_json(results: list[FollowUpCaseResult], planned: int | None = None) -> str:
    """Machine-readable results plus the summary."""
    payload = {
        "summary": summarize(results, planned),
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
            label = _label(scenario, kind_of(case))
            lines.append(f'- [ ] **{case.id}** ({label}) — "{case.input.message}"')
            lines.append(f"  - Expected: {EXPECTED_BEHAVIOUR.get(scenario, 'see story')}")
        lines.append("")
    return "\n".join(lines)
