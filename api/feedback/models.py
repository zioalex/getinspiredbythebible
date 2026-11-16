"""
Feedback models - Pydantic for API and SQLAlchemy for database.
"""

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints
from sqlalchemy import Boolean, Date, DateTime, Float, Index, Integer, String, Text

# Aliased for the same reason as api/scripture/models.py: `text` is a plausible
# column name, and a bare import would be shadowed inside a class body.
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


# ==================== Pydantic Models (API) ====================


class FeedbackRequest(BaseModel):
    """Request model for submitting message feedback (thumbs up/down)."""

    model_config = ConfigDict(protected_namespaces=())

    message_id: str = Field(..., max_length=128, description="Unique ID of the chat message")
    rating: Literal["positive", "negative"] = Field(..., description="Rating: positive or negative")
    comment: str | None = Field(
        None, max_length=2000, description="Optional user comment about the response"
    )
    user_message: str = Field(..., max_length=2000, description="The user's original question")
    assistant_response: str = Field(..., max_length=20000, description="The AI's response text")
    verses_cited: list[Annotated[str, StringConstraints(max_length=100)]] | None = Field(
        None, max_length=50, description="Array of verse references used"
    )
    # 100 = width of feedback.model_used (String(100)); a longer value would be a DB error
    model_used: str | None = Field(
        None, max_length=100, description="LLM model that generated the response"
    )
    response_time_ms: int | None = Field(None, description="Response generation time in ms")
    session_id: str | None = Field(None, max_length=128, description="Optional session identifier")
    # 40 = width of feedback.reason (String(40)); a longer value would be a DB error
    reason: str | None = Field(
        None, max_length=40, description="Optional category of what went wrong (negative feedback)"
    )


class FeedbackResponse(BaseModel):
    """Response model for feedback submission."""

    id: int
    message_id: str
    rating: str
    created_at: datetime


class ContactRequest(BaseModel):
    """Request model for contact form submission."""

    email: EmailStr = Field(..., description="Reply email address")
    subject: Literal["spiritual", "bug", "feature", "feedback", "other"] = Field(
        ..., description="Subject category"
    )
    message: str = Field(..., min_length=1, max_length=5000, description="The user's message")
    session_id: str | None = Field(None, max_length=128, description="Optional session identifier")
    user_agent: str | None = Field(
        None, max_length=500, description="Browser/device info for bug reports"
    )


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
    # server_default mirrors what is actually deployed (scripts/init.sql,
    # scripts/migrations/001). Without it the ORM claims there is no
    # database-level default while production has one, which `alembic check`
    # reports as drift forever -- see BITB-093.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=sql_text("now()")
    )
    message_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rating: Mapped[str] = mapped_column(String(10))  # 'positive' or 'negative'
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    verses_cited: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(40), nullable=True)

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, rating='{self.rating}', message_id='{self.message_id}')>"


class ContactSubmission(Base):
    """
    General contact form submissions stored in the database.
    """

    __tablename__ = "contact_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=sql_text("now()")
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str] = mapped_column(
        String(50)
    )  # 'spiritual', 'bug', 'feature', 'feedback', 'other'
    message: Mapped[str] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="new", server_default=sql_text("'new'")
    )  # 'new', 'read', 'replied', 'resolved'

    def __repr__(self) -> str:
        return (
            f"<ContactSubmission(id={self.id}, subject='{self.subject}', status='{self.status}')>"
        )


class BlockedMessageSample(Base):
    """
    Privacy-minimal record of a message the safety system blocked.

    Captured to fine-tune the multi-stage filter pipeline (keyword filter,
    OpenAI Moderation, Llama Guard, Azure Content Safety). Designed so a
    single user cannot be re-identified or amplified:

    - No raw IP, user id, or user-agent — only `session_id_hash`.
    - Text is capped (see settings.blocked_sample_max_chars) and deduplicated
      by sha256, so repeats increment `hit_count` instead of adding rows.
    - Rows are deleted after `expires_at` (TTL set from
      settings.blocked_sample_retention_days).
    - Writes are gated by settings.blocked_sample_capture_enabled.
    """

    __tablename__ = "blocked_message_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    stage: Mapped[str] = mapped_column(String(40))
    categories: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    severity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    message_text: Mapped[str] = mapped_column(Text)
    message_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    session_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=1)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_blocked_message_samples_stage_created", "stage", "created_at"),)

    def __repr__(self) -> str:
        return (
            f"<BlockedMessageSample(id={self.id}, stage='{self.stage}', " f"hits={self.hit_count})>"
        )


class TtsEventDaily(Base):
    """
    Daily aggregate of read-aloud client events (BITB-247).

    One row per (day, event, locale, platform, browser, os); ``count`` is
    incremented with an atomic ``INSERT ... ON CONFLICT DO UPDATE``. Every
    dimension is an enum normalized in ``api/main.py`` so cardinality is
    bounded. Never holds text, voice names, user agents, IPs or identifiers.
    """

    __tablename__ = "tts_event_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    event: Mapped[str] = mapped_column(String(32), primary_key=True)
    locale: Mapped[str] = mapped_column(String(8), primary_key=True)
    platform: Mapped[str] = mapped_column(String(16), primary_key=True)
    browser: Mapped[str] = mapped_column(String(16), primary_key=True)
    os: Mapped[str] = mapped_column(String(16), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0, server_default=sql_text("0"))

    def __repr__(self) -> str:
        return (
            f"<TtsEventDaily({self.day} {self.event} {self.locale} "
            f"{self.platform}/{self.browser}/{self.os} = {self.count})>"
        )


class RetrievalMissSample(Base):
    """
    Privacy-safe record of a chat turn where scripture retrieval was weak (BITB-256).

    One row per signature (reasons + intent + language + translation + topics + retrieval mode +
    embedding model);
    repeats increment ``hit_count``. Holds only *derived* signals -- canonical
    topic ids, sanitized expansion keywords, verse references and scores -- and
    **no column holds user or model text**. ``expires_at`` is fixed at first
    insert (never refreshed), so retention is at most
    settings.retrieval_miss_retention_days. Writes are gated by
    settings.retrieval_miss_capture_enabled.
    """

    __tablename__ = "retrieval_miss_samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=sql_text("now()"),
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reasons: Mapped[list[str]] = mapped_column(ARRAY(String(24)))
    intent: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(10))
    translation: Mapped[str] = mapped_column(String(20))
    topics: Mapped[list] = mapped_column(JSONB)
    expansion_terms: Mapped[list] = mapped_column(JSONB)
    top_refs: Mapped[list] = mapped_column(JSONB)
    top_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    cited_outside_pool: Mapped[list] = mapped_column(JSONB)
    retrieval_mode: Mapped[str] = mapped_column(String(24))
    embedding_provider: Mapped[str] = mapped_column(String(32))
    embedding_model: Mapped[str] = mapped_column(String(100))
    session_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signature_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=1, server_default=sql_text("1"))

    __table_args__ = (Index("ix_retrieval_miss_samples_lang_created", "language", "created_at"),)

    def __repr__(self) -> str:
        return (
            f"<RetrievalMissSample(id={self.id}, reasons={self.reasons}, "
            f"lang='{self.language}', hits={self.hit_count})>"
        )
