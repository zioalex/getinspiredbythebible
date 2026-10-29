"""BITB-251: route-level pieces of the crisis path.

* ``CF-IPCountry`` is passed to the service as ``client_country`` on both chat routes.
* The profanity / repeated-characters route filter must not pre-empt the crisis path.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

sys.path.insert(0, str(Path(__file__).parent.parent))

from chat.service import ChatRequest, ChatResponse
from utils.security import check_content_filter

# ---------------------------------------------------------------------------
# CF-IPCountry passthrough
# ---------------------------------------------------------------------------


def _http(headers: dict[str, str]):
    http = MagicMock()
    # Real starlette Headers: lookup is case-insensitive, like on a live request.
    http.headers = Headers(headers)
    return http


def _response():
    return ChatResponse(message_id="m", message="hi", provider="p", model="m")


@pytest.mark.asyncio
@pytest.mark.parametrize("header_name", ["CF-IPCountry", "cf-ipcountry"])
async def test_blocking_route_passes_cf_country(header_name):
    from routes.chat import chat

    request = ChatRequest(message="hello")
    with (
        patch("routes.chat.ChatService") as service_cls,
        patch("routes.chat.track_session", new_callable=AsyncMock),
    ):
        service = MagicMock()
        service.chat = AsyncMock(return_value=_response())
        service_cls.return_value = service
        await chat(
            request,
            _http({header_name: "IT", "user-agent": "t"}),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
        )
    service.chat.assert_awaited_once_with(request, client_country="IT")


@pytest.mark.asyncio
async def test_blocking_route_passes_none_when_header_absent():
    from routes.chat import chat

    request = ChatRequest(message="hello")
    with (
        patch("routes.chat.ChatService") as service_cls,
        patch("routes.chat.track_session", new_callable=AsyncMock),
    ):
        service = MagicMock()
        service.chat = AsyncMock(return_value=_response())
        service_cls.return_value = service
        await chat(request, _http({}), AsyncMock(), AsyncMock(), AsyncMock())
    service.chat.assert_awaited_once_with(request, client_country=None)


@pytest.mark.asyncio
@pytest.mark.parametrize("country", ["DE", "XX", None])
async def test_stream_route_passes_cf_country_and_forwards_card_event(country):
    from routes.chat import chat_stream

    request = ChatRequest(message="hello")
    seen: dict = {}
    card = {"kind": "self_harm", "country": "DE"}

    async def gen(req, *, client_country=None):
        seen["req"] = req
        seen["client_country"] = client_country
        yield {"type": "crisis_resources", "resources": card}
        yield {"type": "content", "content": "x"}

    headers = {"CF-IPCountry": country} if country else {}
    with (
        patch("routes.chat.ChatService") as service_cls,
        patch("routes.chat.track_session", new_callable=AsyncMock),
    ):
        service = MagicMock()
        service.chat_stream = gen
        service_cls.return_value = service
        response = await chat_stream(request, _http(headers), AsyncMock(), AsyncMock(), AsyncMock())
        chunks = [chunk async for chunk in response.body_iterator]

    assert seen["req"] is request
    assert seen["client_country"] == country
    assert chunks[0].startswith('data: {"type": "crisis_resources"')
    assert "[DONE]" in chunks[-1]


# ---------------------------------------------------------------------------
# Profanity / repeated-chars filter yields to crisis wording
# ---------------------------------------------------------------------------


class _FakeRequest:
    def __init__(self, body: dict):
        self.method = "POST"
        self.headers: dict[str, str] = {}
        self.client = None
        self._body = body

    async def json(self):
        return self._body


async def _run_filter(message: str):
    await check_content_filter(_FakeRequest({"message": message}))  # type: ignore[arg-type]


PROFANE_CRISIS = [
    ("en", "fuck this, I want to kill myself"),
    ("en", "shit I can't do this anymore, I want to end my life"),
    ("en", "I'm going to kill my boss, that son of a bitch"),
    ("it", "cazzo, voglio uccidermi, fuck"),
    ("de", "scheiße, ich will mich umbringen, fuck this"),
    ("es", "mierda, quiero matarme, fuck"),
    ("fr", "putain, je veux me tuer, fuck"),
]
REPEATED_CRISIS = [
    ("en", "nooooooooo I want to die"),
    ("en", "I want to kill myselfffffffff"),
    ("it", "voglio morireeeeeeee"),
    ("de", "ich will mich umbringennnnnnn"),
    ("es", "quiero matarmeeeeeeee"),
    ("fr", "je veux me tuerrrrrrr"),
    ("pt", "quero me matarrrrrrr"),
    ("ru", "я хочу умерееееееееть"),
    ("zh", "我想死死死死死死死死死"),
    ("ko", "죽고 싶어어어어어어어어"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("language,message", PROFANE_CRISIS)
async def test_profanity_with_crisis_wording_reaches_the_safety_pipeline(language, message):
    await _run_filter(message)  # must NOT raise


@pytest.mark.asyncio
@pytest.mark.parametrize("language,message", REPEATED_CRISIS)
async def test_repeated_chars_with_crisis_wording_reach_the_safety_pipeline(language, message):
    await _run_filter(message)  # must NOT raise


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "fuck you",
        "this is shit",
        "Hellooooooo there",
        "aaaaaaaaaaaa",
        "damn it all",
        "I love my dog sooooooooo much",
    ],
)
async def test_cosmetic_violations_without_crisis_wording_still_block(message):
    with pytest.raises(HTTPException) as exc_info:
        await _run_filter(message)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "content_blocked"


@pytest.mark.asyncio
async def test_url_spam_is_still_blocked_even_with_crisis_wording():
    with pytest.raises(HTTPException) as exc_info:
        await _run_filter("I want to kill myself https://spam.example.com buy now")
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_bypass_logs_no_message_text(caplog):
    private_text = "fuck this I want to kill myself secret-marker"
    with caplog.at_level("DEBUG"):
        await _run_filter(private_text)
    assert "secret-marker" not in caplog.text
    assert any("bypassed for crisis wording" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_bypassed_violation_does_not_write_a_blocked_sample():
    with patch("feedback.blocked_samples.record_blocked_sample", new_callable=AsyncMock) as rec:
        await _run_filter("fuck this, I want to kill myself")
    rec.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message",
    [
        "shit http://evil.example/buy kill",
        "fuck https://casino.example.com murder",
        "fuck this I want to kill myself casino.example.com",
        "nooooooo I want to die http://evil.example/buy",
    ],
)
async def test_url_hidden_behind_profanity_or_repeats_still_blocks_with_crisis_wording(message):
    """`check` reports only the first violation; the bypass must re-check the rest."""
    with pytest.raises(HTTPException) as exc_info:
        await _run_filter(message)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["error"] == "content_blocked"
    assert "URL" in exc_info.value.detail["message"]


def test_content_filter_check_skip_ignores_only_the_named_types():
    from utils.security import ContentFilter, ViolationType

    flt = ContentFilter()
    skip = frozenset({ViolationType.PROFANITY, ViolationType.REPEATED_CHARS})
    assert flt.check("fuck this")[1] == ViolationType.PROFANITY
    assert flt.check("fuck this", skip=skip) == (True, None, None)
    assert flt.check("fuck http://a.example/x", skip=skip)[1] == ViolationType.URL_DETECTED
