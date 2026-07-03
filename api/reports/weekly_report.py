"""
Weekly activity digest builder.

Pure, independently testable: queries the backend Postgres DB for the last
``window_days`` of feedback, contact submissions, and session engagement, and
renders a plain-text + HTML email body. Both the web app and the Android app
hit the same API, so this DB-only view already covers both clients.

Firebase/GA4 Android engagement (screen views, verse taps, retention) is
deliberately out of scope here — it needs a separate Google Analytics Data API
integration.
"""

import html
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from feedback.models import ContactSubmission, Feedback
from utils.logging_config import get_logger

# How many recent negative comments to surface in the digest.
MAX_NEGATIVE_COMMENTS = 10
# How many top languages to list.
MAX_LANGUAGES = 5
UNDEFINED_SESSIONS_SQLSTATES = {"42P01", "42703"}
SESSIONS_ANALYTICS_ERROR_MARKERS = (
    "sessions",
    "last_activity",
    "message_count",
    "is_mobile",
    "language",
)

logger = get_logger(__name__)


# ==================== Result models ====================


class NegativeComment(BaseModel):
    created_at: datetime
    comment: str


class FeedbackStats(BaseModel):
    total: int
    positive: int
    negative: int
    # None when there is no feedback at all (avoids a misleading 0%/divide).
    positive_ratio: float | None
    recent_negative: list[NegativeComment]


class ContactStats(BaseModel):
    total: int
    by_subject: dict[str, int]


class LanguageCount(BaseModel):
    language: str
    count: int


class EngagementStats(BaseModel):
    active_sessions: int
    new_sessions: int
    # Approximate: message_count is a per-session lifetime counter, summed over
    # sessions active in the window.
    total_messages: int
    web_sessions: int
    mobile_sessions: int
    top_languages: list[LanguageCount]


class WeeklyReport(BaseModel):
    window_start: datetime
    window_end: datetime
    window_days: int
    feedback: FeedbackStats
    contact: ContactStats
    engagement: EngagementStats
    # Week-over-week comparison points (previous window of equal length).
    feedback_total_prev: int
    new_sessions_prev: int


def _empty_engagement() -> EngagementStats:
    return EngagementStats(
        active_sessions=0,
        new_sessions=0,
        total_messages=0,
        web_sessions=0,
        mobile_sessions=0,
        top_languages=[],
    )


def _is_missing_sessions_schema(error: ProgrammingError) -> bool:
    orig = getattr(error, "orig", None)
    # asyncpg exposes PostgreSQL SQLSTATE as ``sqlstate`` on its exceptions, while
    # psycopg-style DBAPI exceptions conventionally use ``pgcode``.
    sqlstate = getattr(orig, "pgcode", None) or getattr(orig, "sqlstate", None)
    if sqlstate in UNDEFINED_SESSIONS_SQLSTATES:
        return True

    message = str(error).lower()
    return (
        ("sessions" in message and ("does not exist" in message or "undefinedtable" in message))
        or (
            "undefinedcolumn" in message
            and any(marker in message for marker in SESSIONS_ANALYTICS_ERROR_MARKERS)
        )
    )


# ==================== Builder ====================


async def build_weekly_report(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    window_days: int = 7,
) -> WeeklyReport:
    """Build the weekly activity report over the last ``window_days``.

    ``now`` is injectable so tests are deterministic. Issues a fixed sequence
    of queries (order matters for unit tests that mock ``db.execute``):

    1. feedback ratings grouped by rating (current window)
    2. recent negative comments (current window)
    3. contact submissions grouped by subject (current window)
    4. session engagement aggregate (one row)
    5. top languages among active sessions
    6. feedback total in the previous window (delta)
    7. new sessions in the previous window (delta)
    """
    end = now or datetime.now(UTC)
    start = end - timedelta(days=window_days)
    prev_start = start - timedelta(days=window_days)

    # 1. Feedback by rating (ORM).
    fb_rows = (
        await db.execute(
            select(Feedback.rating, func.count())
            .where(Feedback.created_at >= start, Feedback.created_at < end)
            .group_by(Feedback.rating)
        )
    ).all()
    rating_counts = {rating: count for rating, count in fb_rows}
    positive = rating_counts.get("positive", 0)
    negative = rating_counts.get("negative", 0)
    total_fb = sum(rating_counts.values())
    positive_ratio = (positive / total_fb) if total_fb else None

    # 2. Recent negative comments (ORM).
    neg_rows = (
        await db.execute(
            select(Feedback.created_at, Feedback.comment)
            .where(
                Feedback.rating == "negative",
                Feedback.created_at >= start,
                Feedback.created_at < end,
                Feedback.comment.isnot(None),
                Feedback.comment != "",
            )
            .order_by(Feedback.created_at.desc())
            .limit(MAX_NEGATIVE_COMMENTS)
        )
    ).all()
    recent_negative = [
        NegativeComment(created_at=created_at, comment=comment) for created_at, comment in neg_rows
    ]

    feedback = FeedbackStats(
        total=total_fb,
        positive=positive,
        negative=negative,
        positive_ratio=positive_ratio,
        recent_negative=recent_negative,
    )

    # 3. Contact submissions by subject (ORM).
    contact_rows = (
        await db.execute(
            select(ContactSubmission.subject, func.count())
            .where(
                ContactSubmission.created_at >= start,
                ContactSubmission.created_at < end,
            )
            .group_by(ContactSubmission.subject)
        )
    ).all()
    by_subject = {subject: count for subject, count in contact_rows}
    contact = ContactStats(total=sum(by_subject.values()), by_subject=by_subject)

    sessions_analytics_available = True
    try:
        # 4. Engagement aggregate (raw SQL — there is no ORM model for `sessions`).
        eng_row = (
            await db.execute(
                text("""
                    SELECT
                        COUNT(*) FILTER (
                            WHERE last_activity >= :start AND last_activity < :end
                        ) AS active_sessions,
                        COUNT(*) FILTER (
                            WHERE created_at >= :start AND created_at < :end
                        ) AS new_sessions,
                        COALESCE(SUM(message_count) FILTER (
                            WHERE last_activity >= :start AND last_activity < :end
                        ), 0) AS total_messages,
                        COUNT(*) FILTER (
                            WHERE last_activity >= :start AND last_activity < :end
                            AND is_mobile
                        ) AS mobile_sessions,
                        COUNT(*) FILTER (
                            WHERE last_activity >= :start AND last_activity < :end
                            AND NOT is_mobile
                        ) AS web_sessions
                    FROM sessions
                """),
                {"start": start, "end": end},
            )
        ).one()
        active_sessions, new_sessions, total_messages, mobile_sessions, web_sessions = eng_row

        # 5. Top languages among active sessions (raw SQL).
        lang_rows = (
            await db.execute(
                text("""
                    SELECT language, COUNT(*) AS cnt
                    FROM sessions
                    WHERE last_activity >= :start AND last_activity < :end
                      AND language IS NOT NULL
                    GROUP BY language
                    ORDER BY cnt DESC
                    LIMIT :limit
                """),
                {"start": start, "end": end, "limit": MAX_LANGUAGES},
            )
        ).all()
        top_languages = [
            LanguageCount(language=language, count=count) for language, count in lang_rows
        ]

        engagement = EngagementStats(
            active_sessions=active_sessions,
            new_sessions=new_sessions,
            total_messages=total_messages,
            web_sessions=web_sessions,
            mobile_sessions=mobile_sessions,
            top_languages=top_languages,
        )
    except ProgrammingError as exc:
        if not _is_missing_sessions_schema(exc):
            raise
        logger.warning(
            "Weekly report sessions analytics unavailable; falling back to zero engagement stats",
            extra={"error": str(exc)},
        )
        sessions_analytics_available = False
        engagement = _empty_engagement()

    # 6. Previous-window feedback total (ORM) — week-over-week delta.
    feedback_total_prev = (
        await db.execute(
            select(func.count()).where(
                Feedback.created_at >= prev_start, Feedback.created_at < start
            )
        )
    ).scalar() or 0

    # 7. Previous-window new sessions (raw SQL) — week-over-week delta.
    if sessions_analytics_available:
        new_sessions_prev = (
            (
                await db.execute(
                    text("""
                    SELECT COUNT(*) FROM sessions
                    WHERE created_at >= :prev_start AND created_at < :start
                """),
                    {"prev_start": prev_start, "start": start},
                )
            ).scalar()
            or 0
        )
    else:
        new_sessions_prev = 0

    return WeeklyReport(
        window_start=start,
        window_end=end,
        window_days=window_days,
        feedback=feedback,
        contact=contact,
        engagement=engagement,
        feedback_total_prev=feedback_total_prev,
        new_sessions_prev=new_sessions_prev,
    )


# ==================== Rendering ====================


def _pct(ratio: float | None) -> str:
    return "n/a" if ratio is None else f"{ratio * 100:.0f}%"


def _delta(current: int, previous: int) -> str:
    """Human-readable signed delta vs. the previous window."""
    diff = current - previous
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff} vs. previous {previous}"


def render_text(report: WeeklyReport) -> str:
    """Render the digest as plain text."""
    r = report
    lines: list[str] = []
    lines.append("Vox Quieta — Weekly Activity Digest")
    lines.append(
        f"{r.window_start:%Y-%m-%d %H:%M} to {r.window_end:%Y-%m-%d %H:%M} UTC "
        f"(last {r.window_days} days)"
    )
    lines.append("(covers both the web app and the Android app)")
    lines.append("")

    lines.append("FEEDBACK")
    lines.append(
        f"  Total: {r.feedback.total} " f"({_delta(r.feedback.total, r.feedback_total_prev)})"
    )
    lines.append(f"  Positive: {r.feedback.positive}")
    lines.append(f"  Negative: {r.feedback.negative}")
    lines.append(f"  Positive ratio: {_pct(r.feedback.positive_ratio)}")
    if r.feedback.recent_negative:
        lines.append("  Recent negative comments:")
        for nc in r.feedback.recent_negative:
            lines.append(f"    - [{nc.created_at:%Y-%m-%d}] {nc.comment}")
    lines.append("")

    lines.append("CONTACT SUBMISSIONS")
    lines.append(f"  Total: {r.contact.total}")
    for subject, count in sorted(r.contact.by_subject.items()):
        lines.append(f"    {subject}: {count}")
    lines.append("")

    e = r.engagement
    lines.append("ENGAGEMENT")
    lines.append(f"  Active sessions: {e.active_sessions}")
    lines.append(
        f"  New sessions: {e.new_sessions} " f"({_delta(e.new_sessions, r.new_sessions_prev)})"
    )
    lines.append(f"  Messages (approx, lifetime per active session): {e.total_messages}")
    lines.append(f"  Web sessions: {e.web_sessions}")
    lines.append(f"  Mobile sessions: {e.mobile_sessions}")
    if e.top_languages:
        lines.append("  Top languages:")
        for lc in e.top_languages:
            lines.append(f"    {lc.language}: {lc.count}")
    lines.append("")

    return "\n".join(lines).strip()


def _esc(value: str) -> str:
    """HTML-escape free text, then turn newlines into <br>."""
    return html.escape(value).replace("\n", "<br>")


def render_html(report: WeeklyReport) -> str:
    """Render the digest as HTML (mirrors the contact-notification style)."""
    r = report
    e = r.engagement

    neg_html = ""
    if r.feedback.recent_negative:
        items = "".join(
            f'<div style="background: #f9f9f9; padding: 10px 15px; '
            f'border-left: 4px solid #5c6ac4; margin: 8px 0;">'
            f'<span style="font-size: 12px; color: #888;">'
            f"{nc.created_at:%Y-%m-%d}</span><br>{_esc(nc.comment)}</div>"
            for nc in r.feedback.recent_negative
        )
        neg_html = f"<h3>Recent negative comments</h3>{items}"

    contact_rows = (
        "".join(
            f'<tr><td style="padding: 8px; background: #f5f5f5;">{_esc(subject)}</td>'
            f'<td style="padding: 8px;">{count}</td></tr>'
            for subject, count in sorted(r.contact.by_subject.items())
        )
        or '<tr><td style="padding: 8px;" colspan="2"><em>None</em></td></tr>'
    )

    lang_rows = (
        "".join(
            f'<tr><td style="padding: 8px; background: #f5f5f5;">{_esc(lc.language)}</td>'
            f'<td style="padding: 8px;">{lc.count}</td></tr>'
            for lc in e.top_languages
        )
        or '<tr><td style="padding: 8px;" colspan="2"><em>None</em></td></tr>'
    )

    return f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #5c6ac4;">Vox Quieta — Weekly Activity Digest</h2>
    <p style="color: #888; font-size: 13px;">
        {r.window_start:%Y-%m-%d} to {r.window_end:%Y-%m-%d} UTC
        (last {r.window_days} days) — covers both the web app and the Android app.
    </p>

    <h3>Feedback</h3>
    <table style="border-collapse: collapse; margin: 10px 0;">
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Total</td>
            <td style="padding: 8px;">{r.feedback.total} ({_delta(r.feedback.total, r.feedback_total_prev)})</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Positive</td>
            <td style="padding: 8px;">{r.feedback.positive}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Negative</td>
            <td style="padding: 8px;">{r.feedback.negative}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Positive ratio</td>
            <td style="padding: 8px;">{_pct(r.feedback.positive_ratio)}</td>
        </tr>
    </table>
    {neg_html}

    <h3>Contact submissions ({r.contact.total})</h3>
    <table style="border-collapse: collapse; margin: 10px 0;">{contact_rows}</table>

    <h3>Engagement</h3>
    <table style="border-collapse: collapse; margin: 10px 0;">
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Active sessions</td>
            <td style="padding: 8px;">{e.active_sessions}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">New sessions</td>
            <td style="padding: 8px;">{e.new_sessions} ({_delta(e.new_sessions, r.new_sessions_prev)})</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Messages (approx)</td>
            <td style="padding: 8px;">{e.total_messages}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Web / Mobile</td>
            <td style="padding: 8px;">{e.web_sessions} / {e.mobile_sessions}</td>
        </tr>
    </table>
    <h4 style="margin-bottom: 4px;">Top languages</h4>
    <table style="border-collapse: collapse; margin: 10px 0;">{lang_rows}</table>

    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="font-size: 12px; color: #888;">
        Automated weekly digest. Messages figure is approximate (per-session
        lifetime counter). Android in-app engagement (screen views, verse taps)
        is not yet included.
    </p>
</body>
</html>
    """.strip()
