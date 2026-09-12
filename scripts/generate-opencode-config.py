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
DEFAULT_FALLBACK = "opencode/muse-spark-1.3-contributor-free"

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
# is inert.
PLUGIN = [
    [
        "opencode-runtime-fallback@0.2.4",
        {
            "enabled": True,
            "retry_on_errors": [429, 500, 502, 503, 504],
            "retryable_error_patterns": [
                "upstream error",
                "temporarily overloaded",
                "service temporarily unavailable",
            ],
            "max_fallback_attempts": 1,
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


def main():
    agents = {}
    for md in sorted(AGENTS_DIR.glob("*.md")):
        name, agent = parse_agent_md(md)
        agents[name] = agent

    builtins = {
        name: {**spec, "fallback_models": [DEFAULT_FALLBACK]}
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
    json.dump(config, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
