"""Pin the BLOCKED_SAMPLE_CAPTURE_ENABLED plumbing (BITB-326).

The capture code (api/feedback/blocked_samples.py) shipped off by default and was never
wired into Terraform, so production stored nothing and `make export-blocked-samples`
always returned an empty result. Production now turns it on via terraform.tfvars; the
code default and the Terraform variable default stay off (local stacks never record).
"""

import re
from pathlib import Path

import yaml

from config import Settings

REPO = Path(__file__).resolve().parents[2]


def test_terraform_variable_is_bool_default_false():
    text = (REPO / "deployment" / "variables.tf").read_text()
    block = re.search(r'variable "blocked_sample_capture_enabled" \{(.*?)\n\}', text, re.DOTALL)
    assert block, "variable blocked_sample_capture_enabled missing"
    assert re.search(r"type\s*=\s*bool", block.group(1))
    assert re.search(r"default\s*=\s*false", block.group(1))


def test_terraform_maps_flag_into_backend_env():
    text = (REPO / "deployment" / "main.tf").read_text()
    assert re.search(
        r'"BLOCKED_SAMPLE_CAPTURE_ENABLED"\s*=\s*\{\s*value\s*=\s*'
        r"tostring\(var\.blocked_sample_capture_enabled\)",
        text,
    )


def test_production_tfvars_enables_capture():
    text = (REPO / "deployment" / "terraform.tfvars").read_text()
    assert re.search(r"(?m)^\s*blocked_sample_capture_enabled\s*=\s*true\s*$", text)


def test_example_tfvars_documents_flag_off():
    text = (REPO / "deployment" / "terraform.tfvars.example").read_text()
    assert re.search(r"(?m)^\s*blocked_sample_capture_enabled\s*=\s*false\s*$", text)


def test_env_manifest_declares_flag_as_remote_only():
    manifest = yaml.safe_load((REPO / "scripts" / "env-manifest.yaml").read_text())
    entry = manifest["variables"]["BLOCKED_SAMPLE_CAPTURE_ENABLED"]
    assert entry["required_in"] == "remote" and entry["default"] == "false"


def test_code_default_is_off_and_env_turns_it_on(monkeypatch):
    monkeypatch.delenv("BLOCKED_SAMPLE_CAPTURE_ENABLED", raising=False)
    assert Settings().blocked_sample_capture_enabled is False
    monkeypatch.setenv("BLOCKED_SAMPLE_CAPTURE_ENABLED", "true")
    assert Settings().blocked_sample_capture_enabled is True
