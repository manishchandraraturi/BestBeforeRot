"""SQLite fact cache: one judged claim in, one judged claim out, until its TTL expires (§8)."""

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from app.config import settings
from app.models import Claim

logger = logging.getLogger(__name__)

# 03-RULES.md §D: a locked database gets three short tries, then we run without a cache.
LOCK_RETRIES = 3
LOCK_SLEEP_S = 0.05
BUSY_TIMEOUT_S = 1.0


def fact_key(text: str) -> str:
    """sha1 of the normalised claim text, so casing and spacing cannot split one fact."""
    normalised = " ".join(text.lower().split())
    return hashlib.sha1(normalised.encode("utf-8")).hexdigest()


def _utc_now() -> datetime:
    """Current time as an aware UTC datetime."""
    return datetime.now(timezone.utc)


def _connect() -> sqlite3.Connection:
    """Open the shared cache DB and ensure the `facts` table exists."""
    conn = sqlite3.connect(settings.CACHE_DB, timeout=BUSY_TIMEOUT_S)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS facts ("
        "key TEXT PRIMARY KEY, claim_json TEXT NOT NULL, "
        "checked_at TEXT NOT NULL, expires_at TEXT NOT NULL)"
    )
    conn.commit()
    return conn


def _run(operation):
    """Run one DB operation, retrying only a locked database."""
    for attempt in range(1, LOCK_RETRIES + 1):
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == LOCK_RETRIES:
                raise
            logger.warning("fact cache locked, retrying (%d/%d)", attempt, LOCK_RETRIES - 1)
            time.sleep(LOCK_SLEEP_S)
    raise sqlite3.OperationalError("fact cache unavailable")


def _select(key: str) -> tuple[str, str] | None:
    """Return (claim_json, expires_at) for one key, or None."""
    conn = _connect()
    try:
        return _run(
            lambda: conn.execute(
                "SELECT claim_json, expires_at FROM facts WHERE key = ?", (key,)
            ).fetchone()
        )
    finally:
        conn.close()


def _read_sync(key: str) -> Claim | None:
    """Load one cached claim, ignoring expired or unreadable rows."""
    try:
        row = _select(key)
    except sqlite3.Error as exc:
        logger.warning("fact cache read failed, running without cache: %s", exc)
        return None

    if row is None:
        return None
    claim_json, expires_at = row
    if expires_at <= _utc_now().isoformat():
        return None
    try:
        return Claim.model_validate(json.loads(claim_json))
    except (ValueError, ValidationError, TypeError) as exc:
        logger.warning("fact cache row unreadable, treating as a miss: %s", exc)
        return None


def _write_sync(key: str, claim_json: str, checked_at: str, expires_at: str) -> None:
    """Insert or overwrite one fact; a failure only loses the caching."""
    try:
        conn = _connect()
        try:
            _run(
                lambda: conn.execute(
                    "INSERT INTO facts (key, claim_json, checked_at, expires_at) "
                    "VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET "
                    "claim_json = excluded.claim_json, checked_at = excluded.checked_at, "
                    "expires_at = excluded.expires_at",
                    (key, claim_json, checked_at, expires_at),
                )
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("fact cache write failed: %s", exc)


def _list_sync() -> list[dict]:
    """Return every unexpired fact with the seconds it has left."""
    now = _utc_now()
    try:
        conn = _connect()
        try:
            rows = _run(
                lambda: conn.execute(
                    "SELECT key, claim_json, checked_at, expires_at FROM facts "
                    "WHERE expires_at > ? ORDER BY expires_at",
                    (now.isoformat(),),
                ).fetchall()
            )
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("fact cache list failed: %s", exc)
        return []

    items: list[dict] = []
    for key, claim_json, checked_at, expires_at in rows:
        try:
            claim = json.loads(claim_json)
            seconds_left = int((datetime.fromisoformat(expires_at) - now).total_seconds())
        except (ValueError, TypeError) as exc:
            logger.warning("skipping an unreadable cache row: %s", exc)
            continue
        items.append(
            {
                "key": key,
                "text": claim.get("text"),
                "type": claim.get("type"),
                "verdict": claim.get("verdict"),
                "checked_at": checked_at,
                "expires_at": expires_at,
                "seconds_left": max(seconds_left, 0),
            }
        )
    return items


def _clear_sync() -> int:
    """Delete every cached fact and return how many rows went away."""
    try:
        conn = _connect()
        try:
            deleted = _run(lambda: conn.execute("DELETE FROM facts")).rowcount
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("fact cache clear failed: %s", exc)
        return 0
    return int(deleted or 0)


async def get_fact(key: str) -> Claim | None:
    """Return the cached claim for a key, or None on a miss or an expired row."""
    return await asyncio.to_thread(_read_sync, key)


async def put_fact(claim: Claim, ttl_days: int) -> None:
    """Store one judged claim with `expires_at = now + ttl_days`, and set it on the claim."""
    checked_at = _utc_now()
    expires_at = checked_at + timedelta(days=ttl_days)
    claim.expires_at = expires_at
    await asyncio.to_thread(
        _write_sync,
        fact_key(claim.text),
        claim.model_dump_json(),
        checked_at.isoformat(),
        expires_at.isoformat(),
    )


async def list_facts() -> list[dict]:
    """List cached facts that are still fresh, with `seconds_left` for the UI."""
    return await asyncio.to_thread(_list_sync)


async def clear_facts() -> int:
    """Clear the facts table (demo reset) and return the deleted row count."""
    return await asyncio.to_thread(_clear_sync)
