#!/usr/bin/env python3
"""Tests for the KubeOpenCode manifests and the committed opencode.json.

BITB-129. `scripts/test_generate_opencode_config.py` covers the *generator*;
nothing covered the *committed artifact* or the manifests that ship it to the
cluster. The gaps these close:

- T1: `.opencode/agents/*.md` is the source of truth and `opencode.json` is a
  generated, committed artifact. Editing an agent without running
  `make gen-opencode-config` leaves a stale `opencode.json`, which is exactly
  what `make sync-opencode-configmap` pushes to the cluster -- silently.
- T2: the Agent manifest points at a ConfigMap by name. If that name and the
  one `make sync-opencode-configmap` creates ever diverge, the Agent references
  a ConfigMap that does not exist and (per the README) will not start.
- T3: an undocumented credential secret means the agent silently degrades to the
  free fallback model instead of failing loudly.
- T4: the README is the only runbook for this deployment; a renamed make target
  makes it wrong.
- T5: BITB-128 persistence -- a typo in the `persistence` block means the
  workspace silently stays an EmptyDir, which is the bug BITB-128 fixes.
- T6 (BITB-171, historical): `k8s/kubeopencode/agent-default-wf2.yaml` and the
  removed `deployment/kubeopencode/agent.yaml` once declared the SAME Agent
  object; applying the thinner one stripped fields from the live Agent. The
  pair-parity tests died with the deployment copy when BITB-285 sunset the
  obsolete folder (verified zero drift first, and owner `kubectl diff`
  confirmed live == the k8s manifests, 2026-11-09); T2/T3/T5 now run directly
  against the single canonical manifest.
- T7: BITB-172 -- the live Agent ran a custom agentImage wired only on the
  cluster (kubectl patch), so repo applies silently fell back to the default
  :latest image; and the pre-wired server-password credential crashlooped
  pods on clusters without the opencode-server-auth secret (the default-wf3
  failure that surfaced the drift). These tests pin the custom image + pull
  secret on every manifest (desktop's pin is DESIRED state pending its apply,
  BITB-283), keep default-wf3 in parity with default-wf2, and
  keep the mobile credential opt-in (exact credential match, no additions).
- T8: BITB-283/285 -- the 2026-11-09 outage recovery check verified the k8s
  wf3 manifest field-for-field against the live export; the wf2/wf3 parity is
  enforced at WHOLE-SPEC level (the subset loop misses one-sided additions,
  and wf3's documented contract is "the wf2 shape under a new name"). The
  obsolete deployment/kubeopencode/ folder must stay a stub-only README --
  nothing guards against docs and manifests re-accumulating in a dead folder
  by accident, which is the steering failure that motivated BITB-285 in the
  first place.
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
MAKEFILE = REPO_ROOT / "Makefile"

# BITB-285: k8s/kubeopencode/ is THE canonical manifest/docs home (owner ruling
# 2026-11-09); the deployment/kubeopencode/ folder is a stub-only relic.
K8S_DIR = REPO_ROOT / "k8s" / "kubeopencode"
AGENT_YAML = K8S_DIR / "agent-default-wf2.yaml"
README = K8S_DIR / "README.md"
STUB_DIR = REPO_ROOT / "deployment" / "kubeopencode"
STUB_README = STUB_DIR / "README.md"

# BITB-172: the wf3 test agent + the suspended desktop agent.
K8S_WF3_AGENT_YAML = K8S_DIR / "agent-default-wf3.yaml"
K8S_DESKTOP_AGENT_YAML = K8S_DIR / "agent-desktop.yaml"
CUSTOM_AGENT_IMAGE = "ghcr.io/zioalex/kubeopencode-agent-opencode:v0.1.9-oc1.18.31"
GHCR_PULL_NAME = "ghcr-pull"

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
#
# BITB-285: runs against the canonical k8s manifests + k8s README; covers
# every credential-bearing Agent (desktop wires none, so it is excluded).


@pytest.mark.parametrize(
    "agent_yaml",
    [AGENT_YAML, K8S_WF3_AGENT_YAML],
    ids=["wf2", "wf3"],
)
def test_every_credential_secret_is_documented(agent_yaml, readme_text):
    spec = yaml.safe_load(agent_yaml.read_text())["spec"]
    for credential in spec.get("credentials", []):
        secret_name = credential["secretRef"]["name"]
        assert secret_name in readme_text, (
            f"secret '{secret_name}' is wired in {agent_yaml.name} but not "
            "documented in k8s/kubeopencode/README.md -- an operator would "
            "not know to create it, and the agent silently degrades to the "
            "fallback model"
        )


@pytest.mark.parametrize(
    "agent_yaml",
    [AGENT_YAML, K8S_WF3_AGENT_YAML],
    ids=["wf2", "wf3"],
)
def test_every_credential_env_var_is_documented(agent_yaml, readme_text):
    spec = yaml.safe_load(agent_yaml.read_text())["spec"]
    for credential in spec.get("credentials", []):
        env_var = credential["env"]
        assert env_var in readme_text, (
            f"env var '{env_var}' is injected by {agent_yaml.name} but "
            "undocumented in k8s/kubeopencode/README.md"
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
PLUGIN_HELPERS_FILE = REPO_ROOT / ".opencode" / "plugin" / "task-reliability-helpers.ts"
PLUGIN_TEST_FILE = REPO_ROOT / ".opencode" / "plugin" / "task-reliability.test.ts"
PLUGIN_REGISTRY_DEFAULT = "/workspace/.opencode/task-registry.jsonl"


def test_task_reliability_plugin_file():
    """BITB-169 L1 + BITB-269/T-1254PLG: single-export loader contract + hooks.

    opencode 1.18.31 iterates every runtime export of the plugin module: any
    non-function export fails the whole load with `Plugin export is not a
    function` (the 2026-11-08 live incident), and every function export is
    called as plugin(ctx, options) — so co-resident helpers break the load
    too. The plugin module must therefore carry exactly one runtime export
    (the default function) and import its helpers from the sibling module.
    """
    assert PLUGIN_FILE.is_file(), (
        f"{PLUGIN_FILE.relative_to(REPO_ROOT)} is missing -- the task-reliability "
        "plugin auto-discovers from .opencode/plugin/, which ships with the clone"
    )
    text = PLUGIN_FILE.read_text(encoding="utf-8")
    # Static mirror of the runtime contract test in task-reliability.test.ts.
    runtime_exports = re.findall(
        r"^export\s+(?!type\b|interface\b)(\S+)", text, re.MULTILINE
    )
    assert runtime_exports == ["default"], (
        f"{PLUGIN_FILE.relative_to(REPO_ROOT)} must export exactly one default "
        f"function (opencode 1.18.31 loader contract); found: {runtime_exports}"
    )
    for needle in (
        "tool.execute.after",
        "tool.definition",
        "task-reliability-helpers.ts",
    ):
        assert needle in text, (
            f"{PLUGIN_FILE.relative_to(REPO_ROOT)} must contain {needle!r} -- "
            "a missing hook or unimported helper library breaks the recovery protocol"
        )
    catch_count = text.count("catch")
    assert catch_count >= 3, (
        "task-reliability must be inert-by-design: expected >= 3 try/catch guards "
        f"(event, tool.execute.after, tool.definition), found {catch_count}"
    )


def test_task_reliability_plugin_helpers_file():
    """BITB-269/T-1254PLG: the helper library carries what moved out of the plugin module."""
    assert PLUGIN_HELPERS_FILE.is_file(), (
        f"{PLUGIN_HELPERS_FILE.relative_to(REPO_ROOT)} is missing -- the plugin's "
        "named helpers must live outside the loader-imported module (see "
        "test_task_reliability_plugin_file for the contract)"
    )
    text = PLUGIN_HELPERS_FILE.read_text(encoding="utf-8")
    for needle in (
        "session.created",
        PLUGIN_REGISTRY_DEFAULT,
        "properties.info",  # empirical 1.18.31 nested event shape (watchdog arming)
        "export function handleBusEvent",
        "export function detectStuckChildren",
    ):
        assert needle in text, (
            f"{PLUGIN_HELPERS_FILE.relative_to(REPO_ROOT)} must contain {needle!r} -- "
            "the registry protocol and stuck-child watchdog depend on it"
        )


def test_task_reliability_plugin_helpers_run():
    """BITB-169 L1: the helper unit tests must pass under node --experimental-strip-types.

    Node changed the test-runner spec-reporter summary prefix from `#` to `ℹ`
    (caught on CI 2026-10-24, PR #1202); assertions must accept both formats.
    """
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
    # Accept both old (`# fail 0`) and new (`ℹ fail 0`) spec-reporter prefixes.
    # Must still fail when fail count is non-zero (e.g. `fail 1`, `fail 17`).
    assert re.search(r"[#ℹ]\s*fail\s+0\b", result.stdout), (
        f"task-reliability helper tests reported failures:\n{result.stdout}"
    )
# --- T6 (BITB-171, retired with the twin): the pair-parity tests between
# k8s/kubeopencode/agent-default-wf2.yaml and the removed
# deployment/kubeopencode/agent.yaml died with the deployment copy when
# BITB-285 sunset the obsolete folder (verified field-for-field identical
# before removal; owner kubectl diff confirmed live == the k8s manifests,
# 2026-11-09). T2/T3/T5 now run directly against the single canonical
# manifest; the BITB-171 lesson lives on in the wf2<->wf3 parity below.


def _credentials_by_name(spec):
    return {cred["name"]: cred for cred in spec.get("credentials", [])}


# --- T7: BITB-172 custom image wiring + wf3 parity -------------------------
#
# The live default-wf2 ran agentImage/imagePullSecrets wired only on the
# cluster; repo manifests pinned nothing and silently fell back to the default
# :latest image. And the pre-wired mobile credential crashlooped fresh pods
# (missing secret). These tests keep the committed state honest.


@pytest.fixture(scope="module")
def wf3_agent_spec():
    return yaml.safe_load(K8S_WF3_AGENT_YAML.read_text())["spec"]


@pytest.mark.parametrize(
    "agent_yaml",
    [AGENT_YAML, K8S_WF3_AGENT_YAML, K8S_DESKTOP_AGENT_YAML],
    ids=["wf2", "wf3", "desktop"],
)
def test_agent_image_pinned_with_pull_secret(agent_yaml):
    """Every Agent manifest pins the custom build (never :latest) and wires
    the pull secret for the private GHCR package (BITB-172). desktop's pin is
    DESIRED state pending its apply (live runs unpinned until then,
    BITB-283) — the test guards the committed manifest so the pin cannot be
    quietly dropped while the apply decision is pending."""
    spec = yaml.safe_load(agent_yaml.read_text())["spec"]

    image = spec.get("agentImage")
    assert image, (
        f"{agent_yaml.name} does not pin spec.agentImage -- the live Agents run "
        "a custom build; an unpinned manifest applies the default :latest image "
        "and repo drifts from live (BITB-172)"
    )
    assert not image.endswith(":latest"), (
        f"{agent_yaml.name} pins {image} -- :latest with IfNotPresent means a "
        "node silently keeps a stale cache (custom-opencode-image.md)"
    )
    assert image == CUSTOM_AGENT_IMAGE, (
        f"{agent_yaml.name} agentImage {image!r} != the fleet build "
        f"{CUSTOM_AGENT_IMAGE!r} -- the manifests must converge with live "
        "(and keep the opencode binary contract one version across the fleet)"
    )

    pull_secrets = [s["name"] for s in spec.get("imagePullSecrets", [])]
    assert GHCR_PULL_NAME in pull_secrets, (
        f"{agent_yaml.name} pins a private-package agentImage without the "
        f"{GHCR_PULL_NAME} pull secret -- pods fail image pull with 401"
    )


def test_wf3_agent_matches_wf2_shape(agent_spec, wf3_agent_spec):
    """default-wf3 is the wf2 shape under a new name: same config, persistence,
    credentials, and image wiring — only its own PVCs/Service differ (the
    operator provisions those per name). Parity is what made wf3 a faithful
    test of the custom image instead of a second source of drift."""
    for field in (
        "profile",
        "workspaceDir",
        "serviceAccountName",
        "configRef",
        "persistence",
        "agentImage",
        "imagePullSecrets",
    ):
        assert wf3_agent_spec[field] == agent_spec[field], (
            f"agent-default-wf3.yaml spec.{field} drifts from "
            "agent-default-wf2.yaml -- wf3 stopped being a faithful test of "
            "the custom image (BITB-172)"
        )
    assert _credentials_by_name(wf3_agent_spec) == _credentials_by_name(agent_spec), (
        "agent-default-wf3.yaml credentials drift from agent-default-wf2.yaml (BITB-172)"
    )


# --- T8: BITB-283/285 whole-spec parity + obsolete-folder guard --------------
#
# k8s/kubeopencode/ is THE canonical manifest home (owner ruling 2026-11-09;
# BITB-285 implemented the sunset of the obsolete deployment/kubeopencode/
# folder). wf3's documented contract (its own header + T7) is "the wf2 shape
# under a new name" — nothing spec-level differs; only its operator-provisioned
# PVCs/Service differ, which are not spec fields. The T7 subset loop above
# gives per-field diagnostics but misses ONE-SIDED ADDITIONS (a field gained
# by only one twin — e.g. someone adds `suspend` or `maxConcurrentTasks` to
# wf3 alone — ships silently). Whole-spec equality closes that gap.


def test_k8s_wf3_spec_identical_to_k8s_wf2():
    """Whole-spec parity between the canonical wf2/wf3 manifests.

    wf3 exists to exercise the custom agent image as a faithful clone of
    wf2 (BITB-172); any spec difference — changed field, one-sided
    addition, or removal — means wf3 stopped being that clone. When the
    two Agents legitimately need different specs someday, change this test
    DELIBERATELY (and the wf3 header) rather than letting it drift.
    """
    wf2_spec = yaml.safe_load(AGENT_YAML.read_text())["spec"]
    wf3_spec = yaml.safe_load(K8S_WF3_AGENT_YAML.read_text())["spec"]

    assert wf3_spec == wf2_spec, (
        "spec drift between k8s/kubeopencode/agent-default-wf2.yaml and "
        "agent-default-wf3.yaml -- wf3's contract is the wf2 shape under a "
        "new name (BITB-172); the T7 field-subset test stays green on "
        "one-sided additions, so treat any failure here as real drift"
    )


def test_obsolete_deployment_folder_is_stubbed_only():
    """BITB-285: the obsolete deployment/kubeopencode/ folder must contain
    ONLY the stub README.

    The folder kept accreting real content (the pinned manifest, runbook
    sections from merged PRs) with nothing stopping it — the steering failure
    that made two PRs treat the dead tree as canonical. This test is the
    mechanical backstop: any new file there fails CI until it is either
    moved to k8s/kubeopencode/ or explicitly justified in this test.
    """
    assert STUB_DIR.is_dir(), (
        f"{STUB_DIR} should still exist as a stub-only folder with a README "
        "pointing at k8s/kubeopencode/ (BITB-285)"
    )
    entries = sorted(p.name for p in STUB_DIR.iterdir())
    assert entries == ["README.md"], (
        f"deployment/kubeopencode/ must be stub-only (obsolete, BITB-285); "
        f"found extra entries: {[e for e in entries if e != 'README.md']} -- "
        "move new content to k8s/kubeopencode/ instead"
    )
    stub_text = STUB_README.read_text()
    assert "obsolete" in stub_text.lower(), (
        "the deployment/kubeopencode/ stub README must state the folder is "
        "obsolete (BITB-285)"
    )
    assert "k8s/kubeopencode" in stub_text, (
        "the deployment/kubeopencode/ stub README must point at the canonical "
        "k8s/kubeopencode/ home (BITB-285)"
    )
