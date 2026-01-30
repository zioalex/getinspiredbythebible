"""
Chat API routes.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from chat import ChatRequest, ChatResponse, ChatService
from providers import EmbeddingProviderDep, LLMProviderDep
from scripture import DbSession
from utils.security import check_content_filter, require_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    dependencies=[Depends(require_rate_limit), Depends(check_content_filter)],
)
async def chat(
    request: ChatRequest, db: DbSession, llm: LLMProviderDep, embedding: EmbeddingProviderDep
):
    """
    Send a message and receive a Bible-grounded response.

    The response will include relevant scripture context
    and a thoughtful, compassionate reply.
    """
    service = ChatService(db, llm, embedding)

    try:
        response = await service.chat(request)
        return response
    except RuntimeError as e:
        # Handle "all models rate limited" from OpenRouter fallback
        if "All models rate limited" in str(e):
            logger.warning("All LLM models rate limited: %s", str(e))
            raise HTTPException(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                detail="Our AI service is temporarily busy. Please try again in a moment.",
            ) from e
        # Other runtime errors
        logger.exception("Chat runtime error: %s", str(e))
        raise HTTPException(status_code=500, detail="An unexpected error occurred") from e
    except Exception as e:
        logger.exception("Chat request failed: %s", str(e))
        raise HTTPException(
            status_code=500, detail="An error occurred processing your request"
        ) from e


@router.post(
    "/stream",
    dependencies=[Depends(require_rate_limit), Depends(check_content_filter)],
)
async def chat_stream(
    request: ChatRequest, db: DbSession, llm: LLMProviderDep, embedding: EmbeddingProviderDep
):
    """
    Stream a chat response for real-time display.

    Returns Server-Sent Events (SSE) with response chunks.
    """
    service = ChatService(db, llm, embedding)

    async def generate():
        try:
            async for chunk in service.chat_stream(request):
                # SSE format
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except RuntimeError as e:
            # Handle "all models rate limited" from OpenRouter fallback
            if "All models rate limited" in str(e):
                logger.warning("Streaming: All LLM models rate limited: %s", str(e))
                yield f"data: {json.dumps({'error': 'Our AI service is temporarily busy. Please try again in a moment.'})}\n\n"
            else:
                logger.exception("Chat stream runtime error: %s", str(e))
                yield f"data: {json.dumps({'error': 'An unexpected error occurred'})}\n\n"
        except Exception as e:
            logger.exception("Chat stream failed: %s", str(e))
            yield f"data: {json.dumps({'error': 'An error occurred processing your request'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/verse/{book}/{chapter}/{verse}")
async def get_verse_context(
    book: str,
    chapter: int,
    verse: int,
    db: DbSession,
    llm: LLMProviderDep,
    embedding: EmbeddingProviderDep,
):
    """
    Get a verse with surrounding context.

    Useful for displaying more context when user clicks on a verse.
    """
    service = ChatService(db, llm, embedding)

    try:
        return await service.get_verse_context(book, chapter, verse)
    except Exception as e:
        logger.exception("Get verse context failed: %s", str(e))
        raise HTTPException(
            status_code=500, detail="An error occurred retrieving verse context"
        ) from e
