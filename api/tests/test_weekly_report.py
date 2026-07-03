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
    WeeklyReport,
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
    class DummyOrig(Exception):
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
                DummyOrig(error_message, pgcode=pgcode),
            ),
            _result(scalar_=0),
        ]
    )

    async def execute(*_args, **_kwargs):
        action = next(actions)
        if isinstance(action, Exception):
            raise action
        return action

    db.execute = AsyncMock(side_effect=execute)

    report = await build_weekly_report(db, now=NOW)

    assert report.feedback.total == 2
    assert report.contact.by_subject == {"bug": 1}
    assert report.engagement.active_sessions == 0
    assert report.engagement.new_sessions == 0
    assert report.engagement.total_messages == 0
    assert report.engagement.top_languages == []
    assert report.new_sessions_prev == 0
    assert db.execute.await_count == 5


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
