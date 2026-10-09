"""Tests for the golden set runner and its CLI (BITB-178).

Live mode is driven through ``httpx.MockTransport``: no network, no real API, no real secrets.
"""

import importlib.util
import io
import json
from pathlib import Path

import httpx
import pytest

from golden_set import runner
from golden_set.loader import filter_by_category, load_test_cases
from golden_set.models import Expectations, GoldenSetCase, GoldenSetInput

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REAL_ASYNC_CLIENT = httpx.AsyncClient
SECRET = "s3cr3t-probe-value-do-not-leak"  # pragma: allowlist secret


def _case(case_id="t-1", message="Who is spoken of in Luke 1:79?", **input_kwargs) -> GoldenSetCase:
    return GoldenSetCase(
        id=case_id,
        category="interpretation",
        name=case_id,
        input=GoldenSetInput(message=message, **input_kwargs),
        expectations=Expectations(
            must_contain_scripture=False,
            must_contain_any=[["1:78", "verse 78"], ["messiah"]],
        ),
    )


def _ok_body(message="Verse 78 names the Messiah.") -> dict:
    return {
        "message": message,
        "provider": "claude",
        "model": "claude-test",
        "scripture_context": {"verses": []},
    }


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _load_cli():
    spec = importlib.util.spec_from_file_location(
        "run_golden_set_cli", _REPO_ROOT / "scripts" / "run_golden_set.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def patch_transport(monkeypatch):
    """Make ``run_live`` (which builds its own AsyncClient) use a mocked transport."""

    def install(handler):
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda *a, **kw: _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler)),
        )

    return install


# ==================== Payload ====================


class TestBuildPayload:
    def test_carries_history_language_and_translation(self):
        history = [
            {"role": "user", "content": "Who is spoken of in Luke 1:79?"},
            {"role": "assistant", "content": "John the Baptist."},
        ]
        case = _case(
            message="Are you sure?",
            conversation_history=history,
            language="de",
            preferred_translation="luther1912",
        )
        payload = runner.build_payload(case)
        assert payload["message"] == "Are you sure?"
        assert payload["conversation_history"] == history
        assert payload["language"] == "de"
        assert payload["preferred_translation"] == "luther1912"
        assert payload["include_search"] is True

    def test_optional_fields_are_omitted_when_unset(self):
        payload = runner.build_payload(_case())
        assert "language" not in payload
        assert "preferred_translation" not in payload
        assert payload["conversation_history"] == []

    def test_every_interpretation_payload_validates_as_a_chat_request(self):
        from chat.service import ChatRequest

        for case in filter_by_category(load_test_cases(), "interpretation"):
            request = ChatRequest(**runner.build_payload(case))
            assert request.message == case.input.message
            assert len(request.conversation_history) == len(case.input.conversation_history)


# ==================== Mock mode ====================


class TestMockMode:
    def test_runs_every_case_without_an_api(self):
        cases = filter_by_category(load_test_cases(), "interpretation")
        run = runner.run_mock(cases)
        assert run.mode == "mock"
        assert [r.case_id for r in run.results] == [c.id for c in cases]
        assert len(run.results) == 81
        # the placeholder answer cannot satisfy the checks: mock mode exercises the pipeline only
        assert not any(r.automated_score.passed for r in run.results)

    def test_save_and_load_round_trip(self, tmp_path):
        run = runner.run_mock([_case("a"), _case("b")])
        path = runner.save_run(run, tmp_path / "nested" / "run.json")
        loaded = runner.load_run(path)
        assert loaded.run_id == run.run_id
        assert [r.case_id for r in loaded.results] == ["a", "b"]

    def test_default_save_location_is_named_after_the_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)
        run = runner.run_mock([_case()])
        assert runner.save_run(run) == tmp_path / f"{run.run_id}.json"


# ==================== Live mode ====================


class TestRunLive:
    async def test_posts_each_case_with_history_language_and_translation(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append((request.url.path, json.loads(request.content)))
            return httpx.Response(200, json=_ok_body())

        history = [
            {"role": "user", "content": "Von wem ist in Lukas 1,79 die Rede?"},
            {"role": "assistant", "content": "Von Johannes."},
        ]
        cases = [
            _case("a", message="Von wem ist in Lukas 1,79 die Rede?", language="de"),
            _case(
                "b",
                message="Bist du sicher?",
                conversation_history=history,
                language="de",
                preferred_translation="luther1912",
            ),
        ]
        async with _client(handler) as client:
            run = await runner.run_live(cases, "http://api.test/", client=client)

        assert [path for path, _ in seen] == ["/api/v1/chat", "/api/v1/chat"]
        assert seen[0][1]["language"] == "de"
        assert seen[0][1]["conversation_history"] == []
        assert seen[1][1]["conversation_history"] == history
        assert seen[1][1]["preferred_translation"] == "luther1912"
        assert run.mode == "live"
        assert run.provider == "claude" and run.model == "claude-test"
        assert all(r.automated_score.passed for r in run.results)
        assert run.results[0].scripture_context == {"verses": []}

    async def test_a_poor_answer_is_a_failed_check_not_a_transport_failure(self):
        def handler(request):
            return httpx.Response(200, json=_ok_body("John the Baptist, I think."))

        async with _client(handler) as client:
            run = await runner.run_live([_case()], "http://api.test", client=client)

        result = run.results[0]
        assert not result.automated_score.passed
        assert "required_alternatives" in result.automated_score.failed_checks
        summary = runner.summarize(run)
        assert (summary["failed"], summary["blocked"], summary["errored"]) == (1, 0, 0)
        assert runner.has_scorable_answer(run)

    async def test_403_is_reported_as_blocked_not_as_a_model_failure(self):
        def handler(request):
            return httpx.Response(403, json={"detail": "Turnstile"})

        async with _client(handler) as client:
            run = await runner.run_live([_case("a"), _case("b")], "http://api.test", client=client)

        assert [r.automated_score.failed_checks for r in run.results] == [["blocked"]] * 2
        summary = runner.summarize(run)
        assert (summary["blocked"], summary["failed"], summary["errored"]) == (2, 0, 0)
        assert not runner.has_scorable_answer(run)
        out = io.StringIO()
        runner.print_summary(run, out)
        text = out.getvalue()
        assert "[BLOCKED] a" in text and "Turnstile" in text
        assert "FAIL" not in text

    async def test_other_http_errors_are_errored_cases(self):
        def handler(request):
            return httpx.Response(500, text="boom")

        async with _client(handler) as client:
            run = await runner.run_live([_case()], "http://api.test", client=client)

        assert run.results[0].automated_score.failed_checks == ["http_error"]
        assert "HTTP 500" in run.results[0].automated_score.details["http_error"]
        assert runner.summarize(run)["errored"] == 1
        assert not runner.has_scorable_answer(run)

    async def test_unreadable_200_body_is_an_error(self):
        def handler(request):
            return httpx.Response(200, text="<html>not json</html>")

        async with _client(handler) as client:
            run = await runner.run_live([_case()], "http://api.test", client=client)

        assert run.results[0].automated_score.failed_checks == ["http_error"]

    async def test_transport_failure_is_recorded_and_the_run_continues(self):
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            if len(calls) == 1:
                raise httpx.ConnectTimeout("timed out", request=request)
            return httpx.Response(200, json=_ok_body())

        async with _client(handler) as client:
            run = await runner.run_live([_case("a"), _case("b")], "http://api.test", client=client)

        assert run.results[0].automated_score.failed_checks == ["request_error"]
        assert run.results[0].automated_score.details["request_error"] == "ConnectTimeout"
        assert run.results[1].automated_score.passed
        assert runner.has_scorable_answer(run)

    async def test_delay_is_applied_between_requests_only(self, monkeypatch):
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        monkeypatch.setattr(runner.asyncio, "sleep", fake_sleep)

        def handler(request):
            return httpx.Response(200, json=_ok_body())

        async with _client(handler) as client:
            await runner.run_live(
                [_case("a"), _case("b"), _case("c")], "http://api.test", delay=2.5, client=client
            )
        assert sleeps == [2.5, 2.5]

    async def test_owns_and_closes_its_client_when_none_is_given(self, patch_transport):
        patch_transport(lambda request: httpx.Response(200, json=_ok_body()))
        run = await runner.run_live([_case()], "http://api.test")
        assert run.results[0].automated_score.passed


# ==================== Probe header ====================


class TestProbeHeader:
    def test_header_is_built_from_the_environment_only(self):
        assert runner.probe_headers_from_env({}) is None
        assert runner.probe_headers_from_env({"GOLDEN_SET_PROBE_SECRET": ""}) is None
        assert runner.probe_headers_from_env({"GOLDEN_SET_PROBE_SECRET": SECRET}) == {
            "X-Monitor-Probe-Secret": SECRET
        }

    def test_header_name_matches_the_backend_probe_bypass(self):
        from utils.monitor_probe import PROBE_HEADER

        assert runner.PROBE_HEADER == PROBE_HEADER

    async def test_header_is_sent_only_when_given(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers.get("X-Monitor-Probe-Secret"))
            return httpx.Response(200, json=_ok_body())

        async with _client(handler) as client:
            await runner.run_live([_case()], "http://api.test", client=client)
            await runner.run_live(
                [_case()],
                "http://api.test",
                client=client,
                headers=runner.probe_headers_from_env({"GOLDEN_SET_PROBE_SECRET": SECRET}),
            )
        assert seen == [None, SECRET]

    async def test_secret_is_not_in_the_saved_run_or_the_summary(self, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/chat") and json.loads(request.content)["message"] == "x":
                raise httpx.ConnectError("connect failed", request=request)
            return httpx.Response(403)

        async with _client(handler) as client:
            run = await runner.run_live(
                [_case("a"), _case("b", message="x")],
                "http://api.test",
                client=client,
                headers={"X-Monitor-Probe-Secret": SECRET},
            )
        saved = runner.save_run(run, tmp_path / "run.json").read_text(encoding="utf-8")
        out = io.StringIO()
        runner.print_summary(run, out)
        assert SECRET not in saved
        assert SECRET not in out.getvalue()
        assert run.metadata["probe_header_sent"] is True


# ==================== CLI ====================


class TestCli:
    @pytest.fixture
    def cli(self):
        return _load_cli()

    def test_mock_runs_every_interpretation_case_and_writes_a_result_file(
        self, cli, tmp_path, capsys
    ):
        out_file = tmp_path / "mock.json"
        code = cli.main(["--mock", "--category", "interpretation", "--output", str(out_file)])
        assert code == 0
        saved = runner.load_run(out_file)
        assert saved.mode == "mock"
        assert len(saved.results) == 81
        assert "0/81 passed" in capsys.readouterr().out

    def test_filters_by_tags_and_ids(self, cli, tmp_path):
        out_file = tmp_path / "f.json"
        assert cli.main(["--mock", "--tags", "pushback-user-right", "--output", str(out_file)]) == 0
        assert {"interp-030", "interp-063"} <= {
            r.case_id for r in runner.load_run(out_file).results
        }
        assert (
            cli.main(["--mock", "--ids", "interp-001, interp-002", "--output", str(out_file)]) == 0
        )
        assert [r.case_id for r in runner.load_run(out_file).results] == [
            "interp-001",
            "interp-002",
        ]

    def test_exit_2_when_no_case_matches(self, cli, tmp_path, capsys):
        code = cli.main(
            ["--mock", "--category", "no-such-category", "--output", str(tmp_path / "x")]
        )
        assert code == 2
        assert "No golden set cases" in capsys.readouterr().err

    def test_exit_0_by_default_even_when_every_check_fails(self, cli, tmp_path, patch_transport):
        patch_transport(lambda request: httpx.Response(200, json=_ok_body("Nothing useful.")))
        args = ["--base-url", "http://api.test", "--ids", "interp-001", "--output"]
        assert cli.main([*args, str(tmp_path / "r.json")]) == 0

    def test_exit_1_below_fail_under(self, cli, tmp_path, patch_transport, capsys):
        patch_transport(lambda request: httpx.Response(200, json=_ok_body("Nothing useful.")))
        code = cli.main(
            [
                "--base-url",
                "http://api.test",
                "--ids",
                "interp-001",
                "--fail-under",
                "0.5",
                "--output",
                str(tmp_path / "r.json"),
            ]
        )
        assert code == 1
        assert "below --fail-under" in capsys.readouterr().err

    def test_exit_3_when_nothing_was_scorable(self, cli, tmp_path, patch_transport, capsys):
        patch_transport(lambda request: httpx.Response(403))
        out_file = tmp_path / "blocked.json"
        code = cli.main(
            [
                "--base-url",
                "http://api.test",
                "--category",
                "interpretation",
                "--fail-under",
                "0.9",
                "--output",
                str(out_file),
            ]
        )
        assert code == 3
        assert "scorable" in capsys.readouterr().err
        saved = runner.load_run(out_file)  # the run is still saved for inspection
        assert len(saved.results) == 81
        assert all(r.automated_score.failed_checks == ["blocked"] for r in saved.results)

    def test_probe_secret_comes_from_the_environment_and_never_leaks(
        self, cli, tmp_path, patch_transport, monkeypatch, capsys
    ):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers.get("X-Monitor-Probe-Secret"))
            return httpx.Response(403)

        patch_transport(handler)
        monkeypatch.setenv("GOLDEN_SET_PROBE_SECRET", SECRET)
        out_file = tmp_path / "run.json"
        args = ["--base-url", "http://api.test", "--ids", "interp-001", "--output", str(out_file)]
        assert cli.main(args) == 3

        assert seen == [SECRET]
        captured = capsys.readouterr()
        assert SECRET not in captured.out and SECRET not in captured.err
        assert SECRET not in out_file.read_text(encoding="utf-8")

    def test_no_probe_header_when_the_variable_is_unset(
        self, cli, tmp_path, patch_transport, monkeypatch
    ):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append("X-Monitor-Probe-Secret" in request.headers)
            return httpx.Response(200, json=_ok_body())

        patch_transport(handler)
        monkeypatch.delenv("GOLDEN_SET_PROBE_SECRET", raising=False)
        args = ["--base-url", "http://api.test", "--ids", "interp-001"]
        assert cli.main([*args, "--output", str(tmp_path / "r.json")]) == 0
        assert seen == [False]

    def test_secret_is_not_accepted_on_the_command_line(self, cli):
        with pytest.raises(SystemExit):
            cli.main(["--mock", "--probe-secret", SECRET])
