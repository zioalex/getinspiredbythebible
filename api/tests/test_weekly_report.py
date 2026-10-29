"""
Tests for the weekly activity digest builder and renderers.

The builder issues a fixed sequence of `db.execute` calls (documented in
`build_weekly_report`); these tests mock that sequence with canned results.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import ProgrammingError

sys.path.insert(0, str(Path(__file__).parent.parent))

from reports.weekly_report import (
    ContactStats,
    EngagementStats,
    FeedbackStats,
    LanguageCount,
    NegativeComment,
    TtsStats,
    WeeklyReport,
    _build_tts_stats,
    build_weekly_report,
    render_html,
    render_text,
)

NOW = datetime(2026, 6, 8, 18, 0, tzinfo=UTC)


def _result(all_=None, one_=None, scalar_=None):
    """Build a mock SQLAlchemy Result exposing .all()/.one()/.scalar()."""
    r = MagicMock()
    r.all.return_value = all_ if all_ is not None else []
    r.one.return_value = one_
    r.scalar.return_value = scalar_
    return r


def _db_with(results):
    db = MagicMock()
    db.execute = AsyncMock(side_effect=results)
    return db


@pytest.mark.asyncio
async def test_build_report_happy_path():
    db = _db_with(
        [
            _result(all_=[("positive", 8), ("negative", 2)]),  # 1 ratings
            _result(all_=[(NOW, "too slow"), (NOW, "wrong verse")]),  # 2 neg comments
            _result(all_=[("bug", 3), ("feature", 1)]),  # 3 contact
            _result(one_=(40, 12, 95, 7, 33)),  # 4 engagement aggregate
            _result(all_=[("en", 20), ("it", 8)]),  # 5 languages
            _result(scalar_=6),  # 6 prev feedback total
            _result(scalar_=9),  # 7 prev new sessions
            _result(all_=[]),  # 8 read-aloud
        ]
    )

    report = await build_weekly_report(db, now=NOW)

    assert report.feedback.total == 10
    assert report.feedback.positive == 8
    assert report.feedback.negative == 2
    assert report.feedback.positive_ratio == pytest.approx(0.8)
    assert len(report.feedback.recent_negative) == 2

    assert report.contact.total == 4
    assert report.contact.by_subject == {"bug": 3, "feature": 1}

    assert report.engagement.active_sessions == 40
    assert report.engagement.new_sessions == 12
    assert report.engagement.total_messages == 95
    assert report.engagement.mobile_sessions == 7
    assert report.engagement.web_sessions == 33
    assert report.engagement.top_languages[0].language == "en"

    assert report.feedback_total_prev == 6
    assert report.new_sessions_prev == 9
    assert report.window_days == 7


@pytest.mark.asyncio
async def test_build_report_empty_data_no_divide_error():
    db = _db_with(
        [
            _result(all_=[]),  # ratings
            _result(all_=[]),  # neg comments
            _result(all_=[]),  # contact
            _result(one_=(0, 0, 0, 0, 0)),  # engagement
            _result(all_=[]),  # languages
            _result(scalar_=None),  # prev feedback total (None -> 0)
            _result(scalar_=None),  # prev new sessions
            _result(all_=[]),  # read-aloud
        ]
    )

    report = await build_weekly_report(db, now=NOW)

    assert report.feedback.total == 0
    assert report.feedback.positive_ratio is None  # not a ZeroDivisionError
    assert report.contact.total == 0
    assert report.engagement.active_sessions == 0
    assert report.feedback_total_prev == 0
    assert report.new_sessions_prev == 0

    # Renderers must not crash on an empty report.
    assert "Weekly Activity Digest" in render_text(report)
    assert "n/a" in render_text(report)
    assert "<html>" in render_html(report)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_message", "pgcode"),
    [
        ('relation "sessions" does not exist', None),
        ("undefinedtable: sessions", None),
        ('column "is_mobile" does not exist', "42703"),
    ],
)
async def test_build_report_falls_back_when_sessions_schema_is_missing(
    error_message: str, pgcode: str | None
):
    class DummyOrigError(Exception):
        def __init__(self, message: str, *, pgcode: str | None):
            super().__init__(message)
            self.pgcode = pgcode

    db = MagicMock()
    actions = iter(
        [
            _result(all_=[("positive", 2)]),
            _result(all_=[]),
            _result(all_=[("bug", 1)]),
            ProgrammingError(
                "SELECT active_sessions FROM sessions",
                {},
                DummyOrigError(error_message, pgcode=pgcode),
            ),
            _result(scalar_=0),
            _result(all_=[]),  # read-aloud
        ]
    )

    async def execute(*_args, **_kwargs):
        action = next(actions)
        if isinstance(action, Exception):
            raise action
        return action

    db.execute = AsyncMock(side_effect=execute)
    db.rollback = AsyncMock()

    report = await build_weekly_report(db, now=NOW)

    assert report.feedback.total == 2
    assert report.contact.by_subject == {"bug": 1}
    assert report.engagement.active_sessions == 0
    assert report.engagement.new_sessions == 0
    assert report.engagement.total_messages == 0
    assert report.engagement.top_languages == []
    assert report.new_sessions_prev == 0
    assert db.execute.await_count == 6
    # The failed sessions query aborts the transaction; the fallback must roll
    # it back or the remaining queries die with InFailedSQLTransaction.
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_report_reraises_unrelated_programming_error():
    """A ProgrammingError that isn't the missing-sessions-schema case (e.g. a
    genuine SQL syntax error) must propagate, not be swallowed into the
    zero-engagement fallback."""

    class DummyOrigError(Exception):
        def __init__(self, message: str, *, pgcode: str | None):
            super().__init__(message)
            self.pgcode = pgcode

    db = MagicMock()
    actions = iter(
        [
            _result(all_=[("positive", 2)]),
            _result(all_=[]),
            _result(all_=[("bug", 1)]),
            ProgrammingError(
                "SELECT active_sessions FROM sessions",
                {},
                DummyOrigError('syntax error at or near "SELECT"', pgcode="42601"),
            ),
        ]
    )

    async def execute(*_args, **_kwargs):
        action = next(actions)
        if isinstance(action, Exception):
            raise action
        return action

    db.execute = AsyncMock(side_effect=execute)
    db.rollback = AsyncMock()

    with pytest.raises(ProgrammingError):
        await build_weekly_report(db, now=NOW)

    db.rollback.assert_not_awaited()


def _report_with_comment(comment: str) -> WeeklyReport:
    return WeeklyReport(
        window_start=NOW,
        window_end=NOW,
        window_days=7,
        feedback=FeedbackStats(
            total=1,
            positive=0,
            negative=1,
            positive_ratio=0.0,
            recent_negative=[NegativeComment(created_at=NOW, comment=comment)],
        ),
        contact=ContactStats(total=0, by_subject={}),
        engagement=EngagementStats(
            active_sessions=0,
            new_sessions=0,
            total_messages=0,
            web_sessions=0,
            mobile_sessions=0,
            top_languages=[LanguageCount(language="en", count=1)],
        ),
        feedback_total_prev=0,
        new_sessions_prev=0,
    )


def test_render_html_escapes_user_text():
    report = _report_with_comment("<script>alert('x')</script> & bad")
    html_out = render_html(report)

    # Raw tag/entity must be escaped, not present verbatim.
    assert "<script>" not in html_out
    assert "&lt;script&gt;" in html_out
    assert "&amp; bad" in html_out


# ==================== Read aloud (BITB-247) ====================

_TTS_ROWS = [
    ("tts_started", "chrome", "windows", 60),
    ("tts_started", "safari", "ios", 40),
    ("tts_completed", "chrome", "windows", 50),
    ("tts_completed", "safari", "ios", 20),
    ("tts_start_failed", "firefox", "linux", 7),
    ("tts_start_failed", "safari", "ios", 5),
    ("tts_error", "safari", "ios", 3),
    ("tts_error", "chrome", "android", 2),
    ("tts_error", "app", "android", 1),
    ("tts_unavailable", "firefox", "linux", 4),
]


def test_build_tts_stats_totals_rates_and_top_failures():
    stats = _build_tts_stats(_TTS_ROWS)

    assert stats.available is True
    assert stats.totals == {
        "tts_started": 100,
        "tts_completed": 70,
        "tts_start_failed": 12,
        "tts_error": 6,
        "tts_unavailable": 4,
    }
    assert stats.completion_rate == pytest.approx(0.7)
    assert stats.failure_rate == pytest.approx(0.18)
    # safari/ios 5+3=8, firefox/linux 7, chrome/android 2 (app/android 1 is cut: top 3).
    assert [(p.browser, p.os, p.failures) for p in stats.top_failures] == [
        ("safari", "ios", 8),
        ("firefox", "linux", 7),
        ("chrome", "android", 2),
    ]


def test_build_tts_stats_no_started_gives_none_rates():
    stats = _build_tts_stats([("tts_unavailable", "other", "other", 3)])
    assert stats.completion_rate is None
    assert stats.failure_rate is None
    assert stats.top_failures == []


@pytest.mark.asyncio
async def test_build_report_includes_read_aloud_from_seeded_rows():
    db = _db_with(
        [
            _result(all_=[]),
            _result(all_=[]),
            _result(all_=[]),
            _result(one_=(0, 0, 0, 0, 0)),
            _result(all_=[]),
            _result(scalar_=0),
            _result(scalar_=0),
            _result(all_=_TTS_ROWS),
        ]
    )

    report = await build_weekly_report(db, now=NOW)

    assert report.tts.totals["tts_started"] == 100
    # Window is the 7 UTC calendar days ending on NOW's date.
    params = db.execute.await_args_list[-1].args[1]
    assert str(params["first_day"]) == "2026-06-02"
    assert str(params["last_day"]) == "2026-06-08"

    text_out = render_text(report)
    assert "READ ALOUD" in text_out
    assert "Completed: 70" in text_out
    assert "Completion rate (completed / started): 70%" in text_out
    assert "Failure rate ((start failed + error) / started): 18%" in text_out
    assert "safari / ios: 8" in text_out
    html_out = render_html(report)
    assert "Read aloud" in html_out
    assert "safari / ios" in html_out
    assert "70%" in html_out


@pytest.mark.asyncio
async def test_build_report_tolerates_missing_tts_table():
    class DummyOrigError(Exception):
        pgcode = "42P01"

    db = MagicMock()
    actions = iter(
        [
            _result(all_=[]),
            _result(all_=[]),
            _result(all_=[]),
            _result(one_=(0, 0, 0, 0, 0)),
            _result(all_=[]),
            _result(scalar_=0),
            _result(scalar_=0),
            ProgrammingError(
                "SELECT ... FROM tts_event_daily",
                {},
                DummyOrigError('relation "tts_event_daily" does not exist'),
            ),
        ]
    )

    async def execute(*_args, **_kwargs):
        action = next(actions)
        if isinstance(action, Exception):
            raise action
        return action

    db.execute = AsyncMock(side_effect=execute)
    db.rollback = AsyncMock()

    report = await build_weekly_report(db, now=NOW)

    assert report.tts.available is False
    assert report.tts.totals["tts_started"] == 0
    db.rollback.assert_awaited_once()
    assert "Not available" in render_text(report)
    assert "Not available" in render_html(report)


@pytest.mark.asyncio
async def test_build_report_reraises_unrelated_tts_programming_error():
    class DummyOrigError(Exception):
        pgcode = "42601"

    db = MagicMock()
    actions = iter(
        [
            _result(all_=[]),
            _result(all_=[]),
            _result(all_=[]),
            _result(one_=(0, 0, 0, 0, 0)),
            _result(all_=[]),
            _result(scalar_=0),
            _result(scalar_=0),
            ProgrammingError("SELECT", {}, DummyOrigError("syntax error")),
        ]
    )

    async def execute(*_args, **_kwargs):
        action = next(actions)
        if isinstance(action, Exception):
            raise action
        return action

    db.execute = AsyncMock(side_effect=execute)
    db.rollback = AsyncMock()

    with pytest.raises(ProgrammingError):
        await build_weekly_report(db, now=NOW)


def test_tts_stats_model_defaults_unavailable_report_renders():
    report = _report_with_comment("x")
    assert isinstance(report.tts, TtsStats)
    assert report.tts.available is False
    assert "Not available" in render_text(report)
