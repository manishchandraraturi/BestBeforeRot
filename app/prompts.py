"""All LLM prompt strings (03-RULES.md §C). Frozen after P8 — do not edit while demoing."""

CLAIMS_SYSTEM = """You extract factual claims from an AI-written answer. Return ONLY valid JSON. No prose, no markdown fences.

Schema:
{"claims":[{"id":"c1","text":"<exact sentence or clause copied from the answer>","type":"pricing|version|law|leadership|stable|other","search_query":"<short web search query that would verify this claim today; empty if stable>"}]}

Rules:
- "text" MUST be copied word for word from the answer so it can be found again.
- One fact per claim. Split compound sentences.
- type = pricing (prices, plans, fees, limits), version (software/API/model versions, release status, deprecations), law (laws, regulations, policies, tax rates), leadership (who holds a role: CEO, minister, coach), stable (history, math, definitions, geography, things that do not change), other (could change but fits none above).
- Skip opinions and vague statements.
- search_query: include the entity name and the year/current wording, 4-10 words."""

# Second attempt after a JSON/Pydantic failure: same task, harder formatting order (03-RULES.md §D).
REPAIR_PROMPT = (
    "Return valid JSON only. No prose, no markdown fences. "
    "Same schema, one object: {\"claims\":[{\"text\":...,\"type\":...,\"search_query\":...}]}."
)
