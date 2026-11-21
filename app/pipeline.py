"""The request flow of 02-ARCHITECTURE.md §4: extract, cache, search, judge, score, rewrite."""

import asyncio
import logging
import time
import uuid

from app.config import settings
from app.models import (
    Claim,
    ClaimStatus,
    Source,
    Stats,
    Verdict,
    VerifyResponse,
    Volatility,
)
from app.services import bifrost_client, cache
from app.services import claims as claims_service
from app.services import judge as judge_service
from app.services import rewrite, scoring, tavily_client

logger = logging.getLogger(__name__)


class _Run:
    """Counters for one verify() call; the stats strip is built from these."""

    def __init__(self, use_cache: bool) -> None:
        self.use_cache = use_cache
        self.cache_hits = 0
        self.searched = 0
        self.skipped_stable = 0


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


def _apply_cached(claim: Claim, cached: Claim) -> None:
    """Copy a cached verdict onto today's claim; its own id, text and TTL stay untouched."""
    claim.status = ClaimStatus.CHECKED
    claim.verdict = cached.verdict
    claim.corrected_text = cached.corrected_text
    claim.reason = cached.reason
    claim.confidence = cached.confidence
    claim.sources = cached.sources
    claim.from_cache = True
    claim.expires_at = cached.expires_at


async def _process(
    claim: Claim, query: str, semaphore: asyncio.Semaphore, run: _Run
) -> Claim:
    """Serve one volatile claim from the fact cache, or search, judge and store it."""
    async with semaphore:
        if run.use_cache:
            cached = await cache.get_fact(cache.fact_key(claim.text))
            if cached is not None:
                # A hit spends no Tavily credit and no LLM call at all.
                _apply_cached(claim, cached)
                run.cache_hits += 1
                logger.info("fact cache hit claim=%s type=%s", claim.id, claim.type)
                return claim

        evidence = await tavily_client.search(query)
        run.searched += 1
        verdict = await judge_service.judge(claim, query, evidence)

    _attach(claim, verdict, evidence)
    if claim.ttl_days is not None:
        await cache.put_fact(claim, claim.ttl_days)
    return claim


def _stats(claims: list[Claim], run: _Run, llm_calls: list, started: float) -> Stats:
    """Build the stats strip from this run's counters and the Bifrost replies it saw."""
    return Stats(
        claims_total=len(claims),
        claims_searched=run.searched,
        claims_skipped_stable=run.skipped_stable,
        cache_hits=run.cache_hits,
        # One Tavily basic search costs one credit.
        tavily_credits_used=run.searched,
        tavily_credits_saved=run.cache_hits + run.skipped_stable,
        llm_calls=len(llm_calls),
        tokens_in=sum(result.tokens_in for result in llm_calls),
        tokens_out=sum(result.tokens_out for result in llm_calls),
        providers_used=sorted({result.provider for result in llm_calls}),
        fallback_triggered=any(result.fallback_triggered for result in llm_calls),
        latency_ms=int(round((time.perf_counter() - started) * 1000)),
    )


async def verify(
    answer: str, use_cache: bool = True, force_fallback: bool = False
) -> VerifyResponse:
    """Verify an answer end to end and return the frozen §5 response."""
    started = time.perf_counter()
    run = _Run(use_cache)
    llm_calls: list[bifrost_client.ChatResult] = []
    usage_token = bifrost_client.usage_sink.set(llm_calls)
    outage_token = bifrost_client.simulated_outage.set(force_fallback)
    try:
        claims = await claims_service.extract(answer)
        # Snapshot before anything awaits: last_queries is module state owned by the last extract().
        queries = dict(claims_service.last_queries)

        volatile: list[Claim] = []
        for claim in claims:
            if claim.volatility is Volatility.NEVER:
                claim.status = ClaimStatus.SKIPPED_STABLE
                claim.sources = []
                run.skipped_stable += 1
            else:
                volatile.append(claim)

        semaphore = asyncio.Semaphore(max(settings.MAX_PARALLEL, 1))
        results = await asyncio.gather(
            *(_process(claim, _query_for(claim, queries), semaphore, run) for claim in volatile),
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
    finally:
        bifrost_client.simulated_outage.reset(outage_token)
        bifrost_client.usage_sink.reset(usage_token)

    overall, band = scoring.score_claims(claims)
    stats = _stats(claims, run, llm_calls, started)
    logger.info(
        "verify claims=%d searched=%d stable=%d hits=%d errors=%d overall=%d band=%s latency_ms=%d",
        stats.claims_total,
        stats.claims_searched,
        stats.claims_skipped_stable,
        stats.cache_hits,
        sum(1 for claim in volatile if claim.status is ClaimStatus.ERROR),
        overall,
        band,
        stats.latency_ms,
    )
    return VerifyResponse(
        request_id=str(uuid.uuid4()),
        original_answer=answer,
        corrected_answer=rewrite.apply(answer, claims),
        overall_score=overall,
        overall_band=band,
        claims=claims,
        stats=stats,
    )
