"""Guards the Playwright-install budget that cancelled `Frontend E2E` (BITB-341).

On 2026-11-17 three consecutive `Frontend E2E` runs (PRs #1312, #1306, #1308) were cancelled at
the 15-minute job timeout: `npx playwright install --with-deps <browser>` had no headroom and no
retry, and a crawling Ubuntu mirror consumed the whole budget in one attempt -- the webkit leg was
killed at `Get:96` of ~100 packages, i.e. almost done. The same unretried step sat on a 10-minute
budget in `prod-browser-smoke.yml`, where a timeout pages the owner via Telegram about a perfectly
healthy production.

The fix splits the install in two halves that fail for different reasons, and these tests pin that
split:

* the **apt half** (`playwright install-deps`) gets one generous attempt bounded by the step's
  `timeout-minutes`, and must NOT be retry-wrapped -- `timeout` TERMs `npx` and orphans the
  `sudo apt-get` beneath it, which keeps `/var/lib/dpkg/lock-frontend`, so a second attempt dies
  instantly on "Could not get lock" and a merely-slow mirror becomes a hard failure. apt already
  retries its own downloads (`Acquire::Retries`).
* the **binary half** (`playwright install`) is a plain CDN fetch holding no system locks, so it
  is retried with a bounded per-attempt `timeout`.

Attempt counts and minute values are *derived* from the scripts, so tuning them needs no test
edit; what is asserted is the shape and the arithmetic. Deliberately narrow -- a regression guard
for one failure mode, not a schema validation of the workflows. No DB, network or secrets needed.
"""

import re
from pathlib import Path

import pytest
import yaml

_WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
_E2E = "frontend-e2e.yml"
_SMOKE = "prod-browser-smoke.yml"
_WORKFLOW_NAMES = [_E2E, _SMOKE]

# The job must leave room for a slow mirror: the 2026-11-17 event needed ~13m for apt alone.
_MIN_JOB_TIMEOUT = {_E2E: 25, _SMOKE: 20}
# ... and the apt step's own bound must cover it.
_MIN_DEPS_TIMEOUT = 10

_DEPS_RE = re.compile(r"playwright install-deps\b")
_BROWSER_RE = re.compile(r"playwright install (?!-)")
_TEST_RE = re.compile(r"playwright test\b")
_ATTEMPTS_RE = re.compile(r"seq 1 (\d+)")
_PER_ATTEMPT_RE = re.compile(r"\btimeout (\d+)m\b")


def _job(name: str) -> dict:
    """The single job of a workflow (`on` loads as a string key here: it is quoted in the YAML)."""
    workflow = yaml.safe_load((_WORKFLOWS / name).read_text())
    jobs = workflow["jobs"]
    assert len(jobs) == 1, f"{name}: expected exactly one job, got {list(jobs)}"
    return next(iter(jobs.values()))


def _only_step(job: dict, pattern: re.Pattern, what: str, name: str) -> dict:
    steps = [s for s in job["steps"] if pattern.search(s.get("run", "") or "")]
    assert len(steps) == 1, f"{name}: expected exactly one {what} step, got {len(steps)}"
    return steps[0]


def _deps_step(job: dict, name: str) -> dict:
    return _only_step(job, _DEPS_RE, "`playwright install-deps`", name)


def _browser_step(job: dict, name: str) -> dict:
    return _only_step(job, _BROWSER_RE, "`playwright install <browser>`", name)


def _test_step(job: dict, name: str) -> dict:
    return _only_step(job, _TEST_RE, "`playwright test`", name)


def _retry_budget(step: dict, name: str) -> tuple[int, int]:
    """(attempts, per-attempt minutes) parsed out of a retry-wrapped step's script."""
    script = step["run"]
    attempts = _ATTEMPTS_RE.search(script)
    per_attempt = _PER_ATTEMPT_RE.search(script)
    assert attempts, f"{name}: {step['name']!r} has no retry loop (`seq 1 N`)"
    assert per_attempt, f"{name}: {step['name']!r} has no per-attempt `timeout <N>m` guard"
    return int(attempts.group(1)), int(per_attempt.group(1))


@pytest.mark.parametrize("name", _WORKFLOW_NAMES)
def test_install_is_split_into_apt_and_binary_halves(name):
    """One opaque `install --with-deps` hid which half was slow; keep them separate steps."""
    job = _job(name)
    deps, browser = _deps_step(job, name), _browser_step(job, name)
    assert deps is not browser, f"{name}: deps and browser install are the same step"
    assert (
        "--with-deps" not in deps["run"] + browser["run"]
    ), f"{name}: `--with-deps` is back, re-merging the apt and binary halves"


@pytest.mark.parametrize("name", _WORKFLOW_NAMES)
def test_browser_install_retries_with_bounded_timeout(name):
    attempts, minutes = _retry_budget(_browser_step(_job(name), name), name)
    assert attempts > 1, f"{name}: the browser download does not retry ({attempts} attempt)"
    assert minutes >= 1, f"{name}: per-attempt timeout {minutes}m is not a real bound"


@pytest.mark.parametrize("name", _WORKFLOW_NAMES)
def test_apt_step_is_not_retry_wrapped(name):
    """Retrying apt under `timeout` orphans `apt-get` and deadlocks on the dpkg lock.

    This is the one assertion that encodes *why* the two halves differ. If a future change
    "helpfully" wraps the apt step in the same retry loop as the binary download, a slow mirror
    stops being slow and starts being a hard failure after the second attempt.
    """
    job = _job(name)
    step = _deps_step(job, name)
    script = step["run"]
    assert not _PER_ATTEMPT_RE.search(script), (
        f"{name}: {step['name']!r} wraps apt in `timeout` -- that orphans `sudo apt-get`, which "
        "keeps /var/lib/dpkg/lock-frontend and makes the next attempt fail instantly"
    )
    assert not _ATTEMPTS_RE.search(
        script
    ), f"{name}: {step['name']!r} retries apt; see the docstring -- one bounded attempt only"
    bound = step.get("timeout-minutes")
    assert (
        bound is not None
    ), f"{name}: {step['name']!r} has no timeout-minutes, so apt is unbounded"
    assert bound >= _MIN_DEPS_TIMEOUT, (
        f"{name}: {step['name']!r} timeout-minutes {bound} < {_MIN_DEPS_TIMEOUT}; the 2026-11-17 "
        "slow mirror needed ~13m for apt alone"
    )


@pytest.mark.parametrize("name", _WORKFLOW_NAMES)
def test_worst_case_budget_fits_the_job_timeout(name):
    """A retry storm must not itself be the thing that kills the job."""
    job = _job(name)
    deps_minutes = _deps_step(job, name)["timeout-minutes"]
    attempts, per_attempt = _retry_budget(_browser_step(job, name), name)
    test_minutes = _test_step(job, name)["timeout-minutes"]
    total = deps_minutes + attempts * per_attempt + test_minutes
    budget = job["timeout-minutes"]
    assert total <= budget, (
        f"{name}: worst case deps {deps_minutes}m + browser {attempts}x{per_attempt}m "
        f"+ spec {test_minutes}m = {total}m exceeds the job's timeout-minutes {budget}m"
    )


@pytest.mark.parametrize("name", _WORKFLOW_NAMES)
def test_browser_step_timeout_exceeds_its_retry_budget(name):
    """Otherwise the step timeout, not the retry policy, decides the outcome."""
    job = _job(name)
    step = _browser_step(job, name)
    attempts, per_attempt = _retry_budget(step, name)
    assert step["timeout-minutes"] > attempts * per_attempt, (
        f"{name}: {step['name']!r} timeout-minutes {step.get('timeout-minutes')} must exceed its "
        f"retry budget {attempts}x{per_attempt}m"
    )


@pytest.mark.parametrize("name", _WORKFLOW_NAMES)
def test_browser_binaries_are_cached(name):
    paths = [
        (s.get("with") or {}).get("path", "")
        for s in _job(name)["steps"]
        if str(s.get("uses", "")).startswith("actions/cache@")
    ]
    assert any("~/.cache/ms-playwright" in p for p in paths), (
        f"{name}: no actions/cache step for ~/.cache/ms-playwright, so every leg re-downloads "
        "the browser binaries"
    )


@pytest.mark.parametrize("name", _WORKFLOW_NAMES)
def test_job_timeout_has_headroom(name):
    timeout = _job(name).get("timeout-minutes")
    assert timeout is not None, f"{name}: job has no timeout-minutes"
    assert (
        timeout >= _MIN_JOB_TIMEOUT[name]
    ), f"{name}: job timeout-minutes {timeout} < {_MIN_JOB_TIMEOUT[name]}"


@pytest.mark.parametrize("name", _WORKFLOW_NAMES)
def test_playwright_test_step_has_own_timeout(name):
    """So a hang in the spec is never misattributed to a slow install."""
    job = _job(name)
    assert "timeout-minutes" in _test_step(
        job, name
    ), f"{name}: the `playwright test` step has no timeout-minutes of its own"


def test_e2e_engine_matrix_unchanged():
    """The fix must not have quietly dropped the leg that was failing."""
    matrix = _job(_E2E)["strategy"]["matrix"]["project"]
    assert set(matrix) == {"chromium", "firefox", "webkit", "Mobile Safari"}
    assert len(matrix) == 4
