"""Deterministic freshness scores from 01-PRD.md §7. The LLM never decides numbers."""

from urllib.parse import urlsplit

from app.models import Claim, OverallBand, Verdict, Volatility

WEIGHTS: dict[Volatility, float] = {Volatility.FAST: 1.5, Volatility.SLOW: 1.0}
FRESH_BASE = 80
FRESH_CONFIDENCE_BONUS = 10
FRESH_SOURCES_BONUS = 10
STALE_SCORE = 15
UNVERIFIABLE_SCORE = 40


def _independent_domains(claim: Claim) -> set[str]:
    """Distinct source domains, so two articles on one site are not two sources."""
    return {urlsplit(source.url).netloc.lower() for source in claim.sources if source.url}


def claim_score(claim: Claim) -> int | None:
    """Score one claim, or None when it is stable and therefore not scored."""
    if claim.volatility is Volatility.NEVER or claim.verdict is None:
        return None
    if claim.verdict is Verdict.STALE:
        return STALE_SCORE
    if claim.verdict is Verdict.UNVERIFIABLE:
        return UNVERIFIABLE_SCORE
    score = FRESH_BASE + FRESH_CONFIDENCE_BONUS * float(claim.confidence or 0.0)
    if len(_independent_domains(claim)) >= 2:
        score += FRESH_SOURCES_BONUS
    return int(round(min(score, 100)))


def band_for(score: int) -> OverallBand:
    """Map an overall score to the UI band: 80-100 fresh, 50-79 mixed, 0-49 risky."""
    if score >= 80:
        return OverallBand.FRESH
    if score >= 50:
        return OverallBand.MIXED
    return OverallBand.RISKY


def score_claims(claims: list[Claim]) -> tuple[int, str]:
    """Score every claim, store it on the claim, and return the weighted overall score and band."""
    weighted = 0.0
    total_weight = 0.0
    for claim in claims:
        score = claim_score(claim)
        claim.score = score
        weight = WEIGHTS.get(claim.volatility)
        if score is None or weight is None:
            continue
        weighted += score * weight
        total_weight += weight

    if total_weight == 0:
        # Nothing can go stale, so the answer carries no freshness risk.
        return 100, band_for(100).value
    overall = int(round(weighted / total_weight))
    overall = min(max(overall, 0), 100)
    return overall, band_for(overall).value
