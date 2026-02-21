"""
Functional tests against the live backend API.

These make **real HTTP requests** — they are NOT mocked.
The entire suite is skipped automatically when the API is unreachable.

Architecture note
-----------------
These tests target the **backend API** directly (FastAPI on Azure Container Apps).
The backend URL is separate from the frontend URL (https://getinspiredbythebible.ai4you.sh).
In CI, BACKEND_API_URL is passed from the deploy job output. Locally, set it
to http://localhost:8000 or the Azure Container Apps FQDN.

For frontend page tests (simulating real user browser visits), see tests/e2e/.

Usage
-----
# Against production backend (set BACKEND_API_URL in CI via deploy job output):
    BACKEND_API_URL=https://<backend-fqdn>.azurecontainerapps.io \
        pytest tests/functional/ -m functional -v

# Against local dev:
    BACKEND_API_URL=http://localhost:8000 \
        pytest tests/functional/ -m functional -v

# Via Makefile:
    make test-functional          # production (requires BACKEND_API_URL)
    make test-functional-local    # localhost:8000

Environment variables
---------------------
BACKEND_API_URL   Base URL of the backend API to test against (required in CI).
                  Falls back to FUNCTIONAL_TEST_URL for backward compatibility.
                  No default — the suite is skipped if no URL is configured.
"""

import os

import httpx
import pytest

# BACKEND_API_URL is the Azure Container Apps FQDN for the backend API.
# FUNCTIONAL_TEST_URL is kept as a backward-compat alias.
BASE_URL = os.environ.get("BACKEND_API_URL") or os.environ.get("FUNCTIONAL_TEST_URL") or ""
TIMEOUT = 30.0

pytestmark = pytest.mark.functional


# ---------------------------------------------------------------------------
# Session-scoped client — skips everything if the API is down
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def api():
    """
    Synchronous httpx Client pointed at BASE_URL (the backend API).
    The entire test session is skipped when BASE_URL is not set or not reachable.
    """
    if not BASE_URL:
        pytest.skip("Backend API URL not configured. Set BACKEND_API_URL to the backend FQDN.")

    try:
        resp = httpx.get(f"{BASE_URL}/health/live", timeout=10.0)
        resp.raise_for_status()
    except Exception as exc:
        pytest.skip(f"Backend API not reachable at {BASE_URL}: {exc}")

    with httpx.Client(base_url=BASE_URL, timeout=TIMEOUT) as client:
        yield client


# ---------------------------------------------------------------------------
# Smoke — basic API sanity
# ---------------------------------------------------------------------------


class TestHealthSmoke:
    """Basic liveness / configuration checks."""

    def test_liveness_probe(self, api):
        """GET /health/live always returns 200 with status=alive."""
        r = api.get("/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

    def test_health_check_structure(self, api):
        """GET /health returns a well-formed response with a valid status value."""
        r = api.get("/health")
        assert r.status_code in (200, 503)
        data = r.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "components" in data
        assert "memory" in data

    def test_config_endpoint(self, api):
        """GET /config exposes llm and embedding configuration."""
        r = api.get("/config")
        assert r.status_code == 200
        data = r.json()
        assert "llm" in data
        assert "embedding" in data
        assert "provider" in data["llm"]
        assert "model" in data["llm"]

    def test_translations_list_includes_all_languages(self, api):
        """
        GET /api/v1/scripture/translations returns all 8 expected translations,
        including the 4 newly added non-English ones (valera, ls1910, almeida, arabicsv).
        """
        r = api.get("/api/v1/scripture/translations")
        assert r.status_code == 200
        codes = {t["code"] for t in r.json()["translations"]}
        for expected in (
            "kjv",
            "web",
            "ita1927",
            "schlachter",
            "valera",
            "ls1910",
            "almeida",
            "arabicsv",
        ):
            assert expected in codes, f"Translation missing from /translations: {expected}"


# ---------------------------------------------------------------------------
# Bug 1 regression — localized book name in URL path is normalized
# ---------------------------------------------------------------------------


class TestLocalizedBookNameInUrl:
    """
    When a user clicks a verse reference in localized chat text (e.g., "Juan 3:16")
    the frontend sends GET /verse/Juan/3/16?translation=valera.

    Before the fix: 404 (book "Juan" not found in DB).
    After the fix:  200 (normalize_book_name("Juan") → "John" before DB lookup).
    """

    @pytest.mark.parametrize(
        "localized_book, chapter, verse, translation",
        [
            # Italian
            ("Giovanni", 3, 16, "ita1927"),
            ("Genesi", 1, 1, "ita1927"),
            # German
            ("Johannes", 3, 16, "schlachter"),
            # Spanish
            ("Juan", 3, 16, "valera"),
            ("Génesis", 1, 1, "valera"),
            # French
            ("Jean", 3, 16, "ls1910"),
            ("Genèse", 1, 1, "ls1910"),
            # Portuguese
            ("João", 3, 16, "almeida"),
            # Arabic
            ("يوحنا", 3, 16, "arabicsv"),
        ],
    )
    def test_localized_verse_url_returns_200(
        self, api, localized_book, chapter, verse, translation
    ):
        """GET /verse/<localized>/<ch>/<v> must return 200, not 404 (Bug 1 fix)."""
        r = api.get(
            f"/api/v1/scripture/verse/{localized_book}/{chapter}/{verse}",
            params={"translation": translation},
        )
        assert r.status_code == 200, (
            f"Expected 200 for {localized_book} {chapter}:{verse} [{translation}], "
            f"got {r.status_code}: {r.text[:300]}"
        )

    @pytest.mark.parametrize(
        "localized_book, chapter, translation",
        [
            ("Giovanni", 3, "ita1927"),
            ("Juan", 3, "valera"),
            ("Jean", 3, "ls1910"),
            ("João", 3, "almeida"),
            ("يوحنا", 3, "arabicsv"),
        ],
    )
    def test_localized_chapter_url_returns_200(self, api, localized_book, chapter, translation):
        """GET /chapter/<localized>/<ch> must return 200, not 404 (Bug 1 fix)."""
        r = api.get(
            f"/api/v1/scripture/chapter/{localized_book}/{chapter}",
            params={"translation": translation},
        )
        assert r.status_code == 200, (
            f"Expected 200 for chapter {localized_book}/{chapter} [{translation}], "
            f"got {r.status_code}: {r.text[:300]}"
        )

    def test_english_book_name_still_works(self, api):
        """English book names (John, Genesis) continue to work as before."""
        r = api.get("/api/v1/scripture/verse/John/3/16", params={"translation": "kjv"})
        assert r.status_code == 200

    def test_unknown_book_name_returns_404(self, api):
        """A completely unknown book name returns 404, not 500."""
        r = api.get("/api/v1/scripture/verse/NotABook/1/1")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Bug 3 regression — localized_book field present in API responses
# ---------------------------------------------------------------------------


class TestLocalizedBookFieldInVerseResponse:
    """
    Before the fix: /verse/{book}/{ch}/{v} had no localized_book field,
    so the right pane showed "John 3:16" even in Spanish mode.
    After the fix:  localized_book is present and holds the translated name.
    """

    @pytest.mark.parametrize(
        "translation, expected_localized",
        [
            ("ita1927", "Giovanni"),
            ("schlachter", "Johannes"),
            ("valera", "Juan"),
            ("ls1910", "Jean"),
            ("almeida", "João"),
            ("arabicsv", "يوحنا"),
            ("kjv", "John"),
            ("web", "John"),
        ],
    )
    def test_verse_response_has_correct_localized_book(self, api, translation, expected_localized):
        """GET /verse/John/3/16?translation=<code> returns localized_book for each language."""
        r = api.get(
            "/api/v1/scripture/verse/John/3/16",
            params={"translation": translation},
        )
        assert r.status_code == 200
        data = r.json()
        assert (
            "localized_book" in data
        ), f"localized_book missing from verse response fields: {list(data.keys())}"
        assert data["localized_book"] == expected_localized, (
            f"[{translation}] Expected localized_book={expected_localized!r}, "
            f"got {data['localized_book']!r}"
        )
        # Canonical English name is also present
        assert data["book"] == "John"

    @pytest.mark.parametrize(
        "translation, expected_localized",
        [
            ("ita1927", "Giovanni"),
            ("valera", "Juan"),
            ("ls1910", "Jean"),
            ("kjv", "John"),
        ],
    )
    def test_chapter_response_top_level_localized_book(self, api, translation, expected_localized):
        """GET /chapter/John/3 top-level response has correct localized_book."""
        r = api.get(
            "/api/v1/scripture/chapter/John/3",
            params={"translation": translation},
        )
        assert r.status_code == 200
        data = r.json()
        assert "localized_book" in data
        assert data["localized_book"] == expected_localized

    def test_chapter_verse_entries_have_localized_book(self, api):
        """Every verse inside a chapter response has a localized_book field (Spanish)."""
        r = api.get("/api/v1/scripture/chapter/John/3", params={"translation": "valera"})
        assert r.status_code == 200
        verses = r.json()["verses"]
        assert verses, "No verses returned"
        for v in verses:
            assert "localized_book" in v, f"Verse missing localized_book: {list(v.keys())}"
            assert v["localized_book"] == "Juan"

    def test_localized_input_returns_localized_book_in_response(self, api):
        """
        Localized URL + localized translation → response includes the right localized_book.
        End-to-end check: click "Juan 3:16" → GET /verse/Juan/3/16?translation=valera
        → localized_book == "Juan" (not "John").
        """
        r = api.get("/api/v1/scripture/verse/Juan/3/16", params={"translation": "valera"})
        assert r.status_code == 200
        data = r.json()
        assert data["book"] == "John"  # canonical stays English
        assert data["localized_book"] == "Juan"  # localized field uses Spanish


# ---------------------------------------------------------------------------
# Scripture search
# ---------------------------------------------------------------------------


class TestScriptureSearch:
    """Search endpoint correctness and multilanguage localization."""

    def test_english_search_returns_results(self, api):
        """Semantic search with an English query returns at least one verse."""
        r = api.get("/api/v1/scripture/search", params={"q": "God so loved the world"})
        assert r.status_code == 200
        data = r.json()
        assert "verses" in data
        assert len(data["verses"]) > 0

    def test_search_result_structure(self, api):
        """Search verse results have required fields including localized_book."""
        r = api.get("/api/v1/scripture/search", params={"q": "faith hope love"})
        assert r.status_code == 200
        for verse in r.json()["verses"]:
            for field in ("reference", "text", "book", "localized_book", "similarity"):
                assert field in verse, f"Field {field!r} missing from search result"

    def test_spanish_search_includes_localized_book(self, api):
        """Search with Spanish translation returns Spanish localized_book values."""
        r = api.get(
            "/api/v1/scripture/search",
            params={"q": "amor de Dios", "translation": "valera"},
        )
        assert r.status_code == 200
        for verse in r.json()["verses"]:
            assert "localized_book" in verse
            # localized_book must not be None
            assert verse["localized_book"] is not None

    def test_search_requires_query_param(self, api):
        """GET /search without q returns 422."""
        r = api.get("/api/v1/scripture/search")
        assert r.status_code == 422

    def test_search_query_minimum_length(self, api):
        """GET /search with a single character returns 422 (min_length=2)."""
        r = api.get("/api/v1/scripture/search", params={"q": "a"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Chat endpoint — structural validation only (no LLM inference triggered)
# ---------------------------------------------------------------------------


class TestChatEndpointValidation:
    """
    Only validate request/response structure.
    We do NOT send real messages to avoid LLM cost and non-determinism.
    """

    def test_chat_rejects_missing_message_field(self, api):
        """POST /chat without 'message' field returns 422."""
        r = api.post("/api/v1/chat", json={"language": "es"})
        assert r.status_code == 422

    def test_chat_rejects_empty_body(self, api):
        """POST /chat with an empty body returns 422."""
        r = api.post("/api/v1/chat", json={})
        assert r.status_code == 422

    def test_chat_rejects_empty_message(self, api):
        """POST /chat with an empty string message returns 422 or 400."""
        r = api.post("/api/v1/chat", json={"message": ""})
        # FastAPI may return 422 (validation) or 400 (business logic)
        assert r.status_code in (400, 422)
