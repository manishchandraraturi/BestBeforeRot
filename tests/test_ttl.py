"""Tests for app/ttl.py."""

import pytest

from app.models import ClaimType, Volatility
from app.ttl import TTL_DAYS, for_type, volatility_for


@pytest.mark.parametrize(
    ("claim_type", "days"),
    [
        ("pricing", 1),
        ("version", 7),
        ("leadership", 30),
        ("law", 30),
        ("other", 7),
        ("stable", None),
    ],
)
def test_for_type(claim_type: str, days: int | None) -> None:
    """Each claim type maps to its frozen TTL."""
    assert for_type(claim_type) == days
    assert for_type(ClaimType(claim_type)) == days


@pytest.mark.parametrize(
    ("claim_type", "expected"),
    [
        ("pricing", Volatility.FAST),
        ("version", Volatility.FAST),
        ("other", Volatility.FAST),
        ("leadership", Volatility.SLOW),
        ("law", Volatility.SLOW),
        ("stable", Volatility.NEVER),
    ],
)
def test_volatility_for(claim_type: str, expected: Volatility) -> None:
    """Each claim type maps to its volatility band."""
    assert volatility_for(claim_type) == expected


def test_ttl_table_covers_every_claim_type() -> None:
    """The TTL table has exactly one entry per claim type."""
    assert set(TTL_DAYS) == set(ClaimType)
