"""
Feedback API routes - Endpoints for feedback and contact form submissions.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from feedback import FeedbackRepository
from feedback.models import ContactRequest, ContactResponse, FeedbackRequest, FeedbackResponse
from scripture import get_db_session
from utils.email_service import email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


async def get_feedback_repository(
    db: AsyncSession = Depends(get_db_session),
) -> FeedbackRepository:
    """Dependency to get feedback repository."""
    return FeedbackRepository(db)


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    repo: FeedbackRepository = Depends(get_feedback_repository),
):
    """
    Submit feedback for a chat message (thumbs up/down).

    This endpoint logs the user's feedback along with the message content
    for quality improvement purposes.

    **Privacy Notice**: By submitting feedback, the user's message and the AI
    response will be logged to help improve the service.
    """
    logger.info(
        "Feedback submission received",
        extra={
            "message_id": request.message_id,
            "rating": request.rating,
            "has_comment": bool(request.comment),
        },
    )

    try:
        feedback = await repo.save_feedback(request)
        logger.info(
            "Feedback saved successfully",
            extra={"feedback_id": feedback.id, "rating": feedback.rating},
        )

        # Send email notification for negative feedback
        if request.rating == "negative":
            email_service.send_feedback_notification(
                rating=request.rating,
                comment=request.comment,
                user_message=request.user_message,
                assistant_response=request.assistant_response,
            )

        return FeedbackResponse(
            id=feedback.id,
            message_id=str(feedback.message_id),
            rating=feedback.rating,
            created_at=feedback.created_at,
        )
    except ValueError as e:
        logger.warning(
            "Invalid feedback request",
            extra={"error": str(e), "message_id": request.message_id},
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Failed to save feedback",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "message_id": request.message_id,
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {str(e)}")


@router.post("/contact", response_model=ContactResponse)
async def submit_contact(
    request: ContactRequest,
    repo: FeedbackRepository = Depends(get_feedback_repository),
):
    """
    Submit a general contact form message.

    Categories:
    - bug: Report a bug or issue
    - feature: Request a new feature
    - feedback: General feedback about the service
    - other: Other inquiries
    """
    logger.info(
        "Contact form submission received",
        extra={
            "subject": request.subject,
            "has_email": bool(request.email),
            "message_length": len(request.message),
        },
    )

    try:
        contact = await repo.save_contact(request)
        logger.info(
            "Contact submission saved",
            extra={"contact_id": contact.id, "subject": contact.subject},
        )

        # Send email notification
        email_sent = email_service.send_contact_notification(
            subject_type=request.subject,
            message=request.message,
            reply_email=request.email,
            user_agent=request.user_agent,
        )

        if email_sent:
            logger.info("Contact notification email sent")
        else:
            logger.debug("Contact notification email not sent (disabled or failed)")

        return ContactResponse(
            id=contact.id,
            subject=contact.subject,
            created_at=contact.created_at,
        )
    except Exception as e:
        logger.error(
            "Failed to save contact submission",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "subject": request.subject,
            },
        )
        raise HTTPException(status_code=500, detail=f"Failed to save contact: {str(e)}")
