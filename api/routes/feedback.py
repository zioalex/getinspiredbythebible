"""
Feedback API routes - Endpoints for feedback and contact form submissions.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from feedback import FeedbackRepository
from feedback.models import (
    ContactRequest,
    ContactResponse,
    FeedbackRequest,
    FeedbackResponse,
)
from scripture import get_db_session
from utils.email_service import email_service
from utils.logging_config import get_logger
from utils.metrics import contact_form_counter, feedback_counter
from utils.turnstile import require_turnstile

logger = get_logger(__name__)

router = APIRouter(prefix="/feedback", tags=["feedback"])


async def get_feedback_repository(
    db: AsyncSession = Depends(get_db_session),
) -> FeedbackRepository:
    """Dependency to get feedback repository."""
    return FeedbackRepository(db)


@router.post("", response_model=FeedbackResponse, dependencies=[Depends(require_turnstile)])
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

        # Record metrics
        feedback_counter.add(1, {"rating": request.rating})

        logger.info(
            "Feedback saved successfully",
            extra={"feedback_id": feedback.id, "rating": feedback.rating},
        )

        # Send email notification for negative feedback, or positive with a comment
        should_notify = request.rating == "negative" or (
            request.rating == "positive" and bool(request.comment)
        )
        if should_notify:
            await email_service.send_feedback_notification(
                rating=request.rating,
                comment=request.comment,
                user_message=request.user_message,
                assistant_response=request.assistant_response,
                message_id=request.message_id,
                verses_cited=request.verses_cited,
                model_used=request.model_used,
                response_time_ms=request.response_time_ms,
                reason=request.reason,
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
        raise HTTPException(
            status_code=500, detail="Failed to save feedback. Please try again."
        ) from e


@router.post("/contact", response_model=ContactResponse, dependencies=[Depends(require_turnstile)])
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

        # Record metrics
        contact_form_counter.add(1, {"subject": request.subject})

        logger.info(
            "Contact submission saved",
            extra={"contact_id": contact.id, "subject": contact.subject},
        )

        # Send email notification
        email_sent = await email_service.send_contact_notification(
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
        raise HTTPException(
            status_code=500, detail="Failed to save contact. Please try again."
        ) from e
