"""Manual smoke test: python -m scripts.try_claims "The Notion Plus plan costs $10 per month."."""

import argparse
import asyncio
import sys
import time

from app.config import settings
from app.services import bifrost_client, claims

# The Windows console defaults to cp1252; model text can contain any character.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main() -> int:
    """Extract claims from one answer and print type, volatility, TTL and search query."""
    parser = argparse.ArgumentParser(description="Extract claims from an answer through Bifrost.")
    parser.add_argument("answer", nargs="?", default="-", help="answer text, or - to read stdin")
    args = parser.parse_args()

    answer = sys.stdin.read() if args.answer == "-" else args.answer
    if not answer.strip():
        print("FAILED: empty answer")
        return 1

    print(f"MODEL: {settings.WEAK_MODEL or settings.PRIMARY_MODEL}")
    print(f"MAX_CLAIMS: {settings.MAX_CLAIMS}")
    print(f"ANSWER: {answer.strip()}")
    print("")

    started = time.perf_counter()
    try:
        result = await claims.extract(answer)
    except claims.ParseError as exc:
        print(f"FAILED: {exc}")
        return 1
    except bifrost_client.UpstreamError as exc:
        print(f"FAILED: {exc}")
        return 1
    finally:
        await bifrost_client.aclose()
    elapsed_ms = (time.perf_counter() - started) * 1000

    print(f"raw model reply (repair_retry={claims.last_repaired}):")
    print((claims.last_raw or "")[:1200])
    print("")
    print(f"CLAIMS: {len(result)}  elapsed_ms={elapsed_ms:.0f}")
    for claim in result:
        query = claims.last_queries.get(claim.id, "")
        print(f"[{claim.id}] type={claim.type} volatility={claim.volatility} ttl_days={claim.ttl_days}")
        print(f"    text: {claim.text!r}")
        print(f"    search_query: {query!r}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
