"""
Scripture API routes - Bible data and search endpoints.
"""

import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel

from providers import EmbeddingProviderDep
from scripture import (
    DbSession,
    ScriptureRepository,
    ScriptureSearchService,
    SearchResults,
    VerseResult,
)
from scripture.repository import QueryTimeoutError
from utils.book_names import LOCALIZED_TO_ENGLISH, get_localized_book_name, normalize_book_name
from utils.language import get_all_translations, get_translation_info, resolve_translation
from utils.logging_config import get_logger
from utils.metrics import scripture_search_counter, scripture_verses_returned

router = APIRouter(prefix="/scripture", tags=["scripture"])
logger = get_logger("routes.scripture")

# Verse text that is empty or contains only punctuation/slashes/whitespace
# (e.g. "////", "---") is a data defect, never real scripture.
_PLACEHOLDER_TEXT_RE = re.compile(r"^[\s\W_]*$", re.UNICODE)


def _is_placeholder_text(text: str | None) -> bool:
    """Return True if verse text is empty or consists only of punctuation/whitespace."""
    if text is None:
        return True
    return bool(_PLACEHOLDER_TEXT_RE.match(text))


class BooksResponse(BaseModel):
    """List of all Bible books."""

    books: list[dict]


class ChapterResponse(BaseModel):
    """Verses in a chapter."""

    book: str
    localized_book: str
    chapter: int
    verses: list[dict]
    translation: str | None = None
    translation_name: str | None = None


# ==================== Translations ====================


@router.get("/translations")
async def get_translations():
    """Get all available Bible translations."""
    return {"translations": get_all_translations()}


# ==================== Book Names ====================


@router.get("/book-names")
async def get_book_names(response: Response):
    """Return complete localized→English book name mapping for client-side verse detection."""
    multi_word_names = sorted(
        [key for key in LOCALIZED_TO_ENGLISH if " " in key and not key[0].isdigit()],
        key=len,
        reverse=True,
    )
    response.headers["Cache-Control"] = "public, max-age=86400"
    return {
        "localized_to_english": LOCALIZED_TO_ENGLISH,
        "multi_word_names": multi_word_names,
    }


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
    book: str,
    chapter: int,
    verse: int,
    db: DbSession,
    embedding: EmbeddingProviderDep,
    translation: str | None = Query(None, description="Translation code (e.g., 'kjv', 'ita1927')"),
):
    """Get a specific verse by reference, optionally filtered by translation."""
    book = normalize_book_name(book)
    repo = ScriptureRepository(db)
    try:
        result = await repo.get_verse(book, chapter, verse, translation=translation)
    except QueryTimeoutError:
        logger.error("Verse query timed out: %s %s:%s", book, chapter, verse)
        raise HTTPException(status_code=504, detail="Verse lookup timed out, please try again.")
    except Exception:
        logger.exception("Verse query failed: %s %s:%s", book, chapter, verse)
        raise HTTPException(status_code=503, detail="Verse lookup temporarily unavailable.")

    if not result:
        raise HTTPException(status_code=404, detail=f"Verse not found: {book} {chapter}:{verse}")

    if _is_placeholder_text(result.text):
        logger.warning(
            "Placeholder verse text blocked: %s %s:%s (translation=%s)",
            book,
            chapter,
            verse,
            result.translation,
        )
        raise HTTPException(status_code=404, detail=f"Verse not found: {book} {chapter}:{verse}")

    localized_book = get_localized_book_name(result.book.name, result.translation)
    return {
        "reference": result.reference,
        "text": result.text,
        "book": result.book.name,
        "localized_book": localized_book,
        "chapter": result.chapter_number,
        "verse": result.verse_number,
        "translation": result.translation,
    }


@router.get("/chapter/{book}/{chapter}", response_model=ChapterResponse)
async def get_chapter(
    book: str,
    chapter: int,
    db: DbSession,
    translation: str | None = Query(None, description="Translation code (e.g., 'kjv', 'ita1927')"),
    lang: Annotated[
        str | None,
        Query(description="UI language code (e.g. 'de') used to pick a default translation"),
    ] = None,
    http_request: Request = None,
):
    """Get all verses in a chapter, optionally filtered by translation."""
    book = normalize_book_name(book)
    repo = ScriptureRepository(db)
    try:
        verses = await repo.get_chapter_verses(book, chapter, translation=translation)
    except QueryTimeoutError:
        logger.error("Chapter query timed out: %s %s", book, chapter)
        raise HTTPException(status_code=504, detail="Chapter lookup timed out, please try again.")
    except Exception:
        logger.exception("Chapter query failed: %s %s", book, chapter)
        raise HTTPException(status_code=503, detail="Chapter lookup temporarily unavailable.")

    # Drop placeholder/empty verses (e.g. "////") — these are data defects, not scripture.
    verses = [v for v in verses if not _is_placeholder_text(v.text)]

    if not verses:
        raise HTTPException(status_code=404, detail=f"Chapter not found: {book} {chapter}")

    # When no translation was requested, restrict to a single translation chosen
    # deterministically. The query returns every translation in the DB for this
    # chapter, so picking verses[0] would be non-deterministic and surface a
    # random version (any language) on each request. Prefer the caller's UI
    # language (`lang`) — the language they're actually reading — then fall back
    # to the Accept-Language header, then to the first translation by code so the
    # result is always stable.
    if not translation:
        available = {v.translation for v in verses}
        accept_lang = http_request.headers.get("accept-language", "") if http_request else ""
        header_lang = accept_lang.split(",")[0] if accept_lang else None
        language = (lang or header_lang or "").split("-")[0] or None
        preferred = resolve_translation(None, language)
        default_translation = preferred if preferred in available else sorted(available)[0]
        verses = [v for v in verses if v.translation == default_translation]

    # Get the translation from the first verse if not specified
    actual_translation = translation or (verses[0].translation if verses else None)
    trans_info = get_translation_info(actual_translation) if actual_translation else None

    # Localize book name for chapter response
    localized_book = get_localized_book_name(book, actual_translation)
    return ChapterResponse(
        book=book,
        localized_book=localized_book,
        chapter=chapter,
        verses=[
            {
                "reference": v.reference,
                "text": v.text,
                "book": v.book.name,
                "localized_book": get_localized_book_name(v.book.name, v.translation),
                "chapter": v.chapter_number,
                "verse": v.verse_number,
                "translation": v.translation,
            }
            for v in verses
        ],
        translation=actual_translation,
        translation_name=trans_info["name"] if trans_info else None,
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
    book = normalize_book_name(book)
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
    translation: str | None = Query(None, description="Translation code (e.g., 'kjv', 'ita1927')"),
    db: DbSession = None,  # type: ignore
    embedding: EmbeddingProviderDep = None,  # type: ignore
):
    """
    Semantic search for relevant scripture.

    Search using natural language queries like:
    - "I'm feeling anxious about my future"
    - "verses about forgiveness"
    - "comfort for grief"

    Optionally filter by translation code.
    """
    service = ScriptureSearchService(db, embedding)

    results = await service.search(
        query=q, max_verses=max_verses, max_passages=max_passages, translation=translation
    )

    # Record search metrics
    scripture_search_counter.add(1)
    scripture_verses_returned.record(len(results.verses))

    return results


@router.get("/search/text")
async def search_text(
    q: str = Query(..., min_length=2, description="Text to search"),
    limit: int = Query(20, ge=1, le=100),
    db: DbSession = None,  # type: ignore
    embedding: EmbeddingProviderDep = None,  # type: ignore
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
