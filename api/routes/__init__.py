"""
API Routes package.
"""

from .chat import router as chat_router
from .church import router as church_router
from .feedback import router as feedback_router
from .health import router as health_router
from .scripture import router as scripture_router

__all__ = [
    "chat_router",
    "church_router",
    "feedback_router",
    "health_router",
    "scripture_router",
]
