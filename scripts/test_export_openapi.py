#!/usr/bin/env python3
"""Offline unit tests for scripts/export_openapi.py (BITB-261).

The schema loader is monkeypatched for the ordering / ``--check`` tests, so they need neither
FastAPI nor a database. The two ``real_app`` tests import the actual backend app and are
skipped when the backend dependencies (api/requirements.txt) are not installed.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("export_openapi", _SCRIPTS_DIR / "export_openapi.py")
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
sys.modules["export_openapi"] = mod
_spec.loader.exec_module(mod)

SCHEMA_A = {
    "openapi": "3.1.0",
    "paths": {"/z": {"get": {}}, "/a": {"post": {}, "get": {}}},
    "components": {"schemas": {"Zed": {"type": "object"}, "Alpha": {"type": "string"}}},
}
# Same content, different insertion order.
SCHEMA_B = {
    "components": {"schemas": {"Alpha": {"type": "string"}, "Zed": {"type": "object"}}},
    "paths": {"/a": {"get": {}, "post": {}}, "/z": {"get": {}}},
    "openapi": "3.1.0",
}


@pytest.fixture
def fake_schema(monkeypatch):
    holder = {"schema": SCHEMA_A}
    monkeypatch.setattr(mod, "load_openapi_schema", lambda: holder["schema"])
    return holder


def test_render_is_order_independent_and_sorted():
    assert mod.render(SCHEMA_A) == mod.render(SCHEMA_B)
    out = mod.render(SCHEMA_A)
    assert out.endswith("\n") and not out.endswith("\n\n")
    paths = list(json.loads(out)["paths"])
    assert paths == sorted(paths)
    assert out.index('"Alpha"') < out.index('"Zed"')


def test_render_keeps_non_ascii_readable():
    assert "シ" in mod.render({"description": "シ"})


def test_write_then_check_passes(fake_schema, tmp_path, capsys):
    target = tmp_path / "sub" / "openapi.json"
    assert mod.main(["--output", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == mod.render(SCHEMA_A)
    assert mod.main(["--check", "--output", str(target)]) == 0
    assert "OK:" in capsys.readouterr().out


def test_check_fails_when_stale_and_does_not_write(fake_schema, tmp_path, capsys):
    target = tmp_path / "openapi.json"
    target.write_text(mod.render(SCHEMA_A), encoding="utf-8")
    fake_schema["schema"] = {**SCHEMA_A, "paths": {"/new": {"get": {}}}}
    before = target.read_text(encoding="utf-8")
    assert mod.main(["--check", "--output", str(target)]) == 1
    err = capsys.readouterr().err
    assert "stale" in err and "make parity-export" in err and "/new" in err
    assert target.read_text(encoding="utf-8") == before


def test_check_fails_when_artifact_missing(fake_schema, tmp_path):
    assert mod.main(["--check", "--output", str(tmp_path / "missing.json")]) == 1
    assert not (tmp_path / "missing.json").exists()


def test_check_fails_on_hand_edit(fake_schema, tmp_path):
    target = tmp_path / "openapi.json"
    mod.main(["--output", str(target)])
    target.write_text(target.read_text(encoding="utf-8").replace("/a", "/b"), encoding="utf-8")
    assert mod.main(["--check", "--output", str(target)]) == 1


@pytest.fixture
def real_app_schema():
    pytest.importorskip("fastapi")
    return mod.load_openapi_schema()


def test_real_app_export_is_offline_and_deterministic(real_app_schema):
    assert real_app_schema["paths"], "backend app exposes no paths"
    assert mod.render(real_app_schema) == mod.render(mod.load_openapi_schema())


def test_committed_artifact_is_current(real_app_schema):
    committed = mod._OUTPUT_PATH.read_text(encoding="utf-8")
    assert committed == mod.render(real_app_schema), "run `make parity-export`"
