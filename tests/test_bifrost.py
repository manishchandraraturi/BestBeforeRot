"""Unit tests for app/services/bifrost_client.py, with the HTTP call mocked by respx."""

import httpx
import pytest
import respx

from app.config import settings
from app.services import bifrost_client

URL = f"{settings.BIFROST_URL.rstrip('/')}/v1/chat/completions"


def _payload(provider: str, is_fallback: bool | None = None) -> dict:
    """Build an OpenAI-shaped Bifrost response body."""
    routing: dict = {"provider": provider}
    if is_fallback is not None:
        routing["is_fallback"] = is_fallback
    return {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
        "extra_fields": {"routing_info": routing},
    }


@pytest.mark.asyncio
@respx.mock
async def test_chat_primary_provider() -> None:
    """Normal call reports the primary provider and no fallback."""
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=_payload("groq")))
    result = await bifrost_client.chat([{"role": "user", "content": "Say hello"}])
    assert result.text == "hello"
    assert result.provider == "groq"
    assert result.fallback_triggered is False
    assert (result.tokens_in, result.tokens_out) == (12, 3)
    sent = route.calls.last.request
    assert sent.read() and b'"fallbacks"' in sent.content
    await bifrost_client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_chat_fallback_flag_from_body() -> None:
    """A fallback answer is reported as fallback_triggered."""
    respx.post(URL).mock(return_value=httpx.Response(200, json=_payload("gemini", True)))
    result = await bifrost_client.chat(
        [{"role": "user", "content": "Say hello"}], force_fallback=True
    )
    assert result.provider == "gemini"
    assert result.fallback_triggered is True


@pytest.mark.asyncio
@respx.mock
async def test_force_fallback_sends_invalid_primary_and_fallback_list() -> None:
    """Simulated outage sends the invalid model plus the configured fallback."""
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=_payload("gemini", True)))
    await bifrost_client.chat([{"role": "user", "content": "hi"}], force_fallback=True)
    body = route.calls.last.request.content.decode()
    assert bifrost_client.INVALID_MODEL in body
    assert settings.FALLBACK_MODEL in body


@pytest.mark.asyncio
@respx.mock
async def test_provider_from_headers_when_no_extra_fields() -> None:
    """Headers are used when the body carries no extra_fields."""
    body = {
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    respx.post(URL).mock(
        return_value=httpx.Response(
            200,
            json=body,
            headers={
                "x-bifrost-routing-info-provider": "gemini",
                "x-bifrost-routing-info-is-fallback": "true",
                "x-bifrost-fallback-index": "1",
            },
        )
    )
    result = await bifrost_client.chat([{"role": "user", "content": "hi"}], force_fallback=True)
    assert (result.provider, result.fallback_triggered) == ("gemini", True)


@pytest.mark.asyncio
@respx.mock
async def test_one_retry_on_connect_error() -> None:
    """A connection error is retried once, then succeeds."""
    route = respx.post(URL).mock(
        side_effect=[httpx.ConnectError("boom"), httpx.Response(200, json=_payload("groq"))]
    )
    result = await bifrost_client.chat([{"role": "user", "content": "hi"}])
    assert result.provider == "groq"
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_http_error_raises_upstream_error() -> None:
    """A 5xx from Bifrost becomes UpstreamError."""
    respx.post(URL).mock(return_value=httpx.Response(503, json={"error": "down"}))
    with pytest.raises(bifrost_client.UpstreamError):
        await bifrost_client.chat([{"role": "user", "content": "hi"}])
