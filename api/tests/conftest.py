"""Shared pytest fixtures."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _reset_ip_rate_limiters():
    """BITB-298: per-scope IP limiters (search/feedback/contact/church) are process-global.

    Many tests POST to those routes from the same TestClient IP; without a reset the counters
    would leak between tests and trip the new limits.
    """
    from utils.rate_limiter import reset_rate_limiter

    reset_rate_limiter()
    yield
    reset_rate_limiter()
