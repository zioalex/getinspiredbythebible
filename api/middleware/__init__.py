"""
Middleware package for Bible Inspiration Chat API.

Provides:
- CorrelationIDMiddleware: Request tracing via X-Request-ID header
- REQUEST_ID_CTX_VAR: ContextVar for accessing request ID in handlers
"""

from middleware.context import REQUEST_ID_CTX_VAR
from middleware.correlation_id import CorrelationIDMiddleware

__all__ = ["CorrelationIDMiddleware", "REQUEST_ID_CTX_VAR"]
