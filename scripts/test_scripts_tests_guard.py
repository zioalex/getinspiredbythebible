"""Guard for the `make test-scripts` catch-all (BITB-274). Standard library + pytest only.

Keeps SCRIPTS_TEST_EXCLUDE from growing silently: every excluded file must exist and carry a
documented reason in docs/CONTRIBUTING.md, and every other scripts/test_*.py must be selected.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAKEFILE = (ROOT / "Makefile").read_text(encoding="utf-8")
DOC = (ROOT / "docs" / "CONTRIBUTING.md").read_text(encoding="utf-8")


def _excluded() -> list[str]:
    m = re.search(r"^SCRIPTS_TEST_EXCLUDE\s*:=\s*(.+)$", MAKEFILE, re.M)
    assert m, "SCRIPTS_TEST_EXCLUDE is not defined in the Makefile"
    return m.group(1).split()


def test_excluded_files_exist_and_are_documented():
    excluded = _excluded()
    assert excluded, "an empty exclusion list should be removed from the Makefile, not kept"
    for path in excluded:
        assert (ROOT / path).is_file(), f"{path} is excluded but does not exist"
        assert f"`{path}`" in DOC, f"{path} is excluded without a reason in docs/CONTRIBUTING.md"


def test_make_target_selects_every_other_test_file():
    out = subprocess.run(
        ["make", "-n", "test-scripts"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    excluded = set(_excluded())
    for f in sorted((ROOT / "scripts").glob("test_*.py")):
        rel = f"scripts/{f.name}"
        if rel in excluded:
            assert rel not in out
        else:
            assert rel in out, f"{rel} is not run by `make test-scripts`"
    assert "-m pytest" in out


def test_workflow_triggers_cover_scripts_and_makefile():
    wf = (ROOT / ".github" / "workflows" / "scripts-tests.yml").read_text(encoding="utf-8")
    assert wf.count('"scripts/**"') == 2 and wf.count('"Makefile"') == 2
    assert "make test-scripts" in wf
