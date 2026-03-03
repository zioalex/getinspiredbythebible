"""
Correlation ID Middleware for request tracing.

Adds a unique request ID to every incoming request. The ID is:
- Extracted from the X-Request-ID header if provided by the client
- Generated as a UUID v4 if not provided

The request ID is:
- Stored in a ContextVar for access throughout the request lifecycle
- Added to all log entries via the CorrelationIDFilter
- Returned in the X-Request-ID response header
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from middleware.context import REQUEST_ID_CTX_VAR


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that assigns a correlation ID to every request.

    The correlation ID is used to trace a single request through the entire
    application lifecycle, making it easier to debug issues and correlate
    logs, traces, and errors.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        """
        Process the request and add correlation ID.

        Args:
            request: The incoming request
            call_next: The next middleware/handler in the chain

        Returns:
            Response with X-Request-ID header added
        """
        # Extract X-Request-ID from incoming headers, or generate new UUID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store in context var (accessible throughout request lifecycle)
        token = REQUEST_ID_CTX_VAR.set(request_id)

        try:
            # Process request
            response: Response = await call_next(request)  # type: ignore[assignment]

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response
        finally:
            # Clean up context var
            REQUEST_ID_CTX_VAR.reset(token)
