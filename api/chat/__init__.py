"""
Chat package - Conversation orchestration and prompts.
"""

from .service import (
    ChatService,
    ChatRequest,
    ChatResponse,
    ConversationMessage
)
from .prompts import (
    SYSTEM_PROMPT,
    build_search_context_prompt,
    build_conversation_context
)

__all__ = [
    "ChatService",
    "ChatRequest",
    "ChatResponse",
    "ConversationMessage",
    "SYSTEM_PROMPT",
    "build_search_context_prompt",
    "build_conversation_context",
]
