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


def _step_index_containing(needle: str) -> int:
    for index, step in enumerate(_seed_post_steps()):
        if needle in (step.get("run") or ""):
            return index
    raise AssertionError(f"no step in seed-database-post runs {needle!r}")


def _step_containing(needle: str) -> dict:
    return _seed_post_steps()[_step_index_containing(needle)]


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


def test_seed_post_installs_the_topic_scripts_dependencies():
    """Both topic scripts import api/chat/topics.py, which pulls in
    config.Settings (pydantic-settings). Drop this from the install line and
    the steps die at import -- automation that is itself a silent no-op."""
    install_steps = [s for s in _seed_post_steps() if "pip install" in (s.get("run") or "")]
    assert install_steps, "seed-database-post has no pip install step"
    assert any("pydantic-settings" in step["run"] for step in install_steps)


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
