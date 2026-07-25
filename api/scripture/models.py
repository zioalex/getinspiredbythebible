"""
Scripture database models using SQLAlchemy.

Defines the schema for storing Bible verses with vector embeddings.
"""

from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from config import settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class Translation(Base):
    """
    Bible translation metadata.

    Stores information about available Bible translations (KJV, Italian, German, etc.)
    """

    __tablename__ = "translations"

    code: Mapped[str] = mapped_column(
        String(20), primary_key=True
    )  # e.g., 'kjv', 'ita1927', 'deu1912'
    name: Mapped[str] = mapped_column(String(100))  # e.g., 'King James Version'
    language: Mapped[str] = mapped_column(String(50))  # e.g., 'English', 'Italian'
    language_code: Mapped[str] = mapped_column(String(10))  # ISO 639-1: 'en', 'it', 'de'
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    license: Mapped[str] = mapped_column(String(100), default="Public Domain")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    verses: Mapped[list["Verse"]] = relationship(back_populates="translation_rel")

    def __repr__(self) -> str:
        return f"<Translation(code='{self.code}', name='{self.name}', language='{self.language}')>"


class Book(Base):
    """
    Bible book (e.g., Genesis, Matthew).
    """

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    abbreviation: Mapped[str] = mapped_column(String(10))
    testament: Mapped[str] = mapped_column(String(20))  # 'old' or 'new'
    position: Mapped[int] = mapped_column(Integer)  # Order in Bible (1-66)

    # Relationships
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
    verses: Mapped[list["Verse"]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Book(name='{self.name}', testament='{self.testament}')>"


class Chapter(Base):
    """
    Bible chapter within a book.
    """

    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    number: Mapped[int] = mapped_column(Integer)

    # Relationships
    book: Mapped["Book"] = relationship(back_populates="chapters")
    verses: Mapped[list["Verse"]] = relationship(
        back_populates="chapter", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("book_id", "number", name="unique_chapter"),)

    def __repr__(self) -> str:
        return f"<Chapter(book_id={self.book_id}, number={self.number})>"


class Verse(Base):
    """
    Individual Bible verse with embedding for semantic search.

    Supports multiple translations (KJV, Italian, German, etc.)
    """

    __tablename__ = "verses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    chapter_id: Mapped[int] = mapped_column(Integer, ForeignKey("chapters.id"))
    chapter_number: Mapped[int] = mapped_column(Integer)
    verse_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    translation: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("translations.code", ondelete="CASCADE"),
        default="kjv",
    )

    # Vector embedding for semantic search
    embedding: Mapped[Optional[Vector]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )

    # Relationships
    book: Mapped["Book"] = relationship(back_populates="verses")
    chapter: Mapped["Chapter"] = relationship(back_populates="verses")
    translation_rel: Mapped["Translation"] = relationship(back_populates="verses")

    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "chapter_number",
            "verse_number",
            "translation",
            name="unique_verse_translation",
        ),
        Index(
            "idx_verse_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("idx_verses_translation", "translation"),
    )

    @property
    def reference(self) -> str:
        """Return the verse reference (e.g., 'John 3:16')."""
        return f"{self.book.name} {self.chapter_number}:{self.verse_number}"

    def __repr__(self) -> str:
        return f"<Verse(reference='{self.reference}', translation='{self.translation}')>"


class Passage(Base):
    """
    Pre-defined passages (multiple verses) for common topics.

    This allows semantic search on meaningful passages rather than
    individual verses, which often lack context.
    """

    __tablename__ = "passages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))  # e.g., "The Lord's Prayer"
    start_book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"))
    start_chapter: Mapped[int] = mapped_column(Integer)
    start_verse: Mapped[int] = mapped_column(Integer)
    end_chapter: Mapped[int] = mapped_column(Integer)
    end_verse: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)  # Full passage text
    topics: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # Comma-separated topics

    # Vector embedding for semantic search
    embedding: Mapped[Optional[Vector]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )

    # Relationships
    book: Mapped["Book"] = relationship()

    __table_args__ = (
        Index(
            "idx_passage_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    @property
    def reference(self) -> str:
        """Return the passage reference."""
        if self.start_chapter == self.end_chapter:
            return f"{self.book.name} {self.start_chapter}:{self.start_verse}-{self.end_verse}"
        return f"{self.book.name} {self.start_chapter}:{self.start_verse}-{self.end_chapter}:{self.end_verse}"

    def __repr__(self) -> str:
        return f"<Passage(title='{self.title}', reference='{self.reference}')>"


# Topic categories for organizing verses
class Topic(Base):
    """
    Topics/themes for categorizing verses.
    """

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("topics.id"), nullable=True
    )

    # Embedding for topic-based search
    embedding: Mapped[Optional[Vector]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )

    # Self-referential relationship for hierarchical topics
    parent: Mapped[Optional["Topic"]] = relationship(remote_side=[id], backref="children")

    __table_args__ = (
        Index(
            "idx_topic_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<Topic(name='{self.name}')>"
