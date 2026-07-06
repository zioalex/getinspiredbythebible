"""
Feedback repository - Database operations for feedback and contact submissions.
"""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utils.db_retry import run_with_disconnect_retry

from .models import ContactRequest, ContactSubmission, Feedback, FeedbackRequest


class FeedbackRepository:
    """Repository for feedback database operations."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def save_feedback(self, request: FeedbackRequest) -> Feedback:
        """
        Save message feedback to the database.

        The commit/refresh is retried once on a transient DB disconnect via
        run_with_disconnect_retry (utils/db_retry.py). Note: this repository is
        constructed with a single request-scoped session (self.db), so a retry
        re-runs add/commit/refresh against the same session object rather than a
        fresh one — SQLAlchemy's pool_pre_ping + connection invalidation means the
        session transparently gets a new underlying connection on the next
        operation, which is sufficient here since nothing was flushed before the
        failure.

        Args:
            request: FeedbackRequest with rating and message details

        Returns:
            Created Feedback record
        """

        async def _do_save() -> Feedback:
            feedback = Feedback(
                message_id=UUID(request.message_id),
                session_id=request.session_id,
                rating=request.rating,
                comment=request.comment,
                user_message=request.user_message,
                assistant_response=request.assistant_response,
                verses_cited=request.verses_cited,
                model_used=request.model_used,
                response_time_ms=request.response_time_ms,
                reason=request.reason,
                created_at=datetime.now(UTC),
            )

            self.db.add(feedback)
            await self.db.commit()
            await self.db.refresh(feedback)

            return feedback

        return await run_with_disconnect_retry(_do_save, op_name="save_feedback")

    async def save_contact(self, request: ContactRequest) -> ContactSubmission:
        """
        Save contact form submission to the database.

        The commit/refresh is retried once on a transient DB disconnect via
        run_with_disconnect_retry (utils/db_retry.py); see save_feedback's
        docstring for the same-session retry note.

        Args:
            request: ContactRequest with message details

        Returns:
            Created ContactSubmission record
        """

        async def _do_save() -> ContactSubmission:
            contact = ContactSubmission(
                email=request.email,
                subject=request.subject,
                message=request.message,
                session_id=request.session_id,
                user_agent=request.user_agent,
                status="new",
                created_at=datetime.now(UTC),
            )

            self.db.add(contact)
            await self.db.commit()
            await self.db.refresh(contact)

            return contact

        return await run_with_disconnect_retry(_do_save, op_name="save_contact")

    async def get_feedback_by_message_id(self, message_id: str) -> Feedback | None:
        """
        Get feedback for a specific message ID.

        Args:
            message_id: The message UUID

        Returns:
            Feedback record if found, None otherwise
        """
        result = await self.db.execute(
            select(Feedback).where(Feedback.message_id == UUID(message_id))
        )
        return cast(Feedback | None, result.scalar_one_or_none())
