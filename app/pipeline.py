"""Steps 1-5 of the request flow (02-ARCHITECTURE.md §4): extract, skip stable, search, judge."""

import asyncio
import logging

from app.config import settings
from app.models import Claim, ClaimStatus, Source, Verdict, Volatility
from app.services import claims as claims_service
from app.services import judge as judge_service
from app.services import scoring, tavily_client

logger = logging.getLogger(__name__)


def _query_for(claim: Claim, queries: dict[str, str]) -> str:
    """Use the extracted search query, falling back to the claim text when it is empty."""
    return (queries.get(claim.id) or "").strip() or claim.text


def _attach(claim: Claim, verdict: judge_service.Verdict, evidence: list) -> None:
    """Copy one judge result onto the claim, turning cited urls into typed sources."""
    by_url = {item.url: item for item in evidence}
    claim.verdict = verdict.verdict
    claim.corrected_text = verdict.corrected_text or None
    claim.reason = verdict.reason or None
    claim.confidence = verdict.confidence
    claim.sources = [
        Source(
            title=by_url[url].title or url,
            url=url,
            published=by_url[url].published_date,
        )
        for url in verdict.source_urls
        if url in by_url
    ]


async def _process(claim: Claim, query: str, semaphore: asyncio.Semaphore) -> Claim:
    """Search then judge one claim, holding one of the MAX_PARALLEL slots."""
    async with semaphore:
        evidence = await tavily_client.search(query)
        verdict = await judge_service.judge(claim, query, evidence)
    _attach(claim, verdict, evidence)
    return claim


async def verify(answer: str) -> list[Claim]:
    """Verify every claim in an answer and attach verdicts, sources and scores."""
    claims = await claims_service.extract(answer)
    if not claims:
        return []

    # Snapshot before anything awaits: last_queries is module state owned by the last extract().
    queries = dict(claims_service.last_queries)

    volatile: list[Claim] = []
    for claim in claims:
        if claim.volatility is Volatility.NEVER:
            claim.status = ClaimStatus.SKIPPED_STABLE
            claim.sources = []
        else:
            volatile.append(claim)

    semaphore = asyncio.Semaphore(max(settings.MAX_PARALLEL, 1))
    results = await asyncio.gather(
        *(_process(claim, _query_for(claim, queries), semaphore) for claim in volatile),
        return_exceptions=True,
    )

    for claim, outcome in zip(volatile, results):
        if isinstance(outcome, Claim):
            continue
        # One broken claim never fails the request (03-RULES.md §D).
        claim.status = ClaimStatus.ERROR
        claim.verdict = Verdict.UNVERIFIABLE
        claim.reason = "error"
        claim.confidence = 0.0
        claim.sources = []
        logger.warning(
            "claim %s failed (%s): %s", claim.id, type(outcome).__name__, outcome
        )

    overall, band = scoring.score_claims(claims)
    logger.info(
        "verify claims=%d searched=%d stable=%d errors=%d overall=%d band=%s",
        len(claims),
        len(volatile),
        len(claims) - len(volatile),
        sum(1 for claim in volatile if claim.status is ClaimStatus.ERROR),
        overall,
        band,
    )
    return claims
