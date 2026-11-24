"""BITB-311: Compose must not hard-default LLM_MODEL for the backend service.

A non-empty ``LLM_MODEL`` default makes the model look operator-set, so
``LLM_PROVIDER=claude make docker-up`` sent an Ollama model name to Anthropic.
Parses the compose files with PyYAML; no Docker daemon needed.
"""

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = sorted(REPO_ROOT.glob("docker-compose*.yml"))
# Services that run the FastAPI backend (the Ollama container's LLM_MODEL is its own pull list).
BACKEND_SERVICES = {"api"}


def _env(service: dict) -> dict:
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return {k: str(v) for k, v in env.items()}
    out = {}
    for item in env:
        key, _, value = item.partition("=")
        out[key] = value
    return out


def _backend_services():
    for path in COMPOSE_FILES:
        services = yaml.safe_load(path.read_text(encoding="utf-8")).get("services", {})
        for name, svc in services.items():
            if name in BACKEND_SERVICES:
                yield pytest.param(path, name, svc, id=f"{path.name}:{name}")


def test_compose_files_found():
    assert len(COMPOSE_FILES) >= 4


@pytest.mark.parametrize("path,name,svc", list(_backend_services()))
def test_backend_does_not_hard_default_llm_model(path, name, svc):
    value = _env(svc).get("LLM_MODEL")
    if value is None:
        return
    # Accept "" or "${LLM_MODEL:-}" / "${LLM_MODEL}" only; never a non-empty default.
    assert re.fullmatch(r"|\$\{LLM_MODEL(:?-)?\}", value), f"{path.name} {name}: LLM_MODEL={value}"


@pytest.mark.parametrize("filename", ["docker-compose.yml", "docker-compose.dev.yml"])
def test_ollama_stacks_default_ollama_llm_model(filename):
    services = yaml.safe_load((REPO_ROOT / filename).read_text(encoding="utf-8"))["services"]
    value = _env(services["api"]).get("OLLAMA_LLM_MODEL")
    assert value is not None and value.endswith(":-mistral:7b}"), value
