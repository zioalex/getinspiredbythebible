"""
Feedback models - Pydantic for API and SQLAlchemy for database.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base

Base: Any = declarative_base()


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
    subject: Literal["bug", "feature", "feedback", "other"] = Field(
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

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    message_id = Column(PGUUID(as_uuid=True), nullable=False)
    session_id = Column(String(255), nullable=True)
    rating = Column(String(10), nullable=False)  # 'positive' or 'negative'
    comment = Column(Text, nullable=True)
    user_message = Column(Text, nullable=True)
    assistant_response = Column(Text, nullable=True)
    verses_cited = Column(JSONB, nullable=True)
    model_used = Column(String(100), nullable=True)
    response_time_ms = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<Feedback(id={self.id}, rating='{self.rating}', message_id='{self.message_id}')>"


class ContactSubmission(Base):
    """
    General contact form submissions stored in the database.
    """

    __tablename__ = "contact_submissions"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    email = Column(String(255), nullable=True)
    subject = Column(String(50), nullable=False)  # 'bug', 'feature', 'feedback', 'other'
    message = Column(Text, nullable=False)
    session_id = Column(String(255), nullable=True)
    user_agent = Column(Text, nullable=True)
    status = Column(String(20), default="new")  # 'new', 'read', 'replied', 'resolved'

    def __repr__(self):
        return (
            f"<ContactSubmission(id={self.id}, subject='{self.subject}', status='{self.status}')>"
        )
