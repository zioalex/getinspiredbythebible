#!/usr/bin/env python3
"""Generate complete opencode.json from .opencode/agents/*.md files."""
import json
import yaml
import pathlib
import sys

AGENTS_DIR = pathlib.Path(".opencode/agents")
SCHEMA = "https://opencode.ai/config.json"

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
    if "permission" in fm:
        agent["permission"] = fm["permission"]
    return path.stem, agent

def main():
    agents = {}
    for md in sorted(AGENTS_DIR.glob("*.md")):
        name, agent = parse_agent_md(md)
        agents[name] = agent

    config = {
        "$schema": SCHEMA,
        "agent": {
            "build": {"mode": "primary"},
            "plan": {"mode": "primary"},
            **agents,
        }
    }
    json.dump(config, sys.stdout, indent=2)
    sys.stdout.write("\n")

if __name__ == "__main__":
    main()
