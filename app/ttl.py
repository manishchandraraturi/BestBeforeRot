"""Single source of truth for how long each claim type stays fresh."""

from app.models import ClaimType, Volatility

TTL_DAYS: dict[ClaimType, int | None] = {
    ClaimType.PRICING: 1,
    ClaimType.VERSION: 7,
    ClaimType.LEADERSHIP: 30,
    ClaimType.LAW: 30,
    ClaimType.OTHER: 7,
    ClaimType.STABLE: None,
}

VOLATILITY: dict[ClaimType, Volatility] = {
    ClaimType.PRICING: Volatility.FAST,
    ClaimType.VERSION: Volatility.FAST,
    ClaimType.LEADERSHIP: Volatility.SLOW,
    ClaimType.LAW: Volatility.SLOW,
    ClaimType.OTHER: Volatility.FAST,
    ClaimType.STABLE: Volatility.NEVER,
}


def for_type(claim_type: ClaimType | str) -> int | None:
    """Return TTL days for a claim type (None = never expires)."""
    return TTL_DAYS[ClaimType(claim_type)]


def volatility_for(claim_type: ClaimType | str) -> Volatility:
    """Return the volatility band for a claim type."""
    return VOLATILITY[ClaimType(claim_type)]
