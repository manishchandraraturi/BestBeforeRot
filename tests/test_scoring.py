"""Tests for app/services/scoring.py against the frozen math in 01-PRD.md §7."""

import pytest

from app import ttl
from app.models import Claim, ClaimStatus, ClaimType, OverallBand, Source
from app.services.scoring import band_for, claim_score, score_claims


def _claim(
    claim_type: str = "pricing",
    verdict: str | None = "fresh",
    confidence: float | None = 0.9,
    urls: tuple[str, ...] = ("https://a.example/pricing",),
    claim_id: str = "c1",
) -> Claim:
    """Build a claim whose volatility and TTL come from the real ttl table."""
    return Claim(
        id=claim_id,
        text="Some claim.",
        type=ClaimType(claim_type),
        volatility=ttl.volatility_for(claim_type),
        ttl_days=ttl.for_type(claim_type),
        status=ClaimStatus.CHECKED,
        verdict=verdict,
        confidence=confidence,
        sources=[Source(title=f"src {index}", url=url) for index, url in enumerate(urls)],
    )


@pytest.mark.parametrize(
    ("confidence", "urls", "expected"),
    [
        (0.9, ("https://a.example/1",), 89),
        (0.9, ("https://a.example/1", "https://b.example/2"), 99),
        (1.0, ("https://a.example/1", "https://b.example/2"), 100),
        (0.0, ("https://a.example/1",), 80),
        # Two articles on one site are not two independent sources.
        (0.9, ("https://a.example/1", "https://a.example/2"), 89),
        (0.9, (), 89),
    ],
)
def test_fresh_score(confidence: float, urls: tuple[str, ...], expected: int) -> None:
    """fresh = 80 + 10*confidence + 10 when at least two domains agree."""
    claim = _claim(confidence=confidence, urls=urls)
    assert claim_score(claim) == expected


def test_fresh_without_confidence_or_sources_is_80() -> None:
    """Missing confidence and sources still give the fresh base score."""
    assert claim_score(_claim(confidence=None, urls=())) == 80


def test_stale_and_unverifiable_are_fixed_scores() -> None:
    """stale is always 15 and unverifiable always 40, whatever the evidence was."""
    stale = _claim(verdict="stale", confidence=1.0, urls=("https://a.example/1", "https://b.example/2"))
    unverifiable = _claim(verdict="unverifiable", confidence=1.0, urls=("https://a.example/1",))
    assert claim_score(stale) == 15
    assert claim_score(unverifiable) == 40


def test_stable_claims_are_not_scored() -> None:
    """A stable claim has no score, even if a verdict somehow reached it."""
    assert claim_score(_claim(claim_type="stable", verdict=None)) is None
    assert claim_score(_claim(claim_type="stable", verdict="fresh")) is None


def test_claim_without_verdict_is_not_scored() -> None:
    """A claim that was never judged contributes nothing to the overall score."""
    assert claim_score(_claim(verdict=None)) is None


def test_score_claims_stores_per_claim_scores_and_weights_fast_above_slow() -> None:
    """(99*1.5 + 15*1.0)/2.5 = 65.4 -> 65: the fast claim pulls the mean harder."""
    claims = [
        _claim(claim_id="c1", urls=("https://a.example/1", "https://b.example/2")),  # 99, fast
        _claim(claim_id="c2", claim_type="leadership", verdict="stale"),  # 15, slow
    ]
    overall, band = score_claims(claims)

    assert [claim.score for claim in claims] == [99, 15]
    assert overall == 65
    assert band == OverallBand.MIXED.value


def test_stable_claims_are_excluded_from_the_mean() -> None:
    """The weighted mean only covers scored claims, so stable rows cannot drag it down."""
    claims = [
        _claim(claim_id="c1", verdict="stale"),
        _claim(claim_id="c2", claim_type="stable", verdict=None),
    ]
    assert score_claims(claims) == (15, OverallBand.RISKY.value)


def test_answer_with_nothing_to_age_is_fresh() -> None:
    """A purely stable answer has no freshness risk, so it scores 100 fresh."""
    assert score_claims([_claim(claim_type="stable", verdict=None)]) == (
        100,
        OverallBand.FRESH.value,
    )
    assert score_claims([]) == (100, OverallBand.FRESH.value)


@pytest.mark.parametrize(
    ("score", "band"),
    [(100, "fresh"), (80, "fresh"), (79, "mixed"), (50, "mixed"), (49, "risky"), (0, "risky")],
)
def test_band_boundaries(score: int, band: str) -> None:
    """Bands are 80-100 fresh, 50-79 mixed, 0-49 risky."""
    assert band_for(score) == band


def test_overall_score_is_an_int_in_range() -> None:
    """The overall score is a rounded int, never a float or out of 0-100."""
    claims = [
        _claim(claim_id="c1", confidence=0.85, urls=("https://a.example/1", "https://b.example/2")),
        _claim(claim_id="c2", claim_type="version", verdict="unverifiable"),
        _claim(claim_id="c3", claim_type="other", verdict="fresh", confidence=0.3),
    ]
    overall, band = score_claims(claims)

    assert isinstance(overall, int)
    assert 0 <= overall <= 100
    assert band == band_for(overall)
