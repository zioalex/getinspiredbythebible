"""
Chat API routes.
"""

import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from chat import ChatRequest, ChatResponse, ChatService, FinalizeRequest, FinalizeResponse
from chat.service import _looks_truncated
from config import settings
from providers import AllModelsExhaustedError, EmbeddingProviderDep, LLMProviderDep
from scripture import DbSession
from utils.language import SUPPORTED_LANGUAGES
from utils.logging_config import get_logger
from utils.metrics import (
    chat_messages_counter,
    chat_response_time,
    chat_sessions_counter,
    chat_stream_client_disconnected_counter,
    chat_stream_counter,
)
from utils.security import check_content_filter, require_ip_rate_limit, require_rate_limit
from utils.session_tracker import track_session
from utils.turnstile import require_turnstile

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Default hint for clients when the provider didn't supply one (e.g. no
# Retry-After header on the upstream rate-limit response).
UPSTREAM_RETRY_AFTER_SECONDS = 30


def _session_language(body_language: str | None, accept_language: str | None) -> str | None:
    """Return the first supported base language, preferring the request body."""
    for candidate in (body_language, accept_language):
        if not candidate:
            continue
        language = candidate.split(",", 1)[0].strip().lower().replace("_", "-").split("-", 1)[0]
        if language in SUPPORTED_LANGUAGES:
            return language
    return None


class _StreamProgress:
    """What a chat stream has sent so far (BITB-320): drives disconnect logs and partial errors."""

    def __init__(self) -> None:
        self.message_id: str | None = None
        self.content_chars = 0
        self.completion_sent = False

    def observe(self, chunk: dict) -> None:
        chunk_type = chunk.get("type")
        if chunk_type == "metadata":
            self.message_id = chunk.get("message_id") or self.message_id
        elif chunk_type == "content":
            self.content_chars += len(chunk.get("content") or "")
        elif chunk_type == "completion":
            self.completion_sent = True

    def error_event(self, payload: dict) -> str:
        """SSE error frame; after content it carries ``partial`` + ``message_id`` (recovery)."""
        if self.content_chars > 0:
            payload = {**payload, "partial": True, "message_id": self.message_id}
        return f"data: {json.dumps({'type': 'error', **payload})}\n\n"


@router.post(
    "",
    response_model=ChatResponse,
    dependencies=[
        Depends(require_turnstile),
        Depends(require_rate_limit),
        Depends(check_content_filter),
    ],
)
async def chat(
    request: ChatRequest,
    http_request: Request,
    db: DbSession,
    llm: LLMProviderDep,
    embedding: EmbeddingProviderDep,
):
    """
    Send a message and receive a Bible-grounded response.

    The response will include relevant scripture context
    and a thoughtful, compassionate reply.
    """
    start = time.monotonic()
    service = ChatService(db, llm, embedding)

    try:
        response = await service.chat(
            request, client_country=http_request.headers.get("CF-IPCountry")
        )

        # Record metrics
        elapsed_ms = (time.monotonic() - start) * 1000
        chat_messages_counter.add(1)
        chat_response_time.record(elapsed_ms)
        if request.session_id:
            chat_sessions_counter.add(1)

        # Track session (fire-and-forget, errors logged internally)
        user_agent = http_request.headers.get("user-agent")
        language = _session_language(request.language, http_request.headers.get("accept-language"))
        await track_session(db, request.session_id, user_agent=user_agent, language=language)

        return response
    except AllModelsExhaustedError as e:
        logger.warning("All LLM models exhausted (%s): %s", e.reason, e)
        retry_after = e.retry_after or UPSTREAM_RETRY_AFTER_SECONDS
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "upstream_unavailable",
                "code": "upstream_unavailable",
                "message": "Our AI service is temporarily busy. Please try again in a moment.",
            },
            headers={"Retry-After": str(retry_after)},
        ) from e
    except RuntimeError as e:
        logger.exception("Chat runtime error: %s", str(e))
        raise HTTPException(status_code=500, detail="An unexpected error occurred") from e
    except Exception as e:
        logger.exception("Chat request failed: %s", str(e))
        raise HTTPException(
            status_code=500, detail="An error occurred processing your request"
        ) from e


@router.post(
    "/stream",
    dependencies=[
        Depends(require_turnstile),
        Depends(require_rate_limit),
        Depends(check_content_filter),
    ],
)
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    db: DbSession,
    llm: LLMProviderDep,
    embedding: EmbeddingProviderDep,
):
    """
    Stream a chat response for real-time display.

    Returns Server-Sent Events (SSE) with response chunks.
    """
    # Record metrics
    chat_messages_counter.add(1)
    chat_stream_counter.add(1)
    if request.session_id:
        chat_sessions_counter.add(1)

    # Session attributes (mirrors the non-streaming `chat` handler).
    user_agent = http_request.headers.get("user-agent")
    language = _session_language(request.language, http_request.headers.get("accept-language"))

    service = ChatService(db, llm, embedding)
    # BITB-255: Cloudflare's IP-geolocation header, used only to pick local emergency numbers.
    client_country = http_request.headers.get("CF-IPCountry")

    async def generate():
        # BITB-320: track what the client has been sent so a disconnect is observable and an
        # error after content can tell the client the reply is partial (and which message).
        progress = _StreamProgress()
        try:
            async for chunk in service.chat_stream(request, client_country=client_country):
                progress.observe(chunk)
                # chunk is now a dict with 'type' field
                # SSE format: data: {json}\n\n
                yield f"data: {json.dumps(chunk)}\n\n"
            # Track session only after the stream completes successfully, matching
            # the non-streaming path. Fire-and-forget (never raises); committed by the
            # get_db_session dependency cleanup once the response body is drained.
            await track_session(db, request.session_id, user_agent=user_agent, language=language)
            yield "data: [DONE]\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            # BITB-320: the client went away (network switch, app backgrounded, proxy reset).
            # Never log message or reply text -- only sizes.
            extra = {
                "content_chars": progress.content_chars,
                "completion_sent": progress.completion_sent,
                "message_id": progress.message_id,
            }
            if progress.completion_sent:
                # The client already has everything it needs; this is just a late close.
                logger.info("Chat stream client disconnected after completion", extra=extra)
            else:
                logger.warning("Chat stream client disconnected before completion", extra=extra)
                chat_stream_client_disconnected_counter.add(1, {"completion_sent": "false"})
            raise
        except AllModelsExhaustedError as e:
            logger.warning("Streaming: all LLM models exhausted (%s): %s", e.reason, e)
            yield progress.error_event(
                {
                    "error": "Our AI service is temporarily busy. Please try again in a moment.",
                    "error_code": "upstream_unavailable",
                    "retry_after": e.retry_after or UPSTREAM_RETRY_AFTER_SECONDS,
                }
            )
        except RuntimeError as e:
            logger.exception("Chat stream runtime error: %s", str(e))
            yield progress.error_event({"error": "An unexpected error occurred"})
        except Exception as e:
            logger.exception("Chat stream failed: %s", str(e))
            yield progress.error_event({"error": "An error occurred processing your request"})

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post(
    "/finalize",
    response_model=FinalizeResponse,
    response_model_exclude_none=True,
    dependencies=[
        # BITB-320: IP-only limit, separate bucket from chat; no Turnstile -- the turn already
        # passed one, and a second challenge would stall recovery. No session message cap.
        Depends(
            require_ip_rate_limit(
                "chat_finalize", lambda: settings.chat_finalize_rate_limit_per_minute
            )
        ),
        Depends(check_content_filter),
    ],
)
async def chat_finalize(
    request: FinalizeRequest,
    db: DbSession,
    llm: LLMProviderDep,
    embedding: EmbeddingProviderDep,
):
    """Recover chips + verse references for a reply whose `completion` event never arrived."""
    service = ChatService(db, llm, embedding)
    try:
        return await service.finalize(request)
    except Exception:  # noqa: BLE001 - recovery degrades to an empty 200, never a 5xx
        logger.exception("Chat finalize failed")
        return {
            "verses_cited": [],
            "resolved_verses": [],
            "citations": [],
            "truncated": _looks_truncated(request.assistant_text),
        }


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
