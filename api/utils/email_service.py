"""
Email service for sending notifications via SMTP2GO HTTP API.

Uses SMTP2GO's REST API with API key authentication.
"""

import html
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from config import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)

SMTP2GO_API_URL = "https://api.smtp2go.com/v3/email/send"


EXPORT_HOWTO_URL = (
    "https://github.com/zioalex/getinspiredbythebible/blob/main/docs/HOW-TO-EXPORT-FEEDBACK.md"
)
_AZURE_PG_SUFFIX = ".postgres.database.azure.com"
_SERVER_PLACEHOLDER = "<server>"


def _esc(value: object) -> str:
    """HTML-escape anything user-controlled before it goes into an HTML body."""
    return html.escape(str(value), quote=True)


def _valid_uuid(value: str | None) -> str | None:
    """Canonical UUID string, or None. Keeps shell metacharacters out of copy-paste commands."""
    if not value:
        return None
    try:
        return str(UUID(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _text_until(created_at: datetime, days: int) -> str:
    """ISO date (UTC) on which text stored at ``created_at`` is deleted."""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return (created_at.astimezone(UTC) + timedelta(days=days)).date().isoformat()


def _prod_server_name() -> str | None:
    """Azure Postgres server name, derived from the host of DATABASE_URL, or None.

    Production's URL is ``...@bible-app-db-<suffix>.postgres.database.azure.com:5432/...``;
    the first label is the server name that ``make db-server-url SERVER=`` and the firewall
    targets expect. Anything else (local Docker, other hosts) yields None.
    """
    try:
        host = (urlsplit(settings.database_url).hostname or "").lower()
    except ValueError:
        return None
    if host.endswith(_AZURE_PG_SUFFIX):
        name = host[: -len(_AZURE_PG_SUFFIX)]
        if re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
            return name
    return None


def _howto_lines(export_args: str | None) -> list[str]:
    """The copy-pasteable command block shared by the text and HTML bodies."""
    server = _prod_server_name()
    server_arg = server or _SERVER_PLACEHOLDER
    lines = [
        "make az-pg-add-ip",
        "export PGPASSWORD='<database admin password>'",
        f'export DATABASE_URL="$(make -s db-server-url SERVER={server_arg})"',
    ]
    if export_args:
        lines.append(f'make export-feedback ARGS="{export_args}"')
    else:
        lines.append('make export-feedback ARGS="--help"  # id missing: pick a selector')
    # az-pg-add-ip names the firewall rule after the server.
    lines.append(f"make az-pg-remove-ip RULE={server_arg}")
    return lines


def _howto_hint(server_known: bool) -> str:
    return (
        ""
        if server_known
        else "Replace <server> with the production server name: run `make db-server-url` "
        "without SERVER, or check deployment/terraform.tfvars."
    )


def _howto_text(export_args: str | None, until: str) -> str:
    hint = _howto_hint(_prod_server_name() is not None)
    out = [
        "How to read the full text",
        "-------------------------",
        f"Text available until {until} (deleted automatically after that).",
        "From the repository root, with `az login` done:",
        "",
        *_howto_lines(export_args),
        "",
    ]
    if hint:
        out.append(hint)
    out.append(f"Details: {EXPORT_HOWTO_URL}")
    return "\n".join(out)


def _howto_html(export_args: str | None, until: str) -> str:
    hint = _howto_hint(_prod_server_name() is not None)
    commands = "<br>".join(_esc(line) for line in _howto_lines(export_args))
    hint_html = f"<p>{_esc(hint)}</p>" if hint else ""
    return (
        "<h3>How to read the full text</h3>"
        f"<p>Text available until <strong>{_esc(until)}</strong> "
        "(deleted automatically after that).</p>"
        "<p>From the repository root, with <code>az login</code> done:</p>"
        '<pre style="background:#f5f5f5; padding:12px; border-radius:6px; '
        f'font-size:13px; white-space:pre-wrap;">{commands}</pre>'
        f"{hint_html}"
        f'<p><a href="{EXPORT_HOWTO_URL}">How to export feedback</a></p>'
    )


class EmailService:
    """Service for sending email notifications via SMTP2GO API."""

    def __init__(self):
        self.enabled = settings.smtp2go_enabled
        self.api_key = settings.smtp2go_api_key
        self.sender_email = settings.smtp2go_sender_email
        self.sender_name = settings.smtp2go_sender_name

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
        reply_to: str | None = None,
    ) -> bool:
        """
        Send an email via SMTP2GO HTTP API.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_text: Plain text body
            body_html: Optional HTML body
            reply_to: Optional reply-to email address

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Email disabled, skipping send", extra={"to": to_email})
            return False

        if not self.api_key:
            logger.warning(
                "SMTP2GO API key not configured",
                extra={"to": to_email},
            )
            return False

        try:
            payload = {
                "api_key": self.api_key,
                "to": [to_email],
                "sender": f"{self.sender_name} <{self.sender_email}>",
                "subject": subject,
                "text_body": body_text,
            }

            if body_html:
                payload["html_body"] = body_html

            if reply_to:
                payload["custom_headers"] = [{"header": "Reply-To", "value": reply_to}]

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(SMTP2GO_API_URL, json=payload)

            if response.status_code == 200:
                result = response.json()
                if result.get("data", {}).get("succeeded", 0) > 0:
                    logger.info(
                        "Email sent successfully",
                        extra={"to": to_email, "subject": subject},
                    )
                    return True
                else:
                    logger.error(
                        "SMTP2GO API returned failure",
                        extra={
                            "to": to_email,
                            "response": result,
                        },
                    )
                    return False
            else:
                logger.error(
                    "SMTP2GO API request failed",
                    extra={
                        "status_code": response.status_code,
                        "to": to_email,
                        "response": response.text[:500],
                    },
                )
                return False

        except httpx.TimeoutException as e:
            logger.error(
                "SMTP2GO API timeout",
                extra={"error": str(e), "to": to_email},
            )
            return False
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error sending email",
                extra={"error": str(e), "to": to_email, "subject": subject},
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error sending email",
                extra={"error": str(e), "type": type(e).__name__, "to": to_email},
            )
            return False

    async def send_contact_notification(
        self,
        subject_type: str,
        contact_id: int | None = None,
        has_reply_email: bool = False,
        created_at: datetime | None = None,
    ) -> bool:
        """
        Send an identifiers-only notification for a new contact form submission.

        BITB-329: the e-mail never carries the message, the sender's address or the user
        agent, and sets no ``Reply-To``. The full text is read with ``make export-feedback``
        while it still exists (``CONTACT_RETENTION_DAYS``); the body says exactly how.

        Args:
            subject_type: Type of contact (spiritual, bug, feature, feedback, other)
            contact_id: Row id of the stored submission
            has_reply_email: Whether the sender left a reply address (yes/no only)
            created_at: When the submission was stored

        Returns:
            True if sent successfully
        """
        to_email = settings.contact_notification_email
        subject_label = _esc(subject_type.title())
        subject = f"[Vox Quieta] New {subject_type.title()} Submission"
        created = created_at or datetime.now(UTC)
        until = _text_until(created, settings.contact_retention_days)
        export_args = f"--contacts --id {contact_id}" if contact_id is not None else None

        body_text = f"""
New contact form submission received (identifiers only, no message text):

Type: {subject_type.title()}
Submission ID: {contact_id if contact_id is not None else 'Unknown'}
Reply email left: {'yes' if has_reply_email else 'no'}
Received: {created.isoformat()}

{_howto_text(export_args, until)}
        """.strip()

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #5c6ac4;">New Contact Form Submission</h2>
    <p>Identifiers only: the message and the sender's address are not in this email.</p>

    <table style="border-collapse: collapse; margin: 20px 0;">
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Type:</td>
            <td style="padding: 8px;">{subject_label}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Submission ID:</td>
            <td style="padding: 8px;">{contact_id if contact_id is not None else 'Unknown'}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Reply email left:</td>
            <td style="padding: 8px;">{'yes' if has_reply_email else 'no'}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Received:</td>
            <td style="padding: 8px;">{_esc(created.isoformat())}</td>
        </tr>
    </table>

    {_howto_html(export_args, until)}
</body>
</html>
        """.strip()

        # No reply_to: the sender's address stays in the database (BITB-329).
        return await self.send_email(to_email, subject, body_text, body_html)

    async def send_feedback_notification(
        self,
        rating: str,
        message_id: str | None = None,
        has_comment: bool = False,
        verses_cited: list[str] | None = None,
        model_used: str | None = None,
        response_time_ms: int | None = None,
        reason: str | None = None,
        created_at: datetime | None = None,
    ) -> bool:
        """
        Send an identifiers-only notification for feedback that warrants attention.

        Sends for negative feedback, or positive feedback with a comment (the caller
        decides when to invoke this). BITB-329: the e-mail never carries the user's
        question, the AI reply or the comment; the body says exactly how to read them with
        ``make export-feedback`` while they still exist
        (``FEEDBACK_TEXT_RETENTION_DAYS``).

        Args:
            rating: positive or negative
            message_id: Chat message UUID (the export selector)
            has_comment: Whether the user wrote a comment (yes/no only)
            verses_cited: Optional list of verse references
            model_used: LLM model that generated the response
            response_time_ms: Response generation time in ms
            reason: Optional category of what went wrong (negative feedback)
            created_at: When the feedback was stored

        Returns:
            True if sent successfully
        """
        to_email = settings.contact_notification_email
        rating_label = "Negative" if rating == "negative" else "Positive"
        subject = f"[Vox Quieta] {rating_label} Feedback Received"
        created = created_at or datetime.now(UTC)
        until = _text_until(created, settings.feedback_text_retention_days)
        valid_id = _valid_uuid(message_id)
        export_args = f"--message-id {valid_id}" if valid_id else None

        verses_str = ", ".join(verses_cited) if verses_cited else "None"
        comment_str = "yes" if has_comment else "no"
        colour = "#c0392b" if rating == "negative" else "#27ae60"

        body_text = f"""
{rating_label} feedback received on a response (identifiers only, no message text):

Reason: {reason or 'Not specified'}
Comment left: {comment_str}

---
Metadata:
Model: {model_used or 'Not specified'}
Response time (ms): {response_time_ms if response_time_ms is not None else 'Not specified'}
Verses cited: {verses_str}
Message ID: {message_id or 'Not specified'}
Received: {created.isoformat()}

{_howto_text(export_args, until)}
        """.strip()

        reason_html = (
            '<h3>Reason</h3><div style="display:inline-block; background:#e8e8e8; '
            f'padding:4px 10px; border-radius:12px; font-size:13px;">{_esc(reason)}</div>'
            if reason
            else ""
        )

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: {colour};">{rating_label} Feedback Received</h2>
    <p>Identifiers only: the question, the AI response and any comment are not in this email.</p>

    {reason_html}

    <h3>Metadata</h3>
    <table style="border-collapse: collapse; margin: 10px 0;">
        <tr>
            <td style="padding: 6px 12px; font-weight: bold; background: #f5f5f5;">Comment left</td>
            <td style="padding: 6px 12px;">{comment_str}</td>
        </tr>
        <tr>
            <td style="padding: 6px 12px; font-weight: bold; background: #f5f5f5;">Model</td>
            <td style="padding: 6px 12px;">{_esc(model_used) if model_used else '<em>Not specified</em>'}</td>
        </tr>
        <tr>
            <td style="padding: 6px 12px; font-weight: bold; background: #f5f5f5;">Response time (ms)</td>
            <td style="padding: 6px 12px;">{response_time_ms if response_time_ms is not None else '<em>Not specified</em>'}</td>
        </tr>
        <tr>
            <td style="padding: 6px 12px; font-weight: bold; background: #f5f5f5;">Verses cited</td>
            <td style="padding: 6px 12px;">{_esc(verses_str)}</td>
        </tr>
        <tr>
            <td style="padding: 6px 12px; font-weight: bold; background: #f5f5f5;">Message ID</td>
            <td style="padding: 6px 12px;">{_esc(message_id) if message_id else '<em>Not specified</em>'}</td>
        </tr>
        <tr>
            <td style="padding: 6px 12px; font-weight: bold; background: #f5f5f5;">Received</td>
            <td style="padding: 6px 12px;">{_esc(created.isoformat())}</td>
        </tr>
    </table>

    {_howto_html(export_args, until)}
</body>
</html>
        """.strip()

        return await self.send_email(to_email, subject, body_text, body_html)


# Singleton instance
email_service = EmailService()
