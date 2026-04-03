"""
Middleware package for Bible Inspiration Chat API.

Provides:
- AccessAuditMiddleware: Classifies API requests as official/unofficial (observability)
- CorrelationIDMiddleware: Request tracing via X-Request-ID header
- REQUEST_ID_CTX_VAR: ContextVar for accessing request ID in handlers

Note: AccessAuditMiddleware is NOT re-exported here to avoid a circular import.
It depends on utils.logging_config, which imports middleware.context, which
triggers this __init__.py.  Import it directly: ``from middleware.access_audit
import AccessAuditMiddleware``.
"""

from middleware.context import REQUEST_ID_CTX_VAR
from middleware.correlation_id import CorrelationIDMiddleware

__all__ = ["CorrelationIDMiddleware", "REQUEST_ID_CTX_VAR"]
