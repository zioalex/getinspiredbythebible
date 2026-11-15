#!/usr/bin/env python3
"""Offline unit tests for scripts/check_secrets_inventory.py (BITB-305)."""

from __future__ import annotations

import importlib.util
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

_SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = _SCRIPTS_DIR.parent
_spec = importlib.util.spec_from_file_location(
    "check_secrets_inventory", _SCRIPTS_DIR / "check_secrets_inventory.py"
)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["check_secrets_inventory"] = mod
_spec.loader.exec_module(mod)

TODAY = date(2026, 11, 14)


def entry(name: str = "FOO", expires: str = "never", **over):
    base = {
        "name": name,
        "kind": "github-actions-secret",
        "used_by": ["x.yml"],
        "expires": expires,
        "rotation_doc": "docs/DATES_TO_WATCH.md#secret-rotation",
        "owner": "unknown",
    }
    base.update(over)
    return base


def inv(*entries):
    return {"secrets": list(entries)}


def in_days(n: int) -> str:
    return (TODAY + timedelta(days=n)).isoformat()


# --- expiry boundary -------------------------------------------------------------------------
@pytest.mark.parametrize(
    "days,fails",
    [(-30, True), (-1, True), (0, True), (20, True), (21, True), (22, False), (365, False)],
)
def test_expiry_boundary(days, fails):
    problems = mod.check_expiry(inv(entry(expires=in_days(days))), TODAY)
    assert bool(problems) is fails


def test_expired_message_says_expired():
    assert "EXPIRED" in mod.check_expiry(inv(entry(expires=in_days(-3))), TODAY)[0]


def test_never_passes():
    assert mod.check_expiry(inv(entry(expires="never")), TODAY) == []


def test_unknown_fails_without_allow_and_passes_with():
    data = inv(entry(expires="unknown"))
    assert mod.check_expiry(data, TODAY)
    assert mod.check_expiry(data, TODAY, allow_unknown=True) == []


def test_unknown_does_not_hide_a_real_expiring_entry():
    data = inv(entry("A", "unknown"), entry("B", in_days(5)))
    problems = mod.check_expiry(data, TODAY, allow_unknown=True)
    assert len(problems) == 1 and problems[0].startswith("B")


# --- schema ----------------------------------------------------------------------------------
def test_valid_schema():
    assert (
        mod.validate_schema(inv(entry(), entry("BAR", "unknown"), entry("BAZ", in_days(90)))) == []
    )


@pytest.mark.parametrize("data", [None, [], {"secrets": "x"}, {"other": []}])
def test_malformed_top_level(data):
    assert mod.validate_schema(data)


@pytest.mark.parametrize("field", mod.REQUIRED_FIELDS)
def test_missing_field(field):
    e = entry()
    del e[field]
    assert any(field in p for p in mod.validate_schema(inv(e)))


@pytest.mark.parametrize("bad", ["2026-13-45", "11/14/2027", "soon", "2026-1-1"])
def test_bad_date(bad):
    assert any("expires" in p for p in mod.validate_schema(inv(entry(expires=bad))))


def test_duplicate_name():
    assert any("duplicate" in p for p in mod.validate_schema(inv(entry("A"), entry("A"))))


def test_unknown_key():
    assert any("unknown key" in p for p in mod.validate_schema(inv(entry(value="oops"))))


def test_bad_kind_used_by_and_rotation_doc():
    assert mod.validate_schema(inv(entry(kind="weird")))
    assert mod.validate_schema(inv(entry(used_by="x.yml")))
    assert mod.validate_schema(inv(entry(rotation_doc="no-anchor.md")))


def test_malformed_yaml_returns_exit_2(tmp_path):
    bad = tmp_path / "inv.yaml"
    bad.write_text("secrets: [unclosed\n")
    assert mod.run(["--inventory", str(bad)], today=TODAY) == 2


def test_schema_error_exit_1(tmp_path):
    bad = tmp_path / "inv.yaml"
    bad.write_text(yaml.safe_dump({"secrets": [{"name": "A"}]}))
    assert mod.run(["--inventory", str(bad)], today=TODAY) == 1


# --- completeness ----------------------------------------------------------------------------
def write_workflow(dirpath: Path, body: str) -> Path:
    dirpath.mkdir(exist_ok=True)
    (dirpath / "w.yml").write_text(body)
    return dirpath


def test_completeness_missing_entry(tmp_path):
    wf = write_workflow(tmp_path / "wf", "x: ${{ secrets.NEW_THING }}\ny: ${{ secrets.FOO }}\n")
    problems, _ = mod.check_completeness(inv(entry("FOO")), wf)
    assert len(problems) == 1 and "NEW_THING" in problems[0]


def test_completeness_github_token_excluded(tmp_path):
    wf = write_workflow(tmp_path / "wf", "x: ${{ secrets.GITHUB_TOKEN }}\n")
    assert mod.check_completeness(inv(entry("FOO")), wf)[0] == []


def test_completeness_warns_on_unreferenced_but_does_not_fail(tmp_path):
    wf = write_workflow(tmp_path / "wf", "x: 1\n")
    problems, warnings = mod.check_completeness(inv(entry("FOO")), wf)
    assert problems == [] and len(warnings) == 1
    # terraform-variable entries are never "unreferenced" by workflows
    assert mod.check_completeness(inv(entry("T", kind="terraform-variable")), wf)[1] == []


def test_completeness_mode_ignores_dates(tmp_path):
    wf = write_workflow(tmp_path / "wf", "x: ${{ secrets.FOO }}\n")
    path = tmp_path / "inv.yaml"
    path.write_text(yaml.safe_dump(inv(entry("FOO", expires="2020-01-01"))))
    assert mod.run(["--inventory", str(path), "--workflows-dir", str(wf), "--completeness"]) == 0


# --- live header -----------------------------------------------------------------------------
def test_live_header_matches():
    data = inv(entry("T", in_days(100)))
    assert mod.check_live_header(data, "T", f"{in_days(100)} 12:00:00 UTC", TODAY) == []


def test_live_header_mismatch():
    data = inv(entry("T", in_days(100)))
    assert mod.check_live_header(data, "T", f"{in_days(99)} 12:00:00 UTC", TODAY)


def test_live_header_inside_window():
    data = inv(entry("T", in_days(21)))
    assert mod.check_live_header(data, "T", f"{in_days(21)} 00:00:00 UTC", TODAY)


def test_live_header_unknown_inventory():
    data = inv(entry("T", "unknown"))
    header = f"{in_days(100)} 00:00:00 UTC"
    assert mod.check_live_header(data, "T", header, TODAY)
    assert mod.check_live_header(data, "T", header, TODAY, allow_unknown=True) == []


def test_live_header_absent():
    assert mod.check_live_header(inv(entry("T", "never")), "T", None, TODAY) == []
    assert mod.check_live_header(inv(entry("T", in_days(100))), "T", "", TODAY)
    assert mod.check_live_header(inv(entry("T", "unknown")), "T", None, TODAY, True) == []


def test_live_header_garbage_and_unknown_name():
    assert mod.check_live_header(inv(entry("T")), "T", "garbage", TODAY)
    assert mod.check_live_header(inv(entry("T")), "OTHER", "x", TODAY)


# --- committed files -------------------------------------------------------------------------
def _slug(heading: str) -> str:
    s = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return s.replace(" ", "-")


def test_committed_inventory_schema_valid():
    data = mod.load_inventory(mod.DEFAULT_INVENTORY)
    assert mod.validate_schema(data) == []
    assert mod.check_expiry(data, TODAY, allow_unknown=True) == []


def test_committed_inventory_complete_against_committed_workflows():
    data = mod.load_inventory(mod.DEFAULT_INVENTORY)
    problems, _ = mod.check_completeness(data, mod.DEFAULT_WORKFLOWS)
    assert problems == []
    assert mod.run(["--completeness"]) == 0


def test_committed_inventory_has_no_secret_looking_values():
    text = mod.DEFAULT_INVENTORY.read_text()
    assert not re.search(r"(ghp_|github_pat_|sk-[A-Za-z0-9]{10})", text)


def test_committed_rotation_docs_exist_with_anchor():
    data = mod.load_inventory(mod.DEFAULT_INVENTORY)
    for e in data["secrets"]:
        path, anchor = e["rotation_doc"].split("#")
        doc = ROOT / path
        assert doc.is_file(), e["name"]
        slugs = {
            _slug(m.group(1)) for m in re.finditer(r"^#+\s+(.*)$", doc.read_text(), re.MULTILINE)
        }
        assert anchor in slugs, f"{e['name']}: anchor {anchor} not in {path}"


def test_workflow_pr_job_never_runs_expiry_check():
    wf = ROOT / ".github" / "workflows" / "secrets-expiry-check.yml"
    data = yaml.safe_load(wf.read_text())
    triggers = data.get("on") or data.get(True)
    assert "schedule" in triggers and "workflow_dispatch" in triggers
    assert "pull_request" in triggers
    minute = triggers["schedule"][0]["cron"].split()[0]
    assert minute not in ("0", "30")
