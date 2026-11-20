"""Judge: one claim plus Tavily evidence becomes a verdict. Own memory is off-limits (§C)."""

import json
import logging
import re
from datetime import date

from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.models import Claim, Evidence, Verdict as VerdictKind
from app.prompts import JUDGE_REPAIR_PROMPT, JUDGE_SYSTEM
from app.services import bifrost_client

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


class ParseError(Exception):
    """The judge model did not return usable JSON, even after one repair retry."""


class Verdict(BaseModel):
    """What the judge decided for one claim (mapped onto `Claim` by the pipeline)."""

    verdict: VerdictKind
    current_value: str = ""
    corrected_text: str = ""
    source_urls: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""


def _strip_fences(text: str) -> str:
    """Remove markdown code fences and any prose around the JSON object."""
    cleaned = _FENCE.sub("", text.strip()).strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _parse(text: str) -> Verdict:
    """Turn one model reply into a Verdict, or raise ParseError."""
    try:
        payload = json.loads(_strip_fences(text))
    except json.JSONDecodeError as exc:
        raise ParseError(f"judge JSON did not parse: {exc.msg}") from exc
    try:
        return Verdict.model_validate(payload)
    except ValidationError as exc:
        raise ParseError(f"judge JSON failed validation: {exc.error_count()} error(s)") from exc


def _evidence_block(evidence: list[Evidence]) -> str:
    """Render evidence as `[n] title | url | published | content`, as 03-RULES.md §C specifies."""
    lines = []
    for index, item in enumerate(evidence, 1):
        published = item.published_date or ""
        lines.append(f"[{index}] {item.title} | {item.url} | {published} | {item.content}")
    return "\n".join(lines)


def _messages(claim: Claim, evidence: list[Evidence]) -> list[dict]:
    """Build the judge messages: frozen system prompt plus TODAY / CLAIM / EVIDENCE."""
    today = date.today().isoformat()
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {
            "role": "user",
            "content": f"TODAY: {today}\nCLAIM: {claim.text}\nEVIDENCE:\n{_evidence_block(evidence)}",
        },
    ]


def _cited_urls(urls: list[str], evidence: list[Evidence]) -> list[str]:
    """Keep only urls that really appear in the evidence (the judge may not invent sources)."""
    allowed = {item.url for item in evidence}
    kept: list[str] = []
    for url in urls:
        url = (url or "").strip()
        if url in allowed and url not in kept:
            kept.append(url)
    return kept


def _confidence(value: float) -> float:
    """Clamp confidence into 0-1, accepting a 0-100 percentage by mistake."""
    number = float(value or 0.0)
    if number > 1:
        number = number / 100
    return min(max(number, 0.0), 1.0)


def _normalise(parsed: Verdict, claim: Claim, evidence: list[Evidence]) -> Verdict:
    """Apply the code-side rules: fresh keeps the claim text, unverifiable has no fix."""
    corrected = (parsed.corrected_text or "").strip()
    if parsed.verdict is VerdictKind.FRESH:
        corrected = claim.text
    elif parsed.verdict is VerdictKind.UNVERIFIABLE:
        corrected = ""
    return Verdict(
        verdict=parsed.verdict,
        current_value=(parsed.current_value or "").strip()[:300],
        corrected_text=corrected,
        source_urls=_cited_urls(parsed.source_urls, evidence),
        confidence=_confidence(parsed.confidence),
        reason=(parsed.reason or "").strip()[:200],
    )


async def judge(claim: Claim, query: str, evidence: list[Evidence]) -> Verdict:
    """Judge one claim against its evidence; no evidence means unverifiable, never a guess."""
    if not evidence:
        logger.info("judge claim=%s query=%r no evidence -> unverifiable", claim.id, query)
        return Verdict(verdict=VerdictKind.UNVERIFIABLE, reason="No search evidence", confidence=0.0)

    messages = _messages(claim, evidence)
    result = await bifrost_client.chat(messages, model=settings.PRIMARY_MODEL)
    try:
        parsed = _parse(result.text)
    except ParseError as first_error:
        logger.warning("claim %s judge JSON unusable, one repair retry: %s", claim.id, first_error)
        repaired = [
            *messages,
            {"role": "assistant", "content": result.text},
            {"role": "user", "content": JUDGE_REPAIR_PROMPT},
        ]
        second = await bifrost_client.chat(repaired, model=settings.PRIMARY_MODEL)
        try:
            parsed = _parse(second.text)
        except ParseError as second_error:
            raise ParseError(
                f"judge returned unusable JSON twice for {claim.id}: {second_error}"
            ) from second_error

    verdict = _normalise(parsed, claim, evidence)
    logger.info(
        "judge claim=%s verdict=%s confidence=%.2f sources=%d provider=%s fallback=%s",
        claim.id,
        verdict.verdict,
        verdict.confidence,
        len(verdict.source_urls),
        result.provider,
        result.fallback_triggered,
    )
    return verdict
