#!/usr/bin/env python3
"""Regression tests for scripts/generate-opencode-config.py.

These guard the BITB-123 regression where the generated opencode.json silently
lost `fallback_models`, `tools`, the runtime-fallback plugin, and the provider
timeouts when config moved out of `spec.config` in agent.yaml into a generated
ConfigMap. The result was that fallback routing was inert: agents hard-failed
on a 429/5xx instead of degrading to the free-tier model.
"""

import json
import pathlib
import re
import subprocess
import sys

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "generate-opencode-config.py"
AGENTS_DIR = REPO_ROOT / ".opencode" / "agents"
AGENTS_DOC = REPO_ROOT / "deployment" / "kubeopencode" / "agents.md"

FALLBACK = "opencode/muse-spark-1.3-contributor-free"
BUILTINS = ("build", "plan", "general", "explore", "compaction", "title", "summary")
PLUGIN_NAME = "opencode-runtime-fallback@0.2.4"


@pytest.fixture(scope="module")
def config():
    """Run the generator exactly as `make gen-opencode-config` does."""
    proc = subprocess.run(
        [sys.executable, str(GENERATOR)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def md_agents():
    names = []
    for path in sorted(AGENTS_DIR.glob("*.md")):
        names.append(path.stem)
    return names


def test_output_is_valid_json(config):
    assert config["$schema"] == "https://opencode.ai/config.json"
    assert isinstance(config["agent"], dict)


def test_all_md_agents_present(config, md_agents):
    for name in md_agents:
        assert name in config["agent"], f"{name} missing from generated config"


def test_every_md_agent_has_fallback_models(config, md_agents):
    """The core regression: fallback_models was absent for every agent."""
    for name in md_agents:
        fallbacks = config["agent"][name].get("fallback_models")
        assert fallbacks, f"{name} has no fallback_models"
        assert FALLBACK in fallbacks, f"{name} missing {FALLBACK}"


def test_builtin_agents_have_fallback_models(config):
    for name in BUILTINS:
        assert name in config["agent"], f"builtin {name} missing"
        assert config["agent"][name].get("fallback_models") == [FALLBACK]


def test_builtin_primary_modes_preserved(config):
    assert config["agent"]["build"]["mode"] == "primary"
    assert config["agent"]["plan"]["mode"] == "primary"


def test_tools_frontmatter_is_forwarded(config):
    """8 agents declare `tools:`; the generator used to drop it silently."""
    declared = [
        p.stem
        for p in sorted(AGENTS_DIR.glob("*.md"))
        if re.search(r"^tools:", p.read_text().split("---", 2)[1], re.MULTILINE)
    ]
    assert declared, "expected some agents to declare tools in frontmatter"
    for name in declared:
        assert "tools" in config["agent"][name], f"{name} lost its tools block"


def test_orchestrator_tools_and_permission(config):
    orch = config["agent"]["orchestrator"]
    assert orch["tools"]["bash"] is True
    assert orch["tools"]["edit"] is True
    assert "permission" in orch, "permission must still be forwarded"


def test_top_level_model_and_plugin_present(config):
    assert config["model"]
    assert config["small_model"]
    assert config["plugin"], "runtime-fallback plugin missing: fallbacks inert"
    assert config["plugin"][0][0] == PLUGIN_NAME


def test_plugin_retry_options(config):
    opts = config["plugin"][0][1]
    assert opts["enabled"] is True
    assert opts["retry_on_errors"] == [429, 500, 502, 503, 504]


def test_provider_timeouts_present(config):
    opts = config["provider"]["opencode"]["options"]
    assert opts["timeout"] == 600000
    assert opts["setCacheKey"] is True


def test_every_agent_has_non_empty_prompt(config, md_agents):
    for name in md_agents:
        assert config["agent"][name]["prompt"].strip(), f"{name} has empty prompt"


def test_models_match_agents_doc(config):
    """Guards against drift between the docs table and the generated config."""
    doc = AGENTS_DOC.read_text()
    rows = re.findall(r"^\|\s*([a-z0-9-]+)\s*\|\s*`([^`]+)`", doc, re.MULTILINE)
    assert len(rows) >= 12, f"could not parse agents.md table (got {len(rows)})"
    for name, model in rows:
        assert name in config["agent"], f"{name} documented but not generated"
        assert config["agent"][name]["model"] == model, (
            f"{name}: agents.md says {model}, " f"generated {config['agent'][name]['model']}"
        )


def test_frontmatter_fallbacks_are_source_of_truth():
    """fallback_models must come from the .md files, not be hardcoded."""
    for path in sorted(AGENTS_DIR.glob("*.md")):
        fm = yaml.safe_load(path.read_text().split("---", 2)[1])
        assert fm.get("fallback_models"), f"{path.name} lacks fallback_models"


def test_generation_is_deterministic():
    runs = set()
    for _ in range(2):
        proc = subprocess.run(
            [sys.executable, str(GENERATOR)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        runs.add(proc.stdout)
    assert len(runs) == 1, "generator output is not deterministic"
