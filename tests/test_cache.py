"""Fact cache, rewrite and the pipeline's cold/warm path (no network)."""

import pytest

from app import pipeline, ttl
from app.config import settings
from app.models import Claim, ClaimStatus, ClaimType, Evidence, Source, Verdict
from app.services import cache, rewrite
from app.services import judge as judge_service


def _claim(claim_id: str, text: str, claim_type: str = "pricing") -> Claim:
    """Build an extracted (unjudged) claim."""
    return Claim(
        id=claim_id,
        text=text,
        type=ClaimType(claim_type),
        volatility=ttl.volatility_for(claim_type),
        ttl_days=ttl.for_type(claim_type),
        status=ClaimStatus.CHECKED,
    )


def _judged(claim: Claim) -> Claim:
    """A claim the judge marked stale, with one source."""
    judged = claim.model_copy(deep=True)
    judged.status = ClaimStatus.CHECKED
    judged.verdict = Verdict.STALE
    judged.corrected_text = "The Notion Plus plan costs $10 per month."
    judged.reason = "Pricing changed."
    judged.confidence = 0.9
    judged.sources = [Source(title="Notion pricing", url="https://notion.example/pricing")]
    return judged


def _evidence() -> list[Evidence]:
    """Two Tavily-shaped results with distinct domains."""
    return [
        Evidence(
            title=f"Result {index}",
            url=f"https://site{index}.example/page",
            content="Notion Plus is $10 per seat/month.",
            score=0.9 - index / 10,
        )
        for index in range(2)
    ]


@pytest.fixture(autouse=True)
def facts_db(tmp_path, monkeypatch):
    """Every test gets its own facts DB, so no test can see another one's cache."""
    monkeypatch.setattr(settings, "CACHE_DB", str(tmp_path / "facts.db"))
    monkeypatch.setattr(settings, "MAX_PARALLEL", 4)
    monkeypatch.setattr(pipeline.claims_service, "last_queries", {})
    yield


@pytest.mark.asyncio
async def test_fact_key_ignores_case_and_spacing() -> None:
    """Casing and repeated whitespace must not split one fact into two keys."""
    assert cache.fact_key("The  Notion Plus costs $5") == cache.fact_key(
        "the notion plus COSTS $5"
    )
    assert cache.fact_key("Notion Plus costs $5") != cache.fact_key(
        "Notion Plus costs $10"
    )


@pytest.mark.asyncio
async def test_put_then_get_returns_the_claim() -> None:
    """A stored claim comes back with its verdict, correction and expiry."""
    claim = _judged(_claim("c1", "The Notion Plus plan costs $5 per month."))

    await cache.put_fact(claim, ttl_days=1)
    hit = await cache.get_fact(cache.fact_key(claim.text))

    assert hit is not None
    assert hit.text == claim.text
    assert hit.verdict is Verdict.STALE
    assert hit.corrected_text == "The Notion Plus plan costs $10 per month."
    assert hit.expires_at is not None


@pytest.mark.asyncio
async def test_expired_fact_is_a_miss() -> None:
    """A negative TTL writes a row that is already expired, so it reads as a miss."""
    claim = _judged(_claim("c1", "The Notion Plus plan costs $5 per month."))

    await cache.put_fact(claim, ttl_days=-1)

    assert await cache.get_fact(cache.fact_key(claim.text)) is None
    assert await cache.list_facts() == []


@pytest.mark.asyncio
async def test_unknown_key_is_a_miss() -> None:
    """An empty cache answers None, not an error."""
    assert await cache.get_fact("0" * 40) is None


@pytest.mark.asyncio
async def test_unusable_db_file_runs_without_cache(tmp_path, monkeypatch) -> None:
    """A path that is not a database only loses caching; nothing raises."""
    monkeypatch.setattr(settings, "CACHE_DB", str(tmp_path))  # a directory: sqlite cannot open it
    claim = _judged(_claim("c1", "The Notion Plus plan costs $5 per month."))

    await cache.put_fact(claim, ttl_days=1)

    assert await cache.get_fact(cache.fact_key(claim.text)) is None
    assert await cache.list_facts() == []
    assert await cache.clear_facts() == 0


@pytest.mark.asyncio
async def test_list_facts_reports_seconds_left() -> None:
    """One day of TTL is reported as roughly 86400 seconds left."""
    claim = _judged(_claim("c1", "The Notion Plus plan costs $5 per month."))
    await cache.put_fact(claim, ttl_days=1)

    facts = await cache.list_facts()

    assert len(facts) == 1
    assert facts[0]["text"] == claim.text
    assert facts[0]["verdict"] == "stale"
    assert 86000 <= facts[0]["seconds_left"] <= 86400


@pytest.mark.asyncio
async def test_clear_removes_rows() -> None:
    """Clearing the table deletes the stored fact and returns the row count."""
    claim = _judged(_claim("c1", "The Notion Plus plan costs $5 per month."))
    await cache.put_fact(claim, ttl_days=1)

    assert await cache.clear_facts() == 1
    assert await cache.get_fact(cache.fact_key(claim.text)) is None


def test_rewrite_replaces_stale_text() -> None:
    """A stale claim found verbatim in the answer is replaced with its correction."""
    answer = "The Notion Plus plan costs $5 per month."
    claim = _judged(_claim("c1", answer))

    assert rewrite.apply(answer, [claim]) == "The Notion Plus plan costs $10 per month."


def test_rewrite_skips_text_that_was_not_found() -> None:
    """Minor punctuation drift means the claim is skipped, never crashed on."""
    claim = _judged(_claim("c1", "The Notion Plus plan costs $5 per month."))

    answer = "Notion Plus costs $5 per month."
    assert rewrite.apply(answer, [claim]) == answer


def test_rewrite_ignores_fresh_and_unverifiable() -> None:
    """Only stale claims are rewritten."""
    answer = "The Notion Plus plan costs $5 per month."
    fresh = _claim("c1", answer)
    fresh.verdict = Verdict.FRESH
    fresh.corrected_text = answer
    unverifiable = _claim("c2", answer)
    unverifiable.verdict = Verdict.UNVERIFIABLE

    assert rewrite.apply(answer, [fresh, unverifiable]) == answer


@pytest.mark.asyncio
async def test_second_verify_is_served_from_the_fact_cache(monkeypatch) -> None:
    """The warm run spends no Tavily credit and no LLM call and reports cache_hits."""
    answer = "The Notion Plus plan costs $5 per month."
    extracted = _claim("c1", "The Notion Plus plan costs $5 per month.")
    searches: list[str] = []

    async def fake_extract(text: str) -> list[Claim]:
        pipeline.claims_service.last_queries.clear()
        pipeline.claims_service.last_queries["c1"] = "Notion Plus price 2026"
        return [extracted.model_copy(deep=True)]

    async def fake_search(query: str) -> list[Evidence]:
        searches.append(query)
        return _evidence()

    async def fake_judge(claim: Claim, query: str, evidence: list[Evidence]):
        return judge_service.Verdict(
            verdict="stale",
            current_value="$10 per month",
            corrected_text="The Notion Plus plan costs $10 per month.",
            source_urls=[item.url for item in evidence],
            confidence=0.9,
            reason="Pricing changed.",
        )

    monkeypatch.setattr(pipeline.claims_service, "extract", fake_extract)
    monkeypatch.setattr(pipeline.tavily_client, "search", fake_search)
    monkeypatch.setattr(pipeline.judge_service, "judge", fake_judge)

    cold = await pipeline.verify(answer)
    assert cold.stats.cache_hits == 0
    assert cold.stats.tavily_credits_used == 1
    assert cold.claims[0].from_cache is False
    assert cold.corrected_answer == "The Notion Plus plan costs $10 per month."

    warm = await pipeline.verify(answer)
    assert warm.stats.cache_hits == 1
    assert warm.stats.tavily_credits_used == 0
    assert warm.stats.llm_calls == 0
    assert warm.claims[0].from_cache is True
    assert warm.claims[0].verdict is Verdict.STALE
    assert warm.corrected_answer == "The Notion Plus plan costs $10 per month."
    assert len(searches) == 1

    fresh_run = await pipeline.verify(answer, use_cache=False)
    assert fresh_run.stats.cache_hits == 0
    assert fresh_run.stats.tavily_credits_used == 1
    assert fresh_run.claims[0].from_cache is False
    assert len(searches) == 2
