"""Guards the verse_topics automation BITB-105 added to the deploy pipeline.

BITB-044 shipped `scripts/populate_verse_topics.py` and nothing ever ran it,
so `verse_topics` stayed empty in production for months and topic boosting
was a silent no-op. The fix is workflow wiring, which is exactly the kind of
thing that regresses silently: a step deleted in a merge conflict, a
dependency dropped from the install line, a `continue-on-error` flipped.

These tests parse `.github/workflows/azure-deploy.yml` and assert the
properties that keep that automation real. Same approach and scope discipline
as `test_deploy_workflow_migrations.py` (BITB-089/BITB-097) -- a regression
guard for one dangerous failure mode, not a schema validation of the workflow.
"""

from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "azure-deploy.yml"

_POPULATE_SCRIPT = "scripts/populate_verse_topics.py"
_COVERAGE_SCRIPT = "scripts/check_verse_topic_coverage.py"


def _load_workflow() -> dict:
    return yaml.safe_load(_WORKFLOW_PATH.read_text())


def _changes_filters() -> dict:
    """The `dorny/paths-filter` inputs from the `changes` job, parsed.

    The filters are authored as a YAML string inside the workflow YAML, so they
    need a second parse.
    """
    workflow = _load_workflow()
    for step in workflow["jobs"]["changes"]["steps"]:
        with_block = step.get("with") or {}
        if "filters" in with_block:
            return yaml.safe_load(with_block["filters"])
    raise AssertionError("no paths-filter step found in the `changes` job")


def _seed_post_steps() -> list[dict]:
    return _load_workflow()["jobs"]["seed-database-post"]["steps"]


def _is_preflight(step: dict) -> bool:
    """The start-up check invokes both scripts with `--help`, so it matches a
    plain path search without being the step that does the work. Everything
    below means "the step that actually runs this script", so it is excluded
    there and looked up explicitly by the test that is about it."""
    return "--help" in (step.get("run") or "")


def _step_index_containing(needle: str) -> int:
    for index, step in enumerate(_seed_post_steps()):
        if needle in (step.get("run") or "") and not _is_preflight(step):
            return index
    raise AssertionError(f"no step in seed-database-post runs {needle!r}")


def _step_containing(needle: str) -> dict:
    return _seed_post_steps()[_step_index_containing(needle)]


def _preflight_index() -> int:
    for index, step in enumerate(_seed_post_steps()):
        if _is_preflight(step):
            return index
    raise AssertionError("seed-database-post has no `--help` start-up check")


def test_seed_database_post_populates_verse_topics():
    """The whole point of BITB-105: something in the pipeline actually runs
    the population script."""
    assert _step_containing(_POPULATE_SCRIPT) is not None


def test_population_runs_before_embedding_generation():
    """`Generate Embeddings` has no continue-on-error, so every step after it
    is skipped when it fails. Tagging placed downstream of it would be
    silently skipped by an unrelated Azure OpenAI outage -- reinstating the
    exact "correct artefact that nothing executed" bug this story closes."""
    populate_index = _step_index_containing(_POPULATE_SCRIPT)
    embeddings_index = next(
        index
        for index, step in enumerate(_seed_post_steps())
        if step.get("name") == "Generate Embeddings"
    )
    assert populate_index < embeddings_index


def test_population_step_cannot_fail_the_deploy():
    """BITB-105's recorded blast-radius decision: topic rows back a
    flag-gated ranking boost, so a tagging failure alarms and does not fail
    the deploy."""
    assert _step_containing(_POPULATE_SCRIPT)["continue-on-error"] is True


def test_coverage_check_step_exists():
    assert _step_containing(_COVERAGE_SCRIPT) is not None


def test_coverage_check_runs_even_when_population_fails():
    """An empty verse_topics must be reported whether the cause was a
    population run that failed or one that never happened."""
    assert "always()" in str(_step_containing(_COVERAGE_SCRIPT)["if"])


def test_coverage_check_cannot_fail_the_deploy():
    assert _step_containing(_COVERAGE_SCRIPT)["continue-on-error"] is True


def test_seed_post_installs_dependencies_from_the_manifest():
    """The original version of this guard asserted that `pydantic-settings`
    appeared in a hand-curated install line -- and passed, while both scripts
    were dying on `ModuleNotFoundError: No module named 'anthropic'` (run
    33213487365). A test that mirrors the author's guess at the import closure
    cannot catch the guess being wrong.

    The closure is genuinely non-obvious: `chat.topics` is a module of keyword
    lists, but importing it runs `api/chat/__init__.py`, which eagerly imports
    .service -> providers -> providers.claude -> `import anthropic`. So the
    property worth pinning is not which package names appear, it is that the
    install comes from the manifest that already tracks them."""
    install_steps = [s for s in _seed_post_steps() if "pip install" in (s.get("run") or "")]
    assert install_steps, "seed-database-post has no pip install step"
    assert any("-r api/requirements.txt" in step["run"] for step in install_steps), (
        "seed-database-post installs a hand-curated dependency list instead of "
        "api/requirements.txt -- the topic scripts import the whole api "
        "package's provider stack, so any curated list re-derives an import "
        "closure by hand and silently drifts out of date"
    )


def test_seed_post_verifies_the_topic_scripts_can_start():
    """Both topic steps are continue-on-error, so a script that cannot even
    start is invisible in the deploy's status. Something in this job has to
    draw the line between "the automation could not run" (a deploy failure)
    and "the automation ran and found a problem" (an alarm) -- otherwise the
    first is silently reported as the second, which is how a missing
    dependency shipped twice."""
    index = _preflight_index()
    step = _seed_post_steps()[index]
    run = step.get("run") or ""

    for script in (_POPULATE_SCRIPT, _COVERAGE_SCRIPT):
        assert script in run, f"the start-up check does not cover {script}"

    assert step.get("continue-on-error") is not True, (
        "the start-up check is continue-on-error -- it is the one thing in "
        "this job that must be able to fail the deploy"
    )
    assert index < _step_index_containing(
        _POPULATE_SCRIPT
    ), "the start-up check runs after the step it is meant to protect"


def test_coverage_check_annotates_a_malfunction():
    """`check_verse_topic_coverage.py` exits 0 when it alarms, so a non-zero
    exit means the check could not run at all. With continue-on-error and no
    annotation that was completely silent: a red step nobody looks at, inside
    a green deploy."""
    run = _step_containing(_COVERAGE_SCRIPT)["run"]
    assert "::warning::" in run, (
        "a coverage-check malfunction produces no annotation -- it exits "
        "non-zero only when it could not run, and continue-on-error hides that"
    )


def test_translation_registry_change_triggers_the_seed_path():
    """A newly added translation edits scripts/translations.py, which must
    trigger the same path that now tags it -- otherwise every new translation
    ships without topic rows, a per-translation repeat of the original bug."""
    filters = _changes_filters()
    assert "scripts/translations.py" in filters["bible_scripts"]
    seed_post_if = str(_load_workflow()["jobs"]["seed-database-post"]["if"])
    assert "needs.changes.outputs.bible_scripts" in seed_post_if


def test_topic_scripts_are_watched_by_a_path_filter():
    """Without this, a fix to the tagging pipeline sits in the repo until some
    unrelated bible_scripts change happens to deploy it."""
    filters = _changes_filters()
    watched = {glob for globs in filters.values() for glob in globs}
    assert _POPULATE_SCRIPT in watched
    assert _COVERAGE_SCRIPT in watched
