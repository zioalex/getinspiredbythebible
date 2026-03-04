"""
Context variables for request-scoped data.

This module defines ContextVars that are set by middleware and accessible
throughout the request lifecycle. By placing these in a separate module,
we avoid circular import issues between middleware and logging configuration.
"""

from contextvars import ContextVar

# Request ID for correlation across logs, traces, and debugging
REQUEST_ID_CTX_VAR: ContextVar[str] = ContextVar("request_id", default="")
