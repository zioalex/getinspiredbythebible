"""
Admin routes — internal, server-to-server operational endpoints.

Not part of the public API (``include_in_schema=False``). Authenticated with
the same shared-secret probe header used by the production monitor, so the
weekly-report GitHub Actions cron can trigger a digest without a session/token.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from reports.weekly_report import build_weekly_report, render_html, render_text
from scripture import get_db_session
from utils.email_service import email_service
from utils.logging_config import get_logger
from utils.monitor_probe import is_monitor_probe

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/weekly-report", include_in_schema=False)
async def trigger_weekly_report(
    request: Request,
    dry_run: bool = Query(False, description="Compute and return stats without sending email"),
    db: AsyncSession = Depends(get_db_session),
):
    """Build the weekly activity digest and email it to the configured recipient.

    Guarded by the monitor-probe shared secret (``X-Monitor-Probe-Secret``).
    Fail-closed: if the secret is unset on the server, every request is 401.
    """
    if not is_monitor_probe(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    report = await build_weekly_report(db)

    email_sent = False
    if not dry_run:
        subject = (
            "[Vox Quieta] Weekly Activity Digest — "
            f"{report.window_start:%Y-%m-%d} to {report.window_end:%Y-%m-%d}"
        )
        # send_email is synchronous (httpx.Client) — do not await.
        email_sent = email_service.send_email(
            to_email=settings.weekly_report_recipient,
            subject=subject,
            body_text=render_text(report),
            body_html=render_html(report),
        )
        logger.info(
            "Weekly report processed",
            extra={"email_sent": email_sent, "recipient": settings.weekly_report_recipient},
        )
    else:
        logger.info("Weekly report dry-run (no email sent)")

    return {
        "dry_run": dry_run,
        "email_sent": email_sent,
        "report": report.model_dump(mode="json"),
    }
