"""
Chat Service - Orchestrates Bible-grounded conversations.

This service combines scripture search, LLM generation, and
conversation management to create meaningful spiritual dialogues.
"""

import hashlib
import time
import uuid
from typing import AsyncIterator

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from providers import ChatMessage, EmbeddingProvider, LLMProvider
from scripture import ScriptureSearchService, SearchResults
from utils.content_safety import ContentSafetyViolationError, get_content_safety_service
from utils.language import (
    detect_language,
    get_model_override_for_language,
    get_translation_info,
    resolve_translation,
)
from utils.logging_config import get_logger
from utils.verse_parser import (
    extract_all_references,
    extract_references,
    is_verse_lookup_request,
    parse_structured_citations,
)

from .prompts import (
    OFF_TOPIC_PROMPT,
    build_search_context_prompt,
    detect_intent_prompt,
    get_prayer_lookup_prompt,
    get_system_prompt,
    get_verse_lookup_prompt,
)
from .topics import detect_topics

logger = get_logger(__name__)


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

    async def _detect_intent(self, message: str, model_override: str | None = None) -> str:
        """
        Classify user intent with a fast LLM call.

        Returns one of: COMFORT, GUIDANCE, CURIOSITY, VERSE_LOOKUP, OFF_TOPIC, GENERAL.
        On any error, returns "GENERAL" (fail-open).
        """
        try:
            messages = [
                ChatMessage(role="system", content="You are an intent classifier."),
                ChatMessage(role="user", content=detect_intent_prompt(message)),
            ]
            response = await self.llm.chat(
                messages=messages,
                temperature=0.0,
                max_tokens=20,
                model_override=model_override,
            )
            intent = response.content.strip().upper().split()[0]
            valid = {"COMFORT", "GUIDANCE", "CURIOSITY", "VERSE_LOOKUP", "OFF_TOPIC", "GENERAL"}
            if intent not in valid:
                logger.warning("Unexpected intent classification: %s", intent)
                return "GENERAL"
            logger.info("Intent detected", extra={"intent": intent})
            return intent
        except Exception as e:
            logger.warning("Intent detection failed, defaulting to GENERAL: %s", e)
            return "GENERAL"

    async def _check_content_safety(
        self,
        message: str,
        detected_language: str,
        session_id: str | None,
        context: str = "chat",
    ) -> bool:
        """
        Check message for harmful content and raise if violation found.

        Args:
            message: The user's message to check
            detected_language: ISO language code detected from message
            session_id: Session identifier for logging
            context: Context label for log messages (e.g., 'chat' or 'chat stream')

        Returns:
            True if help-seeking/compassionate response is needed, False otherwise.
            Raises ContentSafetyViolationError if message is not safe.
        """
        if not settings.content_safety_enabled:
            return False

        safety_service = get_content_safety_service()
        safety_result = await safety_service.check(message, detected_language)

        if not safety_result.allowed:
            text_hash = hashlib.sha256(message.encode()).hexdigest()[:16]
            logger.warning(
                f"Content safety violation in {context}",
                extra={
                    "text_hash": text_hash,
                    "language": detected_language,
                    "reason": safety_result.reason,
                    "categories": safety_result.categories,
                    "session_id": session_id,
                },
            )
            raise ContentSafetyViolationError(
                message=(
                    "We're here to help. If you're struggling or in crisis, please reach out: "
                    "International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/"
                ),
                categories=safety_result.categories,
                reason=safety_result.reason,
            )

        if safety_result.compassionate_response_needed:
            logger.info(
                f"Help-seeking message detected in {context}, will use compassionate response"
            )

        return safety_result.compassionate_response_needed

    async def _expand_query(
        self, user_message: str, language: str, model_override: str | None = None
    ) -> str:
        """
        Expand user query with related biblical themes and concepts using LLM.

        Uses low temperature for consistent expansion results.
        Falls back to original message on any error (fail-open).
        """
        expansion_prompt = f"""You are helping expand a search query to find relevant Bible verses.

User's message: "{user_message}"
Language: {language}

Identify biblical themes, emotions, and related concepts that would help find relevant scripture.
Generate an expanded search query including:
- Core emotions/feelings (anxiety, peace, anger, joy, frustration, etc.)
- Related biblical themes (trust in God, forgiveness, patience, God's love, self-control, etc.)
- Synonyms and related words
- Life situations this applies to

Respond ONLY with the expanded query text in {language}, no explanation.
Keep it under 100 words."""

        start_time = time.time()
        try:
            response = await self.llm.chat(
                messages=[ChatMessage(role="user", content=expansion_prompt)],
                temperature=0.3,
                max_tokens=150,
                model_override=model_override,
            )
            expanded = response.content.strip()
            expansion_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Query expansion completed",
                extra={
                    "original_query": user_message[:100],
                    "expanded_query": expanded[:200],
                    "language": language,
                    "expansion_time_ms": expansion_time_ms,
                },
            )
            return expanded
        except Exception as e:
            logger.warning("Query expansion failed, using original query: %s", e)
            return user_message

    def _detect_topics(self, message: str) -> list[str]:
        """
        Detect biblical topics in user message using keyword-based mapping.

        Fast keyword scan, no LLM call. Returns list of topic names.
        """
        topics = detect_topics(message)
        if topics:
            logger.info(
                "Topics detected for boosting",
                extra={"detected_topics": topics, "message_length": len(message)},
            )
        return topics

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
        model_override = get_model_override_for_language(detected_language)
        logger.info(
            "Language detection and translation resolution",
            extra={
                "detected_language": detected_language,
                "translation": translation,
                "user_preference": request.preferred_translation,
                "model_override": model_override,
                "message_preview": request.message[:50],
            },
        )

        # Content safety check BEFORE LLM call
        await self._check_content_safety(
            request.message, detected_language, request.session_id, context="chat"
        )

        # Intent detection: classify before scripture search
        if settings.content_filter_intent_detection:
            detected_intent = await self._detect_intent(request.message, model_override)
            if detected_intent == "OFF_TOPIC":
                return await self._handle_off_topic(
                    request,
                    detected_language,
                    translation,
                    translation_info,
                    total_start,
                    model_override,
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
            request,
            translation,
            verse_refs,
            is_verse_lookup,
            detected_language=detected_language,
            model_override=model_override,
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
                model_override=model_override,
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

        if "Not from the Bible" in response.content[:120] and len(response.content) < 300:
            logger.warning(
                "Possible truncated prayer response: source disclaimer present but body is short",
                extra={"response_preview": response.content[:200]},
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

    async def _handle_off_topic(
        self,
        request: ChatRequest,
        detected_language: str,
        translation: str,
        translation_info: dict | None,
        total_start: float,
        model_override: str | None = None,
    ) -> ChatResponse:
        """Generate a warm redirect response for off-topic messages, skipping scripture search."""
        logger.info("Off-topic message detected, skipping scripture search")
        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context="",
            language_code=detected_language,
            prompt_type="off_topic",
        )
        response = await self.llm.chat(
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            model_override=model_override,
        )
        message_id = str(uuid.uuid4())
        total_duration = time.time() - total_start
        logger.info(
            "Off-topic redirect completed",
            extra={"total_duration_seconds": f"{total_duration:.2f}"},
        )
        return ChatResponse(
            message_id=message_id,
            message=response.content,
            scripture_context=None,
            provider=response.provider,
            model=response.model,
            detected_translation=translation,
            translation_info=translation_info,
        )

    async def _search_scripture(  # noqa: C901
        self,
        request: ChatRequest,
        translation: str,
        verse_refs: list,
        is_verse_lookup: bool,
        detected_language: str = "en",  # NEW
        model_override: str | None = None,  # NEW
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
            direct_verses = await self._lookup_direct_verses(verse_refs, translation)

            # Query expansion (optional feature flag)
            extra_embeddings: list[list[float]] | None = None
            if settings.query_expansion_enabled:
                expanded_query = await self._expand_query(
                    request.message, detected_language, model_override
                )
                if expanded_query != request.message:
                    # Generate embedding for expanded query
                    expansion_embed_response = await self.embedding.embed(expanded_query)
                    extra_embeddings = [expansion_embed_response.embedding]
                    logger.info(
                        "Query expansion embeddings generated",
                        extra={"num_extra_embeddings": len(extra_embeddings)},
                    )

            # Topic detection for boosting (keyword-based, <10ms)
            boost_topics: list[str] = []
            if settings.topic_boosting_enabled:
                boost_topics = self._detect_topics(request.message)

            # Semantic or hybrid search (optionally with topic boosting)
            if settings.hybrid_search_enabled:
                if settings.topic_boosting_enabled and boost_topics:
                    semantic_results = await self.search_service.search(
                        query=request.message,
                        max_verses=settings.max_context_verses,
                        max_passages=2,
                        similarity_threshold=0.35,
                        translation=translation,
                        extra_embeddings=extra_embeddings,
                    )
                    scripture_context = await self.search_service.search_hybrid_boosted(
                        query=request.message,
                        boost_topics=boost_topics,
                        max_verses=settings.max_context_verses,
                        max_passages=2,
                        similarity_threshold=0.35,
                        translation=translation,
                        semantic_weight=settings.hybrid_search_semantic_weight,
                        keyword_weight=settings.hybrid_search_keyword_weight,
                        topic_boost_factor=settings.topic_boost_factor,
                    )
                else:
                    semantic_results = await self.search_service.search(
                        query=request.message,
                        max_verses=settings.max_context_verses,
                        max_passages=2,
                        similarity_threshold=0.35,
                        translation=translation,
                        extra_embeddings=extra_embeddings,
                    )
                    scripture_context = await self.search_service.search_hybrid(
                        query=request.message,
                        max_verses=settings.max_context_verses,
                        max_passages=2,
                        similarity_threshold=0.35,
                        translation=translation,
                        semantic_weight=settings.hybrid_search_semantic_weight,
                        keyword_weight=settings.hybrid_search_keyword_weight,
                    )
                # Log differences for monitoring
                semantic_refs = {v.reference for v in semantic_results.verses}
                hybrid_refs = {v.reference for v in scripture_context.verses}
                new_in_hybrid = hybrid_refs - semantic_refs
                dropped_in_hybrid = semantic_refs - hybrid_refs
                if new_in_hybrid or dropped_in_hybrid:
                    logger.info(
                        "Hybrid search result differences",
                        extra={
                            "new_in_hybrid": list(new_in_hybrid),
                            "dropped_in_hybrid": list(dropped_in_hybrid),
                        },
                    )
            else:
                if settings.topic_boosting_enabled and boost_topics:
                    scripture_context = await self.search_service.search_boosted(
                        query=request.message,
                        boost_topics=boost_topics,
                        max_verses=settings.max_context_verses,
                        max_passages=2,
                        similarity_threshold=0.35,
                        translation=translation,
                        topic_boost_factor=settings.topic_boost_factor,
                        extra_embeddings=extra_embeddings,
                    )
                else:
                    scripture_context = await self.search_service.search(
                        query=request.message,
                        max_verses=settings.max_context_verses,
                        max_passages=2,
                        similarity_threshold=0.35,
                        translation=translation,
                        extra_embeddings=extra_embeddings,
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
                    "query_expansion_used": extra_embeddings is not None,
                    "hybrid_search_used": settings.hybrid_search_enabled,
                    "topic_boosting_used": settings.topic_boosting_enabled and bool(boost_topics),
                    "boost_topics": boost_topics if boost_topics else [],
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

    async def _lookup_direct_verses(self, verse_refs: list, translation: str | None = None) -> list:
        """Look up specific verses from references, filtered by translation."""
        direct_verses = []
        for ref in verse_refs:
            if ref.verse_end:
                range_verses = await self.search_service.get_verse_range(
                    book=ref.book,
                    chapter=ref.chapter,
                    start_verse=ref.verse_start,
                    end_verse=ref.verse_end,
                    translation=translation,
                )
                direct_verses.extend(range_verses)
            else:
                verse = await self.search_service.get_verse(
                    book=ref.book,
                    chapter=ref.chapter,
                    verse=ref.verse_start,
                    translation=translation,
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

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[dict]:
        """
        Stream a chat response for real-time display.

        Yields:
            Dict with 'type' field:
            - {'type': 'metadata', 'message_id': '...', 'scripture_context': {...}, ...}
            - {'type': 'content', 'content': '...'}
        """
        # Generate unique message ID for feedback tracking
        message_id = str(uuid.uuid4())

        # Resolve translation: user preference > language detection > default
        detected_language = detect_language(request.message)
        translation = resolve_translation(request.preferred_translation, detected_language)
        translation_info = get_translation_info(translation)
        model_override = get_model_override_for_language(detected_language)
        logger.info(
            "Language detection and translation resolution (stream)",
            extra={
                "detected_language": detected_language,
                "translation": translation,
                "user_preference": request.preferred_translation,
                "model_override": model_override,
                "message_preview": request.message[:50],
            },
        )

        # Content safety check BEFORE LLM call
        await self._check_content_safety(
            request.message, detected_language, request.session_id, context="chat stream"
        )

        # Intent detection: short-circuit off-topic before scripture search
        if settings.content_filter_intent_detection:
            detected_intent = await self._detect_intent(request.message, model_override)
            if detected_intent == "OFF_TOPIC":
                logger.info("Off-topic message detected in stream, skipping scripture search")

                # Send metadata first (no scripture context for off-topic)
                yield {
                    "type": "metadata",
                    "message_id": message_id,
                    "scripture_context": None,
                    "provider": settings.llm_provider,
                    "model": settings.llm_model,
                    "detected_translation": translation,
                    "translation_info": translation_info,
                }

                messages = self._build_messages(
                    user_message=request.message,
                    history=request.conversation_history,
                    search_context="",
                    language_code=detected_language,
                    prompt_type="off_topic",
                )
                async for chunk in self.llm.chat_stream(
                    messages=messages,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                    model_override=model_override,
                ):
                    yield {"type": "content", "content": chunk}
                yield {"type": "completion", "verses_cited": []}
                return

        # Check if this is a verse/prayer lookup request
        is_verse_lookup = is_verse_lookup_request(request.message)
        verse_refs, prayer_ref = extract_references(request.message)

        # Step 1: Search for relevant scripture
        scripture_context, search_context_prompt = await self._search_scripture(
            request,
            translation,
            verse_refs,
            is_verse_lookup,
            detected_language=detected_language,
            model_override=model_override,
        )

        # Step 2: Send metadata before streaming starts
        yield {
            "type": "metadata",
            "message_id": message_id,
            "scripture_context": scripture_context.model_dump() if scripture_context else None,
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "detected_translation": translation,
            "translation_info": translation_info,
        }

        # Step 3: Build messages with appropriate prompt type
        prompt_type = self._determine_prompt_type(is_verse_lookup, prayer_ref)

        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context=search_context_prompt,
            language_code=detected_language,
            prompt_type=prompt_type,
        )

        # Step 4: Stream response content and accumulate full response
        full_response = ""
        async for chunk in self.llm.chat_stream(
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            model_override=model_override,
        ):
            full_response += chunk
            yield {"type": "content", "content": chunk}

        # Step 5: Extract cited verses (dual-source) and yield completion event
        structured = parse_structured_citations(full_response)
        regex_extracted = extract_all_references(full_response)

        # Merge and deduplicate (structured takes priority, regex catches misses)
        all_verses: dict[str, None] = {}
        for v in structured:
            all_verses[str(v)] = None
        for v in regex_extracted:
            key = str(v)
            if key not in all_verses:
                all_verses[key] = None

        verses_cited = list(all_verses.keys())

        # Track LLM structured output compliance — helps decide whether to
        # invest in tool/function calling as a more reliable mechanism.
        has_structured = len(structured) > 0
        has_regex = len(regex_extracted) > 0
        logger.info(
            "Verse extraction completed",
            extra={
                "structured_count": len(structured),
                "regex_count": len(regex_extracted),
                "total_unique": len(verses_cited),
                "llm_structured_present": has_structured,
                "regex_only": has_regex and not has_structured,
            },
        )

        yield {
            "type": "completion",
            "verses_cited": verses_cited,
        }

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
            prompt_type: Type of prompt ("default", "verse_lookup", "prayer_lookup", "off_topic")

        Returns:
            List of ChatMessage objects for the LLM
        """
        logger.debug(
            "Building messages for LLM",
            extra={
                "language_code": language_code,
                "prompt_type": prompt_type,
                "has_search_context": bool(search_context),
            },
        )

        messages = []

        # Select appropriate system prompt based on request type
        if prompt_type == "off_topic":
            system_prompt = get_system_prompt(language_code) + "\n\n" + OFF_TOPIC_PROMPT
        elif prompt_type == "verse_lookup":
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
