"""BITB-319: the shared conftest must load without the app's dependencies.

The post-deploy smoke job (``azure-deploy.yml`` -> ``functional-tests``) installs only
httpx/pytest/pytest-asyncio/pydantic/pydantic-settings and runs ``tests/e2e`` and
``tests/functional`` against live URLs. An autouse fixture that imports the FastAPI app
broke every smoke test at setup with ``ModuleNotFoundError: No module named 'fastapi'``
(run 43655682966). This test re-creates that environment by blocking ``fastapi`` in a
subprocess and running a probe test through the real conftest.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parent.parent

_BLOCK_FASTAPI = """
import sys, importlib.abc

class _Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == "fastapi" or name.startswith("fastapi."):
            raise ModuleNotFoundError(f"No module named '{name}'", name=name)
        return None

sys.meta_path.insert(0, _Block())
for mod in [m for m in sys.modules if m == "fastapi" or m.startswith("fastapi.")]:
    del sys.modules[mod]

import pytest
sys.exit(pytest.main(sys.argv[1:]))
"""


@pytest.mark.skipif(os.environ.get("BITB319_PROBE") != "1", reason="only run inside the probe")
def test_probe_runs_with_conftest_fixtures():
    """Runs only inside the subprocess: passing proves the autouse fixtures did not error."""
    with pytest.raises(ModuleNotFoundError):
        import fastapi  # noqa: F401


def test_conftest_loads_without_fastapi():
    env = {**os.environ, "BITB319_PROBE": "1"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _BLOCK_FASTAPI,
            f"{Path(__file__).name}::test_probe_runs_with_conftest_fixtures",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        check=False,
        cwd=API_DIR / "tests",
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "1 passed" in output, output
