"""Tests for the deploy-time Alembic preflight (BITB-126).

The failure these cover is a *diagnosis* failure, not a database failure.
Workflow run 33369807581 re-ran commit 12129b6a on 2026-09-08 -- a commit that
ships r0001..r0005 -- days after r0006 had been applied to production. The
deploy was simply older than the live schema, but `alembic current` cannot
resolve a stamp it has no file for, so the job died on:

    ERROR [alembic.util.messaging] Can't locate revision identified by 'r0006'
    ##[error]Process completed with exit code 255.

The old inline preflight could not have caught it: it read `alembic current`'s
output, so it sat downstream of the command that had already exited 255.

`classify()` is pure, so each verdict is asserted directly rather than through
a workflow run. `format_failure()` is asserted too -- an unhelpful message *is*
the bug here, so the wording is part of the contract, not decoration.
"""

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PREFLIGHT_PATH = _REPO_ROOT / "scripts" / "alembic_preflight.py"


def _load_preflight():
    """Import the script by path: `scripts/` is not an importable package."""
    spec = importlib.util.spec_from_file_location("alembic_preflight", _PREFLIGHT_PATH)
    assert spec and spec.loader, f"cannot load {_PREFLIGHT_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = _load_preflight()
Verdict = preflight.Verdict

# The exact shape of run 33369807581: production stamped at r0006, checkout
# holding only r0001..r0005 with r0005 as its head.
_STALE_CHECKOUT_REVISIONS = {"r0001", "r0002", "r0003", "r0004", "r0005"}


def _classify(db_revisions, known=None, ancestry=None, heads=None):
    """classify() with the linear-single-head defaults this repo actually has."""
    known = _STALE_CHECKOUT_REVISIONS if known is None else known
    ancestry = known if ancestry is None else ancestry
    heads = {"r0005"} if heads is None else heads
    return preflight.classify(db_revisions, known, ancestry, heads)


class TestClassify:
    def test_up_to_date_database_is_ok(self):
        assert _classify({"r0005"}) is Verdict.OK

    def test_database_behind_head_is_ok(self):
        """The ordinary deploy: some revisions still to apply."""
        assert _classify({"r0003"}) is Verdict.OK

    def test_stamp_ahead_of_checkout_is_a_stale_checkout(self):
        """Run 33369807581: prod at r0006, this checkout stops at r0005."""
        assert _classify({"r0006"}) is Verdict.STALE_CHECKOUT

    def test_empty_stamp_is_unstamped(self):
        assert _classify(set()) is Verdict.UNSTAMPED

    def test_revision_outside_head_ancestry_is_diverged(self):
        """Present in the checkout, but `upgrade head` would never replay it."""
        verdict = _classify(
            {"r0004"},
            known={"r0001", "r0004", "r0005"},
            ancestry={"r0001", "r0005"},
        )
        assert verdict is Verdict.DIVERGED

    def test_multiple_heads_is_reported_before_anything_else(self):
        """`alembic upgrade head` is ambiguous with two heads, whatever the
        stamp is -- so this outranks a verdict about the stamp itself."""
        assert _classify(set(), heads={"r0005", "r0005b"}) is Verdict.MULTIPLE_HEADS

    def test_one_unknown_revision_among_several_is_still_stale(self):
        """A branched `alembic_version` must not be judged by its best row."""
        assert _classify({"r0004", "r0099"}) is Verdict.STALE_CHECKOUT


class TestFailureMessages:
    def test_unstamped_message_names_the_stamp_remedy(self):
        """BITB-089's remedy, preserved verbatim from the inline preflight this
        script replaced."""
        message = "\n".join(
            preflight.format_failure(Verdict.UNSTAMPED, set(), _STALE_CHECKOUT_REVISIONS, {"r0005"})
        )
        assert "stamp r0001" in message
        assert "no alembic_version row" in message

    def test_stale_checkout_message_names_the_stamp_and_the_real_cause(self):
        """The whole point of BITB-126: whoever is holding the deploy must be
        told the database is fine and the *commit* is old, not left with a bare
        exit 255 to interpret."""
        message = "\n".join(
            preflight.format_failure(
                Verdict.STALE_CHECKOUT, {"r0006"}, _STALE_CHECKOUT_REVISIONS, {"r0005"}
            )
        )
        assert "r0006" in message, "the message must name the revision the database holds"
        assert "r0005" in message, "the message must name this checkout's head"
        assert "OLDER" in message, "the message must state which side is behind"
        assert "re-run" in message.lower(), "the message must name the usual trigger"
        assert "not broken" in message, "the message must say the database needs no repair"

    def test_diverged_message_does_not_suggest_forcing_the_upgrade(self):
        message = "\n".join(
            preflight.format_failure(
                Verdict.DIVERGED, {"r0004"}, _STALE_CHECKOUT_REVISIONS, {"r0005"}
            )
        )
        assert "diverged" in message
        assert "do not force" in message

    def test_multiple_heads_message_names_the_merge_remedy(self):
        message = "\n".join(
            preflight.format_failure(
                Verdict.MULTIPLE_HEADS, {"r0005"}, _STALE_CHECKOUT_REVISIONS, {"r0005", "r0005b"}
            )
        )
        assert "alembic merge" in message

    def test_ok_has_no_failure_message(self):
        """A silent success path that fell through to a stray message would be
        worse than an exception."""
        with pytest.raises(ValueError):
            preflight.format_failure(Verdict.OK, {"r0005"}, _STALE_CHECKOUT_REVISIONS, {"r0005"})


class TestPendingCount:
    """The count printed on the success path.

    Caught against a real Postgres before merge: a database already at head
    reported "5 revision(s) to apply". A stamp records only the *latest*
    revision, so the applied set is that revision's ancestry -- counting the
    stamped ids alone makes every deploy log overstate the work by the whole
    history. Misreporting schema state is the failure mode this whole story is
    about, so the count gets its own tests.
    """

    @staticmethod
    def _linear_graph(revisions):
        """A linear chain r0001 -> ... -> rNNNN, as the repo actually has."""
        ancestry = {rev: set(revisions[: i + 1]) for i, rev in enumerate(revisions)}
        return preflight.RevisionGraph(
            known=set(revisions),
            head_ancestry=ancestry[revisions[-1]],
            heads={revisions[-1]},
            ancestry=ancestry,
        )

    def test_database_at_head_has_nothing_to_apply(self):
        graph = self._linear_graph(["r0001", "r0002", "r0003"])
        assert preflight.count_pending({"r0003"}, graph) == 0

    def test_database_behind_head_counts_only_the_gap(self):
        graph = self._linear_graph(["r0001", "r0002", "r0003"])
        assert preflight.count_pending({"r0001"}, graph) == 2

    def test_unstamped_database_has_everything_to_apply(self):
        graph = self._linear_graph(["r0001", "r0002", "r0003"])
        assert preflight.count_pending(set(), graph) == 3


class TestRealRevisionGraph:
    """Runs against `api/alembic/versions/` itself -- no database required, so
    it guards every PR, not just deploys."""

    def test_graph_loads_regardless_of_cwd(self, tmp_path, monkeypatch):
        """alembic.ini's `script_location` is relative to api/; the preflight
        runs from the repo root, so it must not inherit that assumption."""
        monkeypatch.chdir(tmp_path)
        graph = preflight.load_revision_graph()
        assert graph.known, "no revisions found in api/alembic/versions/"
        assert "r0001" in graph.known

    def test_repository_has_exactly_one_head(self):
        """Two heads would make `alembic upgrade head` fail at deploy time."""
        graph = preflight.load_revision_graph()
        assert len(graph.heads) == 1, f"expected a single Alembic head, found {sorted(graph.heads)}"

    def test_every_revision_is_an_ancestor_of_head(self):
        graph = preflight.load_revision_graph()
        assert graph.known == graph.head_ancestry, (
            f"revisions unreachable from head: {sorted(graph.known - graph.head_ancestry)} -- "
            "`alembic upgrade head` would never apply them"
        )

    def test_a_database_at_head_needs_no_migration(self):
        graph = preflight.load_revision_graph()
        verdict = preflight.classify(
            set(graph.heads), graph.known, graph.head_ancestry, graph.heads
        )
        assert verdict is Verdict.OK
        assert preflight.count_pending(set(graph.heads), graph) == 0

    def test_a_database_one_revision_ahead_is_caught(self):
        """The regression itself, against the live graph: whatever revision
        lands next, deploying the commit before it must be diagnosed rather
        than dying inside `alembic current`."""
        graph = preflight.load_revision_graph()
        verdict = preflight.classify({"r9999"}, graph.known, graph.head_ancestry, graph.heads)
        assert verdict is Verdict.STALE_CHECKOUT
