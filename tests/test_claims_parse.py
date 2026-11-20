"""Unit tests for app/services/claims.py with the Bifrost call faked (no network)."""

import json

import pytest

from app.config import settings
from app.models import ClaimStatus, ClaimType, Volatility
from app.services import bifrost_client, claims

ANSWER = (
    "The Notion Plus plan costs $10 per month. "
    "The current CEO of OpenAI is Sam Altman. "
    "The Eiffel Tower is in Paris."
)

GOOD = {
    "claims": [
        {
            "id": "c1",
            "text": "The Notion Plus plan costs $10 per month.",
            "type": "pricing",
            "search_query": "Notion Plus plan price per month 2026",
        },
        {
            "id": "c2",
            "text": "The current CEO of OpenAI is Sam Altman.",
            "type": "leadership",
            "search_query": "current CEO of OpenAI 2026",
        },
        {
            "id": "c3",
            "text": "The Eiffel Tower is in Paris.",
            "type": "stable",
            "search_query": "",
        },
    ]
}


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    """Fresh module state and the default claim cap for every test."""
    monkeypatch.setattr(settings, "MAX_CLAIMS", 8)
    monkeypatch.setattr(claims, "last_queries", {})
    monkeypatch.setattr(claims, "last_raw", None)
    monkeypatch.setattr(claims, "last_repaired", False)


def _install(monkeypatch, *replies: str) -> list[list[dict]]:
    """Fake bifrost_client.chat, returning `replies` in order and recording messages."""
    calls: list[list[dict]] = []
    queue = list(replies)

    async def fake_chat(messages, model=None, force_fallback=False):
        calls.append(messages)
        text = queue.pop(0) if queue else ""
        return bifrost_client.ChatResult(
            text=text, tokens_in=11, tokens_out=22, provider="groq"
        )

    monkeypatch.setattr(claims.bifrost_client, "chat", fake_chat)
    return calls


@pytest.mark.asyncio
async def test_fenced_json_is_parsed_and_ttls_assigned(monkeypatch) -> None:
    """A ```json fenced reply yields typed claims with TTL and volatility from ttl.py."""
    body = f"```json\n{json.dumps(GOOD)}\n```"
    calls = _install(monkeypatch, body)

    result = await claims.extract(ANSWER)

    assert len(calls) == 1
    assert calls[0][0] == {"role": "system", "content": claims.CLAIMS_SYSTEM}
    # The prompt asks for the current wording, so the model is told today's date.
    assert calls[0][1]["content"].startswith("TODAY: 20")
    assert ANSWER in calls[0][1]["content"]
    assert [claim.id for claim in result] == ["c1", "c2", "c3"]
    assert [claim.type for claim in result] == [
        ClaimType.PRICING,
        ClaimType.LEADERSHIP,
        ClaimType.STABLE,
    ]
    assert [(claim.volatility, claim.ttl_days) for claim in result] == [
        (Volatility.FAST, 1),
        (Volatility.SLOW, 30),
        (Volatility.NEVER, None),
    ]
    assert all(claim.status == ClaimStatus.CHECKED for claim in result)
    assert claims.last_queries["c1"] == "Notion Plus plan price per month 2026"
    assert claims.last_repaired is False
    assert claims.last_raw == body


@pytest.mark.asyncio
async def test_unfenced_json_with_prose_is_still_parsed(monkeypatch) -> None:
    """Prose around the object is trimmed away instead of costing a repair retry."""
    _install(monkeypatch, f"Here you go:\n{json.dumps(GOOD)}\nDone.")

    result = await claims.extract(ANSWER)

    assert len(result) == 3


@pytest.mark.asyncio
async def test_bad_json_is_repaired_once(monkeypatch) -> None:
    """A truncated reply triggers exactly one repair call whose prompt says valid JSON only."""
    calls = _install(monkeypatch, '{"claims": [{"text": "The Notion', json.dumps(GOOD))

    result = await claims.extract(ANSWER)

    assert len(calls) == 2
    repair_messages = calls[1]
    assert repair_messages[-1]["role"] == "user"
    assert "Return valid JSON only" in repair_messages[-1]["content"]
    assert repair_messages[-2]["role"] == "assistant"
    assert repair_messages[-2]["content"] == '{"claims": [{"text": "The Notion'
    assert claims.last_repaired is True
    assert len(result) == 3


@pytest.mark.asyncio
async def test_bad_json_twice_raises_parse_error(monkeypatch) -> None:
    """Two unusable replies raise ParseError after exactly two model calls."""
    calls = _install(monkeypatch, "not json at all", "still not json")

    with pytest.raises(claims.ParseError):
        await claims.extract(ANSWER)

    assert len(calls) == 2


@pytest.mark.asyncio
async def test_invalid_type_uses_the_repair_retry(monkeypatch) -> None:
    """A type outside the frozen enum is a parse failure, not a silently accepted claim."""
    bad = json.loads(json.dumps(GOOD))
    bad["claims"][0]["type"] = "price"
    calls = _install(monkeypatch, json.dumps(bad), json.dumps(GOOD))

    result = await claims.extract(ANSWER)

    assert len(calls) == 2
    assert result[0].type is ClaimType.PRICING


@pytest.mark.asyncio
async def test_claim_text_missing_from_answer_is_dropped(monkeypatch) -> None:
    """A hallucinated claim is dropped; the verbatim ones survive with contiguous ids."""
    payload = json.loads(json.dumps(GOOD))
    payload["claims"].insert(
        1,
        {
            "id": "c9",
            "text": "The Notion Business plan costs $25 per month.",
            "type": "pricing",
            "search_query": "Notion Business plan price 2026",
        },
    )
    _install(monkeypatch, json.dumps(payload))

    result = await claims.extract(ANSWER)

    assert [claim.text for claim in result] == [
        "The Notion Plus plan costs $10 per month.",
        "The current CEO of OpenAI is Sam Altman.",
        "The Eiffel Tower is in Paris.",
    ]
    assert [claim.id for claim in result] == ["c1", "c2", "c3"]


@pytest.mark.asyncio
async def test_text_matches_ignoring_case_and_punctuation(monkeypatch) -> None:
    """Case, quotes and punctuation differences still count as copied from the answer."""
    answered = "The notion plus plan costs 10 per month"
    _install(
        monkeypatch,
        json.dumps(
            {
                "claims": [
                    {
                        "text": answered,
                        "type": "pricing",
                        "search_query": "Notion Plus price 2026",
                    }
                ]
            }
        ),
    )

    result = await claims.extract(ANSWER)

    assert len(result) == 1
    assert result[0].text == answered


@pytest.mark.asyncio
async def test_cap_drops_least_volatile_first_and_keeps_answer_order(monkeypatch) -> None:
    """With MAX_CLAIMS=2 the stable claim is dropped and the rest keep their order."""
    monkeypatch.setattr(settings, "MAX_CLAIMS", 2)
    _install(monkeypatch, json.dumps(GOOD))

    result = await claims.extract(ANSWER)

    assert [claim.type for claim in result] == [ClaimType.PRICING, ClaimType.LEADERSHIP]
    assert [claim.id for claim in result] == ["c1", "c2"]


@pytest.mark.asyncio
async def test_empty_answer_makes_no_model_call(monkeypatch) -> None:
    """Blank input returns no claims and spends no tokens."""
    calls = _install(monkeypatch)

    assert await claims.extract("   \n ") == []
    assert calls == []


@pytest.mark.asyncio
async def test_empty_claims_list_is_valid(monkeypatch) -> None:
    """An answer with nothing verifiable parses to an empty list, not an error."""
    _install(monkeypatch, '{"claims": []}')

    assert await claims.extract(ANSWER) == []
