#!/usr/bin/env python3
"""Regression tests for scripts/generate-opencode-config.py.

These guard the BITB-123 regression where the generated opencode.json silently
lost `fallback_models`, `tools`, the runtime-fallback plugin, and the provider
timeouts when config moved out of `spec.config` in agent.yaml into a generated
ConfigMap. The result was that fallback routing was inert: agents hard-failed
on a 429/5xx instead of degrading to the free-tier model.

BITB-173 additionally guards against non-existent model IDs: the original
chain pinned `opencode/nemotron-3-super-free` (Zen serves no Super variant) and
`openrouter/openai/gpt-oss-120b:free` (no free variant on OpenRouter), so every
fallback hop failed with ProviderModelNotFoundError and the plugin never once
failed over. Model IDs changed here MUST be verified against the live catalog
(`opencode models`) — the gateway, not the docs, is the source of truth.

BITB-236 updates the matrix to paid primaries and retires `gpt-oss-120b`. The
tests now reflect the new lane‑aware fallback chains.

BITB-279 (2026-11-08 21:30 key-exhaustion incident) retires the cross-provider
tier-1 rule: the `opencode/*` Zen-gateway hops had no credentials in this pod
(dead on arrival), and OpenRouter is now the only provider with credentials AND
the only free slate (12 `nvidia/nemotron-*:free` variants), so a cross-provider
hop is impossible. The invariant that actually survives the observed failure
is a FREE tier-1 — free models draw no credit, so the chain keeps serving
while the paid key is exhausted. Paid tier-2 (glm-5.3 / deepseek-v3.2-exp)
stays as the defense against free-tier rate caps and upstream 5xx/429.
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
AGENTS_DOC = REPO_ROOT / "k8s" / "kubeopencode" / "agents.md"

STRONG_PRIMARY = "openrouter/z-ai/glm-5.3"
TIER2_FALLBACK = "openrouter/deepseek/deepseek-v3.2-exp"
# BITB-279: tier-1 hops must be free-tier `openrouter/:free` models — they
# draw no credit, so the chain survives paid-key exhaustion (the
# 2026-11-08 incident). Cross-provider hops are impossible: OpenRouter is
# the only provider with credentials and the only free slate.
OR_STRONG_FREE = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
OR_LIGHT_FREE = "openrouter/nvidia/nemotron-3.5-lightning:free"
# The retired IDs must never come back: the BITB-173 pair was non-existent
# on its providers; the BITB-279 pair exists but is unservable in this pod
# (no Zen-gateway credentials — dead on arrival, the exact incident that
# made every fallback chain inert during key exhaustion).
STALE_MODEL_IDS = (
    "opencode/nemotron-3-super-free",
    "openrouter/openai/gpt-oss-120b:free",
    "openrouter/openai/gpt-oss-120b",
    "opencode/nemotron-3-ultra-free",
    "opencode/mimo-v2.6-flash-free",
)
BUILTINS = ("build", "plan", "general", "explore", "compaction", "title", "summary")
PLUGIN_NAME = "opencode-runtime-fallback@0.2.4"
# BITB-269: absolute in-pod path to the task-reliability plugin source
# (only the generated opencode.json is synced into the ConfigMap — see the
# PLUGIN comment in the generator for the full load-path rationale).
TASK_RELIABILITY_PLUGIN = "file:///workspace/repo/.opencode/plugin/task-reliability.ts"


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


def expected_chain(primary: str) -> list:
    """Lane-aware fallback chain (BITB-279: free tier-1, all OpenRouter).

    - Workhorse/Builders (GLM-5.3 primary): [ultra free, DeepSeek V3.2 Exp]
    - Skeptics (DeepSeek V3.2 Exp primary): [ultra free, GLM-5.3]
    - Mechanical (free ultra primary): [lightning free, GLM-5.3]
    """
    if primary == "openrouter/z-ai/glm-5.3":
        return [OR_STRONG_FREE, "openrouter/deepseek/deepseek-v3.2-exp"]
    if primary == "openrouter/deepseek/deepseek-v3.2-exp":
        return [OR_STRONG_FREE, "openrouter/z-ai/glm-5.3"]
    # Free primary (mechanical lanes): tier-1 de-duplicated to lightning.
    return [OR_LIGHT_FREE, "openrouter/z-ai/glm-5.3"]


def test_every_md_agent_has_fallback_models(config, md_agents):
    """The core regression: fallback_models was absent for every agent.

    BITB-279 shape: fallbacks must exist, tier-1 must be the lane's free
    `openrouter/:free` hop, and no fallback may duplicate the primary
    (a duplicate hop burns a retry on the same dead model instead of
    failing over — the mechanical lanes' old chain had exactly that bug).
    """
    for name in md_agents:
        fallbacks = config["agent"][name].get("fallback_models")
        assert fallbacks, f"{name} has no fallback_models"
        primary = config["agent"][name]["model"]
        assert fallbacks == expected_chain(primary), (
            f"{name}: expected {expected_chain(primary)}, got {fallbacks}"
        )
        assert primary not in fallbacks, (
            f"{name}: fallback list duplicates the primary {primary}"
        )


def test_fallback_chain_is_free_first_paid_last(config, md_agents):
    """BITB-173 design rule: powerful FREE model first, PAID model last.

    Tier 1 must be a free variant (":free"/"-free" suffix) so routine failovers
    cost nothing; tier 2 is the paid safety net that only engages on double
    failure. This ordering is the whole point of the chain — inverting it
    silently bills every primary hiccup.
    """
    for name in md_agents:
        tier1, tier2 = config["agent"][name]["fallback_models"][:2]
        model1 = tier1.partition("/")[2]
        model2 = tier2.partition("/")[2]
        assert model1.endswith(":free") or model1.endswith("-free"), (
            f"{name}: tier-1 {tier1} is not a free variant"
        )
        assert not (model2.endswith(":free") or model2.endswith("-free")), (
            f"{name}: tier-2 {tier2} must be the paid hop, not another free tier"
        )


def test_fallback_chain_exact_and_ordered(config, md_agents):
    """Every .md agent must declare exactly [tier1, tier2] — no partial edits.

    Expected chain is lane-aware (see expected_chain): tier-1 is always the
    lane's free `openrouter/:free` hop, tier-2 the lane's paid safety net.
    """
    for name in md_agents:
        primary = config["agent"][name]["model"]
        assert config["agent"][name]["fallback_models"] == expected_chain(primary), (
            f"{name} fallback chain is not exactly {expected_chain(primary)}"
        )


def test_primary_is_the_strongest_paid_model(config):
    """The global primary (builtins: build/plan/general/explore/etc.) is the
    strongest **paid** model on the graph — `openrouter/z-ai/glm-5.3`.
    Cheap ops (`small_model`) stay on a free `openrouter/:free` model
    (lightning), off the paid key and off the strong workhorse's rate
    limits (BITB-279).
    """
    assert config["model"] == STRONG_PRIMARY
    # Cheap ops tier stays free-tier; the Zen gateway had no credentials.
    assert config["small_model"] == OR_LIGHT_FREE


def test_fallback_chain_tier1_is_free(config, md_agents):
    """BITB-279: tier-1 must be a free-tier `openrouter/:free` model.

    Policy change (2026-11-08 21:30 key-exhaustion incident): cross-provider
    tier-1 is impossible — OpenRouter is the only provider this pod has
    credentials for and the only free slate (12 `nvidia/nemotron-*:free`
    variants). The invariant that actually rescues the observed failure is
    FREE tier-1: free models draw no credit, so the chain keeps serving
    while the paid key is exhausted. (The old cross-provider rule died with
    the Zen-gateway credentials — every `opencode/*` hop was dead on
    arrival, which is why the 21:30 incident took every lane down.)
    """
    for name in md_agents:
        tier1 = config["agent"][name]["fallback_models"][0]
        assert tier1.startswith("openrouter/") and tier1.endswith(":free"), (
            f"{name}: tier-1 {tier1} is not a free-tier openrouter model — "
            "the chain cannot survive key exhaustion"
        )
    # Builtins inherit the global chain; their tier-1 hop is the strong free
    # workhorse too.
    for name in BUILTINS:
        hop = config["agent"][name]["fallback_models"][0]
        assert hop == OR_STRONG_FREE, f"builtin {name}: tier-1 hop is {hop}"


def test_no_stale_model_ids_in_config(config):
    """Tripwire: the retired non-existent IDs must never reappear (BITB-173)."""
    blob = json.dumps(config)
    for stale in STALE_MODEL_IDS:
        assert stale not in blob, f"retired non-existent model id reappeared: {stale}"


def test_builtin_agents_have_fallback_models(config):
    """Builtins inherit the global chain: [strong free, paid DeepSeek] (BITB-279)."""
    for name in BUILTINS:
        assert name in config["agent"], f"builtin {name} missing"
        fallbacks = config["agent"][name].get("fallback_models")
        assert fallbacks == [OR_STRONG_FREE, "openrouter/deepseek/deepseek-v3.2-exp"], (
            f"builtin {name}: expected [strong free, paid], got {fallbacks}"
        )


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


def test_task_reliability_plugin_entry_present(config):
    """BITB-269: the pod loads plugins ONLY through the generated config.

    `make sync-opencode-configmap` syncs just opencode.json into the ConfigMap;
    auto-discovery scans the effective project root (/workspace in the pod —
    empty), while the plugin source lives in the repo checkout at
    /workspace/repo/.opencode/plugin/. Without this absolute file:// entry the
    pod never loads the plugin and the durable task registry is never written
    (proven by the 2026-11-07 incident forensics).
    """
    plugins = [e[0] if isinstance(e, list) else e for e in config["plugin"]]
    assert TASK_RELIABILITY_PLUGIN in plugins, (
        "task-reliability plugin missing from generated config: "
        "no durable child registry in the pod"
    )


def test_subagent_question_denied(config):
    """BITB-269: every mode: subagent agent must deny the question tool.

    A subagent has no interactive user: a question can never be answered and
    (opencode ≤1.18) parks the session forever while the parent's dispatch
    blocks with it. The per-agent `question: deny` permission from the .md
    frontmatter must round-trip into the generated agent objects.
    """
    subagents = [
        name
        for name, spec in config["agent"].items()
        if spec.get("mode") == "subagent"
    ]
    assert len(subagents) == 11, f"expected 11 subagent agents, got {len(subagents)}"
    for name in subagents:
        permission = config["agent"][name].get("permission")
        assert isinstance(permission, dict), f"{name} has no permission block"
        assert permission.get("question") == "deny", (
            f"{name} does not deny the question tool: {permission.get('question')!r}"
        )


def test_permission_frontmatter_round_trips(config):
    """Every permission key declared in an .md frontmatter survives generation."""
    for path in sorted(AGENTS_DIR.glob("*.md")):
        fm = yaml.safe_load(path.read_text().split("---", 2)[1])
        expected = fm.get("permission")
        if not expected:
            continue
        generated = config["agent"][path.stem].get("permission")
        assert generated == expected, (
            f"{path.name}: permission frontmatter did not round-trip: "
            f"expected {expected}, generated {generated}"
        )


def test_plugin_retry_options(config):
    opts = config["plugin"][0][1]
    assert opts["enabled"] is True
    # Must include auth/quota 4xx codes so an exhausted-subscription provider
    # (e.g. GitHub Copilot credits out → 403) still fails over cross-provider.
    assert opts["retry_on_errors"] == [400, 401, 402, 403, 429, 500, 502, 503, 504]


def test_provider_timeouts_present(config):
    opts = config["provider"]["opencode"]["options"]
    assert opts["timeout"] == 600000
    assert opts["setCacheKey"] is True


def test_every_agent_has_non_empty_prompt(config, md_agents):
    for name in md_agents:
        assert config["agent"][name]["prompt"].strip(), f"{name} has empty prompt"


def test_models_match_agents_doc(config):
    """Guards against drift between the docs table and the generated config.

    BITB-173: the table's fallback columns were silently wrong for months
    (they documented the two non-existent model IDs). Parse all three model
    cells — primary, fallback 1, fallback 2 — and assert each against the
    generated config so the table can never lie again.
    """
    doc = AGENTS_DOC.read_text()
    rows = re.findall(
        r"^\|\s*([a-z0-9-]+)\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`",
        doc,
        re.MULTILINE,
    )
    assert len(rows) >= 12, f"could not parse agents.md table (got {len(rows)})"
    for name, model, fb1, fb2 in rows:
        assert name in config["agent"], f"{name} documented but not generated"
        spec = config["agent"][name]
        assert spec["model"] == model, (
            f"{name}: agents.md says {model}, " f"generated {spec['model']}"
        )
        assert spec["fallback_models"][0] == fb1, (
            f"{name}: agents.md fallback 1 says {fb1}, "
            f"generated {spec['fallback_models'][0]}"
        )
        assert spec["fallback_models"][1] == fb2, (
            f"{name}: agents.md fallback 2 says {fb2}, "
            f"generated {spec['fallback_models'][1]}"
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


def test_every_agent_prompt_states_backend_lives_in_api(config, md_agents):
    """Regression: fullstack-engineer reported it owned `/backend`.

    The backend is `api/`. Every agent must carry the authoritative layout so
    none of them hallucinate a path that does not exist in this repo.
    """
    for name in md_agents:
        prompt = config["agent"][name]["prompt"]
        assert "`api/`" in prompt, f"{name} prompt lacks the api/ layout entry"
        assert (
            "there is no `/backend` directory" in prompt
        ), f"{name} prompt does not rule out the bogus /backend path"


def test_every_agent_prompt_lists_all_siblings(config, md_agents):
    """Regression: agents invented escalation targets ("Design Agent").

    Each agent must see the full roster so it can name a real sibling.
    """
    for name in md_agents:
        prompt = config["agent"][name]["prompt"]
        for sibling in md_agents:
            assert f"`{sibling}`" in prompt, f"{name} prompt is missing sibling {sibling}"


def test_roster_is_derived_not_hardcoded(config, md_agents):
    """The roster must carry each agent's real description, so it can't drift."""
    for name in md_agents:
        description = config["agent"][name]["description"].strip()
        assert description, f"{name} has no description to put in the roster"
        # Every agent's description appears in every other agent's roster.
        assert (
            description in config["agent"]["orchestrator"]["prompt"]
        ), f"{name} description missing from the generated roster"


def test_handoff_rule_names_orchestrator(config, md_agents):
    for name in md_agents:
        assert "hand the work" in config["agent"][name]["prompt"], f"{name} lacks a handoff rule"


def test_agent_body_precedes_shared_context(config):
    """Shared context is a suffix — it must not shadow the agent's own brief."""
    prompt = config["agent"]["verifier"]["prompt"]
    assert prompt.index("independent verifier") < prompt.index("Repository layout")
