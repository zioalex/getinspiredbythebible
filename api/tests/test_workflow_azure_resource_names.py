"""Guards the Azure resource names hardcoded in deploy workflows.

#1183 renamed BACKEND_APP_NAME / ACR_NAME / RESOURCE_GROUP / ... in the workflows to a
`voxquieta-*` scheme, but Terraform still names the real resources from `project_name`
and `resource_suffix` in `deployment/terraform.tfvars`. Every deploy (PR previews and
main) then failed at `az acr login` against a registry that doesn't exist. These tests
derive the expected names the same way `deployment/main.tf` does and assert the
workflows use them, so a rename has to go through Terraform first.
"""

import re
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TFVARS = _REPO_ROOT / "deployment" / "terraform.tfvars"
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"


def _tfvar(name: str) -> str:
    match = re.search(rf'^\s*{name}\s*=\s*"([^"]+)"', _TFVARS.read_text(), re.MULTILINE)
    assert match, f"{name} not set in {_TFVARS}"
    return match.group(1)


def _expected() -> dict[str, str]:
    prefix = _tfvar("project_name")
    suffix = _tfvar("resource_suffix")
    # Mirrors deployment/main.tf resource names.
    return {
        "BACKEND_APP_NAME": f"{prefix}-backend",
        "FRONTEND_APP_NAME": f"{prefix}-frontend",
        "RESOURCE_GROUP": f"{prefix}-rg",
        "CONTAINER_APP_ENV_NAME": f"{prefix}-env",
        "ACR_NAME": f"{prefix.replace('-', '')}acr{suffix}",
    }


def _workflow_env(filename: str) -> dict:
    return yaml.safe_load((_WORKFLOWS / filename).read_text()).get("env", {})


@pytest.mark.parametrize("filename", ["azure-deploy.yml", "prod-deploy-drift.yml"])
def test_workflow_resource_names_match_terraform(filename: str) -> None:
    env = _workflow_env(filename)
    expected = _expected()
    checked = [key for key in expected if key in env]
    assert checked, f"{filename} sets none of the Azure resource names"
    for key in checked:
        assert (
            env[key] == expected[key]
        ), f"{filename} {key}={env[key]!r} but Terraform creates {expected[key]!r}"


def test_main_tf_still_derives_names_from_project_name() -> None:
    main_tf = (_REPO_ROOT / "deployment" / "main.tf").read_text()
    for pattern in (
        '"${local.name_prefix}-backend"',
        '"${local.name_prefix}-frontend"',
        '"${local.name_prefix}-env"',
        '"${local.name_prefix}-rg"',
        '"${replace(local.name_prefix, "-", "")}acr${local.resource_suffix}"',
    ):
        assert pattern in main_tf, f"main.tf naming changed ({pattern}); update this test"
