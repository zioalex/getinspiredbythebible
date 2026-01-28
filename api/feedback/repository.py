"""
Feedback repository - Database operations for feedback and contact submissions.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ContactRequest, ContactSubmission, Feedback, FeedbackRequest


class FeedbackRepository:
    """Repository for feedback database operations."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def save_feedback(self, request: FeedbackRequest) -> Feedback:
        """
        Save message feedback to the database.

        Args:
            request: FeedbackRequest with rating and message details

        Returns:
            Created Feedback record
        """
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
            created_at=datetime.now(UTC),
        )

        self.db.add(feedback)
        await self.db.commit()
        await self.db.refresh(feedback)

        return feedback

    async def save_contact(self, request: ContactRequest) -> ContactSubmission:
        """
        Save contact form submission to the database.

        Args:
            request: ContactRequest with message details

        Returns:
            Created ContactSubmission record
        """
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
        return result.scalar_one_or_none()
