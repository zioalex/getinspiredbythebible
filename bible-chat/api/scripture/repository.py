"""
Scripture Repository - Database operations for Bible data.
"""

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Sequence

from .models import Book, Chapter, Verse, Passage, Topic


class ScriptureRepository:
    """
    Repository for scripture database operations.
    
    Provides methods for querying Bible verses, books, and passages.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # ==================== Books ====================
    
    async def get_all_books(self) -> Sequence[Book]:
        """Get all books in order."""
        result = await self.session.execute(
            select(Book).order_by(Book.position)
        )
        return result.scalars().all()
    
    async def get_book_by_name(self, name: str) -> Book | None:
        """Get a book by its name (case-insensitive)."""
        result = await self.session.execute(
            select(Book).where(func.lower(Book.name) == name.lower())
        )
        return result.scalar_one_or_none()
    
    async def get_book_by_id(self, book_id: int) -> Book | None:
        """Get a book by ID."""
        result = await self.session.execute(
            select(Book).where(Book.id == book_id)
        )
        return result.scalar_one_or_none()
    
    # ==================== Verses ====================
    
    async def get_verse(
        self, 
        book_name: str, 
        chapter: int, 
        verse: int
    ) -> Verse | None:
        """Get a specific verse by reference."""
        result = await self.session.execute(
            select(Verse)
            .join(Book)
            .where(
                func.lower(Book.name) == book_name.lower(),
                Verse.chapter_number == chapter,
                Verse.verse_number == verse
            )
            .options(selectinload(Verse.book))
        )
        return result.scalar_one_or_none()
    
    async def get_verses_in_range(
        self,
        book_name: str,
        chapter: int,
        start_verse: int,
        end_verse: int
    ) -> Sequence[Verse]:
        """Get verses in a range (e.g., John 3:16-21)."""
        result = await self.session.execute(
            select(Verse)
            .join(Book)
            .where(
                func.lower(Book.name) == book_name.lower(),
                Verse.chapter_number == chapter,
                Verse.verse_number >= start_verse,
                Verse.verse_number <= end_verse
            )
            .order_by(Verse.verse_number)
            .options(selectinload(Verse.book))
        )
        return result.scalars().all()
    
    async def get_chapter_verses(
        self, 
        book_name: str, 
        chapter: int
    ) -> Sequence[Verse]:
        """Get all verses in a chapter."""
        result = await self.session.execute(
            select(Verse)
            .join(Book)
            .where(
                func.lower(Book.name) == book_name.lower(),
                Verse.chapter_number == chapter
            )
            .order_by(Verse.verse_number)
            .options(selectinload(Verse.book))
        )
        return result.scalars().all()
    
    async def search_verses_text(
        self, 
        query: str, 
        limit: int = 20
    ) -> Sequence[Verse]:
        """Full-text search on verse content."""
        result = await self.session.execute(
            select(Verse)
            .where(Verse.text.ilike(f"%{query}%"))
            .limit(limit)
            .options(selectinload(Verse.book))
        )
        return result.scalars().all()
    
    async def search_verses_semantic(
        self,
        query_embedding: list[float],
        limit: int = 5,
        similarity_threshold: float = 0.5
    ) -> list[tuple[Verse, float]]:
        """
        Semantic search using vector similarity.
        
        Args:
            query_embedding: The embedding vector of the search query
            limit: Maximum results to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of (verse, similarity_score) tuples
        """
        # Using pgvector's cosine distance (1 - cosine_similarity)
        # So we convert to similarity: 1 - distance
        result = await self.session.execute(
            select(
                Verse,
                (1 - Verse.embedding.cosine_distance(query_embedding)).label("similarity")
            )
            .where(Verse.embedding.isnot(None))
            .where(
                (1 - Verse.embedding.cosine_distance(query_embedding)) >= similarity_threshold
            )
            .order_by(Verse.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .options(selectinload(Verse.book))
        )
        return [(row.Verse, row.similarity) for row in result.all()]
    
    # ==================== Passages ====================
    
    async def get_passage_by_id(self, passage_id: int) -> Passage | None:
        """Get a passage by ID."""
        result = await self.session.execute(
            select(Passage)
            .where(Passage.id == passage_id)
            .options(selectinload(Passage.book))
        )
        return result.scalar_one_or_none()
    
    async def search_passages_semantic(
        self,
        query_embedding: list[float],
        limit: int = 3,
        similarity_threshold: float = 0.5
    ) -> list[tuple[Passage, float]]:
        """Semantic search on passages."""
        result = await self.session.execute(
            select(
                Passage,
                (1 - Passage.embedding.cosine_distance(query_embedding)).label("similarity")
            )
            .where(Passage.embedding.isnot(None))
            .where(
                (1 - Passage.embedding.cosine_distance(query_embedding)) >= similarity_threshold
            )
            .order_by(Passage.embedding.cosine_distance(query_embedding))
            .limit(limit)
            .options(selectinload(Passage.book))
        )
        return [(row.Passage, row.similarity) for row in result.all()]
    
    # ==================== Topics ====================
    
    async def get_all_topics(self) -> Sequence[Topic]:
        """Get all topics."""
        result = await self.session.execute(
            select(Topic).order_by(Topic.name)
        )
        return result.scalars().all()
    
    async def search_topics_semantic(
        self,
        query_embedding: list[float],
        limit: int = 5
    ) -> list[tuple[Topic, float]]:
        """Find topics related to a query."""
        result = await self.session.execute(
            select(
                Topic,
                (1 - Topic.embedding.cosine_distance(query_embedding)).label("similarity")
            )
            .where(Topic.embedding.isnot(None))
            .order_by(Topic.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        return [(row.Topic, row.similarity) for row in result.all()]
    
    # ==================== Stats ====================
    
    async def get_stats(self) -> dict:
        """Get database statistics."""
        books_count = await self.session.execute(select(func.count(Book.id)))
        verses_count = await self.session.execute(select(func.count(Verse.id)))
        embedded_count = await self.session.execute(
            select(func.count(Verse.id)).where(Verse.embedding.isnot(None))
        )
        passages_count = await self.session.execute(select(func.count(Passage.id)))
        
        return {
            "books": books_count.scalar_one(),
            "verses": verses_count.scalar_one(),
            "verses_with_embeddings": embedded_count.scalar_one(),
            "passages": passages_count.scalar_one()
        }
