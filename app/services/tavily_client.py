"""Tavily search client with the 6-hour query cache from 02-ARCHITECTURE.md §8."""

import asyncio
import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.models import Evidence

logger = logging.getLogger(__name__)

TAVILY_URL = "https://api.tavily.com/search"
SEARCH_TTL = timedelta(hours=6)
RETRY_BACKOFF_S = 1.0
CONTENT_LIMIT = 600
MAX_RESULTS = 5

# Debug aid for the CLI: raw JSON of the most recent live response (None on a cache hit).
last_raw: dict | None = None

_client: httpx.AsyncClient | None = None


class SearchError(Exception):
    """Tavily could not answer: invalid key, quota, timeout or a broken response."""


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


def cache_key(query: str) -> str:
    """sha1 of the normalised query, used as `searches.key`."""
    return hashlib.sha1(query.strip().lower().encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    """Current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


def _connect() -> sqlite3.Connection:
    """Open the cache DB and ensure the `searches` table exists."""
    conn = sqlite3.connect(settings.CACHE_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS searches ("
        "key TEXT PRIMARY KEY, results_json TEXT NOT NULL, expires_at TEXT NOT NULL)"
    )
    conn.commit()
    return conn


def _read_sync(key: str) -> list[dict] | None:
    """Return cached rows for a key, or None when the row is missing or expired."""
    try:
        conn = _connect()
    except sqlite3.Error as exc:
        logger.warning("search cache unavailable, running without cache: %s", exc)
        return None
    try:
        row = conn.execute(
            "SELECT results_json, expires_at FROM searches WHERE key = ?", (key,)
        ).fetchone()
    except sqlite3.Error as exc:
        logger.warning("search cache read failed, running without cache: %s", exc)
        return None
    finally:
        conn.close()

    if row is None:
        return None
    results_json, expires_at = row
    if expires_at <= _utc_now().isoformat():
        return None
    return json.loads(results_json)


def _write_sync(key: str, rows: list[dict], expires_at: datetime) -> None:
    """Insert or overwrite the cached rows for a key; failures only lose caching."""
    try:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO searches (key, results_json, expires_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET results_json = excluded.results_json, "
                "expires_at = excluded.expires_at",
                (key, json.dumps(rows, ensure_ascii=False), expires_at.isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("search cache write failed: %s", exc)


async def cache_get(key: str) -> list[Evidence] | None:
    """Return cached evidence for a key, or None on a miss or expired row."""
    rows = await asyncio.to_thread(_read_sync, key)
    if rows is None:
        return None
    return [Evidence(**row) for row in rows]


async def cache_put(key: str, results: list[Evidence], ttl: timedelta = SEARCH_TTL) -> None:
    """Store evidence for a key with an expiry `ttl` from now."""
    rows = [item.model_dump() for item in results]
    await asyncio.to_thread(_write_sync, key, rows, _utc_now() + ttl)


def _parse(payload: dict) -> list[Evidence]:
    """Map Tavily's `results` array to Evidence, trimming each content field."""
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        raise SearchError("Tavily response had no results list")

    evidence: list[Evidence] = []
    for row in raw_results:
        if not isinstance(row, dict):
            continue
        published = row.get("published_date")
        evidence.append(
            Evidence(
                title=str(row.get("title") or "").strip(),
                url=str(row.get("url") or "").strip(),
                content=str(row.get("content") or "").strip()[:CONTENT_LIMIT],
                published_date=str(published).strip() if published else None,
                score=float(row.get("score") or 0.0),
            )
        )
    return evidence


async def _post(query: str) -> httpx.Response:
    """POST the frozen search body, retrying one timeout after a short backoff."""
    headers = {"Authorization": f"Bearer {settings.TAVILY_API_KEY}"}
    body = {
        "query": query,
        "search_depth": "basic",
        "max_results": MAX_RESULTS,
        "include_answer": False,
    }
    client = _get_client()
    for attempt in (1, 2):
        try:
            return await client.post(TAVILY_URL, json=body, headers=headers)
        except httpx.TimeoutException as exc:
            if attempt == 2:
                raise SearchError("Tavily timed out twice") from exc
            logger.warning("Tavily timeout, retrying once")
            await asyncio.sleep(RETRY_BACKOFF_S)
        except httpx.HTTPError as exc:
            raise SearchError(f"Tavily request failed: {type(exc).__name__}") from exc
    raise SearchError("Tavily request failed")


def _check(response: httpx.Response) -> None:
    """Turn Tavily's error statuses into SearchError with a clear message."""
    if response.status_code in (401, 403):
        raise SearchError(
            f"Tavily rejected the API key (HTTP {response.status_code}). "
            "Check TAVILY_API_KEY in .env."
        )
    if response.status_code == 429:
        raise SearchError("Tavily search limit reached (HTTP 429).")
    if response.status_code >= 400:
        raise SearchError(f"Tavily returned HTTP {response.status_code}")


async def search(query: str) -> list[Evidence]:
    """Return up to five Tavily results, served from the 6-hour cache when fresh."""
    global last_raw

    key = cache_key(query)
    cached = await cache_get(key)
    if cached is not None:
        logger.info("tavily cache hit key=%s results=%d", key, len(cached))
        return cached

    response = await _post(query)
    _check(response)
    try:
        payload = response.json()
    except ValueError as exc:
        raise SearchError("Tavily returned non-JSON") from exc
    if not isinstance(payload, dict):
        raise SearchError("Tavily returned an unexpected payload")

    results = _parse(payload)
    last_raw = payload
    await cache_put(key, results)
    logger.info("tavily live search key=%s results=%d", key, len(results))
    return results
