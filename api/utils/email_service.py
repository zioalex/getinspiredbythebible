"""
Email service for sending notifications via SMTP2GO.

Handles contact form notifications and feedback alerts.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending email notifications."""

    def __init__(self):
        self.enabled = settings.smtp_enabled
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.from_email = settings.smtp_from_email
        self.from_name = settings.smtp_from_name

    def _create_smtp_connection(self) -> smtplib.SMTP:
        """Create and authenticate SMTP connection."""
        smtp = smtplib.SMTP(self.host, self.port, timeout=10)
        smtp.starttls()
        if self.username and self.password:
            smtp.login(self.username, self.password)
        return smtp

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> bool:
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_text: Plain text body
            body_html: Optional HTML body

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Email disabled, skipping send", extra={"to": to_email})
            return False

        if not self.username or not self.password:
            logger.warning(
                "SMTP credentials not configured",
                extra={"host": self.host, "to": to_email},
            )
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email

            # Add plain text part
            msg.attach(MIMEText(body_text, "plain"))

            # Add HTML part if provided
            if body_html:
                msg.attach(MIMEText(body_html, "html"))

            with self._create_smtp_connection() as smtp:
                smtp.sendmail(self.from_email, [to_email], msg.as_string())

            logger.info(
                "Email sent successfully",
                extra={"to": to_email, "subject": subject},
            )
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(
                "SMTP authentication failed",
                extra={"error": str(e), "host": self.host, "username": self.username},
            )
            return False
        except smtplib.SMTPException as e:
            logger.error(
                "SMTP error sending email",
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

        return self.send_email(to_email, subject, body_text, body_html)

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
