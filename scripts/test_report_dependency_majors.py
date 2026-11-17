"""Tests for scripts/report_dependency_majors.py (BITB-304). HTTP is always mocked."""

import sys
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import report_dependency_majors as rdm  # noqa: E402


@pytest.mark.parametrize(
    "version,major",
    [("1.109.1", 1), ("^18.3.0", 18), ("~5.2.0", 5), (">=2.0", 2), ("v3", 3), ("latest", None)],
)
def test_major_of(version, major):
    assert rdm.major_of(version) == major


@pytest.mark.parametrize(
    "current,latest,behind",
    [("1.109.1", "3.49.0", True), ("0.125.0", "2.8.0", True), ("^18.3.0", "18.9.9", False),
     ("2.0.0", "2.0.0", False), ("^19.0.0", "18.0.0", False), ("latest", "5.0.0", False)],
)  # fmt: skip
def test_is_behind(current, latest, behind):
    assert rdm.is_behind(current, latest) is behind


def test_parse_requirements_keeps_pins_and_lower_bounds():
    text = "# c\nfastapi==0.162.0\nuvicorn[standard]==0.54.0  # x\nfoo>=1\n\nbar==2.0 ; python_version>'3'\n"
    assert rdm.parse_requirements(text) == {
        "fastapi": "0.162.0",
        "uvicorn": "0.54.0",
        "foo": "1",
        "bar": "2.0",
    }


def test_parse_package_json_merges_dev_deps():
    text = '{"dependencies": {"next": "^16.0.0"}, "devDependencies": {"vitest": "~3.1.0"}}'
    assert rdm.parse_package_json(text) == {"next": "^16.0.0", "vitest": "~3.1.0"}


def test_build_rows_reports_behind_and_lookup_failures():
    latest = {"openai": "3.49.0", "httpx": "0.28.9"}

    def fetch(name):
        if name == "broken":
            raise urllib.error.URLError("down")
        return latest[name]

    rows, failed = rdm.build_rows({"openai": "1.109.1", "httpx": "0.28.1", "broken": "1.0"}, fetch)
    assert rows == [("openai", "1.109.1", "3.49.0")]
    assert failed == ["broken"]


def test_render_section_table_and_empty():
    out = rdm.render_section("Python", [("openai", "1.1", "3.0")], ["x"])
    assert "| `openai` | 1.1 | 3.0 |" in out and "`x`" in out
    assert "No direct dependency" in rdm.render_section("npm", [], [])


def test_main_writes_summary_and_never_fails(monkeypatch, tmp_path):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr(rdm, "latest_pypi", lambda n: "99.0.0")
    monkeypatch.setattr(rdm, "latest_npm", lambda n: "99.0.0")
    assert rdm.main() == 0
    text = summary.read_text()
    assert "Dependency major-version report" in text and "99.0.0" in text


def test_parse_requirements_includes_lower_bound_pins():
    deps = rdm.parse_requirements("pyyaml>=6.0.3\nfoo~=1.2\n")
    assert deps == {"pyyaml": "6.0.3", "foo": "1.2"}


def test_build_rows_survives_unexpected_registry_error():
    def fetch(name):
        if name == "bad":
            raise TypeError("garbage reply")
        return "2.0.0"

    rows, failed = rdm.build_rows({"bad": "1.0", "good": "1.0"}, fetch)
    assert failed == ["bad"]
    assert [r[0] for r in rows] == ["good"]
