"""Corrected answer: exact-substring replacement in code. The LLM is never needed here."""

import logging

from app.models import Claim, Verdict

logger = logging.getLogger(__name__)


def apply(answer: str, claims: list[Claim]) -> str:
    """Replace each stale claim's text with its correction; a text that moved is skipped."""
    corrected = answer
    for claim in claims:
        if claim.verdict is not Verdict.STALE:
            continue
        fix = (claim.corrected_text or "").strip()
        if not fix:
            continue
        if not claim.text or claim.text not in corrected:
            # Punctuation drifted between extraction and rewrite: keep the answer intact.
            logger.info("rewrite skipped claim=%s (text not found in answer)", claim.id)
            continue
        corrected = corrected.replace(claim.text, fix, 1)
    return corrected
