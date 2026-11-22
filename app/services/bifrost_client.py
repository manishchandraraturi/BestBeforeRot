"""Bifrost gateway client: one chat call, with fallback routing and provider reporting."""

import logging
from contextvars import ContextVar

import httpx
from pydantic import BaseModel

from app.config import settings

logger = logging.getLogger(__name__)

# Sent as the primary model name when the caller asks for a simulated outage. The provider
# prefix must stay: Bifrost rejects an unprefixed model before it ever tries a fallback.
INVALID_MODEL = "invalid-model-name"


def invalid_model() -> str:
    """Provider-qualified but nonexistent model, used to force the fallback path."""
    provider = settings.PRIMARY_MODEL.split("/", 1)[0] or "groq"
    return f"{provider}/{INVALID_MODEL}"

_client: httpx.AsyncClient | None = None


class UpstreamError(Exception):
    """Bifrost or both providers failed."""


class ChatResult(BaseModel):
    """Normalised result of one chat completion."""

    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    provider: str
    fallback_triggered: bool = False


# Per-request instrumentation used by the pipeline (P6): the collector is inherited by every
# claim task of one request, so stats stay per-request. Unset means no behaviour change.
usage_sink: ContextVar[list[ChatResult] | None] = ContextVar("usage_sink", default=None)
simulated_outage: ContextVar[bool] = ContextVar("simulated_outage", default=False)


def _get_client() -> httpx.AsyncClient:
    """Return the shared AsyncClient, creating it on first use."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_S)
    return _client


async def aclose() -> None:
    """Close the shared client (tests and shutdown)."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


def _routing(payload: dict, headers: httpx.Headers) -> tuple[str, bool]:
    """Read the provider that answered and whether it was a fallback.

    Order: extra_fields.routing_info, then deprecated extra_fields, then x-bifrost headers.
    """
    extra = payload.get("extra_fields") or {}
    routing = extra.get("routing_info") or {}

    provider = routing.get("provider") or extra.get("provider") or ""
    is_fallback = routing.get("is_fallback")
    if is_fallback is None:
        is_fallback = headers.get("x-bifrost-routing-info-is-fallback") == "true"

    if not provider:
        provider = headers.get("x-bifrost-routing-info-provider", "")
    if not is_fallback:
        is_fallback = headers.get("x-bifrost-fallback-index") is not None
    return provider, bool(is_fallback)


def _content_text(content: object) -> str:
    """Flatten `message.content`, which some OpenAI-compatible providers send as parts.

    Groq's gpt-oss models can answer with `[{"type": "text", "text": "..."}]` instead of a
    plain string; calling .strip() on that list used to crash the whole request.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
        return "".join(chunks).strip()
    return ""


def _text_of(payload: dict) -> str:
    """Pull the assistant text out of an OpenAI-shaped response."""
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise UpstreamError("Bifrost response had no assistant message") from exc
    return _content_text(content)


def _error_detail(response: httpx.Response) -> str:
    """Shortest useful reason for an error status: the gateway's own message when present."""
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300].strip()
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"][:300]
        if isinstance(error, str):
            return error[:300]
        if isinstance(payload.get("message"), str):
            return payload["message"][:300]
    return response.text[:300].strip()


async def chat(
    messages: list[dict],
    model: str | None = None,
    force_fallback: bool = False,
) -> ChatResult:
    """Send one chat completion through Bifrost and report the provider that answered."""
    outage = force_fallback or simulated_outage.get()
    requested = invalid_model() if outage else (model or settings.PRIMARY_MODEL)
    body = {
        "model": requested,
        "messages": messages,
        "temperature": 0,
        "fallbacks": [settings.FALLBACK_MODEL],
    }
    url = f"{settings.BIFROST_URL.rstrip('/')}/v1/chat/completions"
    client = _get_client()

    response: httpx.Response | None = None
    last_error: httpx.HTTPError | None = None
    for attempt in (1, 2):
        try:
            response = await client.post(url, json=body)
            break
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_error = exc
            if attempt == 2:
                break
            logger.warning("Bifrost network error, retrying once: %s", type(exc).__name__)

    if response is None:
        # A slow gateway is not an offline one: report the timeout as such (HTTP 504).
        if isinstance(last_error, httpx.TimeoutException):
            raise UpstreamError(
                f"Bifrost timed out after {settings.REQUEST_TIMEOUT_S:g}s"
            ) from last_error
        raise UpstreamError(f"Bifrost unreachable at {settings.BIFROST_URL}") from last_error
    if response.status_code >= 400:
        # Groq answers 429 on a token-per-minute limit and 5xx while overloaded; both are
        # upstream failures the UI shows as a message, never a crash.
        raise UpstreamError(
            f"Bifrost returned HTTP {response.status_code}: {_error_detail(response)}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise UpstreamError("Bifrost returned non-JSON") from exc
    if not isinstance(payload, dict):
        raise UpstreamError("Bifrost returned an unexpected payload")

    try:
        provider, fallback_triggered = _routing(payload, response.headers)
        usage = payload.get("usage") or {}
        result = ChatResult(
            text=_text_of(payload),
            tokens_in=int(usage.get("prompt_tokens") or 0),
            tokens_out=int(usage.get("completion_tokens") or 0),
            provider=provider or "unknown",
            fallback_triggered=fallback_triggered or outage,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise UpstreamError(f"Bifrost response was malformed: {type(exc).__name__}") from exc
    logger.info(
        "bifrost chat model=%s provider=%s fallback=%s tokens_in=%d tokens_out=%d",
        requested,
        result.provider,
        result.fallback_triggered,
        result.tokens_in,
        result.tokens_out,
    )
    sink = usage_sink.get()
    if sink is not None:
        sink.append(result)
    return result
