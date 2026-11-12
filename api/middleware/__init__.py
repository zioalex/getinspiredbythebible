"""
Middleware package for Vox Quieta API.

Provides:
- AccessAuditMiddleware: Classifies API requests as official/unofficial (observability)
- BodySizeLimitMiddleware: Rejects oversized request bodies with 413 (BITB-296)
- CorrelationIDMiddleware: Request tracing via X-Request-ID header
- REQUEST_ID_CTX_VAR: ContextVar for accessing request ID in handlers

Note: AccessAuditMiddleware and BodySizeLimitMiddleware are NOT re-exported here to
avoid a circular import. They depend on utils.logging_config, which imports
middleware.context, which triggers this __init__.py.  Import them directly: ``from middleware.access_audit
import AccessAuditMiddleware``, ``from middleware.body_size_limit import
BodySizeLimitMiddleware``.
"""

from middleware.context import REQUEST_ID_CTX_VAR
from middleware.correlation_id import CorrelationIDMiddleware

__all__ = ["CorrelationIDMiddleware", "REQUEST_ID_CTX_VAR"]
