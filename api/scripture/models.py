"""
Scripture database models using SQLAlchemy.

Defines the schema for storing Bible verses with vector embeddings.
"""

from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

from config import settings

Base: Any = declarative_base()


class Book(Base):
    """
    Bible book (e.g., Genesis, Matthew).
    """

    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    abbreviation = Column(String(10), nullable=False)
    testament = Column(String(20), nullable=False)  # 'old' or 'new'
    position = Column(Integer, nullable=False)  # Order in Bible (1-66)

    # Relationships
    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")
    verses = relationship("Verse", back_populates="book", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Book(name='{self.name}', testament='{self.testament}')>"


class Chapter(Base):
    """
    Bible chapter within a book.
    """

    __tablename__ = "chapters"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    number = Column(Integer, nullable=False)

    # Relationships
    book = relationship("Book", back_populates="chapters")
    verses = relationship("Verse", back_populates="chapter", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("book_id", "number", name="unique_chapter"),)

    def __repr__(self):
        return f"<Chapter(book_id={self.book_id}, number={self.number})>"


class Verse(Base):
    """
    Individual Bible verse with embedding for semantic search.
    """

    __tablename__ = "verses"

    id = Column(Integer, primary_key=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id"), nullable=False)
    chapter_number = Column(Integer, nullable=False)
    verse_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)

    # Vector embedding for semantic search
    embedding = Column(Vector(settings.embedding_dimensions), nullable=True)

    # Relationships
    book = relationship("Book", back_populates="verses")
    chapter = relationship("Chapter", back_populates="verses")

    __table_args__ = (
        UniqueConstraint("book_id", "chapter_number", "verse_number", name="unique_verse"),
        Index("idx_verse_embedding", "embedding", postgresql_using="ivfflat"),
    )

    @property
    def reference(self) -> str:
        """Return the verse reference (e.g., 'John 3:16')."""
        return f"{self.book.name} {self.chapter_number}:{self.verse_number}"

    def __repr__(self):
        return f"<Verse(reference='{self.reference}')>"


class Passage(Base):
    """
    Pre-defined passages (multiple verses) for common topics.

    This allows semantic search on meaningful passages rather than
    individual verses, which often lack context.
    """

    __tablename__ = "passages"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)  # e.g., "The Lord's Prayer"
    start_book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    start_chapter = Column(Integer, nullable=False)
    start_verse = Column(Integer, nullable=False)
    end_chapter = Column(Integer, nullable=False)
    end_verse = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)  # Full passage text
    topics = Column(String(500), nullable=True)  # Comma-separated topics

    # Vector embedding for semantic search
    embedding = Column(Vector(settings.embedding_dimensions), nullable=True)

    # Relationships
    book = relationship("Book")

    __table_args__ = (Index("idx_passage_embedding", "embedding", postgresql_using="ivfflat"),)

    @property
    def reference(self) -> str:
        """Return the passage reference."""
        if self.start_chapter == self.end_chapter:
            return f"{self.book.name} {self.start_chapter}:{self.start_verse}-{self.end_verse}"
        return f"{self.book.name} {self.start_chapter}:{self.start_verse}-{self.end_chapter}:{self.end_verse}"

    def __repr__(self):
        return f"<Passage(title='{self.title}', reference='{self.reference}')>"


# Topic categories for organizing verses
class Topic(Base):
    """
    Topics/themes for categorizing verses.
    """

    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    parent_id = Column(Integer, ForeignKey("topics.id"), nullable=True)

    # Embedding for topic-based search
    embedding = Column(Vector(settings.embedding_dimensions), nullable=True)

    # Self-referential relationship for hierarchical topics
    parent = relationship("Topic", remote_side=[id], backref="children")

    def __repr__(self):
        return f"<Topic(name='{self.name}')>"
