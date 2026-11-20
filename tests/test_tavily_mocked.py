"""Unit tests for app/services/tavily_client.py, with Tavily mocked by respx."""

from datetime import timedelta

import httpx
import pytest
import respx

from app.config import settings
from app.services import tavily_client

URL = tavily_client.TAVILY_URL


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Use a throwaway cache DB, a dummy key and no retry sleep."""
    monkeypatch.setattr(settings, "CACHE_DB", str(tmp_path / "searches.db"))
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "tvly-test-key")
    monkeypatch.setattr(tavily_client, "RETRY_BACKOFF_S", 0)
    monkeypatch.setattr(tavily_client, "last_raw", None)
    yield


def _payload(count: int = 2, content_len: int = 700) -> dict:
    """Build a Tavily-shaped search response with `count` results."""
    results = [
        {
            "title": f"Result {index}",
            "url": f"https://example.com/{index}",
            "content": "x" * content_len,
            "score": 0.9 - index / 10,
        }
        for index in range(count)
    ]
    results[0]["published_date"] = "Wed, 12 Nov 2026 09:00:00 GMT"
    return {"query": "q", "results": results, "response_time": 0.42}


def _query(query: str = "notion pricing") -> str:
    """Return a short stand-in query."""
    return query


@pytest.mark.asyncio
@respx.mock
async def test_search_sends_frozen_body_and_returns_evidence() -> None:
    """The request matches §7 and the results are trimmed and typed."""
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=_payload()))
    results = await tavily_client.search(_query())

    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer tvly-test-key"
    body = request.read().decode()
    assert '"search_depth": "basic"' in body or '"search_depth":"basic"' in body
    assert '"max_results": 5' in body or '"max_results":5' in body
    assert '"include_answer": false' in body or '"include_answer":false' in body

    assert len(results) == 2
    assert results[0].url == "https://example.com/0"
    assert results[0].published_date == "Wed, 12 Nov 2026 09:00:00 GMT"
    assert results[1].published_date is None
    assert len(results[0].content) == 600
    assert isinstance(results[0].score, float)
    await tavily_client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_429_raises_search_error() -> None:
    """A quota answer becomes SearchError instead of crashing."""
    respx.post(URL).mock(return_value=httpx.Response(429, json={"detail": "rate limited"}))
    with pytest.raises(tavily_client.SearchError) as excinfo:
        await tavily_client.search(_query())
    assert "429" in str(excinfo.value)


@pytest.mark.asyncio
@respx.mock
async def test_401_raises_search_error_about_the_key() -> None:
    """A rejected key becomes SearchError that names TAVILY_API_KEY."""
    respx.post(URL).mock(return_value=httpx.Response(401, json={"detail": "unauthorized"}))
    with pytest.raises(tavily_client.SearchError) as excinfo:
        await tavily_client.search(_query())
    assert "TAVILY_API_KEY" in str(excinfo.value)


@pytest.mark.asyncio
@respx.mock
async def test_timeout_retries_once_then_raises() -> None:
    """Two timeouts in a row raise SearchError after exactly two attempts."""
    route = respx.post(URL).mock(side_effect=httpx.ReadTimeout("slow"))
    with pytest.raises(tavily_client.SearchError):
        await tavily_client.search(_query())
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_cache_hit_skips_the_api_call() -> None:
    """The second identical search is served from SQLite, not Tavily."""
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=_payload()))
    first = await tavily_client.search(_query())
    second = await tavily_client.search(_query())

    assert route.call_count == 1
    assert [item.url for item in first] == [item.url for item in second]
    assert len(second) == 2
    await tavily_client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_expired_cache_row_is_ignored() -> None:
    """A stale cache row does not answer the search."""
    route = respx.post(URL).mock(return_value=httpx.Response(200, json=_payload()))
    key = tavily_client.cache_key(_query())
    results = await tavily_client.search(_query())
    await tavily_client.cache_put(key, results, ttl=timedelta(seconds=-1))

    assert await tavily_client.cache_get(key) is None
    await tavily_client.search(_query())
    assert route.call_count == 2
    await tavily_client.aclose()


@pytest.mark.asyncio
@respx.mock
async def test_missing_results_list_raises_search_error() -> None:
    """A payload without `results` is a SearchError, not a silent empty list."""
    respx.post(URL).mock(return_value=httpx.Response(200, json={"answer": "hi"}))
    with pytest.raises(tavily_client.SearchError):
        await tavily_client.search(_query())
