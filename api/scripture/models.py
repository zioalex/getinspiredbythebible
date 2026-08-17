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

# Aliased: Verse and Passage both declare a column named `text`, which shadows a
# bare `text` import inside the class body (TypeError: 'MappedColumn' object is
# not callable).
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import TSVECTOR
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
    # server_default mirrors what is actually deployed (scripts/init.sql). Without
    # it the ORM claims a column has no database-level default while production
    # has one, which `alembic check` reports as drift forever -- see BITB-093.
    license: Mapped[str] = mapped_column(
        String(100), default="Public Domain", server_default=sql_text("'Public Domain'")
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=sql_text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=sql_text("CURRENT_TIMESTAMP")
    )

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
        # Deployed with a database-level default too (scripts/init.sql) -- see BITB-093.
        server_default=sql_text("'kjv'"),
    )

    # Vector embedding for semantic search
    embedding: Mapped[Optional[Vector]] = mapped_column(
        Vector(settings.embedding_dimensions), nullable=True
    )

    # The persisted full-text search vector lives in `VerseTsv`, deliberately
    # not as a column here -- see that class and Alembic r0004 (BITB-096).

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


class VerseTsv(Base):
    """Persisted ``simple`` full-text search vector for each verse (BITB-096).

    A side table rather than a column on ``verses`` because adding a ``STORED``
    generated column rewrites the whole table under ``ACCESS EXCLUSIVE`` -- a
    45-minute production outage on 2026-08-17 -- and because rewriting
    ``verses`` rows also churns ``idx_verse_embedding_hnsw`` over its 1536-dim
    vectors. Populating a separate table costs neither. See Alembic ``r0004``.

    Keeping the tsvector off ``Verse`` has a second benefit worth preserving:
    ``search_verses_text`` issues ``select(Verse)``, which emits every mapped
    column, so a tsvector column there makes *every verse read* depend on the
    migration having run. That coupling is what turned a slow migration into a
    total outage. Nothing here is mapped onto ``Verse``, and there is
    intentionally no ``relationship()`` between the two.

    Maintained by the ``verses_tsv_sync`` trigger (also ``r0004``), so the app
    never writes it; deletes are handled by ``ON DELETE CASCADE``.
    """

    __tablename__ = "verse_tsv"

    verse_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("verses.id", ondelete="CASCADE"),
        primary_key=True,
    )
    text_tsv: Mapped[str] = mapped_column(TSVECTOR, nullable=False)

    __table_args__ = (Index("idx_verse_tsv_tsv", "text_tsv", postgresql_using="gin"),)

    def __repr__(self) -> str:
        return f"<VerseTsv(verse_id={self.verse_id})>"


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
