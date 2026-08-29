"""Guards against BITB-107 (`eval-smoke` cannot pass) regressing.

Parses `search-eval-full.yml` directly, following the style of
`test_search_eval_workflow_credentials.py`. The failure this workflow had for
five straight days was silent/config-shaped (a dimension mismatch, a missing
`--config` guard) rather than something a Python unit test can exercise, so
these assertions parse the actual YAML the runner executes instead of
mocking around it.
"""

import re
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "search-eval-full.yml"


def _workflow_text() -> str:
    return _WORKFLOW_PATH.read_text()


def _load_workflow() -> dict:
    return yaml.safe_load(_workflow_text())


def _step(job: dict, name: str) -> dict:
    for step in job["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"no step named {name!r} in job {job!r}")


def test_smoke_step_sets_embedding_dimensions_1536():
    """The smoke job must set EMBEDDING_DIMENSIONS, and it must be 1536 to
    match the vector(1536) column the job itself seeds (BITB-107 finding 2)."""
    workflow = _load_workflow()
    step = _step(workflow["jobs"]["eval-smoke"], "Run smoke eval")
    assert step["env"].get("EMBEDDING_DIMENSIONS") == "1536", (
        "eval-smoke's 'Run smoke eval' step env is missing EMBEDDING_DIMENSIONS=1536 -- "
        "the embedding provider would default to 1024 (mxbai-embed-large's "
        "dimension) against a 1536-wide column."
    )


def test_eval_prod_step_also_sets_embedding_dimensions_1536():
    """eval-prod needs the same fix — and needs it together with config.py's
    dimension validator now covering azure_openai, or the nightly prod route
    would break at Settings() import time."""
    workflow = _load_workflow()
    step = _step(workflow["jobs"]["eval-prod"], "Run eval against prod (read-only)")
    assert step["env"].get("EMBEDDING_DIMENSIONS") == "1536", (
        "eval-prod's env is missing EMBEDDING_DIMENSIONS=1536 -- required now "
        "that config.py's validate_embedding_dimensions() covers azure_openai."
    )


def test_smoke_dimensions_match_the_seeded_column_width():
    """Ties EMBEDDING_DIMENSIONS to the actual --dimensions flag the 'Load 1
    Corinthians' step uses to create the column, rather than two independently
    hardcoded '1536' literals that could silently drift apart."""
    workflow = _load_workflow()
    smoke_job = workflow["jobs"]["eval-smoke"]

    load_step = _step(smoke_job, "Load 1 Corinthians (CI subset)")
    match = re.search(r"--dimensions\s+(\d+)", load_step["run"])
    assert match, "could not find --dimensions in the 'Load 1 Corinthians' step"
    seeded_dimensions = match.group(1)

    run_step = _step(smoke_job, "Run smoke eval")
    assert run_step["env"].get("EMBEDDING_DIMENSIONS") == seeded_dimensions, (
        f"eval-smoke's EMBEDDING_DIMENSIONS ({run_step['env'].get('EMBEDDING_DIMENSIONS')!r}) "
        f"must match the column width the job seeds ({seeded_dimensions!r})."
    )


def test_smoke_pins_the_translation_it_actually_loaded():
    """BITB-107 (live-verified): without --translation, every golden-set query
    resolves to a language's *static* default translation (e.g. "web" for
    English) rather than whatever this ephemeral job actually loaded/embedded
    -- a corpus/query mismatch that always retrieves zero verses, silently,
    with no error. --translation must be pinned to the same code the 'Load 1
    Corinthians' step passes to load_bible.py, not hardcoded independently."""
    workflow = _load_workflow()
    smoke_job = workflow["jobs"]["eval-smoke"]

    load_step = _step(smoke_job, "Load 1 Corinthians (CI subset)")
    # load_bible.py defaults to "kjv" when --translation is not passed
    # explicitly (see scripts/load_bible.py); support either form.
    match = re.search(r"--translation\s+(\S+)", load_step["run"])
    loaded_translation = match.group(1) if match else "kjv"

    run_step = _step(smoke_job, "Run smoke eval")
    # Search only the actual CLI invocation line, not surrounding comments
    # (which also discuss --translation in prose).
    invocation_line = next(
        line for line in run_step["run"].splitlines() if "run_search_eval.py" in line
    )
    run_match = re.search(r"--translation\s+(\S+)", invocation_line)
    assert run_match, "eval-smoke's run_search_eval.py invocation is missing --translation"
    assert run_match.group(1) == loaded_translation, (
        f"eval-smoke queries translation {run_match.group(1)!r} but the job "
        f"loads {loaded_translation!r} -- every query would resolve to a "
        "translation with zero rows and always retrieve nothing."
    )


def test_smoke_defaults_to_baseline_semantic_config():
    """Unlike eval-prod (which only falls back to baseline_semantic when no
    LLM credential is present), eval-smoke must default to baseline_semantic
    UNCONDITIONALLY unless the workflow's `configs` input overrides it --
    smoke has no business depending on an LLM credential at all (BITB-107
    finding 4)."""
    workflow = _load_workflow()
    step = _step(workflow["jobs"]["eval-smoke"], "Run smoke eval")
    run_script = step["run"]
    assert "config_flag=(--config baseline_semantic)" in run_script, (
        "eval-smoke's run script does not default config_flag to "
        "baseline_semantic -- it would fall through to the CLI default "
        "(baseline_semantic,expansion_semantic) and attempt the expansion "
        "leg with no LLM credential."
    )
    # And that default must be conditional on the workflow's own `configs`
    # input, not applied even when the operator explicitly overrides it.
    assert "INPUT_CONFIGS" in step["env"], (
        "eval-smoke does not wire the workflow_dispatch `configs` input "
        "into the run step -- an explicit override would be silently ignored."
    )
    assert 'if [ -n "$INPUT_CONFIGS" ]' in run_script


def test_smoke_respects_language_input():
    """eval-smoke previously ignored the `language` workflow_dispatch input
    entirely; it must now be wired in like eval-prod already does."""
    workflow = _load_workflow()
    step = _step(workflow["jobs"]["eval-smoke"], "Run smoke eval")
    assert "INPUT_LANGUAGE" in step["env"]
    assert "--language" in step["run"]


def test_probe_step_exists_before_the_eval_step():
    """BITB-107 finding: the actual root cause could not be pinned down from
    the eval run's artifact alone, because search-eval's fail-open handler
    discarded the exception's cause chain. The probe step exists to print a
    real diagnosis straight into the console log, and must run before (not
    after, and not instead of) the eval step."""
    workflow = _load_workflow()
    smoke_job = workflow["jobs"]["eval-smoke"]
    step_names = [step.get("name") for step in smoke_job["steps"]]

    assert "Probe the embedding provider (app stack)" in step_names
    probe_index = step_names.index("Probe the embedding provider (app stack)")
    eval_index = step_names.index("Run smoke eval")
    assert probe_index < eval_index, "the probe step must run before 'Run smoke eval', not after"

    probe_step = smoke_job["steps"][probe_index]
    assert "--probe-embedding" in probe_step["run"]
    # Must NOT be wrapped in `set +e` -- a real failure here should fail the
    # step loudly with a full traceback in the console log, not be swallowed.
    assert "set +e" not in probe_step["run"]


def test_summarize_step_fails_on_nonzero_errors():
    """A green exit code alone is not sufficient (BITB-107 Verification note):
    a run where every query errored used to still exit 0. The summarize step
    must inspect the JSON output and fail this step when total n_errors is
    nonzero."""
    workflow = _load_workflow()
    step = _step(workflow["jobs"]["eval-smoke"], "Summarize results")
    script = step["run"]
    assert "n_errors" in script
    assert 'if [ "$err_total" != "0" ]' in script
    assert "exit 1" in script


def test_summarize_step_only_warns_on_zero_verses():
    """Live-verified (BITB-107): with the connection and translation defects
    both fixed, a fully healthy eval-smoke run can legitimately retrieve zero
    verses (1 Corinthians alone, similarity_threshold=0.35, topically
    unrelated golden-set queries) with zero errors -- exactly what this job's
    own header comment always said would happen. Zero verses must be a
    warning, not a step failure, or eval-smoke would be permanently red
    regardless of how healthy the plumbing actually is."""
    workflow = _load_workflow()
    step = _step(workflow["jobs"]["eval-smoke"], "Summarize results")
    script = step["run"]
    assert "verses_total" in script
    # The zero-verses branch must warn, not exit the step.
    zero_verses_idx = script.index('if [ "$verses_total" == "0" ]')
    branch = script[zero_verses_idx : zero_verses_idx + 400]
    assert "::warning::" in branch
    assert "exit 1" not in branch


# ---------------------------------------------------------------------------
# Route A's own version of the same blind spot (found on run 33213383692).
#
# BITB-107 gave eval-smoke a verses-retrieved count, because "exit 0 with no
# errors" turned out to say nothing about whether the eval had actually
# retrieved anything. eval-prod never got that count: its only checks are
# false positives and query errors, and a run that retrieves nothing scores
# zero on both -- identical to a flawless run, and reported as green with
# every metric 0.00.
#
# The asymmetry with smoke is deliberate. Smoke reads 1 Corinthians alone, so
# matching nothing is legitimate and only warns. Route A reads the whole
# production corpus, where zero retrieval means the measurement is broken --
# most likely translation resolution, since no golden-set case pins a
# translation and the readiness-aware default only works inside the app.
# ---------------------------------------------------------------------------


def _eval_prod_summary_step() -> dict:
    return _step(_load_workflow()["jobs"]["eval-prod"], "Summarize results")


def test_eval_prod_counts_the_verses_it_retrieved():
    run = _eval_prod_summary_step()["run"]
    assert "query_results[].retrieved" in run, (
        "eval-prod does not count retrieved verses -- without it, a run that "
        "retrieved nothing is indistinguishable from a perfect one (no "
        "errors, no false positives, exit 0, all metrics 0.00)"
    )


def test_eval_prod_fails_when_it_retrieved_nothing():
    run = _eval_prod_summary_step()["run"]
    assert "verses_total" in run and re.search(
        r'if \[ "\$verses_total" = "0" \]', run
    ), "eval-prod has no zero-retrieval check"
    zero_branch = run.split('if [ "$verses_total" = "0" ]', 1)[1]
    assert "::error::" in zero_branch and "exit 1" in zero_branch, (
        "a zero-retrieval eval-prod run does not fail -- publishing 0.00 as "
        "though it were a measurement is worse than publishing nothing"
    )


def test_eval_prod_puts_its_results_on_the_console():
    """A number that exists only in $GITHUB_STEP_SUMMARY and an artifact
    cannot be read from the API, from a phone, or by anything automated --
    which is why 'green but empty' took a re-dispatch to see."""
    run = _eval_prod_summary_step()["run"]
    assert 'tee -a "$GITHUB_STEP_SUMMARY"' in run, (
        "eval-prod's results are redirected only into the job summary; tee "
        "them so the console keeps a copy"
    )
