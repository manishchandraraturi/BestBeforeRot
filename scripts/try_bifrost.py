"""Manual smoke test: python -m scripts.try_bifrost "Say hello" [--force-fallback] [--raw]."""

import argparse
import asyncio
import json
import sys

import httpx

from app.config import settings
from app.services import bifrost_client

# The Windows console defaults to cp1252; model replies often contain emoji.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


async def main() -> int:
    """Run one chat call and print the raw response plus the parsed result."""
    parser = argparse.ArgumentParser(description="Call Bifrost through the app client.")
    parser.add_argument("prompt", help="user message to send")
    parser.add_argument("--force-fallback", action="store_true", help="simulate a primary outage")
    args = parser.parse_args()

    model = bifrost_client.invalid_model() if args.force_fallback else settings.PRIMARY_MODEL
    body = {
        "model": model,
        "messages": [{"role": "user", "content": args.prompt}],
        "temperature": 0,
        "fallbacks": [settings.FALLBACK_MODEL],
    }
    url = f"{settings.BIFROST_URL.rstrip('/')}/v1/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_S) as client:
            response = await client.post(url, json=body)
        print(f"POST {url} -> HTTP {response.status_code}")
        print("RAW RESPONSE:")
        try:
            print(json.dumps(response.json(), indent=2)[:4000])
        except ValueError:
            print(response.text[:4000])
        print("x-bifrost headers: " + json.dumps(
            {k: v for k, v in response.headers.items() if k.startswith("x-bifrost")},
            indent=2,
        ))
        result = await bifrost_client.chat(
            [{"role": "user", "content": args.prompt}], force_fallback=args.force_fallback
        )
    except bifrost_client.UpstreamError as exc:
        print(f"FAILED: {exc}")
        return 1
    finally:
        await bifrost_client.aclose()

    print(f"text={result.text!r}")
    print(f"provider={result.provider}")
    print(f"fallback_triggered={result.fallback_triggered}")
    print(f"tokens_in={result.tokens_in} tokens_out={result.tokens_out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
