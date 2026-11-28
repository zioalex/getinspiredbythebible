"""Guards the BITB-294 prod wiring of Azure AI Content Safety (the `azure` failover hop).

Shipped switched OFF (enable_azure_content_safety = false). The key follows the BITB-288
out-of-band pattern, but its real value comes from the Terraform-created account (a
sensitive output), not a GitHub secret.
"""

import re
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _ROOT / ".github" / "workflows" / "azure-deploy.yml"
_MAIN_TF = _ROOT / "deployment" / "main.tf"
_VARS_TF = _ROOT / "deployment" / "variables.tf"
_OUT_TF = _ROOT / "deployment" / "outputs.tf"

_PLACEHOLDER = "set-out-of-band-see-azure-deploy-yml"
_SECRET = "azure-content-safety-key"  # pragma: allowlist secret


def _block(text: str, header: str) -> str:
    start = text.index(header)
    open_idx = text.index("{", start)
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise AssertionError(f"unbalanced block for {header}")


def _steps():
    wf = yaml.safe_load(_WORKFLOW.read_text())
    for job in wf["jobs"].values():
        yield job, job.get("steps", [])


def _step(prefix: str) -> dict:
    found = [s for _, steps in _steps() for s in steps if s.get("name", "").startswith(prefix)]
    assert len(found) == 1, prefix
    return found[0]


def test_variable_defaults():
    v = _VARS_TF.read_text()
    assert re.search(
        r"enable_azure_content_safety\"\s*\{[^}]*default\s*=\s*false", v, re.DOTALL
    ), "must ship off"
    sku = _block(v, 'variable "azure_content_safety_sku"')
    assert re.search(r'default\s*=\s*"F0"', sku)
    assert '["F0", "S0"]' in sku
    chain = _block(v, 'variable "content_safety_ml_failover_chain"')
    assert re.search(r'default\s*=\s*""', chain)
    assert "openai_moderation" in chain and "azure" in chain
    timeout = _block(v, 'variable "azure_content_safety_timeout"')
    assert re.search(r"default\s*=\s*3\b", timeout)
    assert "> 0" in timeout
    loc = _block(v, 'variable "azure_content_safety_location"')
    assert re.search(r'default\s*=\s*""', loc)


def test_resource_count_gated_and_kind():
    tf = _MAIN_TF.read_text()
    res = _block(tf, 'resource "azurerm_cognitive_account" "content_safety"')
    assert re.search(r"count\s*=\s*var\.enable_azure_content_safety \? 1 : 0", res)
    assert re.search(r'kind\s*=\s*"ContentSafety"', res)
    assert "var.azure_content_safety_sku" in res
    assert "coalesce(var.azure_content_safety_location, var.location)" in res
    assert "custom_subdomain_name" in res


def test_env_vars_gated_and_key_is_secret_ref():
    tf = _MAIN_TF.read_text()
    m = re.search(r"var\.enable_azure_content_safety \? \{(.*?)\} : \{\},", tf, re.DOTALL)
    assert m, "azure env block must be gated on the flag"
    body = m.group(1)
    for name in (
        "AZURE_CONTENT_SAFETY_ENABLED",
        "AZURE_CONTENT_SAFETY_ENDPOINT",
        "AZURE_CONTENT_SAFETY_TIMEOUT",
    ):
        assert name in body
    assert re.search(r'"AZURE_CONTENT_SAFETY_KEY"\s*=\s*\{\s*secret_name\s*=\s*"' + _SECRET, body)
    assert "primary_access_key" not in body


def test_failover_chain_env_always_set_from_local():
    tf = _MAIN_TF.read_text()
    assert re.search(
        r'"CONTENT_SAFETY_ML_FAILOVER_CHAIN"\s*=\s*\{\s*value\s*=\s*'
        r"local\.content_safety_ml_failover_chain",
        tf,
    )
    local = re.search(r"content_safety_ml_failover_chain = \((.*?)\n  \)", tf, re.DOTALL)
    assert local
    assert '"openai_moderation,azure"' in local.group(1)
    assert "var.enable_azure_content_safety ?" in local.group(1)


def test_secret_block_placeholder():
    tf = _MAIN_TF.read_text()
    m = re.search(
        r'dynamic "secret" \{\s*for_each\s*=\s*var\.enable_azure_content_safety \? \[1\] : \[\]'
        r'\s*content \{\s*name\s*=\s*"' + _SECRET + r'"\s*value\s*=\s*"([^"]+)"',
        tf,
    )
    assert m
    assert m.group(1) == _PLACEHOLDER


def test_not_in_backend_secret_trigger():
    tf = _MAIN_TF.read_text()
    trigger = _block(tf, 'resource "terraform_data" "backend_secret_trigger"')
    code = "\n".join(ln for ln in trigger.splitlines() if not ln.strip().startswith("#"))
    assert "content_safety" not in code
    assert "var.openrouter_api_key" in code


def test_outputs_exist_key_sensitive():
    out = _OUT_TF.read_text()
    assert 'output "azure_content_safety_endpoint"' in out
    key = _block(out, 'output "azure_content_safety_key"')
    assert re.search(r"sensitive\s*=\s*true", key)
    assert '""' in key  # empty when disabled


def test_pre_seed_precedes_apply_checks_plan_and_never_overwrites():
    for job, steps in _steps():
        names = [s.get("name", "") for s in steps]
        if "Terraform Apply" not in names:
            continue
        idx = [i for i, n in enumerate(names) if n.startswith("Pre-seed azure-content-safety-key")]
        assert idx and idx[0] < names.index("Terraform Apply")
        step = steps[idx[0]]
        script = step["run"]
        assert step.get("working-directory") == "deployment"
        assert "terraform show -json tfplan" in script
        assert "azurerm_cognitive_account.content_safety[0]" in script
        assert "az containerapp secret list" in script
        listing = script.index("az containerapp secret list")
        assert script.index("grep -qx 'azure-content-safety-key'") > listing
        assert listing < script.index("az containerapp secret set")
        assert script.count("az containerapp secret set") == 1
        assert _PLACEHOLDER in script
        assert "2>/dev/null" not in script
        nf = script.index("ResourceNotFound")
        assert "exit 0" in script[nf : nf + 200]
        assert "for i in 1 2 3 4" in script
        return
    raise AssertionError("no job with Terraform Apply found")


def test_populate_step_sets_key_masked_and_never_echoed():
    step = _step("Populate out-of-band secrets")
    script = step["run"]
    assert step.get("working-directory") == "deployment"
    assert "terraform output -raw azure_content_safety_endpoint" in script
    assert "terraform output -raw azure_content_safety_key" in script
    assert 'pairs+=("azure-content-safety-key=$CS_KEY")' in script
    assert script.index("::add-mask::$CS_KEY") < script.index('pairs+=("azure-content-safety-key')
    for line in script.splitlines():
        if re.match(r"\s*(echo|printf)\b", line) and "add-mask" not in line:
            assert "CS_KEY" not in line, line
    assert script.count("az containerapp revision restart") == 1


@pytest.mark.parametrize("chain", ["openai_moderation", "openai_moderation,azure"])
def test_terraform_chain_values_parse_in_app(chain):
    from config import parse_ml_failover_chain

    assert parse_ml_failover_chain(chain) == chain.split(",")
