#!/usr/bin/env python3
"""Generate complete opencode.json from .opencode/agents/*.md files.

Per-agent settings (model, fallback_models, tools, permission, prompt) are
sourced from the frontmatter of `.opencode/agents/*.md`, which is the single
source of truth. The global settings below have no other home: they used to
live inline in `deployment/kubeopencode/agent.yaml` under `spec.config`, which
is now replaced by `spec.configRef` pointing at a ConfigMap built from this
file's output.
"""

import json
import pathlib
import sys

import yaml

AGENTS_DIR = pathlib.Path(".opencode/agents")
SCHEMA = "https://opencode.ai/config.json"

# BITB-236: paid primaries on high-stakes lanes (glm-5.3 / deepseek-v3.2-exp);
# gpt-oss-120b RETIRED (41.8% Aider, weakest on ranking).
# BITB-279 (2026-11-08 21:30 key-exhaustion incident): the old tier-1 hops
# pointed at the opencode Zen gateway (`opencode/nemotron-3-ultra-free`,
# `opencode/mimo-v2.6-flash-free`) for which this pod has NO credentials —
# dead on arrival, so a failed primary had no working failover, and the paid
# tier-2 shared the same exhausted OpenRouter key. Cross-provider tier-1 is
# impossible now: OpenRouter is the only provider with credentials here AND
# the only free slate (12 `nvidia/nemotron-*:free` variants, audited
# 2026-11-08). The invariant that survives the observed failure is a FREE
# tier-1: `:free` models draw no credit, so the chain keeps serving while
# the paid key is exhausted.
#
# Chain design — paid primary on workhorse/skeptic lanes, tier-1 always a
# free `openrouter/:free` model, tier-2 always PAID (the OTHER paid model
# of the pair):
#   - Workhorse/Builders (6 agents + global builtins + orchestrator):
#     primary — `openrouter/z-ai/glm-5.3` (paid), tier 1 —
#     `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`, tier 2 —
#     `openrouter/deepseek/deepseek-v3.2-exp` (paid).
#   - Skeptics (4 agents):
#     primary — `openrouter/deepseek/deepseek-v3.2-exp` (paid), tier 1 —
#     ultra-free, tier 2 — `openrouter/z-ai/glm-5.3` (paid).
#   - Mechanical (2 agents, free by design per BITB-236):
#     primary — ultra-free, tier 1 —
#     `openrouter/nvidia/nemotron-3.5-lightning:free` (de-duplicated: the
#     ultra model IS the primary), tier 2 — `openrouter/z-ai/glm-5.3` (paid).
#   - small_model (title/summary/compaction) — lightning-free: cheap ops
#     stay free-tier and light.
#   - tier 2 is ALWAYS paid and always OpenRouter (enforce_openrouter_for_paid).
DEFAULT_MODEL = "openrouter/z-ai/glm-5.3"
DEFAULT_SMALL_MODEL = "openrouter/nvidia/nemotron-3.5-lightning:free"
# Live-catalog-verified IDs (glm/deepseek via `opencode models` 2026-10-24;
# both nemotron `:free` variants re-verified in the 2026-11-08 OpenRouter
# audit — see the BITB-279 story):
GLM_5_3 = "openrouter/z-ai/glm-5.3"
DEEPSEEK_V3_2_EXP = "openrouter/deepseek/deepseek-v3.2-exp"
OR_STRONG_FREE = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"

# Built-in (non-.md) agents still need a fallback so they degrade instead of
# hard-failing when the primary provider returns 429/5xx.
# Builtins inherit the global model (GLM-5.3), so their tier-1 hop is the
# strong free workhorse; paid DeepSeek-V3.2-Exp stays the last hop (BITB-279).
BUILTIN_AGENTS = {
    "build": {"mode": "primary"},
    "plan": {"mode": "primary"},
    "general": {},
    "explore": {},
    "compaction": {},
    "title": {},
    "summary": {},
}

# Fallback routing is executed by this plugin; without it `fallback_models`
# is inert. 401/402/403 are included because a provider returning an auth or
# quota error (e.g. GitHub Copilot subscription credits exhausted → 403, or
# the PAT-rejected "not supported for this endpoint" 400) must still fail over
# to a different provider rather than hard-failing the agent.
PLUGIN = [
    [
        "opencode-runtime-fallback@0.2.4",
        {
            "enabled": True,
            "retry_on_errors": [400, 401, 402, 403, 429, 500, 502, 503, 504],
            "retryable_error_patterns": [
                "upstream error",
                "temporarily overloaded",
                "service temporarily unavailable",
                "subscription",
                "quota",
                "credits",
                "exceeded",
                "insufficient",
                "not supported for this endpoint",
                "bad request",
            ],
            "max_fallback_attempts": 2,
            "cooldown_seconds": 120,
            "timeout_seconds": 45,
            "notify_on_fallback": True,
        },
    ],
    # BITB-269: the task-reliability plugin (BITB-169) MUST also load in the
    # KubeOpenCode pod. Load-path design (verified 2026-11-08 against
    # opencode 1.18.31):
    #
    #   - `make sync-opencode-configmap` syncs ONLY opencode.json into the
    #     `opencode-config` ConfigMap → /tools/opencode.json (OPENCODE_CONFIG).
    #     The plugin .ts file is never synced, and plugin auto-discovery scans
    #     `.opencode/plugin/` under the EFFECTIVE project root, which in the
    #     pod is /workspace (WORKSPACE_DIR, PVC) — empty. The plugin source
    #     only exists in the repo checkout at /workspace/repo/.opencode/plugin/,
    #     so an absolute file:// URL is the only way the pod loads it.
    #   - DELIVERY (2026-11-08 live incident fix, T-1254PLG): this path points
    #     INTO the pod's shared checkout, which nothing updated after the
    #     initial clone — the config was synced while the checkout sat 6 days
    #     stale, and the OLD plugin it pointed at was rejected by the runtime
    #     (`failed to load plugin … error="Plugin export is not a function"`,
    #     runtime log 18:52:00Z). `make sync-opencode-configmap` therefore
    #     also runs scripts/sync-opencode-workspace.sh, which fast-forwards
    #     /workspace/repo to origin/main (ff-only, never rewrites; attached
    #     worktrees unaffected) and runs the plugin's unit tests in the pod
    #     BEFORE the ConfigMap is touched. MERGE THE PR FIRST, then sync.
    #   - LOADER CONTRACT (empirically pinned, opencode 1.18.31): the plugin
    #     module's runtime export surface must be EXACTLY one function — the
    #     default export. The loader iterates Object.values(module): any
    #     non-function export (a string/number constant) fails the whole
    #     load with `Plugin export is not a function`, and every function
    #     export is CALLED as plugin(ctx, options) — a co-resident helper
    #     throws with the wrong args. Helpers therefore live in
    #     .opencode/plugin/task-reliability-helpers.ts (imported, NEVER
    #     re-exported); task-reliability.test.ts asserts the export surface
    #     and opencode-ci.yml runs the suite on every .opencode/** change.
    #   - On developer laptops the absolute path usually does not resolve.
    #     Empirically verified: opencode 1.18.31 tolerates a missing file://
    #     plugin entry — `opencode serve` starts and listens, and a full
    #     `opencode run` session completes (the entry is silently skipped;
    #     no startup or session failure). Laptops additionally get the plugin
    #     for free via auto-discovery in the repo checkout.
    #   - Duplicate loading (explicit entry + auto-discovery) is harmless: the
    #     registry is an append-only JSONL event log.
    #
    # The plugin itself records subagent `question.asked` events as
    # `status: "asking"` registry lines and marks (and best-effort aborts)
    # children inactive for TASK_RELIABILITY_STUCK_SECONDS (default 1200s) —
    # the 2026-11-07 9h34m orchestrator hang class (BITB-269). On 1.18.31 the
    # `session.created` parent linkage arrives nested in
    # `properties.info.parentID` (pinned by test), so created lines and
    # watchdog tracking work against the live event shape.
    "file:///workspace/repo/.opencode/plugin/task-reliability.ts",
]

PROVIDER = {
    "opencode": {
        "options": {
            "timeout": 600000,
            "headerTimeout": 60000,
            "chunkTimeout": 120000,
            "setCacheKey": True,
        }
    }
}


# Appended to every .md agent prompt. Two failure modes seen in live
# delegation smoke tests motivated this:
#   1. fullstack-engineer claimed it owned `/backend` — this repo uses `api/`.
#   2. Agents asked to name an escalation target invented non-existent agents
#      ("Backend Engineer", "Design Agent") because no agent knew its siblings.
# Keeping this in the generator rather than duplicated across the .md files
# means new agents inherit it for free and the roster cannot drift.
REPO_LAYOUT = """\
## Repository layout (authoritative)

| Path | Contents |
| ---- | -------- |
| `api/` | Python 3.12 / FastAPI backend. **The backend lives here — there is no `/backend` directory.** |
| `frontend/` | Next.js / React / TypeScript web app |
| `android/` | Kotlin / Jetpack Compose Android app |
| `deployment/` | Terraform configs for Azure, KubeOpenCode manifests |
| `scripts/` | DB init, embedding generation, migrations, env validation |
| `data/` | Bible data files |
| `docs/` | Documentation, `BACKLOG.md`, `BACKLOG_STORIES/` |

Never invent or assume a path. If you need a directory that is not listed
above, verify it exists before relying on it."""

HANDOFF_RULES = """\
When a request falls outside your scope, do not attempt it and do not invent
an agent name. Name the correct agent from the roster above and hand the work
back to `orchestrator`, which owns planning and delegation."""


def build_shared_context(agents: dict) -> str:
    """Build the shared prompt suffix, with the roster derived from the agents.

    Deriving the roster from the parsed agents (rather than hardcoding it)
    guarantees it stays in sync as agents are added, removed, or re-scoped.
    """
    rows = "\n".join(
        f"| `{name}` | {spec.get('description', '').strip()} |"
        for name, spec in sorted(agents.items())
    )
    roster = (
        "## Agent roster (your siblings)\n\n| Agent | Responsibility |\n| ----- | -------------- |\n"
        + rows
    )
    return f"\n\n---\n\n{REPO_LAYOUT}\n\n{roster}\n\n{HANDOFF_RULES}\n"


def parse_agent_md(path: pathlib.Path):
    content = path.read_text()
    if not content.startswith("---"):
        raise ValueError(f"{path}: missing frontmatter")
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path}: invalid frontmatter format")
    fm = yaml.safe_load(parts[1])
    body = parts[2].strip()

    agent = {
        "description": fm.get("description", ""),
        "mode": fm.get("mode", "subagent"),
        "model": fm.get("model"),
        "prompt": body,
    }

    fallback = fm.get("fallback_models") or [OR_STRONG_FREE, DEEPSEEK_V3_2_EXP]
    agent["fallback_models"] = fallback

    # Only forwarded when declared, so the generated config stays minimal.
    for optional in ("tools", "permission"):
        if optional in fm:
            agent[optional] = fm[optional]

    return path.stem, agent


def enforce_openrouter_for_paid(config: dict) -> None:
    """Fail generation if a paid model is not served via OpenRouter.

    Convention: free-tier models (":free" / "-free" suffix) may live on any
    provider; anything billable must be "openrouter/..." — the only provider
    in this graph backed by our own key/credits. This keeps a future edit
    from silently re-attaching a paid primary elsewhere (cf. the retired
    github-copilot/claude-opus-5 primary, which died with exhausted
    subscription credits and returned empty responses).
    """
    violations = []
    checked = {
        "<global>/model": config["model"],
        "<global>/small_model": config["small_model"],
    }
    for name, spec in config["agent"].items():
        if spec.get("model"):
            checked[f"{name}/model"] = spec["model"]
        for i, fb in enumerate(spec.get("fallback_models") or []):
            checked[f"{name}/fallback_models[{i}]"] = fb
    for where, model_id in checked.items():
        provider, _, model = model_id.partition("/")
        if not (model.endswith(":free") or model.endswith("-free")) and provider != "openrouter":
            violations.append(f"{where}={model_id}")
    if violations:
        raise SystemExit("Paid models must use the openrouter provider: " + ", ".join(violations))


def main():
    agents = {}
    for md in sorted(AGENTS_DIR.glob("*.md")):
        name, agent = parse_agent_md(md)
        agents[name] = agent

    # Appended after all agents are parsed so the roster is complete.
    shared = build_shared_context(agents)
    for agent in agents.values():
        agent["prompt"] = agent["prompt"] + shared

    # Builtins inherit the global model (GLM-5.3); their chain is the global
    # one: strong free tier-1, paid DeepSeek-V3.2-Exp last (BITB-279).
    builtins = {
        name: {**spec, "fallback_models": [OR_STRONG_FREE, DEEPSEEK_V3_2_EXP]}
        for name, spec in BUILTIN_AGENTS.items()
    }

    config = {
        "$schema": SCHEMA,
        "model": DEFAULT_MODEL,
        "small_model": DEFAULT_SMALL_MODEL,
        "plugin": PLUGIN,
        "provider": PROVIDER,
        "agent": {
            **builtins,
            **agents,
        },
    }
    enforce_openrouter_for_paid(config)
    json.dump(config, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
