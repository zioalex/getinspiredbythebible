"""Pin the CHAT_FOLLOW_UPS_ENABLED flag plumbing (BITB-178)."""

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
