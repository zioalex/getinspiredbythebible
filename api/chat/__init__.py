"""
Chat package - Conversation orchestration and prompts.
"""

from .prompts import SYSTEM_PROMPT, build_conversation_context, build_search_context_prompt
from .service import ChatRequest, ChatResponse, ChatService, ConversationMessage

__all__ = [
    "ChatService",
    "ChatRequest",
    "ChatResponse",
    "ConversationMessage",
    "SYSTEM_PROMPT",
    "build_search_context_prompt",
    "build_conversation_context",
]
