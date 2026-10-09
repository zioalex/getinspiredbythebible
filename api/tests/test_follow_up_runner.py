"""Tests for the follow-up chip runner and CLI against a mocked backend (BITB-178)."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from golden_set.follow_up_runner import (
    BackendUnreachableError,
    FollowUpCaseResult,
    render_checklist,
    render_json,
    render_text_report,
    run_case,
    summarize,
)
from golden_set.loader import filter_by_category, load_test_cases
from golden_set.models import Expectations, GoldenSetCase, GoldenSetInput

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_follow_up_eval.py"
_SPEC = importlib.util.spec_from_file_location("run_follow_up_eval", _SCRIPT)
assert _SPEC and _SPEC.loader
cli = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cli)


def make_case(scenario="expected", mode="expected", tap=False, lang="en"):
    return GoldenSetCase(
        id=f"fu-{lang}-test",
        category="follow_ups",
        name="t",
        input=GoldenSetInput(message="Tell me about grace", language=lang, tap_follow_up=tap),
        expectations=Expectations(
            follow_ups=mode, response_language=lang, must_contain_scripture=False
        ),
        tags=[lang, scenario],
    )


def sse(*events, done=True):
    lines = [f"data: {json.dumps(e)}\n\n" for e in events]
    if done:
        lines.append("data: [DONE]\n\n")
    return httpx.Response(
        200, content="".join(lines).encode(), headers={"content-type": "text/event-stream"}
    )


def stream_events(text="Grace is a gift.", chips=("What is faith?", "Who was Paul?"), **extra):
    done = {"type": "completion", "verses_cited": []}
    if chips is not None:
        done["follow_ups"] = list(chips)
    done.update(extra)
    return [
        {"type": "metadata"},
        {"type": "content", "content": text[:5]},
        {"type": "content", "content": text[5:]},
        done,
    ]


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def run(handler, case=None, **kw):
    with client_for(handler) as c:
        return run_case(c, case or make_case(), sleep=kw.pop("sleep", lambda s: None), **kw)


class TestStream:
    def test_happy_path_and_request_body(self):
        seen = []

        def handler(request):
            seen.append(request)
            return sse(*stream_events())

        result = run(handler)
        assert result.error is None
        assert result.chips == [["What is faith?", "Who was Paul?"]]
        assert result.answer_excerpt == "Grace is a gift."
        assert str(seen[0].url).endswith("/api/v1/chat/stream")
        body = json.loads(seen[0].content)
        assert body["message"] == "Tell me about grace"
        assert body["language"] == "en"
        assert body["conversation_history"] == []
        assert body["session_id"].startswith("fu-eval-")
        assert body["include_search"] is True

    def test_fresh_session_id_per_case(self):
        ids = []

        def handler(request):
            ids.append(json.loads(request.content)["session_id"])
            return sse(*stream_events())

        run(handler)
        run(handler)
        assert ids[0] != ids[1]

    def test_corrected_message_replaces_body(self):
        result = run(lambda r: sse(*stream_events(corrected_message="Corrected body.")))
        assert result.answer_excerpt == "Corrected body."

    def test_missing_follow_ups_is_empty(self):
        result = run(lambda r: sse(*stream_events(chips=None)))
        assert result.chips == [[]]
        assert not result.passed
        assert "follow_up_count" in result.score.failed_checks

    def test_suppressed_case_passes_without_chips(self):
        case = make_case("suppressed", "suppressed")
        assert run(lambda r: sse(*stream_events(chips=None)), case).passed

    def test_error_event(self):
        result = run(lambda r: sse({"type": "error", "error": "boom"}))
        assert result.error and "boom" in result.error
        assert not result.passed

    def test_trailer_leak_fails(self):
        result = run(lambda r: sse(*stream_events(text="Body <!-- FOLLOWUPS: a|b -->")))
        assert "follow_up_no_trailer_leak" in result.score.failed_checks

    def test_http_error(self):
        result = run(lambda r: httpx.Response(500))
        assert result.error == "HTTP 500"

    def test_unreachable_raises(self):
        def handler(request):
            raise httpx.ConnectError("refused")

        with pytest.raises(BackendUnreachableError):
            run(handler)


class TestJsonMode:
    def test_json_endpoint(self):
        seen = []

        def handler(request):
            seen.append(str(request.url))
            return httpx.Response(
                200, json={"message": "Answer.", "follow_ups": ["A one?", "B two?"]}
            )

        result = run(handler, mode="json")
        assert seen[0].endswith("/api/v1/chat")
        assert result.chips == [["A one?", "B two?"]]


class TestRetry:
    def test_429_then_200_honours_retry_after(self):
        calls = {"n": 0}
        sleeps: list[float] = []

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, headers={"Retry-After": "7"})
            return sse(*stream_events())

        result = run(handler, sleep=sleeps.append)
        assert result.error is None
        assert sleeps == [7.0]

    def test_default_delay_when_header_missing(self):
        sleeps: list[float] = []
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(503) if calls["n"] == 1 else sse(*stream_events())

        run(handler, sleep=sleeps.append)
        assert sleeps == [10.0]

    def test_gives_up_after_three_retries(self):
        sleeps: list[float] = []
        result = run(
            lambda r: httpx.Response(429, headers={"Retry-After": "1"}), sleep=sleeps.append
        )
        assert result.error == "HTTP 429"
        assert len(sleeps) == 3


class TestMultiTurn:
    def test_taps_first_chip_with_history(self):
        bodies = []

        def handler(request):
            bodies.append(json.loads(request.content))
            if len(bodies) == 1:
                return sse(*stream_events(text="First answer."))
            return sse(*stream_events(text="Second answer.", chips=("Another one?", "And more?")))

        result = run(handler, make_case("multi-turn", tap=True))
        assert len(bodies) == 2
        assert bodies[1]["message"] == "What is faith?"
        assert bodies[1]["conversation_history"] == [
            {"role": "user", "content": "Tell me about grace"},
            {"role": "assistant", "content": "First answer."},
        ]
        assert bodies[1]["session_id"] == bodies[0]["session_id"]
        assert result.chips[1] == ["Another one?", "And more?"]
        assert result.passed, result.score.failed_checks

    def test_repeated_chip_set_fails(self):
        result = run(lambda r: sse(*stream_events()), make_case("multi-turn", tap=True))
        assert not result.passed
        assert "turn2_follow_up_no_repeat_set" in result.score.failed_checks
        assert "turn2_follow_up_no_repeat_tapped" in result.score.failed_checks

    def test_no_chip_to_tap(self):
        result = run(lambda r: sse(*stream_events(chips=None)), make_case("multi-turn", tap=True))
        assert not result.passed
        assert result.score.details["follow_up_tap"]["detail"] == "no chip to tap"


class TestSummaryAndReports:
    def _results(self, chips_present: bool) -> list[FollowUpCaseResult]:
        events = stream_events(chips=("A one?", "B two?") if chips_present else None)
        return [
            run(lambda r: sse(*events), make_case("expected", lang="en")),
            run(
                lambda r: sse(*stream_events(chips=None)),
                make_case("suppressed", "suppressed", lang="it"),
            ),
        ]

    def test_summary_counts(self):
        s = summarize(self._results(True))
        assert s["total"] == 2
        assert s["by_language"]["it"] == {"total": 1, "passed": 1}
        assert s["by_scenario"]["suppressed"]["passed"] == 1
        assert s["hint"] is None
        assert "content-safety" in s["note"]

    def test_hint_when_all_expected_empty(self):
        s = summarize(self._results(False))
        assert "CHAT_FOLLOW_UPS_ENABLED" in s["hint"]

    def test_text_and_json_reports(self):
        results = self._results(False)
        text = render_text_report(results)
        assert "[FAIL] fu-en-test" in text and "By language" in text and "HINT" in text
        data = json.loads(render_json(results))
        assert data["summary"]["total"] == 2
        assert data["results"][0]["passed"] is False

    def test_checklist_renders_every_case(self):
        cases = filter_by_category(load_test_cases(), "follow_ups")
        text = render_checklist(cases)
        for case in cases:
            assert f"**{case.id}**" in text
        assert text.count("- [ ]") == len(cases)
        assert "## ko" in text


class TestCli:
    def _patch_transport(self, monkeypatch, handler):
        real = httpx.Client

        def factory(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return real(*args, **kwargs)

        monkeypatch.setattr(cli.httpx, "Client", factory)

    def test_checklist_offline(self, capsys):
        assert cli.main(["--checklist", "--language", "it,de"]) == 0
        out = capsys.readouterr().out
        assert "fu-it-01" in out and "fu-de-01" in out and "fu-en-01" not in out

    def test_filters(self):
        cases = filter_by_category(load_test_cases(), "follow_ups")
        picked = cli.select_cases(cases, {"zh"}, "suppressed", set())
        assert len(picked) == 2 and all("zh" in c.tags for c in picked)
        assert [c.id for c in cli.select_cases(cases, set(), None, {"fu-ko-03"})] == ["fu-ko-03"]

    def test_no_matching_cases(self, capsys):
        assert cli.main(["--case", "nope"]) == 1

    def test_pass_exit_zero_and_out_file(self, monkeypatch, tmp_path, capsys):
        self._patch_transport(monkeypatch, lambda r: sse(*stream_events()))
        out = tmp_path / "r.json"
        argv = ["--case", "fu-en-01", "--delay", "0", "--out", str(out)]
        assert cli.main(argv) == 0
        assert json.loads(out.read_text())["summary"]["passed"] == 1
        assert "Total: 1/1" in capsys.readouterr().out

    def test_failure_exit_one_json(self, monkeypatch, capsys):
        self._patch_transport(monkeypatch, lambda r: sse(*stream_events(chips=None)))
        assert cli.main(["--case", "fu-en-01", "--delay", "0", "--json"]) == 1
        assert json.loads(capsys.readouterr().out)["summary"]["failed"] == 1

    def test_unreachable_exit_two(self, monkeypatch, capsys):
        def handler(request):
            raise httpx.ConnectError("refused")

        self._patch_transport(monkeypatch, handler)
        assert cli.main(["--case", "fu-en-01", "--delay", "0"]) == 2
        err = capsys.readouterr().err
        assert "Cannot reach backend" in err and "Traceback" not in err
