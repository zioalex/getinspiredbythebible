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


_VAR = re.compile(r"\$\{(\w+):-((?:[^${}]|\$\{[^}]*\})*)\}")


def _interpolate(value: str, env: dict[str, str]) -> str:
    """Minimal Compose ``${VAR:-default}`` interpolation (nested defaults allowed)."""
    while True:
        new = _VAR.sub(lambda m: env.get(m.group(1)) or m.group(2), value)
        if new == value:
            return new
        value = new


def _ollama_env(filename: str) -> tuple[dict, dict]:
    services = yaml.safe_load((REPO_ROOT / filename).read_text(encoding="utf-8"))["services"]
    return _env(services["api"]), _env(services["ollama"])


@pytest.mark.parametrize("filename", ["docker-compose.yml", "docker-compose.dev.yml"])
@pytest.mark.parametrize(
    "operator_env,expected",
    [
        ({}, "mistral:7b"),
        ({"OLLAMA_LLM_MODEL": "phi3"}, "phi3"),
    ],
)
def test_backend_ollama_model_matches_the_pulled_model(filename, operator_env, expected):
    """The api's OLLAMA_LLM_MODEL must resolve to what the ollama container pulls."""
    api, ollama = _ollama_env(filename)
    assert "OLLAMA_LLM_MODEL" in api, f"{filename}: api lacks OLLAMA_LLM_MODEL"
    assert _interpolate(api["OLLAMA_LLM_MODEL"], operator_env) == expected
    assert _interpolate(ollama["LLM_MODEL"], operator_env) == expected
    # Backend LLM_MODEL stays unset unless the operator set it (BITB-311).
    assert _interpolate(api["LLM_MODEL"], operator_env) == ""


def test_main_stack_keeps_legacy_llm_model_override():
    """docker-compose.yml: an operator-set LLM_MODEL still drives both api and pull."""
    api, ollama = _ollama_env("docker-compose.yml")
    env = {"LLM_MODEL": "qwen"}
    assert _interpolate(api["LLM_MODEL"], env) == "qwen"
    assert _interpolate(api["OLLAMA_LLM_MODEL"], env) == "qwen"
    assert _interpolate(ollama["LLM_MODEL"], env) == "qwen"
