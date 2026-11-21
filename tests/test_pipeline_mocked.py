"""Pipeline tests with claim extraction, Tavily and the judge faked (no network)."""

import asyncio

import pytest

from app import pipeline, ttl
from app.config import settings
from app.models import Claim, ClaimStatus, ClaimType, Evidence, Verdict
from app.services import judge as judge_service
from app.services import tavily_client


def _claim(claim_id: str, text: str, claim_type: str) -> Claim:
    """Build an extracted (unjudged) claim."""
    return Claim(
        id=claim_id,
        text=text,
        type=ClaimType(claim_type),
        volatility=ttl.volatility_for(claim_type),
        ttl_days=ttl.for_type(claim_type),
        status=ClaimStatus.CHECKED,
    )


def _evidence(count: int = 2) -> list[Evidence]:
    """Two Tavily-shaped results with distinct domains."""
    return [
        Evidence(
            title=f"Result {index}",
            url=f"https://site{index}.example/page",
            content="Notion Plus is $10 per seat/month.",
            score=0.9 - index / 10,
        )
        for index in range(count)
    ]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Deterministic settings, a private facts DB and clean module state for every test."""
    monkeypatch.setattr(settings, "MAX_PARALLEL", 4)
    monkeypatch.setattr(settings, "CACHE_DB", str(tmp_path / "facts.db"))
    monkeypatch.setattr(pipeline.claims_service, "last_queries", {})
    yield


def _install_extract(monkeypatch, extracted: list[Claim], queries: dict[str, str]) -> None:
    """Fake claim extraction, including the last_queries side effect."""

    async def fake_extract(answer: str) -> list[Claim]:
        pipeline.claims_service.last_queries.clear()
        pipeline.claims_service.last_queries.update(queries)
        return [claim.model_copy(deep=True) for claim in extracted]

    monkeypatch.setattr(pipeline.claims_service, "extract", fake_extract)


def _install_search(monkeypatch, handler) -> list[str]:
    """Fake Tavily search and record the queries it was asked."""
    queries: list[str] = []

    async def fake_search(query: str) -> list[Evidence]:
        queries.append(query)
        return await handler(query)

    monkeypatch.setattr(pipeline.tavily_client, "search", fake_search)
    return queries


def _install_judge(monkeypatch, judge_handler) -> list[tuple[str, str]]:
    """Fake the judge and record (claim id, query)."""
    seen: list[tuple[str, str]] = []

    async def fake_judge(claim: Claim, query: str, evidence: list[Evidence]):
        seen.append((claim.id, query))
        return await judge_handler(claim, query, evidence)

    monkeypatch.setattr(pipeline.judge_service, "judge", fake_judge)
    return seen


async def _fresh(claim: Claim, query: str, evidence: list[Evidence]) -> judge_service.Verdict:
    """Judge stub that confirms the claim and cites every result."""
    return judge_service.Verdict(
        verdict="fresh",
        current_value="$10 per month",
        corrected_text=claim.text,
        source_urls=[item.url for item in evidence],
        confidence=0.9,
        reason="Evidence agrees.",
    )


@pytest.mark.asyncio
async def test_stable_claim_is_skipped_without_a_search(monkeypatch) -> None:
    """Stable claims cost no Tavily credit and are marked skipped_stable."""
    _install_extract(
        monkeypatch,
        [
            _claim("c1", "Notion Plus costs $5 per month.", "pricing"),
            _claim("c2", "The Eiffel Tower is in Paris.", "stable"),
        ],
        {"c1": "Notion Plus price 2026", "c2": ""},
    )
    queries = _install_search(monkeypatch, lambda query: _as_list(_evidence()))
    _install_judge(monkeypatch, _fresh)

    result = (await pipeline.verify("answer text")).claims

    assert queries == ["Notion Plus price 2026"]
    stable = result[1]
    assert stable.status is ClaimStatus.SKIPPED_STABLE
    assert stable.verdict is None
    assert stable.score is None
    assert stable.sources == []


@pytest.mark.asyncio
async def test_verdict_sources_and_score_are_attached(monkeypatch) -> None:
    """A judged claim carries verdict, corrected text, typed sources and a PRD score."""
    _install_extract(monkeypatch, [_claim("c1", "Notion Plus costs $5 per month.", "pricing")], {"c1": "q1"})
    _install_search(monkeypatch, lambda query: _as_list(_evidence()))
    _install_judge(monkeypatch, _fresh)

    claims = (await pipeline.verify("answer text")).claims

    claim = claims[0]
    assert claim.status is ClaimStatus.CHECKED
    assert claim.verdict is Verdict.FRESH
    assert claim.confidence == 0.9
    assert claim.corrected_text == "Notion Plus costs $5 per month."
    assert [source.url for source in claim.sources] == [
        "https://site0.example/page",
        "https://site1.example/page",
    ]
    assert claim.sources[0].title == "Result 0"
    assert claim.score == 99  # 80 + 9 + 10 for two independent domains


@pytest.mark.asyncio
async def test_search_uses_the_extracted_query_and_falls_back_to_the_claim_text(monkeypatch) -> None:
    """The query comes from claims.last_queries; an empty one falls back to the claim text."""
    _install_extract(
        monkeypatch,
        [
            _claim("c1", "Notion Plus costs $5 per month.", "pricing"),
            _claim("c2", "Notion Plus has unlimited blocks.", "pricing"),
        ],
        {"c1": "Notion Plus price 2026", "c2": ""},
    )
    queries = _install_search(monkeypatch, lambda query: _as_list(_evidence()))
    _install_judge(monkeypatch, _fresh)

    await pipeline.verify("answer text")

    assert queries == ["Notion Plus price 2026", "Notion Plus has unlimited blocks."]


@pytest.mark.asyncio
async def test_search_error_isolates_one_claim(monkeypatch) -> None:
    """A Tavily failure marks only that claim unverifiable and the request still succeeds."""
    _install_extract(
        monkeypatch,
        [
            _claim("c1", "First claim text.", "pricing"),
            _claim("c2", "Second claim text.", "version"),
        ],
        {"c1": "first", "c2": "second"},
    )

    async def handler(query: str) -> list[Evidence]:
        if query == "first":
            raise tavily_client.SearchError("Tavily rejected the API key (HTTP 401).")
        return _evidence()

    _install_search(monkeypatch, handler)
    _install_judge(monkeypatch, _fresh)

    claims = (await pipeline.verify("answer text")).claims

    failed, ok = claims
    assert failed.status is ClaimStatus.ERROR
    assert failed.verdict is Verdict.UNVERIFIABLE
    assert failed.reason == "error"
    assert failed.confidence == 0.0
    assert failed.score == 40
    assert ok.verdict is Verdict.FRESH
    assert ok.status is ClaimStatus.CHECKED


@pytest.mark.asyncio
async def test_judge_parse_error_isolates_one_claim(monkeypatch) -> None:
    """A judge crash on one claim does not take down its neighbours."""
    _install_extract(
        monkeypatch,
        [
            _claim("c1", "First claim text.", "pricing"),
            _claim("c2", "Second claim text.", "version"),
        ],
        {"c1": "first", "c2": "second"},
    )
    _install_search(monkeypatch, lambda query: _as_list(_evidence()))

    async def handler(claim: Claim, query: str, evidence: list[Evidence]):
        if claim.id == "c1":
            raise judge_service.ParseError("judge returned unusable JSON twice")
        return await _fresh(claim, query, evidence)

    _install_judge(monkeypatch, handler)

    claims = (await pipeline.verify("answer text")).claims

    assert claims[0].status is ClaimStatus.ERROR
    assert claims[0].verdict is Verdict.UNVERIFIABLE
    assert claims[1].verdict is Verdict.FRESH


@pytest.mark.asyncio
async def test_max_parallel_bounds_concurrent_claims(monkeypatch) -> None:
    """With MAX_PARALLEL=2, never more than two claims are in flight at once."""
    monkeypatch.setattr(settings, "MAX_PARALLEL", 2)
    extracted = [_claim(f"c{index}", f"Claim number {index}.", "pricing") for index in range(1, 6)]
    _install_extract(monkeypatch, extracted, {claim.id: f"q{claim.id}" for claim in extracted})

    state = {"in_flight": 0, "peak": 0}

    async def handler(query: str) -> list[Evidence]:
        state["in_flight"] += 1
        state["peak"] = max(state["peak"], state["in_flight"])
        await asyncio.sleep(0.02)
        state["in_flight"] -= 1
        return _evidence()

    _install_search(monkeypatch, handler)
    _install_judge(monkeypatch, _fresh)

    claims = (await pipeline.verify("answer text")).claims

    assert state["peak"] == 2
    assert len(claims) == 5


@pytest.mark.asyncio
async def test_no_claims_returns_early_without_searching(monkeypatch) -> None:
    """An answer with no extracted claims costs nothing."""
    _install_extract(monkeypatch, [], {})
    queries = _install_search(monkeypatch, lambda query: _as_list(_evidence()))
    _install_judge(monkeypatch, _fresh)

    assert (await pipeline.verify("answer text")).claims == []
    assert queries == []


async def _as_list(value: list[Evidence]) -> list[Evidence]:
    """Return the evidence unchanged from an async stub."""
    return value
