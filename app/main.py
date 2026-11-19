"""FastAPI entrypoint: health check plus the static site."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create one shared HTTP client for the process lifetime."""
    app.state.http = httpx.AsyncClient(timeout=settings.REQUEST_TIMEOUT_S)
    try:
        yield
    finally:
        await app.state.http.aclose()


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


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
