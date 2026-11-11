"""Guards the BITB-288 prod wiring of OPENAI_API_KEY into the backend Container App.

Content safety's OpenAI Moderation failover (BITB-272) is a no-op in production unless
the backend receives OPENAI_API_KEY. The key follows the BITB-067 gap #6 out-of-band
pattern (like MONITOR_PROBE_SECRET): Terraform only declares a placeholder ACA secret and
the env secretRef, the real value is set by `az containerapp secret set`, and it is kept
OUT of backend_secret_trigger so rotation never replaces the app.
"""

import re
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW = _ROOT / ".github" / "workflows" / "azure-deploy.yml"
_MAIN_TF = _ROOT / "deployment" / "main.tf"
_VARS_TF = _ROOT / "deployment" / "variables.tf"

_PLACEHOLDER = "set-out-of-band-see-azure-deploy-yml"


def _block(text: str, header: str) -> str:
    """Return the brace-balanced block that starts at `header`."""
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


def _populate_step() -> dict:
    wf = yaml.safe_load(_WORKFLOW.read_text())
    steps = [
        s
        for job in wf["jobs"].values()
        for s in job.get("steps", [])
        if s.get("name", "").startswith("Populate out-of-band secrets")
    ]
    assert len(steps) == 1
    return steps[0]


def test_variable_declared_sensitive_with_empty_default():
    block = _block(_VARS_TF.read_text(), 'variable "openai_api_key"')
    assert re.search(r'default\s*=\s*""', block)
    assert re.search(r"sensitive\s*=\s*true", block)
    assert re.search(r"type\s*=\s*string", block)


def test_backend_env_var_gated_and_secret_ref():
    tf = _MAIN_TF.read_text()
    m = re.search(
        r'var\.openai_api_key\s*!=\s*""\s*\?\s*\{\s*"OPENAI_API_KEY"\s*=\s*\{\s*'
        r'secret_name\s*=\s*"openai-api-key"',
        tf,
    )
    assert m, "OPENAI_API_KEY env must be gated and use secret_name openai-api-key"
    # Must not be a plaintext value= env
    assert '"OPENAI_API_KEY" = {\n        value' not in tf


def test_secret_block_uses_placeholder_not_variable():
    tf = _MAIN_TF.read_text()
    m = re.search(
        r'dynamic "secret" \{\s*for_each\s*=\s*var\.openai_api_key != "" \? \[1\] : \[\]'
        r'\s*content \{\s*name\s*=\s*"openai-api-key"\s*value\s*=\s*"([^"]+)"',
        tf,
    )
    assert m, "openai-api-key dynamic secret block missing"
    assert m.group(1) == _PLACEHOLDER


def test_not_in_backend_secret_trigger():
    tf = _MAIN_TF.read_text()
    trigger = _block(tf, 'resource "terraform_data" "backend_secret_trigger"')
    code = "\n".join(line for line in trigger.splitlines() if not line.strip().startswith("#"))
    assert "openai_api_key" not in code
    assert "var.openrouter_api_key" in code  # sanity: we parsed the right block


def test_every_job_setting_monitor_probe_also_sets_openai_key():
    wf = yaml.safe_load(_WORKFLOW.read_text())
    checked = []
    for name, job in wf["jobs"].items():
        env = job.get("env") or {}
        if "TF_VAR_monitor_probe_secret" in env:
            checked.append(name)
            assert env.get("TF_VAR_openai_api_key") == "${{ secrets.OPENAI_API_KEY }}", name
    assert checked, "expected jobs that set TF_VAR_monitor_probe_secret"


def test_populate_step_sets_secret_from_env_without_echoing_value():
    step = _populate_step()
    assert step["env"]["OPENAI_API_KEY"] == "${{ secrets.OPENAI_API_KEY }}"
    script = step["run"]
    assert 'pairs+=("openai-api-key=$OPENAI_API_KEY")' in script
    assert '[ -n "${OPENAI_API_KEY:-}" ]' in script
    for line in script.splitlines():
        if re.match(r"\s*(echo|printf)\b", line):
            assert "OPENAI_API_KEY" not in line, line
            assert "${pairs[@]}" not in line, line
    # only names are printed
    assert "${pairs[*]%%=*}" in script


def test_pre_seed_step_runs_before_terraform_apply():
    wf = yaml.safe_load(_WORKFLOW.read_text())
    for job in wf["jobs"].values():
        names = [s.get("name", "") for s in job.get("steps", [])]
        if "Terraform Apply" in names:
            seed = [i for i, n in enumerate(names) if n.startswith("Pre-seed openai-api-key")]
            assert seed and seed[0] < names.index("Terraform Apply")
            step = job["steps"][seed[0]]
            assert step["env"]["OPENAI_API_KEY"] == "${{ secrets.OPENAI_API_KEY }}"
            assert "echo" not in "".join(
                ln for ln in step["run"].splitlines() if "$OPENAI_API_KEY" in ln and "echo" in ln
            )
            return
    raise AssertionError("no job with Terraform Apply found")


def _pre_seed_script() -> str:
    wf = yaml.safe_load(_WORKFLOW.read_text())
    for job in wf["jobs"].values():
        for step in job.get("steps", []):
            if step.get("name", "").startswith("Pre-seed openai-api-key"):
                return step["run"]
    raise AssertionError("pre-seed step not found")


def test_pre_seed_skips_only_on_not_found_and_fails_otherwise():
    """A failed `az containerapp show` for auth/throttling must not silently skip the seed.

    Otherwise Terraform apply adds an OPENAI_API_KEY secretRef with no matching secret.
    """
    script = _pre_seed_script()
    assert "2>/dev/null" not in script
    assert "ResourceNotFound" in script
    # The not-found branch exits 0; any other show failure exits 1.
    not_found = script.index("ResourceNotFound")
    assert "exit 0" in script[not_found : not_found + 200]
    assert "exit 1" in script[not_found:]


def test_pre_seed_retries_secret_set():
    script = _pre_seed_script()
    assert "for i in 1 2 3 4" in script
    assert script.count("az containerapp secret set") == 1
