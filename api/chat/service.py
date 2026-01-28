"""
Chat Service - Orchestrates Bible-grounded conversations.

This service combines scripture search, LLM generation, and
conversation management to create meaningful spiritual dialogues.
"""

import logging
import uuid
from typing import AsyncIterator

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from providers import ChatMessage, EmbeddingProvider, LLMProvider
from scripture import ScriptureSearchService, SearchResults
from utils.language import detect_language, get_translation_info, resolve_translation

from .prompts import build_search_context_prompt, get_system_prompt

logger = logging.getLogger(__name__)


class ConversationMessage(BaseModel):
    """A message in the conversation."""

    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    """Request to the chat endpoint."""

    message: str
    conversation_history: list[ConversationMessage] = []
    include_search: bool = True  # Whether to search scripture first
    preferred_translation: str | None = None  # User's preferred translation code


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""

    message_id: str  # Unique ID for feedback tracking
    message: str
    scripture_context: SearchResults | None = None
    provider: str
    model: str
    detected_translation: str | None = None
    translation_info: dict | None = None


class ChatService:
    """
    Service for Bible-grounded chat conversations.

    Orchestrates:
    1. Scripture search based on user message
    2. Context building from search results
    3. LLM generation with grounding
    4. Response formatting
    """

    def __init__(
        self,
        db_session: AsyncSession,
        llm_provider: LLMProvider,
        embedding_provider: EmbeddingProvider,
    ):
        self.llm = llm_provider
        self.embedding = embedding_provider
        self.search_service = ScriptureSearchService(db_session, embedding_provider)

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Process a chat request and generate a Bible-grounded response.

        Args:
            request: Chat request with message and optional history

        Returns:
            ChatResponse with generated message and context
        """
        logger.info(
            "Processing chat request",
            extra={
                "message_length": len(request.message),
                "history_count": len(request.conversation_history),
                "include_search": request.include_search,
            },
        )

        # Resolve translation: user preference > language detection > default
        detected_language = detect_language(request.message)
        translation = resolve_translation(request.preferred_translation, detected_language)
        translation_info = get_translation_info(translation)
        logger.debug(
            "Language detection",
            extra={"detected": detected_language, "translation": translation},
        )

        # Step 1: Search for relevant scripture (if enabled)
        scripture_context = None
        search_context_prompt = ""

        if request.include_search:
            try:
                scripture_context = await self.search_service.search(
                    query=request.message,
                    max_verses=settings.max_context_verses,
                    max_passages=2,
                    similarity_threshold=0.35,
                    translation=translation,
                )
                logger.debug(
                    "Scripture search completed",
                    extra={
                        "verses_found": len(scripture_context.verses) if scripture_context else 0,
                        "passages_found": (
                            len(scripture_context.passages) if scripture_context else 0
                        ),
                    },
                )
            except Exception as e:
                logger.error(
                    "Scripture search failed",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )
                # Continue without scripture context

            # Build context prompt from search results
            if scripture_context and (scripture_context.verses or scripture_context.passages):
                search_context_prompt = build_search_context_prompt(
                    {
                        "verses": [v.model_dump() for v in scripture_context.verses],
                        "passages": [p.model_dump() for p in scripture_context.passages],
                    }
                )

        # Step 2: Build the message list
        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context=search_context_prompt,
            language_code=detected_language,
        )

        # Step 3: Generate response
        try:
            logger.debug("Sending request to LLM provider")
            response = await self.llm.chat(
                messages=messages,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
            logger.info(
                "LLM response received",
                extra={
                    "provider": response.provider,
                    "model": response.model,
                    "response_length": len(response.content),
                },
            )
        except Exception as e:
            logger.error(
                "LLM provider error",
                extra={
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "provider": settings.llm_provider,
                    "model": settings.llm_model,
                },
            )
            raise

        # Generate unique message ID for feedback tracking
        message_id = str(uuid.uuid4())

        return ChatResponse(
            message_id=message_id,
            message=response.content,
            scripture_context=scripture_context,
            provider=response.provider,
            model=response.model,
            detected_translation=translation,
            translation_info=translation_info,
        )

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        Stream a chat response for real-time display.

        Yields:
            Chunks of the response as they're generated
        """
        # Resolve translation: user preference > language detection > default
        detected_language = detect_language(request.message)
        translation = resolve_translation(request.preferred_translation, detected_language)

        # Step 1: Search for relevant scripture
        search_context_prompt = ""

        if request.include_search:
            scripture_context = await self.search_service.search(
                query=request.message,
                max_verses=settings.max_context_verses,
                max_passages=2,
                similarity_threshold=0.35,
                translation=translation,
            )

            if scripture_context.verses or scripture_context.passages:
                search_context_prompt = build_search_context_prompt(
                    {
                        "verses": [v.model_dump() for v in scripture_context.verses],
                        "passages": [p.model_dump() for p in scripture_context.passages],
                    }
                )

        # Step 2: Build messages
        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context=search_context_prompt,
            language_code=detected_language,
        )

        # Step 3: Stream response
        async for chunk in self.llm.chat_stream(
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        ):
            yield chunk

    def _build_messages(
        self,
        user_message: str,
        history: list[ConversationMessage],
        search_context: str = "",
        language_code: str = "en",
    ) -> list[ChatMessage]:
        """
        Build the message list for the LLM.

        Args:
            user_message: Current user message
            history: Previous conversation messages
            search_context: Optional scripture context from search
            language_code: Detected language code for response language

        Returns:
            List of ChatMessage objects for the LLM
        """
        messages = []

        # System prompt with language instruction and optional search context
        system_prompt = get_system_prompt(language_code)
        system_content = system_prompt
        if search_context:
            system_content = search_context + "\n" + system_prompt

        messages.append(ChatMessage(role="system", content=system_content))

        # Add conversation history (limited to max)
        recent_history = history[-settings.max_conversation_history :]
        for msg in recent_history:
            messages.append(ChatMessage(role=msg.role, content=msg.content))

        # Add current user message
        messages.append(ChatMessage(role="user", content=user_message))

        return messages

    async def get_verse_context(self, book: str, chapter: int, verse: int) -> dict:
        """
        Get a verse with surrounding context.

        Useful when user clicks on a verse to learn more.
        """
        verses = await self.search_service.get_context(
            book=book, chapter=chapter, verse=verse, context_size=3
        )

        return {"target_verse": verse, "verses": [v.model_dump() for v in verses]}
