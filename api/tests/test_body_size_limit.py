"""BITB-296: BodySizeLimitMiddleware (pure ASGI request body guard)."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from main import app as real_app
from middleware.body_size_limit import BodySizeLimitMiddleware

EXPECTED_413 = {"detail": {"error": "request_too_large"}}
LIMIT = 100


def _make_app(handler_calls: list):
    inner = FastAPI()

    @inner.post("/echo")
    async def echo(request: Request):
        body = await request.body()
        handler_calls.append(1)  # recorded only once the body was accepted
        return {"len": len(body), "data": body.decode()}

    inner.add_middleware(BodySizeLimitMiddleware, max_bytes=LIMIT)
    return inner


async def _drive(app, *, headers=(), chunks=(b"",), method="POST", path="/echo", scope_extra=None):
    """Run an ASGI app by hand; return (sent_messages, receive_calls)."""
    sent: list[dict] = []
    queue = list(chunks)
    state = {"receive_calls": 0}

    async def receive():
        state["receive_calls"] += 1
        if queue:
            body = queue.pop(0)
            return {"type": "http.request", "body": body, "more_body": bool(queue)}
        await asyncio.sleep(0)
        return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(k.encode(), v.encode()) for k, v in headers],
        "server": ("test", 80),
        "client": ("127.0.0.1", 1),
        "scheme": "http",
    }
    scope.update(scope_extra or {})
    await app(scope, receive, send)
    return sent, state["receive_calls"]


def _status(sent):
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


def _body(sent):
    return b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")


class TestContentLengthFastPath:
    def test_declared_over_cap_gets_413_and_handler_not_run(self):
        calls: list = []
        client = TestClient(_make_app(calls))
        resp = client.post("/echo", content=b"x" * (LIMIT + 1))
        assert resp.status_code == 413
        assert resp.json() == EXPECTED_413
        assert resp.headers["content-type"] == "application/json"
        assert calls == []

    @pytest.mark.asyncio
    async def test_declared_over_cap_does_not_read_body(self):
        calls: list = []
        sent, receive_calls = await _drive(
            _make_app(calls),
            headers=[("content-length", str(LIMIT + 1))],
            chunks=[b"x" * (LIMIT + 1)],
        )
        assert _status(sent) == 413
        assert json.loads(_body(sent)) == EXPECTED_413
        assert receive_calls == 0
        assert calls == []

    def test_exactly_at_cap_passes(self):
        calls: list = []
        resp = TestClient(_make_app(calls)).post("/echo", content=b"y" * LIMIT)
        assert resp.status_code == 200
        assert resp.json()["len"] == LIMIT
        assert calls == [1]

    def test_under_cap_passes_with_body_intact(self):
        calls: list = []
        resp = TestClient(_make_app(calls)).post("/echo", content=b"hello world")
        assert resp.status_code == 200
        assert resp.json() == {"len": 11, "data": "hello world"}

    @pytest.mark.asyncio
    async def test_malformed_content_length_falls_through_to_counting(self):
        calls: list = []
        sent, _ = await _drive(
            _make_app(calls),
            headers=[("content-length", "abc")],
            chunks=[b"x" * (LIMIT + 5)],
        )
        assert _status(sent) == 413
        assert calls == []

    def test_limit_read_from_settings_when_not_given(self, monkeypatch):
        inner = FastAPI()

        @inner.post("/e")
        async def e(request: Request):
            return {"n": len(await request.body())}

        inner.add_middleware(BodySizeLimitMiddleware)
        monkeypatch.setattr(settings, "max_request_body_bytes", 10)
        client = TestClient(inner)
        assert client.post("/e", content=b"x" * 10).status_code == 200
        assert client.post("/e", content=b"x" * 11).status_code == 413


class TestChunkedBodies:
    @pytest.mark.asyncio
    async def test_chunked_over_cap_without_content_length_gets_413(self):
        calls: list = []
        chunks = [b"a" * 40, b"b" * 40, b"c" * 40]
        sent, _ = await _drive(_make_app(calls), chunks=chunks)
        assert _status(sent) == 413
        assert json.loads(_body(sent)) == EXPECTED_413
        starts = [m for m in sent if m["type"] == "http.response.start"]
        assert len(starts) == 1  # exactly one response, never a second
        assert calls == []

    @pytest.mark.asyncio
    async def test_chunked_at_cap_passes(self):
        calls: list = []
        sent, _ = await _drive(_make_app(calls), chunks=[b"a" * 50, b"b" * 50])
        assert _status(sent) == 200
        assert json.loads(_body(sent))["len"] == LIMIT

    @pytest.mark.asyncio
    async def test_lying_content_length_still_bounded(self):
        calls: list = []
        sent, _ = await _drive(
            _make_app(calls), headers=[("content-length", "5")], chunks=[b"z" * (LIMIT + 1)]
        )
        assert _status(sent) == 413

    def test_chunked_via_httpx_generator(self):
        calls: list = []
        client = TestClient(_make_app(calls))

        def gen():
            for _ in range(5):
                yield b"x" * 40

        resp = client.post("/echo", content=gen())
        assert resp.status_code == 413
        assert resp.json() == EXPECTED_413
        assert calls == []


class TestNonHttpAndStreaming:
    @pytest.mark.asyncio
    async def test_non_http_scope_passes_through(self):
        seen = {}

        async def inner(scope, receive, send):
            seen["type"] = scope["type"]

        await BodySizeLimitMiddleware(inner, max_bytes=1)(
            {"type": "lifespan"}, lambda: None, lambda m: None
        )
        assert seen["type"] == "lifespan"

    @pytest.mark.asyncio
    async def test_streaming_response_is_not_buffered(self):
        first_chunk_seen = asyncio.Event()
        order: list[str] = []

        async def gen():
            yield b"first"
            # The last chunk is only produced after the client side observed chunk one.
            await asyncio.wait_for(first_chunk_seen.wait(), timeout=2)
            order.append("producing-last")
            yield b"last"

        inner = FastAPI()

        @inner.post("/stream")
        async def stream():
            return StreamingResponse(gen(), media_type="text/event-stream")

        app = BodySizeLimitMiddleware(inner, max_bytes=LIMIT)
        sent: list[dict] = []

        delivered = False

        async def receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"{}", "more_body": False}
            await first_chunk_seen.wait()
            await asyncio.sleep(0.05)
            return {"type": "http.disconnect"}

        async def send(message):
            sent.append(message)
            if message["type"] == "http.response.body" and message.get("body") == b"first":
                order.append("saw-first")
                first_chunk_seen.set()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "path": "/stream",
            "raw_path": b"/stream",
            "query_string": b"",
            "headers": [],
            "server": ("t", 80),
            "client": ("127.0.0.1", 1),
            "scheme": "http",
        }
        await app(scope, receive, send)
        assert order == ["saw-first", "producing-last"]
        assert _body(sent) == b"firstlast"


class TestRealApp:
    def test_oversized_chat_gets_413_with_cors_and_request_id(self, monkeypatch):
        monkeypatch.setattr(settings, "max_request_body_bytes", 1000)
        client = TestClient(real_app)
        resp = client.post(
            "/api/v1/chat",
            content=b"x" * 5000,
            headers={"Origin": "http://localhost:3000", "content-type": "application/json"},
        )
        assert resp.status_code == 413
        assert resp.json() == EXPECTED_413
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert "x-request-id" in resp.headers

    def test_oversized_stream_endpoint_gets_413(self, monkeypatch):
        monkeypatch.setattr(settings, "max_request_body_bytes", 1000)
        resp = TestClient(real_app).post(
            "/api/v1/chat/stream",
            content=b"x" * 5000,
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 413
        assert resp.json() == EXPECTED_413

    def test_default_cap_is_one_mebibyte(self):
        assert settings.max_request_body_bytes == 1_048_576
