"""Frozen Pydantic v2 contracts (02-ARCHITECTURE.md §5). Do not rename fields."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ClaimType(StrEnum):
    """Volatility category assigned to a claim."""

    PRICING = "pricing"
    VERSION = "version"
    LAW = "law"
    LEADERSHIP = "leadership"
    STABLE = "stable"
    OTHER = "other"


class Volatility(StrEnum):
    """How fast a claim type ages."""

    FAST = "fast"
    SLOW = "slow"
    NEVER = "never"


class ClaimStatus(StrEnum):
    """Whether a claim was verified, skipped as stable, or errored."""

    CHECKED = "checked"
    SKIPPED_STABLE = "skipped_stable"
    ERROR = "error"


class Verdict(StrEnum):
    """Verification outcome for a checked claim."""

    FRESH = "fresh"
    STALE = "stale"
    UNVERIFIABLE = "unverifiable"


class OverallBand(StrEnum):
    """Freshness band for the whole answer."""

    FRESH = "fresh"
    MIXED = "mixed"
    RISKY = "risky"


class Source(BaseModel):
    """One web source backing a verdict."""

    title: str
    url: str
    published: str | None = None


class Claim(BaseModel):
    """A single factual claim with its verification result."""

    id: str
    text: str
    type: ClaimType
    volatility: Volatility
    ttl_days: int | None = None
    status: ClaimStatus
    verdict: Verdict | None = None
    corrected_text: str | None = None
    reason: str | None = None
    confidence: float | None = None
    score: int | None = None
    sources: list[Source] = Field(default_factory=list)
    from_cache: bool = False
    expires_at: datetime | None = None


class Stats(BaseModel):
    """Run counters for the stats strip."""

    claims_total: int = 0
    claims_searched: int = 0
    claims_skipped_stable: int = 0
    cache_hits: int = 0
    tavily_credits_used: int = 0
    tavily_credits_saved: int = 0
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    providers_used: list[str] = Field(default_factory=list)
    fallback_triggered: bool = False
    latency_ms: int = 0


class VerifyRequest(BaseModel):
    """Body of POST /api/verify."""

    answer: str = Field(min_length=20, max_length=4000)
    question: str | None = None
    force_fallback: bool = False
    use_cache: bool = True


class VerifyResponse(BaseModel):
    """Body returned by POST /api/verify."""

    request_id: str
    original_answer: str
    corrected_answer: str
    overall_score: int
    overall_band: OverallBand
    claims: list[Claim] = Field(default_factory=list)
    stats: Stats = Field(default_factory=Stats)
