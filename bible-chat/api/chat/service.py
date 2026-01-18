"""
Chat Service - Orchestrates Bible-grounded conversations.

This service combines scripture search, LLM generation, and
conversation management to create meaningful spiritual dialogues.
"""

from pydantic import BaseModel
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

from providers import LLMProvider, EmbeddingProvider, ChatMessage
from scripture import ScriptureSearchService, SearchResults
from config import settings
from .prompts import (
    SYSTEM_PROMPT,
    build_search_context_prompt,
    COMFORT_SEEKING_PROMPT,
    GUIDANCE_SEEKING_PROMPT,
    CURIOSITY_PROMPT,
    VERSE_EXPLANATION_PROMPT
)


class ConversationMessage(BaseModel):
    """A message in the conversation."""
    role: str  # 'user' or 'assistant'
    content: str


class ChatRequest(BaseModel):
    """Request to the chat endpoint."""
    message: str
    conversation_history: list[ConversationMessage] = []
    include_search: bool = True  # Whether to search scripture first


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    message: str
    scripture_context: SearchResults | None = None
    provider: str
    model: str


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
        embedding_provider: EmbeddingProvider
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
        # Step 1: Search for relevant scripture (if enabled)
        scripture_context = None
        search_context_prompt = ""
        
        if request.include_search:
            scripture_context = await self.search_service.search(
                query=request.message,
                max_verses=settings.max_context_verses,
                max_passages=2,
                similarity_threshold=0.35
            )
            
            # Build context prompt from search results
            if scripture_context.verses or scripture_context.passages:
                search_context_prompt = build_search_context_prompt({
                    "verses": [v.model_dump() for v in scripture_context.verses],
                    "passages": [p.model_dump() for p in scripture_context.passages]
                })
        
        # Step 2: Build the message list
        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context=search_context_prompt
        )
        
        # Step 3: Generate response
        response = await self.llm.chat(
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens
        )
        
        return ChatResponse(
            message=response.content,
            scripture_context=scripture_context,
            provider=response.provider,
            model=response.model
        )
    
    async def chat_stream(
        self, 
        request: ChatRequest
    ) -> AsyncIterator[str]:
        """
        Stream a chat response for real-time display.
        
        Yields:
            Chunks of the response as they're generated
        """
        # Step 1: Search for relevant scripture
        search_context_prompt = ""
        
        if request.include_search:
            scripture_context = await self.search_service.search(
                query=request.message,
                max_verses=settings.max_context_verses,
                max_passages=2,
                similarity_threshold=0.35
            )
            
            if scripture_context.verses or scripture_context.passages:
                search_context_prompt = build_search_context_prompt({
                    "verses": [v.model_dump() for v in scripture_context.verses],
                    "passages": [p.model_dump() for p in scripture_context.passages]
                })
        
        # Step 2: Build messages
        messages = self._build_messages(
            user_message=request.message,
            history=request.conversation_history,
            search_context=search_context_prompt
        )
        
        # Step 3: Stream response
        async for chunk in self.llm.chat_stream(
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens
        ):
            yield chunk
    
    def _build_messages(
        self,
        user_message: str,
        history: list[ConversationMessage],
        search_context: str = ""
    ) -> list[ChatMessage]:
        """
        Build the message list for the LLM.
        
        Args:
            user_message: Current user message
            history: Previous conversation messages
            search_context: Optional scripture context from search
            
        Returns:
            List of ChatMessage objects for the LLM
        """
        messages = []
        
        # System prompt with optional search context
        system_content = SYSTEM_PROMPT
        if search_context:
            system_content = search_context + "\n" + SYSTEM_PROMPT
        
        messages.append(ChatMessage(role="system", content=system_content))
        
        # Add conversation history (limited to max)
        recent_history = history[-settings.max_conversation_history:]
        for msg in recent_history:
            messages.append(ChatMessage(role=msg.role, content=msg.content))
        
        # Add current user message
        messages.append(ChatMessage(role="user", content=user_message))
        
        return messages
    
    async def get_verse_context(
        self,
        book: str,
        chapter: int,
        verse: int
    ) -> dict:
        """
        Get a verse with surrounding context.
        
        Useful when user clicks on a verse to learn more.
        """
        verses = await self.search_service.get_context(
            book=book,
            chapter=chapter,
            verse=verse,
            context_size=3
        )
        
        return {
            "target_verse": verse,
            "verses": [v.model_dump() for v in verses]
        }
