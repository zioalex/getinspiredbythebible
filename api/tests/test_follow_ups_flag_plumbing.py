"""Pin the CHAT_FOLLOW_UPS_ENABLED flag plumbing (BITB-182) and the BITB-080
web-only production rollout: backend flag via Terraform env, web flag baked
into the frontend image at build time (NEXT_PUBLIC_FOLLOW_UPS_ENABLED)."""

import re
from pathlib import Path

import pytest
import yaml

from config import Settings

REPO = Path(__file__).resolve().parents[2]
EXPECTED_ENTRY = "CHAT_FOLLOW_UPS_ENABLED=${CHAT_FOLLOW_UPS_ENABLED:-false}"
COMPOSE_FILES = [
    "docker-compose.yml",
    "docker-compose.dev.yml",
    "docker-compose.local-prod.yml",
    "docker-compose.local-prod-acr-be.yml",
]


@pytest.mark.parametrize("name", COMPOSE_FILES)
def test_compose_api_service_passes_flag(name):
    compose = yaml.safe_load((REPO / name).read_text())
    assert EXPECTED_ENTRY in compose["services"]["api"]["environment"]


def test_prod_override_has_no_env_list_to_extend():
    compose = yaml.safe_load((REPO / "docker-compose.prod.yml").read_text())
    assert "environment" not in compose["services"]["api"]


def test_terraform_variable_defaults_false():
    text = (REPO / "deployment" / "variables.tf").read_text()
    block = re.search(r'variable "chat_follow_ups_enabled" \{(.*?)\n\}', text, re.DOTALL)
    assert block, "variable chat_follow_ups_enabled missing"
    assert re.search(r"type\s*=\s*bool", block.group(1))
    assert re.search(r"default\s*=\s*false", block.group(1))


def test_terraform_maps_flag_into_backend_env():
    text = (REPO / "deployment" / "main.tf").read_text()
    assert re.search(
        r'"CHAT_FOLLOW_UPS_ENABLED"\s*=\s*\{\s*value\s*=\s*tostring\(var\.chat_follow_ups_enabled\)',
        text,
    )


def test_env_manifest_declares_flag():
    manifest = yaml.safe_load((REPO / "scripts" / "env-manifest.yaml").read_text())
    entry = manifest["variables"]["CHAT_FOLLOW_UPS_ENABLED"]
    assert entry["required_in"] == "both" and entry["default"] == "false"


def test_settings_reads_env_true(monkeypatch):
    monkeypatch.setenv("CHAT_FOLLOW_UPS_ENABLED", "true")
    assert Settings().chat_follow_ups_enabled is True


def test_settings_defaults_false(monkeypatch):
    monkeypatch.delenv("CHAT_FOLLOW_UPS_ENABLED", raising=False)
    assert Settings(_env_file=None).chat_follow_ups_enabled is False


# ---------------------------------------------------------------------------
# Web rollout plumbing (BITB-080 enablement): the web client reads
# NEXT_PUBLIC_FOLLOW_UPS_ENABLED, which Next.js inlines at BUILD time, so the
# flag must reach the frontend image as a docker build-arg — not runtime env.
# ---------------------------------------------------------------------------


def test_terraform_web_variable_defaults_false():
    text = (REPO / "deployment" / "variables.tf").read_text()
    block = re.search(r'variable "web_follow_ups_enabled" \{(.*?)\n\}', text, re.DOTALL)
    assert block, "variable web_follow_ups_enabled missing"
    assert re.search(r"type\s*=\s*bool", block.group(1))
    assert re.search(r"default\s*=\s*false", block.group(1))


def test_prod_tfvars_enables_both_follow_ups_flags():
    # Pins the production rollout state (BITB-187 FR5): only the live tfvars
    # turns the flags on — code defaults stay false. Rolling back means
    # flipping these lines (and redeploying), which this test forces to be
    # a conscious change.
    text = (REPO / "deployment" / "terraform.tfvars").read_text()
    for flag in ("chat_follow_ups_enabled", "web_follow_ups_enabled"):
        assert re.search(
            rf"^\s*{flag}\s*=\s*true\s*$", text, re.MULTILINE
        ), f"{flag} must be set to true in the production tfvars"


def test_workflow_bakes_web_flag_into_frontend_build():
    # azure-deploy.yml must read the flag from terraform.tfvars (single source
    # of truth, same file Terraform applies) and pass it as a docker build-arg
    # so `next build` inlines it into the client bundle.
    text = (REPO / ".github" / "workflows" / "azure-deploy.yml").read_text()
    assert (
        "web_follow_ups_enabled[[:space:]]*=" in text
    ), "workflow must grep web_follow_ups_enabled from deployment/terraform.tfvars"
    assert re.search(
        r"NEXT_PUBLIC_FOLLOW_UPS_ENABLED=\$\{\{ steps\.follow-ups-flag\.outputs\.web_enabled \}\}",
        text,
    ), "NEXT_PUBLIC_FOLLOW_UPS_ENABLED build-arg must come from the tfvars grep step"


def test_frontend_dockerfile_declares_build_arg():
    # Without an ARG declaration, docker build-args never reach the build
    # stage and the flag would silently stay unset inside `next build`.
    text = (REPO / "frontend" / "Dockerfile").read_text()
    assert re.search(r"^ARG NEXT_PUBLIC_FOLLOW_UPS_ENABLED=", text, re.MULTILINE)
    assert re.search(r"^ENV NEXT_PUBLIC_FOLLOW_UPS_ENABLED=", text, re.MULTILINE)
