"""BITB-291: monitor script logic + prod-monitor.yml wiring."""

import importlib.util
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "monitor" / "synthetic_ml_safety_path.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "prod-monitor.yml"


def _load():
    spec = importlib.util.spec_from_file_location("synthetic_ml_safety_path", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


probe = _load()


def _res(allowed, decided_by, failover=False, ml=None):
    ml = decided_by in {"llama_guard", "openai_moderation", "azure"} if ml is None else ml
    return {
        "allowed": allowed,
        "decided_by": decided_by,
        "failover": failover,
        "ml_path": ml,
        "reason": "r",
    }


def test_benign_and_unsafe_pass_on_llama_guard():
    assert probe.evaluate(_res(True, "llama_guard"), True, False)[0] is True
    assert probe.evaluate(_res(False, "llama_guard"), False, False)[0] is True


@pytest.mark.parametrize(
    "decided_by", ["keyword_fallback", "stage1_keywords", "default_allow", "disabled"]
)
@pytest.mark.parametrize("expect_allowed", [True, False])
def test_non_ml_decider_fails_naming_it(decided_by, expect_allowed):
    ok, msg = probe.evaluate(_res(expect_allowed, decided_by), expect_allowed, False)
    assert ok is False
    assert "ML safety path down" in msg and decided_by in msg


def test_wrong_verdict_fails():
    ok, msg = probe.evaluate(_res(False, "llama_guard"), True, False)
    assert not ok and "false positive" in msg
    ok, msg = probe.evaluate(_res(True, "llama_guard"), False, False)
    assert not ok and "ALLOWED" in msg


def test_failover_is_degraded_pass_unless_require_primary():
    r = _res(False, "openai_moderation", failover=True)
    ok, msg = probe.evaluate(r, False, False)
    assert ok and "DEGRADED: Llama Guard down, OpenAI Moderation failover decided" in msg
    ok, msg = probe.evaluate(r, False, True)
    assert not ok and "DEGRADED" in msg


def test_404_hint(monkeypatch):
    class R:
        status_code = 404
        text = "Not Found"

    monkeypatch.setattr(probe.httpx, "post", lambda *a, **k: R())
    result, err = probe.run_probe("https://x", "s", "m", "en", 1)
    assert result is None and "probe secret mismatch or endpoint not deployed" in err


def test_main_exit_codes(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKEND_URL", "https://x")
    monkeypatch.setenv("MONITOR_PROBE_SECRET", "s")
    monkeypatch.setattr("sys.argv", ["p", "--detail-out", str(tmp_path / "d.txt")])
    answers = iter([_res(True, "llama_guard"), _res(False, "llama_guard")])
    monkeypatch.setattr(probe, "run_probe", lambda *a: (next(answers), None))
    assert probe.main() == 0
    answers2 = iter([_res(True, "keyword_fallback", ml=False)])
    monkeypatch.setattr(probe, "run_probe", lambda *a: (next(answers2), None))
    assert probe.main() == 1
    assert "keyword_fallback" in (tmp_path / "d.txt").read_text()


def test_workflow_has_ml_safety_path_job():
    wf = yaml.safe_load(_WORKFLOW.read_text())
    job = wf["jobs"]["ml-safety-path"]
    assert job["name"] == "ML safety path probe"
    steps = job["steps"]
    assert any("synthetic_ml_safety_path.py" in s.get("run", "") for s in steps)
    notify = [s for s in steps if s.get("uses") == "./.github/actions/notify-telegram"]
    assert notify and notify[0]["with"]["job_name"] == "ml-safety-path"
    run_step = next(s for s in steps if "synthetic_ml_safety_path.py" in s.get("run", ""))
    assert run_step["env"]["MONITOR_PROBE_SECRET"] == "${{ secrets.MONITOR_PROBE_SECRET }}"
