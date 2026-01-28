"""
Email service for sending notifications via SMTP2GO HTTP API.

Uses SMTP2GO's REST API with API key authentication.
"""

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

SMTP2GO_API_URL = "https://api.smtp2go.com/v3/email/send"


class EmailService:
    """Service for sending email notifications via SMTP2GO API."""

    def __init__(self):
        self.enabled = settings.smtp2go_enabled
        self.api_key = settings.smtp2go_api_key
        self.sender_email = settings.smtp2go_sender_email
        self.sender_name = settings.smtp2go_sender_name

    def send_email(
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

            with httpx.Client(timeout=10.0) as client:
                response = client.post(SMTP2GO_API_URL, json=payload)

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

    def send_contact_notification(
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

        subject = f"[Bible Inspiration] New {subject_type.title()} Submission"

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

        return self.send_email(to_email, subject, body_text, body_html, reply_to=reply_email)

    def send_feedback_notification(
        self,
        rating: str,
        comment: str | None,
        user_message: str,
        assistant_response: str,
    ) -> bool:
        """
        Send notification for negative feedback (for quality monitoring).

        Only sends for negative feedback to alert about potential issues.

        Args:
            rating: positive or negative
            comment: User's optional comment
            user_message: Original user question
            assistant_response: AI response that received feedback

        Returns:
            True if sent successfully
        """
        # Only notify on negative feedback
        if rating != "negative":
            return True

        to_email = settings.contact_notification_email
        subject = "[Bible Inspiration] Negative Feedback Received"

        body_text = f"""
Negative feedback received on a response:

User Comment: {comment or 'No comment provided'}

---
Original Question:
{user_message[:500]}{'...' if len(user_message) > 500 else ''}

---
AI Response:
{assistant_response[:500]}{'...' if len(assistant_response) > 500 else ''}
        """.strip()

        return self.send_email(to_email, subject, body_text)


# Singleton instance
email_service = EmailService()
