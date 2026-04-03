"""
Middleware package for Bible Inspiration Chat API.

Provides:
- AccessAuditMiddleware: Classifies API requests as official/unofficial (observability)
- CorrelationIDMiddleware: Request tracing via X-Request-ID header
- REQUEST_ID_CTX_VAR: ContextVar for accessing request ID in handlers
"""

from middleware.access_audit import AccessAuditMiddleware
from middleware.context import REQUEST_ID_CTX_VAR
from middleware.correlation_id import CorrelationIDMiddleware

__all__ = ["AccessAuditMiddleware", "CorrelationIDMiddleware", "REQUEST_ID_CTX_VAR"]
