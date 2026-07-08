"""
Cross-provider runtime error types.

These are raised by providers at request time (as opposed to `ProviderError`
in `factory.py`, which signals provider *construction*/configuration failures).
"""

from typing import Literal


class AllModelsExhaustedError(RuntimeError):
    """Raised when a provider's primary model and all configured fallbacks fail
    for a single request. Subclasses `RuntimeError` so any pre-existing
    `except RuntimeError` handler still catches it as a safety net; routes
    should catch this type explicitly to return a 503 instead of a 500.
    """

    def __init__(
        self,
        message: str,
        *,
        reason: Literal["rate_limited", "unavailable"],
        models_tried: list[str],
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.models_tried = models_tried
        self.retry_after = retry_after
