"""FastAPI entrypoint: the verify API, cache/sample routes and the static site."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app import pipeline
from app.config import settings
from app.models import VerifyRequest, VerifyResponse
from app.services import bifrost_client, cache
from app.services import claims as claims_service
from app.services import judge as judge_service
from app.services import tavily_client

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# 02-ARCHITECTURE.md §5: POST /api/ask writes an answer with the weak model, then verifies it.
# 03-RULES.md §C keeps prompts in prompts.py, which is frozen until P8, so this one is local.
ASK_SYSTEM = (
    "Answer the user's question in 2-4 sentences of plain prose. "
    "State concrete details (prices, versions, names, roles) directly, without hedging."
)

# 03-RULES.md §C.7: three demo answers, one per volatile claim family.
SAMPLES: list[dict] = [
    {
        "id": "pricing",
        "title": "Notion pricing",
        "answer": (
            "The Notion Plus plan costs $5 per month per user. It includes unlimited "
            "file uploads, a 30-day version history and the Notion AI add-on."
        ),
    },
    {
        "id": "version",
        "title": "Python release",
        "answer": (
            "Python 3.11 is the latest stable release of Python. It ships the faster "
            "CPython interpreter and is the version recommended for new projects."
        ),
    },
    {
        "id": "leadership",
        "title": "Company leadership",
        "answer": (
            "Jack Dorsey is the CEO of Twitter. The company is still privately held "
            "and runs its own advertising business."
        ),
    },
]


class AskRequest(BaseModel):
    """Body of POST /api/ask."""

    question: str = Field(min_length=3, max_length=500)


async def _read_question(request: AskRequest) -> str:
    """Ask the weak model for a short answer; this answer is what gets verified."""
    result = await bifrost_client.chat(
        [
            {"role": "system", "content": ASK_SYSTEM},
            {"role": "user", "content": request.question},
        ],
        model=settings.WEAK_MODEL or settings.PRIMARY_MODEL,
    )
    return result.text.strip()


def _status_for(message: str) -> int:
    """503 when the gateway itself is unreachable, 502 for every other upstream failure."""
    return 503 if message.startswith("Bifrost unreachable") else 502


def _error(exc: Exception) -> JSONResponse:
    """Render one upstream failure as `{"error": "message"}` with its HTTP status."""
    message = str(exc) or type(exc).__name__
    logger.warning("upstream failure (%d): %s", _status_for(message), message)
    return JSONResponse(status_code=_status_for(message), content={"error": message})


def _failures() -> tuple[type[Exception], ...]:
    """Every error the pipeline can raise all the way up to a route."""
    return (
        bifrost_client.UpstreamError,
        tavily_client.SearchError,
        claims_service.ParseError,
        judge_service.ParseError,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create one shared HTTP client for the process lifetime."""
    app.state.http = httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_S)
    try:
        yield
    finally:
        await app.state.http.aclose()
        await tavily_client.aclose()
        await bifrost_client.aclose()


app = FastAPI(title="FactTTL", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict:
    """Report app liveness, Bifrost reachability and whether a Tavily key is set."""
    bifrost = False
    try:
        response = await app.state.http.get(
            f"{settings.BIFROST_URL.rstrip('/')}/v1/models", timeout=3
        )
        bifrost = response.status_code < 500
    except (httpx.HTTPError, OSError):
        bifrost = False
    return {"ok": True, "bifrost": bifrost, "tavily_key_set": settings.tavily_key_set}


@app.post("/api/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest):
    """Extract, cache, search, judge, score and rewrite one answer."""
    try:
        return await pipeline.verify(
            request.answer,
            use_cache=request.use_cache,
            force_fallback=request.force_fallback,
        )
    except _failures() as exc:
        return _error(exc)


@app.post("/api/ask", response_model=VerifyResponse)
async def ask(request: AskRequest):
    """Generate an answer with the weak model, then verify it like any other answer."""
    try:
        answer = await _read_question(request)
        if not answer:
            return JSONResponse(status_code=502, content={"error": "Bifrost returned an empty answer"})
        return await pipeline.verify(
            answer, use_cache=True, force_fallback=False
        )
    except _failures() as exc:
        return _error(exc)


@app.get("/api/cache")
async def cache_list() -> dict:
    """List the cached facts that are still fresh, with the seconds each one has left."""
    facts = await cache.list_facts()
    return {"count": len(facts), "facts": facts}


@app.delete("/api/cache")
async def cache_clear() -> dict:
    """Clear the facts table (demo reset) and report how many rows went away."""
    deleted = await cache.clear_facts()
    logger.info("fact cache cleared rows=%d", deleted)
    return {"deleted": deleted}


@app.get("/api/samples")
async def samples() -> dict:
    """Three demo answers: pricing, version and leadership."""
    return {"samples": SAMPLES}


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
