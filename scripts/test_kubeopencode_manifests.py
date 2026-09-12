#!/usr/bin/env python3
"""Tests for the KubeOpenCode deployment manifests and the committed opencode.json.

BITB-126. `scripts/test_generate_opencode_config.py` covers the *generator*;
nothing covered the *committed artifact* or the manifests that ship it to the
cluster. The gaps these close:

- T1: `.opencode/agents/*.md` is the source of truth and `opencode.json` is a
  generated, committed artifact. Editing an agent without running
  `make gen-opencode-config` leaves a stale `opencode.json`, which is exactly
  what `make sync-opencode-configmap` pushes to the cluster -- silently.
- T2: `agent.yaml` points at a ConfigMap by name. If that name and the one
  `make sync-opencode-configmap` creates ever diverge, the Agent references a
  ConfigMap that does not exist and (per the README) will not start.
- T3: an undocumented credential secret means the agent silently degrades to the
  free fallback model instead of failing loudly.
- T4: the README is the only runbook for this deployment; a renamed make target
  makes it wrong.
- T5: BITB-125 persistence -- a typo in the `persistence` block means the
  workspace silently stays an EmptyDir, which is the bug BITB-125 fixes.
"""

import pathlib
import re
import subprocess
import sys

import pytest
import yaml

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = REPO_ROOT / "scripts" / "generate-opencode-config.py"
COMMITTED_CONFIG = REPO_ROOT / "opencode.json"
KUBE_DIR = REPO_ROOT / "deployment" / "kubeopencode"
AGENT_YAML = KUBE_DIR / "agent.yaml"
README = KUBE_DIR / "README.md"
MAKEFILE = REPO_ROOT / "Makefile"

# Mirrors the CRD: `kubectl explain agent.spec.persistence --recursive`.
PERSISTENCE_VOLUMES = {"workspace", "sessions"}
PERSISTENCE_FIELDS = {"size", "storageClassName"}
SIZE_RE = re.compile(r"^\d+(Mi|Gi|Ti)$")


@pytest.fixture(scope="module")
def agent_spec():
    return yaml.safe_load(AGENT_YAML.read_text())["spec"]


@pytest.fixture(scope="module")
def persistence(agent_spec):
    """The persistence block; fails explicitly if missing rather than
    silently returning an empty dict and making downstream tests vacuous."""
    if "persistence" not in agent_spec:
        pytest.fail("spec.persistence missing from agent.yaml")
    return agent_spec["persistence"]


@pytest.fixture(scope="module")
def makefile_text():
    return MAKEFILE.read_text()


@pytest.fixture(scope="module")
def readme_text():
    return README.read_text()


# --- T1: committed artifact matches the generator -------------------------


def test_committed_opencode_json_matches_generator():
    """The committed opencode.json must be exactly what the generator emits.

    Run `make gen-opencode-config` and commit the result if this fails.
    """
    result = subprocess.run(
        [sys.executable, str(GENERATOR)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    # Fail on the generator's own error rather than diffing empty output, which
    # would otherwise report a confusing false "drift" (e.g. missing PyYAML).
    assert result.returncode == 0, f"generator failed:\n{result.stderr}"
    assert result.stdout, "generator produced no output"

    assert result.stdout == COMMITTED_CONFIG.read_text(), (
        "opencode.json is out of sync with .opencode/agents/*.md. "
        "Run `make gen-opencode-config` and commit the result."
    )


# --- T2: configRef wiring matches what the Makefile creates ---------------


def _extract_make_target_recipe(makefile_text: str, target: str) -> str:
    """Extract just the recipe lines (tab-indented) for a given target.
    Returns the concatenated recipe text, or empty string if target not found."""
    lines = makefile_text.splitlines()
    in_target = False
    recipe_lines = []
    for i, line in enumerate(lines):
        if not in_target:
            # Match target definition: "target:" at start of line (no leading whitespace)
            if re.match(rf"^{re.escape(target)}:", line):
                in_target = True
            continue
        # We're in the target; collect recipe lines (must start with tab)
        if line.startswith("\t"):
            recipe_lines.append(line)
        elif line.strip() == "":
            # Blank line within recipe - include it
            recipe_lines.append(line)
        else:
            # Non-indented, non-blank line = next target or variable = end of recipe
            break
    return "\n".join(recipe_lines)


def test_agent_configref_matches_makefile_configmap(agent_spec, makefile_text):
    config_ref = agent_spec["configRef"]["configMapRef"]
    sync_target = _extract_make_target_recipe(makefile_text, "sync-opencode-configmap")

    assert f"configmap {config_ref['name']}" in sync_target, (
        f"agent.yaml references ConfigMap '{config_ref['name']}' but "
        "`make sync-opencode-configmap` creates a differently-named one"
    )
    assert f"--from-file={config_ref['key']}=" in sync_target, (
        f"agent.yaml expects key '{config_ref['key']}' which the Makefile does not create"
    )


def test_agent_namespace_matches_makefile_namespace(makefile_text):
    manifest = yaml.safe_load(AGENT_YAML.read_text())
    namespace = manifest["metadata"]["namespace"]
    sync_target = _extract_make_target_recipe(makefile_text, "sync-opencode-configmap")

    assert f"-n {namespace}" in sync_target, (
        f"agent.yaml is in namespace '{namespace}' but the Makefile syncs the "
        "ConfigMap into a different one -- the Agent would reference a "
        "ConfigMap that does not exist"
    )


def test_agent_config_and_configref_are_mutually_exclusive(agent_spec):
    """The CRD runtime-validates this; catch it before it reaches the cluster."""
    assert not ("config" in agent_spec and "configRef" in agent_spec), (
        "spec.config and spec.configRef are mutually exclusive"
    )


# --- T3: credentials are documented ---------------------------------------


def test_every_credential_secret_is_documented(agent_spec, readme_text):
    for credential in agent_spec.get("credentials", []):
        secret_name = credential["secretRef"]["name"]
        assert secret_name in readme_text, (
            f"secret '{secret_name}' is wired in agent.yaml but not documented "
            "in README.md -- an operator would not know to create it, and the "
            "agent silently degrades to the fallback model"
        )


def test_every_credential_env_var_is_documented(agent_spec, readme_text):
    for credential in agent_spec.get("credentials", []):
        env_var = credential["env"]
        assert env_var in readme_text, (
            f"env var '{env_var}' is injected by agent.yaml but undocumented in README.md"
        )


# --- T4: README runbook commands exist ------------------------------------


def test_readme_make_targets_exist(readme_text, makefile_text):
    # Only match `make <target>` inside fenced code blocks or inline backticks,
    # not in prose like "make sure" or "make a decision".
    # Fenced blocks: ```...``` or ```make ...```
    # Inline: `make target`
    code_blocks = re.findall(r"`{3}[\s\S]*?`{3}|`[^`]+`", readme_text)
    code_text = "\n".join(code_blocks)
    referenced = set(re.findall(r"\bmake\s+([a-z0-9][a-z0-9-]+)\b", code_text))
    assert referenced, "expected the README to reference at least one make target in code blocks"

    declared = set(re.findall(r"^([a-zA-Z0-9][a-zA-Z0-9-]*):", makefile_text, re.MULTILINE))
    missing = sorted(referenced - declared)
    assert not missing, f"README references non-existent make targets: {missing}"


# --- T5: BITB-125 persistence block ---------------------------------------


def test_persistence_is_configured(agent_spec):
    """Without spec.persistence the workspace is an EmptyDir (BITB-125)."""
    assert "persistence" in agent_spec, (
        "spec.persistence missing -- the workspace falls back to EmptyDir and "
        "is destroyed on every pod restart (BITB-125)"
    )


def test_persistence_schema_matches_crd(persistence):
    unknown_volumes = set(persistence) - PERSISTENCE_VOLUMES
    assert not unknown_volumes, (
        f"unknown persistence volumes {sorted(unknown_volumes)}; "
        f"the CRD allows {sorted(PERSISTENCE_VOLUMES)}"
    )

    for volume_name, volume in persistence.items():
        unknown_fields = set(volume) - PERSISTENCE_FIELDS
        assert not unknown_fields, (
            f"persistence.{volume_name} has unknown fields {sorted(unknown_fields)}; "
            f"the CRD allows {sorted(PERSISTENCE_FIELDS)}"
        )
        assert SIZE_RE.match(volume["size"]), (
            f"persistence.{volume_name}.size={volume['size']!r} is not a valid quantity"
        )


def test_workspace_persistence_enabled(persistence):
    assert "workspace" in persistence, (
        "persistence.workspace missing -- session data would survive restarts "
        "but the cloned repo and uncommitted work would not (BITB-125)"
    )


def test_persistence_has_no_hardcoded_storage_class(persistence):
    """An empty storageClassName uses the cluster default, keeping this portable."""
    for volume_name, volume in persistence.items():
        assert "storageClassName" not in volume, (
            f"persistence.{volume_name} hardcodes a storageClassName, which ties "
            "the manifest to one cluster; omit it to use the cluster default"
        )
