"""
Scripture API routes - Bible data and search endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from providers import EmbeddingProviderDep
from scripture import (
    DbSession,
    ScriptureRepository,
    ScriptureSearchService,
    SearchResults,
    VerseResult,
)

router = APIRouter(prefix="/scripture", tags=["scripture"])


class BooksResponse(BaseModel):
    """List of all Bible books."""

    books: list[dict]


class ChapterResponse(BaseModel):
    """Verses in a chapter."""

    book: str
    chapter: int
    verses: list[VerseResult]


# ==================== Books ====================


@router.get("/books", response_model=BooksResponse)
async def get_books(db: DbSession):
    """Get all Bible books in order."""
    repo = ScriptureRepository(db)
    books = await repo.get_all_books()

    return BooksResponse(
        books=[
            {
                "id": b.id,
                "name": b.name,
                "abbreviation": b.abbreviation,
                "testament": b.testament,
                "position": b.position,
            }
            for b in books
        ]
    )


# ==================== Verses ====================


@router.get("/verse/{book}/{chapter}/{verse}", response_model=VerseResult)
async def get_verse(
    book: str, chapter: int, verse: int, db: DbSession, embedding: EmbeddingProviderDep
):
    """Get a specific verse by reference."""
    service = ScriptureSearchService(db, embedding)
    result = await service.get_verse(book, chapter, verse)

    if not result:
        raise HTTPException(status_code=404, detail=f"Verse not found: {book} {chapter}:{verse}")

    return result


@router.get("/chapter/{book}/{chapter}", response_model=ChapterResponse)
async def get_chapter(book: str, chapter: int, db: DbSession):
    """Get all verses in a chapter."""
    repo = ScriptureRepository(db)
    verses = await repo.get_chapter_verses(book, chapter)

    if not verses:
        raise HTTPException(status_code=404, detail=f"Chapter not found: {book} {chapter}")

    return ChapterResponse(
        book=book,
        chapter=chapter,
        verses=[
            VerseResult(
                reference=v.reference,
                text=v.text,
                book=v.book.name,
                chapter=v.chapter_number,
                verse=v.verse_number,
            )
            for v in verses
        ],
    )


@router.get("/range/{book}/{chapter}/{start_verse}/{end_verse}")
async def get_verse_range(
    book: str,
    chapter: int,
    start_verse: int,
    end_verse: int,
    db: DbSession,
    embedding: EmbeddingProviderDep,
):
    """Get a range of verses (e.g., John 3:16-21)."""
    service = ScriptureSearchService(db, embedding)
    verses = await service.get_verse_range(book, chapter, start_verse, end_verse)

    if not verses:
        raise HTTPException(
            status_code=404, detail=f"Verses not found: {book} {chapter}:{start_verse}-{end_verse}"
        )

    return {"verses": verses}


# ==================== Search ====================


@router.get("/search", response_model=SearchResults)
async def search_scripture(
    q: str = Query(..., min_length=2, description="Search query"),
    max_verses: int = Query(5, ge=1, le=20),
    max_passages: int = Query(2, ge=0, le=5),
    db: DbSession = None,
    embedding: EmbeddingProviderDep = None,
):
    """
    Semantic search for relevant scripture.

    Search using natural language queries like:
    - "I'm feeling anxious about my future"
    - "verses about forgiveness"
    - "comfort for grief"
    """
    service = ScriptureSearchService(db, embedding)

    results = await service.search(query=q, max_verses=max_verses, max_passages=max_passages)

    return results


@router.get("/search/text")
async def search_text(
    q: str = Query(..., min_length=2, description="Text to search"),
    limit: int = Query(20, ge=1, le=100),
    db: DbSession = None,
    embedding: EmbeddingProviderDep = None,
):
    """
    Simple text search in verse content.

    Searches for exact text matches (case-insensitive).
    """
    service = ScriptureSearchService(db, embedding)
    verses = await service.text_search(q, limit)

    return {"query": q, "verses": verses}


# ==================== Stats ====================


@router.get("/stats")
async def get_stats(db: DbSession):
    """Get database statistics."""
    repo = ScriptureRepository(db)
    return await repo.get_stats()
