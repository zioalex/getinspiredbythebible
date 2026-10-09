"""Tests for the follow-up chip runner and CLI against a mocked backend (BITB-178)."""

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from golden_set.follow_up_runner import (
    BackendUnreachableError,
    FollowUpCaseResult,
    kind_of,
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
        result = run(lambda r: httpx.Response(500, text="kaboom"))
        assert result.error == "HTTP 500: kaboom"

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
        assert sleeps == [60.0]

    def test_gives_up_after_three_retries(self):
        sleeps: list[float] = []
        result = run(
            lambda r: httpx.Response(429, headers={"Retry-After": "1"}), sleep=sleeps.append
        )
        assert result.error.startswith("HTTP 429")
        assert len(sleeps) == 3


RATE_LIMIT_BODY = {"detail": {"error": "Rate limit exceeded", "retry_after": 60}}
LIFETIME_BODY = {"detail": {"error": "session_lifetime_limit", "retry_after": None, "limit": 100}}


class TestRealRateLimitShapes:
    def test_body_retry_after_used_when_no_header(self):
        sleeps: list[float] = []
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, json={"detail": {"retry_after": 7}})
            return sse(*stream_events())

        assert run(handler, sleep=sleeps.append).error is None
        assert sleeps == [7.0]

    def test_real_429_body_without_header_defaults_to_hinted_60(self):
        sleeps: list[float] = []
        result = run(lambda r: httpx.Response(429, json=RATE_LIMIT_BODY), sleep=sleeps.append)
        assert sleeps == [60.0, 60.0, 60.0]
        assert result.error == "HTTP 429: Rate limit exceeded"

    def test_header_wins_over_body(self):
        sleeps: list[float] = []
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, headers={"Retry-After": "2"}, json=RATE_LIMIT_BODY)
            return sse(*stream_events())

        run(handler, sleep=sleeps.append)
        assert sleeps == [2.0]

    def test_session_lifetime_limit_is_not_retried(self):
        sleeps: list[float] = []
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(429, json=LIFETIME_BODY)

        result = run(handler, sleep=sleeps.append)
        assert calls["n"] == 1 and sleeps == []
        assert "session_lifetime_limit" in result.error

    def test_json_mode_uses_same_handling(self):
        sleeps: list[float] = []
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, json=RATE_LIMIT_BODY)
            return httpx.Response(200, json={"message": "A.", "follow_ups": ["A one?", "B two?"]})

        assert run(handler, mode="json", sleep=sleeps.append).chips == [["A one?", "B two?"]]
        assert sleeps == [60.0]


class TestTransportAndErrorReporting:
    def test_read_timeout_is_a_per_case_error(self):
        def handler(request):
            raise httpx.ReadTimeout("slow")

        result = run(handler)
        assert result.error.startswith("timeout after")

    def test_dropped_connection_is_a_per_case_error(self):
        def handler(request):
            raise httpx.RemoteProtocolError("peer closed")

        result = run(handler)
        assert result.error.startswith("connection dropped:") and "peer closed" in result.error

    def test_cli_continues_after_timeout_and_still_writes_report(self, monkeypatch, tmp_path):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ReadTimeout("slow")
            return sse(*stream_events())

        real = httpx.Client
        monkeypatch.setattr(
            cli.httpx,
            "Client",
            lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}),
        )
        out = tmp_path / "r.json"
        argv = ["--case", "fu-en-01,fu-en-02", "--delay", "0", "--out", str(out)]
        assert cli.main(argv) == 1
        data = json.loads(out.read_text())
        assert data["summary"]["total"] == 2 and data["results"][0]["error"]
        assert data["results"][1]["passed"] is True

    def test_non_retryable_http_error_includes_status_and_body(self):
        result = run(lambda r: httpx.Response(422, json={"detail": {"error": "bad language"}}))
        assert result.error == "HTTP 422: bad language"
        long = run(lambda r: httpx.Response(502, text="x" * 500))
        assert long.error == "HTTP 502: " + "x" * 200

    def test_stream_error_includes_error_code(self):
        result = run(lambda r: sse({"type": "error", "error": "no", "error_code": "weird"}))
        assert result.error == "stream error [weird]: no"

    def test_upstream_unavailable_retried_once(self):
        sleeps: list[float] = []
        calls = {"n": 0}
        busy = {"type": "error", "error": "busy", "error_code": "upstream_unavailable"}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return sse({**busy, "retry_after": 4})
            return sse(*stream_events())

        assert run(handler, sleep=sleeps.append).error is None
        assert sleeps == [4.0]

    def test_upstream_unavailable_gives_up_after_one_retry(self):
        sleeps: list[float] = []
        busy = {"type": "error", "error": "busy", "error_code": "upstream_unavailable"}
        result = run(lambda r: sse(busy), sleep=sleeps.append)
        assert len(sleeps) == 1
        assert "upstream_unavailable" in result.error


class TestVersesCommentAndHistory:
    def test_answer_ending_with_verses_comment_passes_end_to_end(self):
        body = "Romans 8:28 says all things work together.\n<!-- VERSES: Romans 8:28 -->"
        events = stream_events(
            text=body,
            chips=("What does Romans 8:28 mean?", "How can I trust God more?"),
            corrected_message=body,
        )
        result = run(lambda r: sse(*events))
        assert result.passed, result.score.failed_checks

    def test_turn_one_sends_configured_history(self):
        bodies = []
        case = make_case()
        case.input.conversation_history = [{"role": "user", "content": "hi"}]

        def handler(request):
            bodies.append(json.loads(request.content))
            return sse(*stream_events())

        run(handler, case)
        assert bodies[0]["conversation_history"] == [{"role": "user", "content": "hi"}]

    def test_hint_fires_for_verse_citing_and_multi_turn_when_all_empty(self):
        empty = lambda r: sse(*stream_events(chips=None))  # noqa: E731
        results = [
            run(empty, make_case("verse-citing")),
            run(empty, make_case("multi-turn", tap=True)),
        ]
        assert "CHAT_FOLLOW_UPS_ENABLED" in summarize(results)["hint"]

    def test_hint_absent_when_only_errors(self):
        results = [run(lambda r: httpx.Response(500), make_case("expected"))]
        assert summarize(results)["hint"] is None


class _BrokenStream(httpx.SyncByteStream):
    """Yields one SSE line, then fails like a dropped connection."""

    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def __iter__(self):
        yield b'data: {"type": "content", "content": "Hel"}\n\n'
        raise self.exc


class TestRobustness:
    @pytest.mark.parametrize(
        "exc,prefix",
        [
            (httpx.ReadTimeout("slow"), "timeout after"),
            (httpx.RemoteProtocolError("peer closed"), "connection dropped:"),
        ],
    )
    def test_stream_failing_midway_is_a_per_case_error(self, exc, prefix):
        result = run(lambda r: httpx.Response(200, stream=_BrokenStream(exc)))
        assert result.error.startswith(prefix)

    def test_non_json_200_in_json_mode(self):
        result = run(lambda r: httpx.Response(200, text="<html>oops</html>"), mode="json")
        assert result.error == "invalid JSON response: <html>oops</html>"

    def test_json_array_body_in_json_mode(self):
        result = run(lambda r: httpx.Response(200, json=["x"]), mode="json")
        assert result.error.startswith("invalid JSON response")

    def test_turn_two_error_keeps_turn_one_chips(self):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return sse(*stream_events(text="First answer."))
            return httpx.Response(500, text="down")

        result = run(handler, make_case("multi-turn", tap=True))
        assert result.error == "HTTP 500: down"
        assert result.chips == [["What is faith?", "Who was Paul?"]]
        assert result.answer_excerpt == "First answer."


def make_kind_case(kind, scenario="suppressed", lang="en"):
    case = make_case(scenario, "suppressed", lang=lang)
    case.tags.append(kind)
    return case


class TestCrisisKinds:
    def _chips_everywhere(self, request):
        return sse(*stream_events())

    def test_kind_of(self):
        assert kind_of(make_kind_case("crisis-ml")) == "crisis-ml"
        assert kind_of(make_kind_case("crisis-keyword")) == "crisis-keyword"
        assert kind_of(make_kind_case("off-topic")) == "off-topic"
        assert kind_of(make_case()) is None

    def test_kind_carried_on_result_and_json(self):
        result = run(self._chips_everywhere, make_kind_case("crisis-ml"))
        assert result.kind == "crisis-ml"
        assert json.loads(render_json([result]))["results"][0]["kind"] == "crisis-ml"

    def test_case_line_shows_kind(self):
        ml = run(self._chips_everywhere, make_kind_case("crisis-ml"))
        kw = run(self._chips_everywhere, make_kind_case("crisis-keyword"))
        plain = run(self._chips_everywhere, make_case())
        text = render_text_report([ml, kw, plain])
        assert "(suppressed · crisis-ml: needs ML safety classifier)" in text
        assert "(suppressed · crisis-keyword)" in text
        assert "(expected)" in text

    def test_crisis_ml_has_separate_tally_and_hint_when_only_failures(self):
        ml = run(self._chips_everywhere, make_kind_case("crisis-ml"))
        ok = run(lambda r: sse(*stream_events(chips=None)), make_kind_case("off-topic"))
        summary = summarize([ml, ok])
        assert summary["by_scenario"]["crisis-ml (needs classifier)"] == {
            "total": 1,
            "passed": 0,
        }
        assert summary["by_scenario"]["suppressed"] == {"total": 1, "passed": 1}
        assert summary["crisis_ml"] == {"total": 1, "passed": 0}
        assert "only crisis-ml cases failed" in summary["crisis_ml_hint"]
        assert "only crisis-ml cases failed" in render_text_report([ml, ok])

    def test_no_crisis_hint_when_other_failures_or_none(self):
        ml = run(self._chips_everywhere, make_kind_case("crisis-ml"))
        kw = run(self._chips_everywhere, make_kind_case("crisis-keyword"))
        assert summarize([ml, kw])["crisis_ml_hint"] is None
        ok = run(lambda r: sse(*stream_events(chips=None)), make_kind_case("crisis-ml"))
        assert summarize([ok])["crisis_ml_hint"] is None

    def test_no_crisis_hint_when_crisis_ml_case_errored(self):
        # A transport/HTTP error says nothing about the safety classifier.
        errored = run(lambda r: httpx.Response(500, text="boom"), make_kind_case("crisis-ml"))
        assert errored.error and not errored.passed
        assert summarize([errored])["crisis_ml_hint"] is None

    def test_scenario_tally_columns_align(self):
        ml = run(self._chips_everywhere, make_kind_case("crisis-ml"))
        ok = run(lambda r: sse(*stream_events(chips=None)), make_kind_case("off-topic"))
        text = render_text_report([ml, ok])
        block = text.split("By scenario:\n", 1)[1].split("\n\n", 1)[0].splitlines()
        assert len(block) == 2
        assert len({line.rindex(" ") for line in block}) == 1, block

    def test_checklist_shows_kind(self):
        cases = filter_by_category(load_test_cases(), "follow_ups")
        text = render_checklist(cases)
        assert text.count("crisis-ml: needs ML safety classifier") == 11
        assert text.count("(suppressed · crisis-keyword)") == 7
        assert "(suppressed · off-topic)" in text


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

    def test_complete_run_is_not_flagged_incomplete(self):
        s = summarize(self._results(True), planned=2)
        assert s["planned"] == 2 and s["incomplete"] is False
        assert "INCOMPLETE" not in render_text_report(self._results(True), planned=2)
        assert summarize(self._results(True))["incomplete"] is False

    def test_partial_run_is_flagged_incomplete(self):
        results = self._results(True)
        s = summarize(results, planned=7)
        assert s["planned"] == 7 and s["incomplete"] is True
        assert "INCOMPLETE: backend went away after 2/7 cases" in render_text_report(
            results, planned=7
        )
        assert json.loads(render_json(results, planned=7))["summary"]["incomplete"] is True

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

    def test_backend_going_down_midway_writes_partial_results(self, monkeypatch, tmp_path, capsys):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] > 1:
                raise httpx.ConnectError("refused")
            return sse(*stream_events())

        self._patch_transport(monkeypatch, handler)
        out = tmp_path / "r.json"
        argv = ["--case", "fu-en-01,fu-en-02", "--delay", "0", "--out", str(out)]
        assert cli.main(argv) == 2
        captured = capsys.readouterr()
        assert "Cannot reach backend" in captured.err and "Total: 1/1" in captured.out
        assert "INCOMPLETE: backend went away after 1/2 cases" in captured.out
        summary = json.loads(out.read_text())["summary"]
        assert summary["total"] == 1 and summary["planned"] == 2 and summary["incomplete"]

    def test_unreachable_exit_two(self, monkeypatch, capsys):
        def handler(request):
            raise httpx.ConnectError("refused")

        self._patch_transport(monkeypatch, handler)
        assert cli.main(["--case", "fu-en-01", "--delay", "0"]) == 2
        err = capsys.readouterr().err
        assert "Cannot reach backend" in err and "Traceback" not in err
