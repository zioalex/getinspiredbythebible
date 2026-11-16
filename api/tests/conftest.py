"""Shared pytest fixtures."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(autouse=True)
def _reset_ip_rate_limiters():
    """BITB-298: per-scope IP limiters (search/feedback/contact/church) are process-global.

    Many tests POST to those routes from the same TestClient IP; without a reset the counters
    would leak between tests and trip the new limits. The /scripture/stats cache is reset too so a cached
    payload never leaks between tests.
    """
    try:
        from routes.scripture import reset_stats_cache
        from utils.rate_limiter import reset_rate_limiter
    except ModuleNotFoundError:
        # BITB-319: the post-deploy smoke job (azure-deploy.yml functional-tests) installs
        # only httpx/pytest/pydantic and runs tests/e2e + tests/functional against live URLs.
        # Those never touch in-process limiters, and importing the app needs fastapi.
        yield
        return

    reset_rate_limiter()
    reset_stats_cache()
    yield
    reset_rate_limiter()
    reset_stats_cache()
