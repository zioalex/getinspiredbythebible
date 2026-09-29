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

DEFAULT_MODEL = "opencode/nemotron-3-ultra-free"
DEFAULT_SMALL_MODEL = "opencode/nemotron-3-ultra-free"
DEFAULT_FALLBACK = "opencode/nemotron-3-super-free"
# Cross-provider fallback activates when OpenCode Zen itself is down (the
# DEFAULT_FALLBACK shares the same provider, so it fails too on a full
# provider outage). Tier-1 is same-family Zen fallback (Ultra -> Super);
# Tier-2 is cross-provider same-120B-class safety net (GPT-OSS-120B free
# via OpenRouter).
CROSS_PROVIDER_FALLBACK = "openrouter/openai/gpt-oss-120b:free"

# Built-in (non-.md) agents still need a fallback so they degrade instead of
# hard-failing when the primary provider returns 429/5xx.
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
    ]
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

    fallback = fm.get("fallback_models") or [DEFAULT_FALLBACK]
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

    builtins = {
        name: {**spec, "fallback_models": [DEFAULT_FALLBACK, CROSS_PROVIDER_FALLBACK]}
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
