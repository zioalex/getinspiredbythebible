"""
Chat Service - Orchestrates Bible-grounded conversations.

This service combines scripture search, LLM generation, and
conversation management to create meaningful spiritual dialogues.
"""

import asyncio
import hashlib
import time
import uuid
from dataclasses import dataclass
from typing import AsyncIterator

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from providers import ChatMessage, EmbeddingProvider, LLMProvider
from scripture import ScriptureSearchService, SearchResults
from utils.content_safety import get_content_safety_service
from utils.language import (
    detect_language,
    detect_language_confident,
    get_model_override_for_language,
    get_translation_info,
    resolve_translation,
)
from utils.logging_config import get_logger
from utils.metrics import (
    chat_verseless_responses_counter,
    scripture_pipeline_errors_counter,
    verse_grounding_corrections_counter,
    verse_grounding_duration_histogram,
    verse_grounding_quotes_checked_counter,
)
from utils.timing import format_timings, record_stage, timed_stage
from utils.verse_parser import (
    extract_all_references,
    extract_inline_quotes,
    extract_references,
    is_verse_lookup_request,
    parse_structured_citations,
)

from .prompts import (
    OFF_TOPIC_PROMPT,
    build_search_context_prompt,
    detect_intent_prompt,
    get_blocked_response,
    get_compassionate_addendum,
    get_prayer_lookup_prompt,
    get_system_prompt,
    get_verse_lookup_prompt,
)
from .topics import detect_topics
from .verse_grounding import ground_response

logger = get_logger(__name__)

# Upper bound on how many verses a single cited range may expand to when
# resolving cited verses for the client "Cited" panel. Guards against an LLM
# emitting an absurd range (e.g. "Psalm 119:1-176") triggering a huge fetch.
MAX_RANGE_SPAN = 50


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
    language: str | None = Field(
        default=None, max_length=10
    )  # Explicit language code from the client (e.g. "it", "de"). When present,
    # overrides server-side language detection so responses are always in the
    # user's chosen language regardless of what language they type in.

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
    language_suggestion: str | None = None  # Detected language differs from selected UI language


@dataclass
class _SafetyOutcome:
    """Result from _check_content_safety — replaces the old raise-or-return-bool pattern."""

    allowed: bool
    compassionate: bool
    reason: str
    categories: dict[str, int]


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
        # Per-request timing context read by the @timed_stage decorator. Set at the top
        # of chat()/chat_stream(); a fresh ChatService is created per request
        # (api/routes/chat.py), so these are safe to keep on the instance.
        self._timings: dict[str, float] | None = None
        self._stage_attrs: dict | None = None
        self._active_stages: set[str] = set()

    @timed_stage("intent")
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

    @timed_stage("content_safety")
    async def _check_content_safety(
        self,
        message: str,
        detected_language: str,
        session_id: str | None,
        context: str = "chat",
    ) -> _SafetyOutcome:
        """
        Check message for harmful content.

        Args:
            message: The user's message to check
            detected_language: ISO language code detected from message
            session_id: Session identifier for logging
            context: Context label for log messages (e.g., 'chat' or 'chat stream')

        Returns:
            _SafetyOutcome with allowed/compassionate flags and reason.
            Never raises — callers handle blocked content by streaming a synthetic response.
        """
        if not settings.content_safety_enabled:
            return _SafetyOutcome(
                allowed=True, compassionate=False, reason="disabled", categories={}
            )

        safety_service = get_content_safety_service()
        safety_result = await safety_service.check(message, detected_language)
        text_hash = hashlib.sha256(message.encode()).hexdigest()[:16]

        if not safety_result.allowed:
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
            # Best-effort capture for filter tuning (no PII, TTL-bounded).
            try:
                from feedback.blocked_samples import record_blocked_sample

                await record_blocked_sample(
                    message=message,
                    stage="content_safety",
                    categories=safety_result.categories,
                    language=detected_language,
                    session_id=session_id,
                )
            except Exception:
                pass
            return _SafetyOutcome(
                allowed=False,
                compassionate=False,
                reason=safety_result.reason,
                categories=safety_result.categories,
            )

        if safety_result.compassionate_response_needed:
            logger.info(
                f"Help-seeking message detected in {context}, injecting compassionate prompt",
                extra={"text_hash": text_hash, "language": detected_language},
            )

        return _SafetyOutcome(
            allowed=True,
            compassionate=safety_result.compassionate_response_needed,
            reason=safety_result.reason,
            categories=safety_result.categories,
        )

    async def _expand_query(
        self, user_message: str, language: str, model_override: str | None = None
    ) -> str:
        """
        Expand user query with related biblical themes and concepts using LLM.

        Uses low temperature for consistent expansion results.
        Falls back to original message on any error (fail-open).
        """
        expansion_prompt = f"""You are helping expand a search query to find thematically relevant Bible verses.

User's message: "{user_message}"
Language: {language}

First, identify the ONE or TWO central spiritual or emotional themes the person is \
actually expressing (for example: anxiety, grief, forgiveness, guidance, hope, \
loneliness). Stay anchored to those core themes — do NOT drift into loosely related \
topics, because off-theme terms pull in irrelevant verses and hurt search quality.

Then build a focused expanded query that stays on theme, including:
- The core emotion(s)/feeling(s) actually present in the message
- The closely related biblical themes they map to (e.g. anxiety → God's peace, trust, \
"do not be afraid"; grief → comfort, hope, God's nearness; guilt → forgiveness, grace)
- Scriptural vocabulary and synonyms for those themes
- The concrete life situation the person is facing

Prefer depth on the real theme over breadth: a tight set of on-theme terms retrieves \
better verses than a long, scattered list. Use recognizable scriptural wording.

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

    @timed_stage("query_expansion")
    async def _build_expansion_embeddings(
        self, message: str, detected_language: str, model_override: str | None = None
    ) -> list[list[float]] | None:
        """Expand the query and embed the expansion for multi-embedding search.

        Returns the extra embeddings to feed into semantic search, or ``None`` when
        expansion produced nothing new. Timed as the ``query_expansion`` stage.
        """
        expanded_query = await self._expand_query(message, detected_language, model_override)
        if expanded_query == message:
            return None
        expansion_embed_response = await self.embedding.embed(expanded_query)
        extra_embeddings = [expansion_embed_response.embedding]
        logger.info(
            "Query expansion embeddings generated",
            extra={"num_extra_embeddings": len(extra_embeddings)},
        )
        return extra_embeddings

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
        timings: dict[str, float] = {}
        stage_attrs = {"stream": False, "provider": settings.llm_provider}
        # Activate the per-request timing context read by @timed_stage-decorated methods.
        self._timings = timings
        self._stage_attrs = stage_attrs
        self._active_stages = set()
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
        # Use the client-supplied language when present; fall back to auto-detection.
        # This ensures the AI always responds in the language the user selected in the
        # app, even when they type their question in a different language.
        effective_language = request.language if request.language else detected_language
        translation = resolve_translation(request.preferred_translation, effective_language)
        translation_info = get_translation_info(translation)
        model_override = get_model_override_for_language(effective_language)
        # Suggest a language switch only when the user explicitly set a UI language,
        # we're confident the message is in a *different* language, and confidence
        # is high enough to avoid false positives on short/ambiguous text.
        _confident_lang = detect_language_confident(request.message)
        language_suggestion = (
            _confident_lang
            if (request.language and _confident_lang and _confident_lang != request.language)
            else None
        )
        logger.info(
            "Language detection and translation resolution",
            extra={
                "detected_language": detected_language,
                "client_language": request.language,
                "effective_language": effective_language,
                "translation": translation,
                "user_preference": request.preferred_translation,
                "model_override": model_override,
                "message_preview": request.message[:50],
            },
        )

        # Content safety check BEFORE LLM call (timed via @timed_stage on the method)
        safety = await self._check_content_safety(
            request.message, effective_language, request.session_id, context="chat"
        )
        if not safety.allowed:
            return self._build_blocked_response(
                safety, effective_language, translation, translation_info
            )

        # Intent detection: classify before scripture search
        if settings.content_filter_intent_detection:
            detected_intent = await self._detect_intent(request.message, model_override)
            if detected_intent == "OFF_TOPIC":
                return await self._handle_off_topic(
                    request,
                    effective_language,
                    translation,
                    translation_info,
                    total_start,
                    model_override,
                    compassionate_mode=safety.compassionate,
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

        # Step 1: Search for relevant scripture (if enabled; timed via @timed_stage)
        scripture_context, search_context_prompt = await self._search_scripture(
            request,
            translation,
            verse_refs,
            is_verse_lookup,
            detected_language=effective_language,
            model_override=model_override,
        )

        # Step 2: Build the message list
        prompt_type = self._determine_prompt_type(is_verse_lookup, prayer_ref)

        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context=search_context_prompt,
            language_code=effective_language,
            prompt_type=prompt_type,
            compassionate_mode=safety.compassionate,
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
            record_stage(timings, "generation", llm_duration * 1000, stage_attrs)
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

        # Ground the response: rewrite any fabricated/mismatched inline verse
        # quote to the canonical DB text before returning it to the client.
        message, _ = await self._apply_verse_grounding(
            response.content, scripture_context, translation, effective_language
        )

        record_stage(timings, "total", (time.time() - total_start) * 1000, stage_attrs)
        logger.info(
            "chat_stage_timings %s",
            format_timings(timings),
            extra={"timings_ms": timings, "stream": False},
        )

        return ChatResponse(
            message_id=message_id,
            message=message,
            scripture_context=scripture_context,
            provider=response.provider,
            model=response.model,
            detected_translation=translation,
            translation_info=translation_info,
            language_suggestion=language_suggestion,
        )

    async def _handle_off_topic(
        self,
        request: ChatRequest,
        detected_language: str,
        translation: str,
        translation_info: dict | None,
        total_start: float,
        model_override: str | None = None,
        compassionate_mode: bool = False,
    ) -> ChatResponse:
        """Generate a warm redirect response for off-topic messages, skipping scripture search."""
        logger.info("Off-topic message detected, skipping scripture search")
        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context="",
            language_code=detected_language,
            prompt_type="off_topic",
            compassionate_mode=compassionate_mode,
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

    def _build_blocked_response(
        self,
        outcome: _SafetyOutcome,
        language: str,
        translation: str,
        translation_info: dict | None,
    ) -> "ChatResponse":
        """Return a warm pre-written ChatResponse for blocked content (no LLM call)."""
        message = get_blocked_response(outcome.reason, language)
        logger.info(
            "Returning synthetic blocked-content response",
            extra={"reason": outcome.reason, "language": language},
        )
        return ChatResponse(
            message_id=str(uuid.uuid4()),
            message=message,
            scripture_context=None,
            provider="content_safety",
            model="content_safety",
            detected_translation=translation,
            translation_info=translation_info,
        )

    async def _stream_blocked_response(
        self,
        outcome: _SafetyOutcome,
        message_id: str,
        language: str,
        translation: str,
        translation_info: dict | None,
    ) -> AsyncIterator[dict]:
        """Yield SSE-compatible chunks for a blocked-content synthetic response."""
        text = get_blocked_response(outcome.reason, language)
        logger.info(
            "Streaming synthetic blocked-content response",
            extra={"reason": outcome.reason, "language": language},
        )
        yield {
            "type": "metadata",
            "message_id": message_id,
            "scripture_context": None,
            "provider": "content_safety",
            "model": "content_safety",
            "detected_translation": translation,
            "translation_info": translation_info,
        }
        # Chunk by ~3-word segments to match real streaming cadence
        words = text.split(" ")
        chunk_size = 3
        for i in range(0, len(words), chunk_size):
            piece = " ".join(words[i : i + chunk_size])
            if i + chunk_size < len(words):
                piece += " "
            yield {"type": "content", "content": piece}
            await asyncio.sleep(0)  # cooperative yield, no real delay
        yield {"type": "completion", "verses_cited": []}

    @timed_stage("retrieval")
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
                extra_embeddings = await self._build_expansion_embeddings(
                    request.message, detected_language, model_override
                )

            # Topic detection for boosting (keyword-based, <10ms)
            boost_topics: list[str] = []
            if settings.topic_boosting_enabled:
                boost_topics = self._detect_topics(request.message)

            # Semantic or hybrid search (optionally with topic boosting).
            # Query-expansion embeddings (when present) feed straight into the hybrid
            # search so expansion actually widens recall on the result we use — and the
            # HNSW candidate pool keeps it index-backed (no full-table scan).
            if settings.hybrid_search_enabled:
                if settings.topic_boosting_enabled and boost_topics:
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
                        extra_embeddings=extra_embeddings,
                    )
                else:
                    scripture_context = await self.search_service.search_hybrid(
                        query=request.message,
                        max_verses=settings.max_context_verses,
                        max_passages=2,
                        similarity_threshold=0.35,
                        translation=translation,
                        semantic_weight=settings.hybrid_search_semantic_weight,
                        keyword_weight=settings.hybrid_search_keyword_weight,
                        extra_embeddings=extra_embeddings,
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
            scripture_pipeline_errors_counter.add(
                1, {"stage": "search", "error_type": type(e).__name__}
            )
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

    async def _resolve_cited_verses(self, verse_refs: list, translation: str | None = None) -> list:
        """Resolve cited VerseReferences to full VerseResult objects.

        Unlike the semantic search pool (driven by the user's query), this returns
        exactly the verses the answer cited — expanding ranges to individual
        verses — so clients can merge them into their verse panel and the "Cited"
        tab is populated even for verses outside the pool. Dedupes by canonical
        reference and never raises: a DB miss or lookup error is skipped so the
        stream is never broken.
        """
        resolved: dict[str, object] = {}
        for ref in verse_refs:
            try:
                if ref.verse_end and ref.verse_end > ref.verse_start:
                    # Cap pathological ranges (e.g. an LLM emitting "Psalm
                    # 119:1-176") so we never issue a huge fetch.
                    end = min(ref.verse_end, ref.verse_start + MAX_RANGE_SPAN - 1)
                    range_verses = await self.search_service.get_verse_range(
                        ref.book, ref.chapter, ref.verse_start, end, translation
                    )
                    for verse in range_verses:
                        resolved.setdefault(verse.reference.lower(), verse)
                else:
                    # Single verse — also covers chapter-spanning ranges where the
                    # parser leaves verse_end < verse_start.
                    verse = await self.search_service.get_verse(
                        ref.book, ref.chapter, ref.verse_start, translation
                    )
                    if verse:
                        resolved.setdefault(verse.reference.lower(), verse)
            except Exception as e:
                scripture_pipeline_errors_counter.add(
                    1, {"stage": "resolve", "error_type": type(e).__name__}
                )
                logger.warning(f"Failed to resolve cited verse {ref}: {e}")
        return list(resolved.values())

    @timed_stage("grounding")
    async def _apply_verse_grounding(
        self,
        text: str,
        scripture_context: SearchResults | None,
        translation: str | None,
        language: str,
        resolved_verses: list | None = None,
    ) -> tuple[str, list]:
        """Rewrite fabricated/mismatched inline verse quotes to canonical DB text.

        Returns (possibly-corrected text, list[Correction]). Reuses pre-resolved
        cited verses when the caller already has them (streaming path) to avoid a
        second DB pass; otherwise resolves the references it finds in ``text``.
        Never raises — grounding must never break a response.
        """
        if not settings.verse_grounding_enabled:
            return text, []
        start = time.perf_counter()
        try:
            if resolved_verses is None:
                resolved_verses = await self._resolve_cited_verses(
                    extract_all_references(text), translation
                )
            context_refs = {
                (v.book.lower(), v.chapter, v.verse)
                for v in (scripture_context.verses if scripture_context else [])
            }
            quotes_checked = len(extract_inline_quotes(text))
            corrected, corrections = ground_response(
                text,
                resolved_verses,
                context_refs,
                strip_unresolved=settings.grounding_strip_unresolved,
            )
        except Exception as e:
            scripture_pipeline_errors_counter.add(
                1, {"stage": "grounding", "language": language, "error_type": type(e).__name__}
            )
            logger.warning(f"Verse grounding skipped due to error: {e}")
            return text, []

        duration_ms = (time.perf_counter() - start) * 1000
        attrs: dict[str, str | bool] = {"language": language, "corrected": bool(corrections)}
        verse_grounding_duration_histogram.record(duration_ms, attrs)
        if quotes_checked:
            verse_grounding_quotes_checked_counter.add(quotes_checked, {"language": language})
        for c in corrections:
            correction_attrs: dict[str, str | bool] = {
                "language": language,
                "reason": c.reason,
                "corrected": c.corrected_quote is not None,
                "book": c.reference.rsplit(" ", 1)[0],
            }
            verse_grounding_corrections_counter.add(1, correction_attrs)
            logger.warning(
                "Scripture fidelity issue corrected",
                extra={
                    "reference": c.reference,
                    "reason": c.reason,
                    "original_quote": c.original_quote[:160],
                    "corrected_quote": (c.corrected_quote or "")[:160],
                    "language": language,
                },
            )
        return corrected, corrections

    @timed_stage("grounding")
    async def _ground_streamed_answer(
        self,
        cited_refs: list,
        full_response: str,
        scripture_context: SearchResults | None,
        translation: str | None,
        language: str,
    ) -> tuple[list, str, list]:
        """Resolve cited verses and ground the streamed answer as one timed stage.

        Returns ``(resolved_verses, corrected_message, corrections)``. The inner
        ``_apply_verse_grounding`` is also ``@timed_stage("grounding")``, but the
        re-entrancy guard means this outer frame owns the single "grounding"
        measurement (resolve + rewrite), matching the previous streaming behaviour.
        """
        resolved_verses = await self._resolve_cited_verses(cited_refs, translation)
        # Ground the streamed answer: detect fabricated/mismatched inline verse quotes
        # and rewrite them to canonical text. Reuses resolved_verses (no extra DB calls).
        # The tokens are already on the client's screen, so the correction is delivered
        # as an authoritative `corrected_message` the client swaps in — only when
        # something actually changed.
        corrected_message, corrections = await self._apply_verse_grounding(
            full_response,
            scripture_context,
            translation,
            language,
            resolved_verses=resolved_verses,
        )
        return resolved_verses, corrected_message, corrections

    def _merge_direct_verses(self, scripture_context: SearchResults, direct_verses: list) -> None:
        """Merge direct lookup verses into scripture context (at beginning)."""
        if not direct_verses or not scripture_context:
            return

        existing_refs = {(v.book, v.chapter, v.verse) for v in scripture_context.verses}
        for dv in direct_verses:
            if (dv.book, dv.chapter, dv.verse) not in existing_refs:
                scripture_context.verses.insert(0, dv)
                existing_refs.add((dv.book, dv.chapter, dv.verse))

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[dict]:  # noqa: C901
        """
        Stream a chat response for real-time display.

        Yields:
            Dict with 'type' field:
            - {'type': 'metadata', 'message_id': '...', 'scripture_context': {...}, ...}
            - {'type': 'content', 'content': '...'}
        """
        # Generate unique message ID for feedback tracking
        message_id = str(uuid.uuid4())

        total_start = time.perf_counter()
        timings: dict[str, float] = {}
        stage_attrs = {"stream": True, "provider": settings.llm_provider}
        # Activate the per-request timing context read by @timed_stage-decorated methods.
        self._timings = timings
        self._stage_attrs = stage_attrs
        self._active_stages = set()

        # Resolve translation: user preference > language detection > default
        detected_language = detect_language(request.message)
        # Use the client-supplied language when present; fall back to auto-detection.
        effective_language = request.language if request.language else detected_language
        translation = resolve_translation(request.preferred_translation, effective_language)
        translation_info = get_translation_info(translation)
        model_override = get_model_override_for_language(effective_language)
        _confident_lang = detect_language_confident(request.message)
        language_suggestion = (
            _confident_lang
            if (request.language and _confident_lang and _confident_lang != request.language)
            else None
        )
        logger.info(
            "Language detection and translation resolution (stream)",
            extra={
                "detected_language": detected_language,
                "client_language": request.language,
                "effective_language": effective_language,
                "translation": translation,
                "user_preference": request.preferred_translation,
                "model_override": model_override,
                "message_preview": request.message[:50],
            },
        )

        # Content safety check BEFORE LLM call (timed via @timed_stage on the method)
        safety = await self._check_content_safety(
            request.message, effective_language, request.session_id, context="chat stream"
        )
        if not safety.allowed:
            async for chunk in self._stream_blocked_response(
                safety, message_id, effective_language, translation, translation_info
            ):
                yield chunk
            return

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
                    "language_suggestion": language_suggestion,
                }

                messages = self._build_messages(
                    user_message=request.message,
                    history=request.conversation_history,
                    search_context="",
                    language_code=effective_language,
                    prompt_type="off_topic",
                    compassionate_mode=safety.compassionate,
                )
                async for token in self.llm.chat_stream(
                    messages=messages,
                    temperature=settings.llm_temperature,
                    max_tokens=settings.llm_max_tokens,
                    model_override=model_override,
                ):
                    yield {"type": "content", "content": token}
                yield {"type": "completion", "verses_cited": []}
                return

        # Check if this is a verse/prayer lookup request
        is_verse_lookup = is_verse_lookup_request(request.message)
        verse_refs, prayer_ref = extract_references(request.message)

        # Step 1: Search for relevant scripture (timed via @timed_stage)
        scripture_context, search_context_prompt = await self._search_scripture(
            request,
            translation,
            verse_refs,
            is_verse_lookup,
            detected_language=effective_language,
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
            "language_suggestion": language_suggestion,
        }

        # Step 3: Build messages with appropriate prompt type
        prompt_type = self._determine_prompt_type(is_verse_lookup, prayer_ref)

        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context=search_context_prompt,
            language_code=effective_language,
            prompt_type=prompt_type,
            compassionate_mode=safety.compassionate,
        )

        # Step 4: Stream response content and accumulate full response
        full_response = ""
        first_token_at: float | None = None
        async for token in self.llm.chat_stream(
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            model_override=model_override,
        ):
            if first_token_at is None:
                # TTFT = everything the user waits through before the first visible
                # token (safety + intent + retrieval + provider latency).
                first_token_at = time.perf_counter()
                record_stage(timings, "ttft", (first_token_at - total_start) * 1000, stage_attrs)
            full_response += token
            yield {"type": "content", "content": token}
        if first_token_at is not None:
            record_stage(
                timings, "generation", (time.perf_counter() - first_token_at) * 1000, stage_attrs
            )

        # Step 5: Extract cited verses (dual-source) and yield completion event
        structured = parse_structured_citations(full_response)
        regex_extracted = extract_all_references(full_response)

        # Merge and deduplicate (structured takes priority, regex catches misses).
        # Keep the VerseReference objects (not just their string form) so we can
        # resolve them against the DB below — including verses the LLM cited that
        # are NOT in the semantic search pool.
        merged_refs: dict[str, object] = {}
        for v in structured:
            merged_refs.setdefault(str(v), v)
        for v in regex_extracted:
            merged_refs.setdefault(str(v), v)

        verses_cited = list(merged_refs.keys())

        # Resolve the cited references to full VerseResult objects so the client
        # can merge them into its verse panel. Without this, a cited verse that
        # is outside the semantic pool (common on follow-up questions) never
        # appears in the "Cited" tab.
        resolved_verses, corrected_message, corrections = await self._ground_streamed_answer(
            list(merged_refs.values()),
            full_response,
            scripture_context,
            translation,
            effective_language,
        )

        # AC2 (BITB-055): emit a business-level SLI when scripture search was
        # attempted but produced zero DB context AND zero resolved citations —
        # the exact signature of a silent pipeline failure (e.g. the 2-week
        # SQL bug that broke all retrieval without any 5xx or user alert).
        # Off-topic early-returns (include_search=False) are excluded; those
        # are expected to be verse-less.
        if (
            request.include_search
            and not (scripture_context and scripture_context.verses)
            and not resolved_verses
        ):
            chat_verseless_responses_counter.add(1, {"language": effective_language})

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
                "cited_resolved": len(resolved_verses),
                "llm_structured_present": has_structured,
                "regex_only": has_regex and not has_structured,
            },
        )

        # Two distinct fields, intentionally:
        #   verses_cited   - list[str] of raw citation references (range form
        #                    preserved, e.g. "Romans 8:38-39"; may include refs
        #                    not in the DB). Drives the client's intersection
        #                    "Cited" filter and feedback logging.
        #   resolved_verses - list[VerseResult] of the SAME citations resolved
        #                    against the DB (ranges expanded to individual
        #                    verses, with text + localized_book). The client
        #                    merges these into its verse pool so the filter has
        #                    cards to match even for verses outside the semantic
        #                    search results.
        completion: dict = {
            "type": "completion",
            "verses_cited": verses_cited,
            "resolved_verses": [v.model_dump() for v in resolved_verses],
        }
        # Only sent when a quote was rewritten; older clients ignore unknown
        # fields, so this is backward compatible.
        if corrections:
            completion["corrected_message"] = corrected_message
            completion["corrections"] = [
                {"reference": c.reference, "reason": c.reason} for c in corrections
            ]

        record_stage(timings, "total", (time.perf_counter() - total_start) * 1000, stage_attrs)
        logger.info(
            "chat_stage_timings %s",
            format_timings(timings),
            extra={"timings_ms": timings, "stream": True},
        )

        yield completion

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
        compassionate_mode: bool = False,
    ) -> list[ChatMessage]:
        """
        Build the message list for the LLM.

        Args:
            user_message: Current user message
            history: Previous conversation messages
            search_context: Optional scripture context from search
            language_code: Detected language code for response language
            prompt_type: Type of prompt ("default", "verse_lookup", "prayer_lookup", "off_topic")
            compassionate_mode: When True, appends COMPASSIONATE_RESPONSE_ADDENDUM to system prompt

        Returns:
            List of ChatMessage objects for the LLM
        """
        logger.debug(
            "Building messages for LLM",
            extra={
                "language_code": language_code,
                "prompt_type": prompt_type,
                "has_search_context": bool(search_context),
                "compassionate_mode": compassionate_mode,
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

        if compassionate_mode:
            system_prompt = system_prompt + get_compassionate_addendum()

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
