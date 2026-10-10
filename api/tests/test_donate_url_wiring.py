"""
Static wiring guards for NEXT_PUBLIC_DONATE_URL (BITB-157).

Next.js inlines NEXT_PUBLIC_* at build time, so the variable only reaches a
built frontend if every layer forwards it: Dockerfile ARG/ENV, compose
(runtime env for the dev-server stack, build args for stacks that build the
production stage), and the azure-deploy.yml build-args. These tests parse the
files with PyYAML / text only -- no Docker daemon needed.
"""

import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCKERFILE = _REPO_ROOT / "frontend" / "Dockerfile"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "azure-deploy.yml"
_MANIFEST = _REPO_ROOT / "scripts" / "env-manifest.yaml"
_VAR = "NEXT_PUBLIC_DONATE_URL"


def _load(name: str) -> dict:
    return yaml.safe_load((_REPO_ROOT / name).read_text())


def _frontend_build_step_args() -> str:
    workflow = yaml.safe_load(_WORKFLOW.read_text())
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            with_ = step.get("with") or {}
            if with_.get("file") == "./frontend/Dockerfile" and "build-args" in with_:
                return with_["build-args"]
    raise AssertionError("frontend build-push step not found in azure-deploy.yml")


def test_dockerfile_declares_arg_and_env_before_build():
    text = _DOCKERFILE.read_text()
    arg = text.index(f"ARG {_VAR}=")
    env = text.index(f"ENV {_VAR}=${{{_VAR}}}")
    build = text.index("RUN npm run build")
    assert arg < env < build


def test_compose_frontend_environment_forwards_var():
    env = _load("docker-compose.yml")["services"]["frontend"]["environment"]
    keys = {e.partition("=")[0] for e in env}
    assert _VAR in keys


def test_dev_compose_frontend_passes_build_arg():
    build = _load("docker-compose.dev.yml")["services"]["frontend"]["build"]
    assert _VAR in build["args"]


def test_prod_compose_frontend_passes_build_arg():
    build = _load("docker-compose.prod.yml")["services"]["frontend"]["build"]
    assert _VAR in build["args"]


def test_azure_deploy_frontend_build_args_include_var():
    lines = [ln.strip() for ln in _frontend_build_step_args().splitlines()]
    assert f"{_VAR}=${{{{ vars.{_VAR} }}}}" in lines


def test_every_dockerfile_public_arg_is_in_azure_build_args():
    """Any NEXT_PUBLIC_* ARG the image declares must be baked by CI too."""
    declared = set(re.findall(r"^ARG (NEXT_PUBLIC_\w+)", _DOCKERFILE.read_text(), re.M))
    assert _VAR in declared
    passed = {ln.strip().partition("=")[0] for ln in _frontend_build_step_args().splitlines()}
    assert declared <= passed, f"missing from azure-deploy build-args: {declared - passed}"


def test_env_manifest_requires_var_locally_only():
    manifest = yaml.safe_load(_MANIFEST.read_text())
    assert manifest["variables"][_VAR]["required_in"] == "local"
