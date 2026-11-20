"""Manual smoke test: python -m scripts.try_pipeline samples/pricing.txt."""

import argparse
import asyncio
import sys
import time
from pathlib import Path

from app.config import settings
from app.models import ClaimStatus
from app.pipeline import verify
from app.services import bifrost_client, claims, judge, scoring, tavily_client

# The Windows console defaults to cp1252; model text can contain any character.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main() -> int:
    """Verify one answer file and print every claim, its verdict, sources and the overall score."""
    parser = argparse.ArgumentParser(description="Run the verify pipeline on an answer file.")
    parser.add_argument("path", nargs="?", default="-", help="answer file, or - to read stdin")
    args = parser.parse_args()

    answer = sys.stdin.read() if args.path == "-" else Path(args.path).read_text(encoding="utf-8")
    if not answer.strip():
        print("FAILED: empty answer")
        return 1

    print(f"SOURCE: {args.path}")
    print(f"TAVILY KEY SET: {settings.tavily_key_set}")
    print(f"MODELS: primary={settings.PRIMARY_MODEL} weak={settings.WEAK_MODEL}")
    print(f"ANSWER: {answer.strip()}")
    print("")

    started = time.perf_counter()
    try:
        result = await verify(answer)
    except claims.ParseError as exc:
        print(f"FAILED: claim extraction: {exc}")
        return 1
    except judge.ParseError as exc:
        print(f"FAILED: judge: {exc}")
        return 1
    except bifrost_client.UpstreamError as exc:
        print(f"FAILED: {exc}")
        return 1
    finally:
        await tavily_client.aclose()
        await bifrost_client.aclose()
    elapsed_ms = (time.perf_counter() - started) * 1000

    overall, band = scoring.score_claims(result)
    print(f"CLAIMS: {len(result)}  elapsed_ms={elapsed_ms:.0f}")
    for claim in result:
        print(f"[{claim.id}] type={claim.type} volatility={claim.volatility} ttl_days={claim.ttl_days}")
        print(f"    text: {claim.text!r}")
        print(f"    status={claim.status} verdict={claim.verdict}")
        print(f"    confidence={claim.confidence} score={claim.score}")
        print(f"    reason: {claim.reason!r}")
        if claim.corrected_text:
            print(f"    corrected: {claim.corrected_text!r}")
        if claim.status is ClaimStatus.SKIPPED_STABLE:
            print("    skipped: stable claim, no search credit spent")
        for source in claim.sources:
            print(f"    source: {source.title} | {source.url} | published={source.published}")

    print("")
    print(f"OVERALL SCORE: {overall} ({band})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
