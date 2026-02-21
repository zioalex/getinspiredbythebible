"""
End-to-end smoke tests simulating real user behavior through the frontend.

These tests hit https://getinspiredbythebible.ai4you.sh (the Next.js frontend)
and verify that pages load with the expected content for each locale — exactly
what a real user's browser would do when opening the application.

Architecture note
-----------------
The frontend is a standalone Next.js app (no API proxy). When a user opens
the site, the browser gets HTML/CSS/JS from the frontend URL. The frontend
JS then calls the backend API (NEXT_PUBLIC_API_URL, a separate Azure FQDN)
directly. These tests cover only the frontend tier (page availability and
content). Backend API tests live in tests/functional/test_production_api.py.

Usage
-----
# Against production (default):
    pytest tests/e2e/ -m e2e -v

# Against local dev:
    FRONTEND_URL=http://localhost:3000 \\
        pytest tests/e2e/ -m e2e -v

# Via Makefile:
    make test-e2e          # production
    make test-e2e-local    # localhost:3000

Environment variables
---------------------
FRONTEND_URL   Base URL of the frontend to test against.
               Defaults to https://getinspiredbythebible.ai4you.sh
"""

import os

import httpx
import pytest

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://getinspiredbythebible.ai4you.sh")
TIMEOUT = 30.0

# All locales registered in frontend/src/i18n/routing.ts
SUPPORTED_LOCALES = ["en", "it", "de", "es", "fr", "pt", "ar"]

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Session-scoped client — skips everything if the frontend is not reachable
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def frontend():
    """
    Synchronous httpx Client pointed at FRONTEND_URL with redirect following.
    The entire test session is skipped when the frontend is not reachable.
    """
    try:
        resp = httpx.get(f"{FRONTEND_URL}/en", timeout=10.0, follow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            pytest.skip(
                f"Frontend at {FRONTEND_URL}/en returned non-HTML content-type: {content_type}"
            )
    except Exception as exc:
        pytest.skip(f"Frontend not reachable at {FRONTEND_URL}: {exc}")

    with httpx.Client(base_url=FRONTEND_URL, timeout=TIMEOUT, follow_redirects=True) as client:
        yield client


# ---------------------------------------------------------------------------
# Page availability — simulates a user visiting the site for the first time
# ---------------------------------------------------------------------------


class TestFrontendPageAvailability:
    """Every locale page must load with HTTP 200 and return HTML content."""

    def test_root_redirects_to_locale(self, frontend):
        """GET / redirects to a locale-prefixed page (browser behavior at site root)."""
        r = frontend.get("/")
        assert r.status_code == 200
        final_url = str(r.url)
        assert any(
            f"/{locale}" in final_url for locale in SUPPORTED_LOCALES
        ), f"Root redirect landed on unexpected URL: {final_url}"

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_locale_page_loads(self, frontend, locale):
        """Each supported locale page returns 200 HTML (user can open /{locale})."""
        r = frontend.get(f"/{locale}")
        assert r.status_code == 200, f"Expected 200 for /{locale}, got {r.status_code}"
        assert "text/html" in r.headers.get(
            "content-type", ""
        ), f"Expected HTML for /{locale}, got: {r.headers.get('content-type')}"

    def test_unknown_locale_not_server_error(self, frontend):
        """An unknown locale /xx must not return 5xx (user typo tolerance)."""
        r = frontend.get("/xx")
        assert (
            r.status_code < 500
        ), f"Unknown locale /xx should not cause 5xx server error, got {r.status_code}"


# ---------------------------------------------------------------------------
# Page content — simulates reading the page the user sees
# ---------------------------------------------------------------------------


class TestFrontendPageContent:
    """The pages users see must contain the expected UI elements and text."""

    def test_english_page_has_bible_content(self, frontend):
        """The English page mentions the Bible (sanity check of page content)."""
        r = frontend.get("/en")
        assert r.status_code == 200
        html = r.text
        assert (
            "bible" in html.lower() or "scripture" in html.lower()
        ), "English page does not mention the Bible or Scripture anywhere"

    def test_english_page_has_chat_input(self, frontend):
        """A chat input element is present on the English page."""
        r = frontend.get("/en")
        assert r.status_code == 200
        html = r.text.lower()
        has_input = "textarea" in html or "<input" in html
        assert has_input, "No chat input/textarea element found in English page HTML"

    def test_english_page_is_not_empty(self, frontend):
        """The English page returns substantial HTML (not an error stub)."""
        r = frontend.get("/en")
        assert r.status_code == 200
        assert len(r.text) > 1000, (
            f"English page HTML is suspiciously short ({len(r.text)} bytes) — "
            "might be an error page"
        )

    @pytest.mark.parametrize("locale", SUPPORTED_LOCALES)
    def test_locale_page_is_not_empty(self, frontend, locale):
        """Each locale page returns substantial HTML."""
        r = frontend.get(f"/{locale}")
        assert r.status_code == 200
        assert (
            len(r.text) > 1000
        ), f"/{locale} page HTML is suspiciously short ({len(r.text)} bytes)"

    @pytest.mark.parametrize(
        "locale",
        ["en", "it", "de", "es", "fr", "pt", "ar"],
    )
    def test_locale_url_contains_locale_code(self, frontend, locale):
        """After loading /{locale} the final URL still contains the locale code."""
        r = frontend.get(f"/{locale}")
        assert r.status_code == 200
        assert locale in str(r.url), f"Expected /{locale} in final URL, got: {r.url}"


# ---------------------------------------------------------------------------
# Real user flows — simulate common navigation patterns
# ---------------------------------------------------------------------------


class TestFrontendUserFlows:
    """Simulate the most common user journeys through the frontend."""

    def test_user_opens_app_in_english(self, frontend):
        """
        Simulate an English-speaking user opening the app.
        GET /en → 200 HTML with substantial content.
        """
        r = frontend.get("/en")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        assert len(r.text) > 1000

    def test_user_opens_app_in_italian(self, frontend):
        """
        Simulate an Italian-speaking user opening the app.
        GET /it → 200 HTML.
        """
        r = frontend.get("/it")
        assert r.status_code == 200
        assert len(r.text) > 1000

    def test_user_opens_app_in_spanish(self, frontend):
        """
        Simulate a Spanish-speaking user opening the app.
        GET /es → 200 HTML.
        """
        r = frontend.get("/es")
        assert r.status_code == 200
        assert len(r.text) > 1000

    def test_user_opens_app_in_arabic(self, frontend):
        """
        Simulate an Arabic-speaking user opening the app.
        GET /ar → 200 HTML.
        """
        r = frontend.get("/ar")
        assert r.status_code == 200
        assert len(r.text) > 1000

    def test_user_opens_app_with_browser_headers(self, frontend):
        """
        Simulate a real browser GET with Accept and User-Agent headers.
        Verifies the app works for real users, not just curl/httpx.
        """
        r = frontend.get(
            "/en",
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        )
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    def test_user_navigates_between_locales(self, frontend):
        """
        Simulate a user switching languages: start at /en, then visit /es.
        Both pages must load successfully.
        """
        r_en = frontend.get("/en")
        assert r_en.status_code == 200

        r_es = frontend.get("/es")
        assert r_es.status_code == 200

        # Both pages must have content
        assert len(r_en.text) > 1000
        assert len(r_es.text) > 1000
