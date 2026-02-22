"""
Feedback models - Pydantic for API and SQLAlchemy for database.
"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


# ==================== Pydantic Models (API) ====================


class FeedbackRequest(BaseModel):
    """Request model for submitting message feedback (thumbs up/down)."""

    model_config = ConfigDict(protected_namespaces=())

    message_id: str = Field(..., description="Unique ID of the chat message")
    rating: Literal["positive", "negative"] = Field(..., description="Rating: positive or negative")
    comment: str | None = Field(None, description="Optional user comment about the response")
    user_message: str = Field(..., description="The user's original question")
    assistant_response: str = Field(..., description="The AI's response text")
    verses_cited: list[str] | None = Field(None, description="Array of verse references used")
    model_used: str | None = Field(None, description="LLM model that generated the response")
    response_time_ms: int | None = Field(None, description="Response generation time in ms")
    session_id: str | None = Field(None, description="Optional session identifier")


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    id: int
    message_id: str
    rating: str
    created_at: datetime


class ContactRequest(BaseModel):
    """Request model for contact form submission."""

    email: str | None = Field(None, description="Optional reply email address")
    subject: Literal["spiritual", "bug", "feature", "feedback", "other"] = Field(
        ..., description="Subject category"
    )
    message: str = Field(..., min_length=1, description="The user's message")
    session_id: str | None = Field(None, description="Optional session identifier")
    user_agent: str | None = Field(None, description="Browser/device info for bug reports")


class ContactResponse(BaseModel):
    """Response model for contact form submission."""

    id: int
    subject: str
    created_at: datetime


# ==================== SQLAlchemy Models (Database) ====================


class Feedback(Base):
    """
    Message feedback (thumbs up/down) stored in the database.
    """

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    message_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rating: Mapped[str] = mapped_column(String(10))  # 'positive' or 'negative'
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assistant_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verses_cited: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, rating='{self.rating}', message_id='{self.message_id}')>"


class ContactSubmission(Base):
    """
    General contact form submissions stored in the database.
    """

    __tablename__ = "contact_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(
        String(50)
    )  # 'spiritual', 'bug', 'feature', 'feedback', 'other'
    message: Mapped[str] = mapped_column(Text)
    session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="new"
    )  # 'new', 'read', 'replied', 'resolved'

    def __repr__(self) -> str:
        return (
            f"<ContactSubmission(id={self.id}, subject='{self.subject}', status='{self.status}')>"
        )
