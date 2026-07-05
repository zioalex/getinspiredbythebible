"""Regression test for the 2026-07-05 `_IncludedRouter` 500 incident.

FastAPI 0.137 / starlette 1.3.1 store an internal ``_IncludedRouter`` object in
``app.routes`` for every ``include_router(...)`` call. Older
``opentelemetry-instrumentation-fastapi`` (0.61b0, pinned transitively by
``azure-monitor-opentelemetry==1.8.8``) walked ``app.routes`` and did
``route.path`` on every entry, crashing with
``'_IncludedRouter' object has no attribute 'path'`` and returning **HTTP 500 on
every CORS preflight** (``OPTIONS /api/v1/*``). Direct GET/POST were unaffected,
so the break was browser-only.

Production applies this instrumentation only when
``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set (``main.py``), so no unit or
integration test previously exercised the instrumented request path. This test
closes that gap deterministically — it forces instrumentation on regardless of
environment and would fail against the old pin.

See BITB-064 for the production smoke-test / alerting follow-up.
"""

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

# Skip cleanly where the OpenTelemetry FastAPI instrumentation isn't installed
# (it ships transitively via azure-monitor-opentelemetry, present in CI).
FastAPIInstrumentor = pytest.importorskip(
    "opentelemetry.instrumentation.fastapi"
).FastAPIInstrumentor

ALLOWED_ORIGIN = "https://voxquieta.org"


def _build_instrumented_app() -> FastAPI:
    """Mirror production route registration: an included router under /api/v1,
    CORS middleware, and FastAPIInstrumentor applied — the exact combination that
    regressed. ``include_router`` is what puts an ``_IncludedRouter`` in
    ``app.routes``."""
    app = FastAPI()

    router = APIRouter(prefix="/chat", tags=["chat"])

    @router.post("/stream")
    async def chat_stream():  # pragma: no cover - trivial handler
        return {"ok": True}

    @router.get("/verse")
    async def chat_verse():  # pragma: no cover - trivial handler
        return {"ok": True}

    FastAPIInstrumentor.instrument_app(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ALLOWED_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1")

    return app


@pytest.fixture(scope="module")
def instrumented_client() -> TestClient:
    # raise_server_exceptions=False so a 500 is returned as a response we can
    # assert on, rather than re-raised into the test.
    return TestClient(_build_instrumented_app(), raise_server_exceptions=False)


def test_cors_preflight_on_included_route_does_not_500(instrumented_client):
    """The exact failing request from the incident: a browser CORS preflight to
    an included-router route must not 500 under OTel instrumentation."""
    resp = instrumented_client.options(
        "/api/v1/chat/stream",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-turnstile-token",
        },
    )
    assert resp.status_code != 500, (
        "CORS preflight to an included route returned 500 — the "
        "'_IncludedRouter' object has no attribute 'path' regression "
        "(FastAPI vs opentelemetry-instrumentation-fastapi version skew)."
    )
    # A correct preflight is a 2xx that echoes the CORS allow headers.
    assert resp.status_code < 400
    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


def test_real_requests_on_included_route_do_not_500(instrumented_client):
    """Direct POST/GET stayed working even under the broken pin; assert they keep
    working so the fix doesn't regress the non-preflight path."""
    assert instrumented_client.post("/api/v1/chat/stream").status_code != 500
    assert instrumented_client.get("/api/v1/chat/verse").status_code != 500
