"""
Feedback API routes - Endpoints for feedback and contact form submissions.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from feedback import FeedbackRepository
from feedback.models import ContactRequest, ContactResponse, FeedbackRequest, FeedbackResponse
from scripture import get_db_session

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
    try:
        feedback = await repo.save_feedback(request)
        return FeedbackResponse(
            id=feedback.id,
            message_id=str(feedback.message_id),
            rating=feedback.rating,
            created_at=feedback.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
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
    try:
        contact = await repo.save_contact(request)
        return ContactResponse(
            id=contact.id,
            subject=contact.subject,
            created_at=contact.created_at,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save contact: {str(e)}")
