"""
Chat API routes.
"""

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from chat import ChatRequest, ChatResponse, ChatService
from providers import EmbeddingProviderDep, LLMProviderDep
from scripture import DbSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
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
    except Exception as e:
        logger.exception("Chat request failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
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
        except Exception as e:
            logger.exception("Chat stream failed: %s", str(e))
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

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
        raise HTTPException(status_code=500, detail=str(e))
