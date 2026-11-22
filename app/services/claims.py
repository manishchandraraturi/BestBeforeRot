"""Claim extraction: one Bifrost call, strict JSON, then code assigns type numbers (P4)."""

import json
import logging
import re
from datetime import date

from pydantic import BaseModel, ValidationError

from app import ttl
from app.config import settings
from app.models import Claim, ClaimStatus, ClaimType, Volatility
from app.prompts import CLAIMS_SYSTEM, REPAIR_PROMPT
from app.services import bifrost_client

logger = logging.getLogger(__name__)

# The cut at MAX_CLAIMS drops the least volatile claims first (03-RULES.md §C.8).
_KEEP_PRIORITY: dict[Volatility, int] = {
    Volatility.FAST: 2,
    Volatility.SLOW: 1,
    Volatility.NEVER: 0,
}

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")

# Trailing commas before a closing brace or bracket are the most common model JSON slip.
_TRAILING_COMMA = re.compile(r",(\s*[}\]])")

# VerifyRequest already caps answers at 4000 characters, so this only guards the extraction
# prompt: it matches that cap rather than cutting the user's text mid-answer. A model that
# still wraps the reply in prose is handled by the brace extraction in _extract_object().
_MAX_ANSWER_CHARS = 4000


class ParseError(Exception):
    """The model did not return usable claim JSON, even after one repair retry."""


class RawClaim(BaseModel):
    """One claim exactly as the model returned it, before any validation of ours."""

    text: str
    type: ClaimType
    search_query: str = ""


class RawClaims(BaseModel):
    """The model's whole JSON object."""

    claims: list[RawClaim]


# Claim.search_query is not in the frozen models.py contract, so the queries made by the
# last extract() call live here, keyed by claim id (same pattern as tavily_client.last_raw).
last_queries: dict[str, str] = {}
last_raw: str | None = None
last_repaired: bool = False


def _model() -> str:
    """Small model for extraction, falling back to the primary when WEAK_MODEL is unset."""
    return settings.WEAK_MODEL or settings.PRIMARY_MODEL


def _messages(answer: str) -> list[dict]:
    """Build the extraction messages: frozen system prompt, today's date, then the answer."""
    # Very long answers make the model drift off the schema and answer conversationally, so
    # only the first _MAX_ANSWER_CHARS characters are sent to the extraction prompt. That is
    # far more than MAX_CLAIMS claims need, and it keeps the reply parseable.
    trimmed = answer[:_MAX_ANSWER_CHARS]
    return [
        {"role": "system", "content": CLAIMS_SYSTEM},
        {"role": "user", "content": f"TODAY: {date.today().isoformat()}\nANSWER:\n{trimmed}"},
    ]


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from a reply that contains no JSON object at all."""
    return _FENCE.sub("", text.strip()).strip()


def _extract_object(text: str) -> str:
    """Slice the reply from its first '{' to its last '}'.

    Whatever the model wrapped around the object - markdown fences, a leading "Sure, here is
    the JSON:", a trailing explanation - is dropped, so only the JSON body is parsed.
    """
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return _strip_fences(text)


def _repair_json(body: str) -> str:
    """Undo the usual model JSON damage (trailing commas) before spending a repair call."""
    return _TRAILING_COMMA.sub(r"\1", body)


def _parse(text: str) -> RawClaims:
    """Turn one model reply into RawClaims, or raise ParseError."""
    body = _extract_object(text)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        # A cheap local fix (trailing commas, ...) beats a second model round trip.
        patched = _repair_json(body)
        if patched == body:
            raise ParseError(f"claim JSON did not parse: {exc.msg}") from exc
        try:
            payload = json.loads(patched)
        except json.JSONDecodeError:
            raise ParseError(f"claim JSON did not parse: {exc.msg}") from exc
    try:
        return RawClaims.model_validate(payload)
    except ValidationError as exc:
        raise ParseError(f"claim JSON failed validation: {exc.error_count()} error(s)") from exc


def _bare(text: str) -> str:
    """Lowercase letters and digits only, so punctuation and quoting cannot break matching."""
    return "".join(char for char in text.lower() if char.isalnum())


def _cap(candidates: list[tuple[str, ClaimType, str]]) -> list[tuple[str, ClaimType, str]]:
    """Keep at most MAX_CLAIMS claims, dropping the least volatile ones, in answer order."""
    limit = max(settings.MAX_CLAIMS, 0)
    if limit == 0:
        return []
    if len(candidates) <= limit:
        return candidates
    ranked = sorted(
        range(len(candidates)),
        key=lambda index: (-_KEEP_PRIORITY[ttl.volatility_for(candidates[index][1])], index),
    )
    kept = sorted(ranked[:limit])
    logger.info(
        "claim cap MAX_CLAIMS=%d: dropped %d least-volatile claim(s)",
        limit,
        len(candidates) - limit,
    )
    return [candidates[index] for index in kept]


async def extract(answer: str) -> list[Claim]:
    """Extract up to MAX_CLAIMS claims found verbatim in the answer, with TTLs assigned."""
    global last_raw, last_repaired
    last_queries.clear()
    last_raw = None
    last_repaired = False

    if not answer.strip():
        return []

    messages = _messages(answer)
    result = await bifrost_client.chat(messages, model=_model())
    last_raw = result.text
    try:
        parsed = _parse(result.text)
    except ParseError as first_error:
        logger.warning("claim JSON unusable, one repair retry: %s", first_error)
        repaired = [
            *messages,
            {"role": "assistant", "content": result.text},
            {"role": "user", "content": REPAIR_PROMPT},
        ]
        second = await bifrost_client.chat(repaired, model=_model())
        last_raw, last_repaired = second.text, True
        try:
            parsed = _parse(second.text)
        except ParseError as second_error:
            raise ParseError(
                f"claim extraction returned unusable JSON twice: {second_error}"
            ) from second_error

    answer_bare = _bare(answer)
    candidates: list[tuple[str, ClaimType, str]] = []
    for raw in parsed.claims:
        text = raw.text.strip()
        bare = _bare(text)
        if not bare or bare not in answer_bare:
            logger.warning("dropped a claim that is not copied from the answer: %r", text[:80])
            continue
        candidates.append((text, raw.type, raw.search_query.strip()))

    claims: list[Claim] = []
    for index, (text, claim_type, query) in enumerate(_cap(candidates), start=1):
        claim_id = f"c{index}"
        claims.append(
            Claim(
                id=claim_id,
                text=text,
                type=claim_type,
                volatility=ttl.volatility_for(claim_type),
                ttl_days=ttl.for_type(claim_type),
                # Extracted claims are all "checked" here; P5 decides what gets skipped.
                status=ClaimStatus.CHECKED,
            )
        )
        last_queries[claim_id] = query

    logger.info(
        "claims extracted=%d model=%s provider=%s fallback=%s repaired=%s",
        len(claims),
        _model(),
        result.provider,
        result.fallback_triggered,
        last_repaired,
    )
    return claims
