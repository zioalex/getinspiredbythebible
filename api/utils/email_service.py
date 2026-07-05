"""
Email service for sending notifications via SMTP2GO HTTP API.

Uses SMTP2GO's REST API with API key authentication.
"""

import httpx

from config import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)

SMTP2GO_API_URL = "https://api.smtp2go.com/v3/email/send"


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
        message: str,
        reply_email: str | None = None,
        user_agent: str | None = None,
    ) -> bool:
        """
        Send notification for new contact form submission.

        Args:
            subject_type: Type of contact (bug, feature, feedback, other)
            message: User's message
            reply_email: Optional reply-to email
            user_agent: Optional browser info

        Returns:
            True if sent successfully
        """
        to_email = settings.contact_notification_email

        subject = f"[Vox Quieta] New {subject_type.title()} Submission"

        body_text = f"""
New contact form submission received:

Type: {subject_type.title()}
Reply Email: {reply_email or 'Not provided'}

Message:
{message}

---
User Agent: {user_agent or 'Not provided'}
        """.strip()

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: #5c6ac4;">New Contact Form Submission</h2>

    <table style="border-collapse: collapse; margin: 20px 0;">
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Type:</td>
            <td style="padding: 8px;">{subject_type.title()}</td>
        </tr>
        <tr>
            <td style="padding: 8px; font-weight: bold; background: #f5f5f5;">Reply Email:</td>
            <td style="padding: 8px;">{reply_email or '<em>Not provided</em>'}</td>
        </tr>
    </table>

    <h3>Message:</h3>
    <div style="background: #f9f9f9; padding: 15px; border-left: 4px solid #5c6ac4; margin: 10px 0;">
        {message.replace(chr(10), '<br>')}
    </div>

    <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
    <p style="font-size: 12px; color: #888;">
        User Agent: {user_agent or 'Not provided'}
    </p>
</body>
</html>
        """.strip()

        return await self.send_email(to_email, subject, body_text, body_html, reply_to=reply_email)

    async def send_feedback_notification(
        self,
        rating: str,
        comment: str | None,
        user_message: str,
        assistant_response: str,
        message_id: str | None = None,
        verses_cited: list[str] | None = None,
        model_used: str | None = None,
        response_time_ms: int | None = None,
        reason: str | None = None,
    ) -> bool:
        """
        Send notification for feedback that warrants maintainer attention.

        Sends for negative feedback, or positive feedback with a comment.
        The caller decides when to invoke this; this method renders whatever
        rating is passed.

        Args:
            rating: positive or negative
            comment: User's optional comment
            user_message: Original user question
            assistant_response: AI response that received feedback
            message_id: Optional chat message UUID
            verses_cited: Optional list of verse references
            model_used: LLM model that generated the response
            response_time_ms: Response generation time in ms
            reason: Optional category of what went wrong (negative feedback)

        Returns:
            True if sent successfully
        """
        to_email = settings.contact_notification_email
        rating_label = "Negative" if rating == "negative" else "Positive"
        subject = f"[Vox Quieta] {rating_label} Feedback Received"

        verses_str = ", ".join(verses_cited) if verses_cited else "None"

        body_text = f"""
{rating_label} feedback received on a response:

User Comment: {comment or 'No comment provided'}
Reason: {reason or 'Not specified'}

---
Original Question:
{user_message}

---
AI Response:
{assistant_response}

---
Metadata:
Model: {model_used or 'Not specified'}
Response time (ms): {response_time_ms if response_time_ms is not None else 'Not specified'}
Verses cited: {verses_str}
Message ID: {message_id or 'Not specified'}
        """.strip()

        body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <h2 style="color: {'#c0392b' if rating == 'negative' else '#27ae60'};">{rating_label} Feedback Received</h2>

    <h3>Comment</h3>
    <div style="background: #f9f9f9; padding: 15px; border-left: 4px solid {'#c0392b' if rating == 'negative' else '#27ae60'}; margin: 10px 0;">
        {(comment or '<em>No comment provided</em>').replace(chr(10), '<br>')}
    </div>

    {f'<h3>Reason</h3><div style="display:inline-block; background:#e8e8e8; padding:4px 10px; border-radius:12px; font-size:13px;">{reason}</div>' if reason else ''}

    <h3>Original Question</h3>
    <div style="background: #f9f9f9; padding: 15px; border-left: 4px solid #5c6ac4; margin: 10px 0;">
        {user_message.replace(chr(10), '<br>')}
    </div>

    <h3>AI Response</h3>
    <div style="background: #f9f9f9; padding: 15px; border-left: 4px solid #5c6ac4; margin: 10px 0;">
        {assistant_response.replace(chr(10), '<br>')}
    </div>

    <h3>Metadata</h3>
    <table style="border-collapse: collapse; margin: 10px 0;">
        <tr>
            <td style="padding: 6px 12px; font-weight: bold; background: #f5f5f5;">Model</td>
            <td style="padding: 6px 12px;">{model_used or '<em>Not specified</em>'}</td>
        </tr>
        <tr>
            <td style="padding: 6px 12px; font-weight: bold; background: #f5f5f5;">Response time (ms)</td>
            <td style="padding: 6px 12px;">{response_time_ms if response_time_ms is not None else '<em>Not specified</em>'}</td>
        </tr>
        <tr>
            <td style="padding: 6px 12px; font-weight: bold; background: #f5f5f5;">Verses cited</td>
            <td style="padding: 6px 12px;">{verses_str}</td>
        </tr>
        <tr>
            <td style="padding: 6px 12px; font-weight: bold; background: #f5f5f5;">Message ID</td>
            <td style="padding: 6px 12px;">{message_id or '<em>Not specified</em>'}</td>
        </tr>
    </table>
</body>
</html>
        """.strip()

        return await self.send_email(to_email, subject, body_text, body_html)


# Singleton instance
email_service = EmailService()
