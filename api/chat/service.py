"""
Chat Service - Orchestrates Bible-grounded conversations.

This service combines scripture search, LLM generation, and
conversation management to create meaningful spiritual dialogues.
"""

import logging
import time
import uuid
from typing import AsyncIterator

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from providers import ChatMessage, EmbeddingProvider, LLMProvider
from scripture import ScriptureSearchService, SearchResults
from utils.language import detect_language, get_translation_info, resolve_translation
from utils.verse_parser import extract_references, is_verse_lookup_request

from .prompts import (
    build_search_context_prompt,
    get_prayer_lookup_prompt,
    get_system_prompt,
    get_verse_lookup_prompt,
)

logger = logging.getLogger(__name__)


class ConversationMessage(BaseModel):
    """A message in the conversation."""

    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    """Request to the chat endpoint."""

    message: str = Field(..., min_length=1, max_length=settings.max_message_length)
    conversation_history: list[ConversationMessage] = []
    include_search: bool = True  # Whether to search scripture first
    preferred_translation: str | None = None  # User's preferred translation code
    session_id: str | None = Field(
        default=None, max_length=64, pattern=r"^[a-zA-Z0-9\-_]+$"
    )  # Optional session identifier for tracking

    @field_validator("message")
    @classmethod
    def validate_message_content(cls, v: str) -> str:
        """Strip whitespace and validate message is not empty."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Message cannot be empty or whitespace only")
        return stripped


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
        total_start = time.time()
        # Track session interactions (history_count + 1 = total messages in session)
        session_message_count = len(request.conversation_history) + 1
        logger.info(
            "Processing chat request",
            extra={
                "session_id": request.session_id,
                "session_message_count": session_message_count,
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

        # Check if this is a verse/prayer lookup request
        is_verse_lookup = is_verse_lookup_request(request.message)
        verse_refs, prayer_ref = extract_references(request.message)

        if is_verse_lookup:
            logger.info(
                "Detected verse lookup request",
                extra={
                    "verse_refs": [str(v) for v in verse_refs],
                    "prayer_ref": prayer_ref.name if prayer_ref else None,
                },
            )

        # Step 1: Search for relevant scripture (if enabled)
        scripture_context, search_context_prompt = await self._search_scripture(
            request, translation, verse_refs, is_verse_lookup
        )

        # Step 2: Build the message list
        prompt_type = self._determine_prompt_type(is_verse_lookup, prayer_ref)

        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context=search_context_prompt,
            language_code=detected_language,
            prompt_type=prompt_type,
        )

        # Step 3: Generate response
        llm_start = time.time()
        try:
            logger.debug("Sending request to LLM provider")
            response = await self.llm.chat(
                messages=messages,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
            llm_duration = time.time() - llm_start
            logger.info(
                "LLM response received",
                extra={
                    "provider": response.provider,
                    "model": response.model,
                    "response_length": len(response.content),
                    "duration_seconds": f"{llm_duration:.2f}",
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

        total_duration = time.time() - total_start
        logger.info(
            "Chat request completed",
            extra={"total_duration_seconds": f"{total_duration:.2f}"},
        )

        return ChatResponse(
            message_id=message_id,
            message=response.content,
            scripture_context=scripture_context,
            provider=response.provider,
            model=response.model,
            detected_translation=translation,
            translation_info=translation_info,
        )

    async def _search_scripture(
        self,
        request: ChatRequest,
        translation: str,
        verse_refs: list,
        is_verse_lookup: bool,
    ) -> tuple[SearchResults | None, str]:
        """
        Search for relevant scripture, including direct lookups for specific verse references.

        Returns:
            Tuple of (scripture_context, search_context_prompt)
        """
        if not request.include_search:
            return None, ""

        search_start = time.time()
        scripture_context = None
        search_context_prompt = ""

        try:
            # Direct verse lookups for specific references
            direct_verses = await self._lookup_direct_verses(verse_refs)

            # Semantic search for additional context
            scripture_context = await self.search_service.search(
                query=request.message,
                max_verses=settings.max_context_verses,
                max_passages=2,
                similarity_threshold=0.35,
                translation=translation,
            )

            # Merge direct lookup results with semantic search
            self._merge_direct_verses(scripture_context, direct_verses)

            search_duration = time.time() - search_start
            logger.info(
                "Scripture search completed",
                extra={
                    "duration_seconds": f"{search_duration:.2f}",
                    "verses_found": len(scripture_context.verses) if scripture_context else 0,
                    "passages_found": (len(scripture_context.passages) if scripture_context else 0),
                    "is_verse_lookup": is_verse_lookup,
                },
            )
        except Exception as e:
            logger.error(f"Scripture search failed: {type(e).__name__}: {e}", exc_info=True)
            return None, ""

        # Build context prompt from search results
        if scripture_context and (scripture_context.verses or scripture_context.passages):
            search_context_prompt = build_search_context_prompt(
                {
                    "verses": [v.model_dump() for v in scripture_context.verses],
                    "passages": [p.model_dump() for p in scripture_context.passages],
                }
            )

        return scripture_context, search_context_prompt

    async def _lookup_direct_verses(self, verse_refs: list) -> list:
        """Look up specific verses from references."""
        direct_verses = []
        for ref in verse_refs:
            if ref.verse_end:
                range_verses = await self.search_service.get_verse_range(
                    book=ref.book,
                    chapter=ref.chapter,
                    start_verse=ref.verse_start,
                    end_verse=ref.verse_end,
                )
                direct_verses.extend(range_verses)
            else:
                verse = await self.search_service.get_verse(
                    book=ref.book, chapter=ref.chapter, verse=ref.verse_start
                )
                if verse:
                    direct_verses.append(verse)

        if direct_verses:
            logger.info("Direct verse lookup completed", extra={"verses_found": len(direct_verses)})
        return direct_verses

    def _merge_direct_verses(self, scripture_context: SearchResults, direct_verses: list) -> None:
        """Merge direct lookup verses into scripture context (at beginning)."""
        if not direct_verses or not scripture_context:
            return

        existing_refs = {(v.book, v.chapter, v.verse) for v in scripture_context.verses}
        for dv in direct_verses:
            if (dv.book, dv.chapter, dv.verse) not in existing_refs:
                scripture_context.verses.insert(0, dv)
                existing_refs.add((dv.book, dv.chapter, dv.verse))

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        Stream a chat response for real-time display.

        Yields:
            Chunks of the response as they're generated
        """
        # Resolve translation: user preference > language detection > default
        detected_language = detect_language(request.message)
        translation = resolve_translation(request.preferred_translation, detected_language)

        # Check if this is a verse/prayer lookup request
        is_verse_lookup = is_verse_lookup_request(request.message)
        verse_refs, prayer_ref = extract_references(request.message)

        # Step 1: Search for relevant scripture
        _, search_context_prompt = await self._search_scripture(
            request, translation, verse_refs, is_verse_lookup
        )

        # Step 2: Build messages with appropriate prompt type
        prompt_type = self._determine_prompt_type(is_verse_lookup, prayer_ref)

        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context=search_context_prompt,
            language_code=detected_language,
            prompt_type=prompt_type,
        )

        # Step 3: Stream response
        async for chunk in self.llm.chat_stream(
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        ):
            yield chunk

    def _determine_prompt_type(self, is_verse_lookup: bool, prayer_ref) -> str:
        """Determine the appropriate prompt type based on request characteristics."""
        if is_verse_lookup and prayer_ref:
            return "prayer_lookup"
        elif is_verse_lookup:
            return "verse_lookup"
        return "default"

    def _build_messages(
        self,
        user_message: str,
        history: list[ConversationMessage],
        search_context: str = "",
        language_code: str = "en",
        prompt_type: str = "default",
    ) -> list[ChatMessage]:
        """
        Build the message list for the LLM.

        Args:
            user_message: Current user message
            history: Previous conversation messages
            search_context: Optional scripture context from search
            language_code: Detected language code for response language
            prompt_type: Type of prompt to use ("default", "verse_lookup", "prayer_lookup")

        Returns:
            List of ChatMessage objects for the LLM
        """
        messages = []

        # Select appropriate system prompt based on request type
        if prompt_type == "verse_lookup":
            system_prompt = get_verse_lookup_prompt(language_code)
        elif prompt_type == "prayer_lookup":
            system_prompt = get_prayer_lookup_prompt(language_code)
        else:
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
