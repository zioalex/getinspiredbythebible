"""Guard: every state-locking ``terraform`` command in CI carries ``-lock-timeout``.

BITB-330: a PR ``tf-plan`` failed instantly with "Error acquiring the state
lock" whenever another run (typically main's ``apply``) held the Azure Blob
state lease. Terraform's default ``-lock-timeout`` is 0s, so a harmless
concurrent run turned into a red check. The fix is ``-lock-timeout=10m`` on
``plan``/``apply``/``destroy``; this test stops a newly added command from
silently regressing it.

The scan reconstructs each *logical* shell command (lines joined by a trailing
``\\``), skips ``#`` comment lines (prose such as "terraform apply" in
``prod-deploy-drift.yml`` must not match) and does not look at
``terraform init``, which only locks when migrating state.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
WORKFLOWS = sorted(p for ext in ("*.yml", "*.yaml") for p in _WORKFLOW_DIR.glob(ext))

_INVOCATION = re.compile(r"\bterraform\s+(plan|apply|destroy)\b")
_LOCK_TIMEOUT = re.compile(r"-lock-timeout=(\S+)")
_DURATION = re.compile(r"^\d+[smh]$")


def _logical_commands(path: Path) -> list[tuple[int, str]]:
    """Return (1-based line, joined command) for each terraform plan/apply/destroy."""
    lines = path.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#") or not _INVOCATION.search(line):
            continue
        parts = [line.rstrip()]
        j = i
        while parts[-1].endswith("\\") and j + 1 < len(lines):
            j += 1
            parts.append(lines[j].rstrip())
        found.append((i + 1, " ".join(p.rstrip("\\").strip() for p in parts)))
    return found


def test_workflows_exist_and_have_terraform_commands():
    assert WORKFLOWS, "no workflow files found"
    total = sum(len(_logical_commands(w)) for w in WORKFLOWS)
    assert total >= 3, "expected the plan/apply/destroy commands in azure-deploy.yml"


def test_every_terraform_plan_apply_destroy_has_lock_timeout():
    problems = []
    for wf in WORKFLOWS:
        for lineno, cmd in _logical_commands(wf):
            m = _LOCK_TIMEOUT.search(cmd)
            if not m:
                problems.append(f"{wf.name}:{lineno} missing -lock-timeout=<N>m: {cmd}")
            elif not _DURATION.match(m.group(1)):
                problems.append(f"{wf.name}:{lineno} malformed -lock-timeout={m.group(1)}: {cmd}")
    assert not problems, (
        "BITB-330: terraform plan/apply/destroy must pass -lock-timeout=10m (default 0s fails "
        "instantly on a held state lock):\n" + "\n".join(problems)
    )
