"""Manual smoke test: python -m scripts.try_tavily "Notion Plus plan price per month"."""

import argparse
import asyncio
import json
import sys
import time

from app.config import settings
from app.services import tavily_client

# The Windows console defaults to cp1252; search snippets can contain any character.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main() -> int:
    """Run one search and print its source, raw payload and results."""
    parser = argparse.ArgumentParser(description="Call Tavily through the app client.")
    parser.add_argument("query", help="search query")
    args = parser.parse_args()

    if not settings.tavily_key_set:
        print("FAILED: TAVILY_API_KEY is empty in .env")
        return 1

    key = tavily_client.cache_key(args.query)
    cached = await tavily_client.cache_get(key)
    print(f"QUERY: {args.query}")
    print(f"CACHE KEY: {key}")
    print(f"source: {'cache (no API call)' if cached is not None else 'live Tavily call'}")

    started = time.perf_counter()
    try:
        results = await tavily_client.search(args.query)
    except tavily_client.SearchError as exc:
        print(f"FAILED: {exc}")
        return 1
    finally:
        await tavily_client.aclose()
    elapsed_ms = (time.perf_counter() - started) * 1000
    print(f"elapsed_ms={elapsed_ms:.0f}")

    if tavily_client.last_raw is not None:
        print("RAW TAVILY JSON (truncated 2500 chars):")
        print(json.dumps(tavily_client.last_raw, indent=2)[:2500])

    print(f"RESULTS: {len(results)}")
    for index, item in enumerate(results, 1):
        print(f"[{index}] {item.title}")
        print(f"    url={item.url}")
        print(f"    published={item.published_date} score={item.score:.3f}")
        print(f"    content={item.content[:200]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
