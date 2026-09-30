#!/usr/bin/env python3
"""Tests for the KubeOpenCode deployment manifests and the committed opencode.json.

BITB-129. `scripts/test_generate_opencode_config.py` covers the *generator*;
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
- T5: BITB-128 persistence -- a typo in the `persistence` block means the
  workspace silently stays an EmptyDir, which is the bug BITB-128 fixes.
- T6: BITB-171 -- `k8s/kubeopencode/agent-default-wf2.yaml` declares the SAME
  Agent object as `deployment/kubeopencode/agent.yaml`. It was once a bare
  sketch (inline config, no persistence, fewer credentials), and `kubectl
  apply` of it stripped persistence/configRef/credentials from the live Agent,
  reverting the workspace to an EmptyDir. These tests keep the two manifests
  in sync so applying either converges instead of regressing the other.
"""

import pathlib
import re
import subprocess
import shutil
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

# BITB-171: the second manifest for the same Agent object.
K8S_AGENT_YAML = REPO_ROOT / "k8s" / "kubeopencode" / "agent-default-wf2.yaml"
K8S_README = REPO_ROOT / "k8s" / "kubeopencode" / "README.md"

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


# --- T5: BITB-128 persistence block ---------------------------------------


def test_persistence_is_configured(agent_spec):
    """Without spec.persistence the workspace is an EmptyDir (BITB-128)."""
    assert "persistence" in agent_spec, (
        "spec.persistence missing -- the workspace falls back to EmptyDir and "
        "is destroyed on every pod restart (BITB-128)"
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
        "but the cloned repo and uncommitted work would not (BITB-128)"
    )


def test_persistence_has_no_hardcoded_storage_class(persistence):
    """An empty storageClassName uses the cluster default, keeping this portable."""
    for volume_name, volume in persistence.items():
        assert "storageClassName" not in volume, (
            f"persistence.{volume_name} hardcodes a storageClassName, which ties "
            "the manifest to one cluster; omit it to use the cluster default"
        )


# ── BITB-169: task-reliability plugin ────────────────────────────────────────

PLUGIN_FILE = REPO_ROOT / ".opencode" / "plugin" / "task-reliability.ts"
PLUGIN_TEST_FILE = REPO_ROOT / ".opencode" / "plugin" / "task-reliability.test.ts"
PLUGIN_REGISTRY_DEFAULT = "/workspace/.opencode/task-registry.jsonl"


def test_task_reliability_plugin_file():
    """BITB-169 L1: the plugin must exist and wire all three hooks defensively."""
    assert PLUGIN_FILE.is_file(), (
        f"{PLUGIN_FILE.relative_to(REPO_ROOT)} is missing -- the task-reliability "
        "plugin auto-discovers from .opencode/plugin/, which ships with the clone"
    )
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    for needle in (
        "tool.execute.after",
        "tool.definition",
        "session.created",
        PLUGIN_REGISTRY_DEFAULT,
    ):
        assert needle in text, (
            f"{PLUGIN_FILE.relative_to(REPO_ROOT)} must contain {needle!r} -- "
            "a missing hook or wrong registry path breaks the recovery protocol"
        )
    catch_count = text.count("catch")
    assert catch_count >= 3, (
        "task-reliability must be inert-by-design: expected >= 3 try/catch guards "
        f"(event, tool.execute.after, tool.definition), found {catch_count}"
    )


def test_task_reliability_plugin_helpers_run():
    """BITB-169 L1: the helper unit tests must pass under node --experimental-strip-types."""
    assert PLUGIN_TEST_FILE.is_file(), (
        f"{PLUGIN_TEST_FILE.relative_to(REPO_ROOT)} is missing -- the plugin helpers "
        "must be covered by the node:test suite"
    )
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not available on this runner")
    result = subprocess.run(
        [node, "--experimental-strip-types", "--test", str(PLUGIN_TEST_FILE)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    if result.returncode != 0 and (
        "bad option" in result.stderr or "Unknown file extension" in result.stderr
    ):
        pytest.skip("this node build lacks TS type-stripping support")
    assert result.returncode == 0, (
        "task-reliability helper tests failed:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "# fail 0" in result.stdout, (
        f"task-reliability helper tests reported failures:\n{result.stdout}"
    )
# --- T6: BITB-171 k8s/kubeopencode parity ----------------------------------
#
# `k8s/kubeopencode/agent-default-wf2.yaml` and `deployment/kubeopencode/agent.yaml`
# declare the same Agent object. If they drift, `kubectl apply` of the thinner one
# strips fields from the live object (three-way merge: fields in last-applied but
# absent in the new manifest get removed) -- the exact regression BITB-171 fixes.


@pytest.fixture(scope="module")
def k8s_agent_manifest():
    return yaml.safe_load(K8S_AGENT_YAML.read_text())


@pytest.fixture(scope="module")
def k8s_agent_spec(k8s_agent_manifest):
    return k8s_agent_manifest["spec"]


@pytest.fixture(scope="module")
def k8s_readme_text():
    return K8S_README.read_text()


def test_k8s_agent_targets_same_object(agent_spec, k8s_agent_manifest, k8s_agent_spec):
    """Same name/namespace and identical identity fields -> converging applies."""
    # metadata parity
    meta_expected = {"name": "default-wf2", "namespace": "kubeopencode-system"}
    for field, expected in meta_expected.items():
        assert k8s_agent_manifest["metadata"][field] == expected, (
            f"k8s agent-default-wf2.yaml metadata.{field}={k8s_agent_manifest['metadata'][field]!r} "
            f"!= deployment agent.yaml {expected!r} -- they are different objects"
        )
    for field in ("profile", "workspaceDir", "serviceAccountName"):
        assert k8s_agent_spec[field] == agent_spec[field], (
            f"k8s agent-default-wf2.yaml spec.{field} drifts from deployment/agent.yaml; "
            "applying one over the other flips the field (BITB-171)"
        )


def test_k8s_agent_persistence_matches_deployment(agent_spec, k8s_agent_spec):
    """The k8s variant must carry the same persistence block, or applying it
    over the live Agent reverts the workspace to an EmptyDir (BITB-128/171)."""
    assert "persistence" in k8s_agent_spec, (
        "spec.persistence missing from k8s/agent-default-wf2.yaml -- applying it "
        "over the live Agent strips the PVCs and the workspace falls back to "
        "EmptyDir, destroyed on every pod restart (BITB-171)"
    )
    expected = {
        name: volume["size"] for name, volume in agent_spec["persistence"].items()
    }
    actual = {
        name: volume["size"] for name, volume in k8s_agent_spec["persistence"].items()
    }
    assert actual == expected, (
        f"persistence drift between deployment/agent.yaml ({expected}) and "
        f"k8s/agent-default-wf2.yaml ({actual}) -- one apply would resize or "
        "drop the other's volumes"
    )


def test_k8s_agent_configref_matches_makefile_configmap(k8s_agent_spec, makefile_text):
    config_ref = k8s_agent_spec["configRef"]["configMapRef"]
    sync_target = _extract_make_target_recipe(makefile_text, "sync-opencode-configmap")

    assert f"configmap {config_ref['name']}" in sync_target, (
        f"k8s agent-default-wf2.yaml references ConfigMap '{config_ref['name']}' but "
        "`make sync-opencode-configmap` creates a differently-named one"
    )
    assert f"--from-file={config_ref['key']}=" in sync_target, (
        f"k8s agent-default-wf2.yaml expects key '{config_ref['key']}' which the "
        "Makefile does not create"
    )


def test_k8s_agent_config_and_configref_are_mutually_exclusive(k8s_agent_spec):
    """The CRD runtime-validates this; catch it before it reaches the cluster."""
    assert not ("config" in k8s_agent_spec and "configRef" in k8s_agent_spec), (
        "spec.config and spec.configRef are mutually exclusive"
    )
    assert "configRef" in k8s_agent_spec, (
        "k8s/agent-default-wf2.yaml has neither configRef nor config; it should "
        "use configRef to consume the full 12-agent config (BITB-171)"
    )


def _credentials_by_name(spec):
    return {cred["name"]: cred for cred in spec.get("credentials", [])}


def test_k8s_agent_credentials_superset_of_deployment(agent_spec, k8s_agent_spec):
    """The k8s variant must wire every deployment credential plus the mobile
    server password; a missing one silently degrades providers on apply."""
    deployment_creds = _credentials_by_name(agent_spec)
    k8s_creds = _credentials_by_name(k8s_agent_spec)

    for name, cred in deployment_creds.items():
        assert name in k8s_creds, (
            f"credential '{name}' is wired in deployment/agent.yaml but missing "
            "from k8s/agent-default-wf2.yaml -- applying the k8s manifest would "
            "strip it from the live Agent (BITB-171)"
        )
        assert k8s_creds[name]["secretRef"] == cred["secretRef"], (
            f"credential '{name}' secretRef drifts between the two manifests"
        )
        assert k8s_creds[name]["env"] == cred["env"], (
            f"credential '{name}' env drifts between the two manifests"
        )

    # The one credential the k8s variant adds on purpose (mobile Basic auth).
    server_pw = k8s_creds.get("server-password")
    assert server_pw is not None, (
        "k8s/agent-default-wf2.yaml must keep the server-password credential "
        "(OPENCODE_SERVER_PASSWORD) -- the mobile app authenticates with it"
    )
    assert server_pw["env"] == "OPENCODE_SERVER_PASSWORD"
    assert server_pw["secretRef"]["name"] == "opencode-server-auth"
    assert server_pw["secretRef"]["key"] == "password"


def test_k8s_credential_secrets_and_envs_documented(k8s_agent_spec, k8s_readme_text):
    """The k8s README is the runbook for the k8s manifests: every secret and
    env var the manifest wires must be documented there (T3, but for the
    k8s variant)."""
    for credential in k8s_agent_spec.get("credentials", []):
        secret_name = credential["secretRef"]["name"]
        assert secret_name in k8s_readme_text, (
            f"secret '{secret_name}' is wired in agent-default-wf2.yaml but not "
            "documented in k8s/kubeopencode/README.md -- an operator following "
            "that README would never create it"
        )
        env_var = credential["env"]
        assert env_var in k8s_readme_text, (
            f"env var '{env_var}' is injected by agent-default-wf2.yaml but "
            "undocumented in k8s/kubeopencode/README.md"
        )
