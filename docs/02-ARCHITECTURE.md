# 02 · ARCHITECTURE — FactTTL

Goal: **fewest moving parts = fewest bugs.** One Python service, one static page, one SQLite file, one gateway.

## 1. Big picture

```
 Browser (static HTML/CSS/JS)
        │  POST /api/verify
        ▼
 FastAPI app  (port 8000)
   │
   ├── 1. claims.py ───────┐
   ├── 2. cache.py (SQLite)│   all LLM calls go through ▼
   ├── 3. tavily_client.py │      ┌────────────────────────┐
   ├── 4. judge.py ────────┼────► │ Bifrost gateway :8080  │──► Groq (primary)
   ├── 5. scoring.py       │      │ routing · fallback ·   │──► Gemini (fallback)
   └── 6. rewrite.py ──────┘      │ usage/cost             │
        │                         └────────────────────────┘
        └──────────────────────────► Tavily API (live web search)
```

**Rule:** the browser never talks to Bifrost or Tavily. Only FastAPI does. API keys live only in `.env`.

## 2. Tech stack (all free)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | fastest to build |
| API | FastAPI + uvicorn | typed, auto docs at `/docs` |
| Models/validation | Pydantic v2 | contracts = fewer bugs |
| HTTP | `httpx` (async) | one client for Bifrost + Tavily, full control |
| Gateway | **Bifrost** via `npx -y @maximhq/bifrost` (or Docker) | required; UI at `http://localhost:8080` |
| LLM providers | Groq (primary) + Gemini (fallback), free tiers | two providers = visible fallback |
| Search | **Tavily** REST `https://api.tavily.com/search` | required; free plan |
| Storage | SQLite (stdlib `sqlite3`) | no server |
| Frontend | Plain HTML + CSS + vanilla JS served by FastAPI `StaticFiles` | no build step, no npm bugs |
| Fonts | Google Fonts (Space Grotesk, Instrument Serif, JetBrains Mono) | see `04-DESIGN.md` |
| Tests | `pytest` + `pytest-asyncio`, `respx` for HTTP mocks | |
| Config | `python-dotenv` + `pydantic-settings` | |

No React, no Docker requirement, no database server, no deployment.

## 3. Folder structure

```
fact-ttl/
├── README.md
├── .env.example
├── requirements.txt
├── docs/                      # the 6 md files live here
├── app/
│   ├── main.py                # FastAPI app, routes, static mount
│   ├── config.py              # settings from .env
│   ├── models.py              # ALL pydantic models (contracts)
│   ├── ttl.py                 # claim type → TTL days (single source of truth)
│   ├── pipeline.py            # orchestrates the flow
│   ├── services/
│   │   ├── bifrost_client.py  # chat() → text, usage, provider
│   │   ├── tavily_client.py   # search() → evidence list
│   │   ├── claims.py          # extract claims (LLM)
│   │   ├── judge.py           # verdict per claim (LLM + evidence)
│   │   ├── rewrite.py         # build corrected answer (code first, LLM never required)
│   │   ├── scoring.py         # deterministic score
│   │   └── cache.py           # SQLite TTL cache
│   └── prompts.py             # all prompt strings
├── web/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── bench/
│   ├── claims.jsonl           # 40+ labeled claims
│   ├── run_bench.py
│   └── results.md             # generated table
└── tests/
    ├── test_ttl.py  test_scoring.py  test_claims_parse.py
    ├── test_cache.py  test_pipeline_mocked.py
```

## 4. Request flow (what `pipeline.verify()` does)

```
verify(answer_text, options)
 1. extract_claims(answer)           → [Claim]            (Bifrost LLM call #1)
 2. for each claim: ttl = ttl.for_type(claim.type)       (pure code)
 3. split: stable → skip ; volatile → continue
 4. for each volatile claim (parallel, max 4 at once, max 8 total):
      a. cache.get(claim_key)        → hit & not expired → use, mark from_cache
      b. else tavily.search(query)   → [Evidence]
      c. judge(claim, evidence)      → Verdict               (Bifrost LLM call #N)
      d. cache.put(claim_key, verdict, expires_at = now + ttl)
 5. scoring.score(claims)            → per-claim + overall
 6. rewrite.apply(answer, verdicts)  → corrected_answer      (string replace in code)
 7. return VerifyResponse (with stats: credits used/saved, providers used, latency)
```

Failure of one claim **never** fails the whole request (see error rules in `03-RULES.md`).

## 5. API contract (FROZEN — change only via `06-MEMORY.md` decision log)

### `POST /api/verify`
Request:
```json
{
  "answer": "string (required, 20–4000 chars)",
  "question": "string | null",
  "force_fallback": false,
  "use_cache": true
}
```
Response:
```json
{
  "request_id": "uuid",
  "original_answer": "string",
  "corrected_answer": "string",
  "overall_score": 62,
  "overall_band": "mixed",
  "claims": [
    {
      "id": "c1",
      "text": "Product X costs $29 per month.",
      "type": "pricing",
      "volatility": "fast",
      "ttl_days": 1,
      "status": "checked",
      "verdict": "stale",
      "corrected_text": "Product X now costs $49 per month.",
      "reason": "Official pricing page lists $49.",
      "confidence": 0.9,
      "score": 15,
      "sources": [{"title": "Pricing", "url": "https://...", "published": "2026-10-02"}],
      "from_cache": false,
      "expires_at": "2026-11-20T10:00:00Z"
    }
  ],
  "stats": {
    "claims_total": 7,
    "claims_searched": 3,
    "claims_skipped_stable": 4,
    "cache_hits": 0,
    "tavily_credits_used": 3,
    "tavily_credits_saved": 4,
    "llm_calls": 4,
    "tokens_in": 1200,
    "tokens_out": 400,
    "providers_used": ["groq"],
    "fallback_triggered": false,
    "latency_ms": 8200
  }
}
```
Enums: `type`: `pricing | version | law | leadership | stable | other` · `volatility`: `fast | slow | never` · `status`: `checked | skipped_stable | error` · `verdict`: `fresh | stale | unverifiable | null` · `overall_band`: `fresh | mixed | risky`.

### Other endpoints
| Route | Purpose |
|---|---|
| `GET /api/health` | `{ok, bifrost: bool, tavily_key_set: bool}` — pings Bifrost |
| `GET /api/cache` | list cached facts + seconds left |
| `DELETE /api/cache` | clear (for demo reset) |
| `POST /api/ask` | `{question}` → weak model answer, then same as verify |
| `GET /api/samples` | 3 sample stale answers |
| `GET /` | static site |

## 6. How Bifrost is used

- Base URL `http://localhost:8080`. Endpoint: `POST /v1/chat/completions` (OpenAI-compatible).
- Model string format: `provider/model`, e.g. `groq/<model>`, `gemini/<model>`. **Put exact names in `.env`, not in code** (free-tier model names change).
- Request body adds a fallback list: `"fallbacks": ["gemini/<model>"]`. Confirm exact field in docs.getbifrost.ai during Phase 2.
- Providers + keys are added once in the Bifrost UI at `http://localhost:8080`.
- **Simulate outage** = send a deliberately invalid primary model name; Bifrost fails over; UI shows the fallback provider.
- Usage (tokens) read from the OpenAI-style `usage` field. Provider that answered: read from the response (`extra_fields.provider` if present). **In Phase 2, print the raw response once and adapt code to the real shape. Do not guess.**

## 7. How Tavily is used

- `POST https://api.tavily.com/search`, header `Authorization: Bearer <TAVILY_API_KEY>`.
- Body: `query`, `search_depth: "basic"` (1 credit; `advanced` = 2), `max_results: 5`, `include_answer: false`, optional `topic`, `time_range`.
- Query comes from the claim (`search_query` field made by the claim step, e.g. `"Notion Plus plan price per month 2026"`).
- Evidence kept per result: `title, url, content (trimmed ~600 chars), published_date if present, score`.
- Search results cached 6 hours by query (separate from fact TTL) to protect credits.

## 8. Cache design (SQLite, `ttl_cache.db`)

```sql
CREATE TABLE IF NOT EXISTS facts (
  key TEXT PRIMARY KEY,         -- sha1(normalized claim text)
  claim_json TEXT NOT NULL,     -- verdict payload
  checked_at TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS searches (
  key TEXT PRIMARY KEY,         -- sha1(query)
  results_json TEXT NOT NULL,
  expires_at TEXT NOT NULL
);
```
- Hit only if `expires_at > now`. Expired rows are ignored and overwritten.
- TTL days live in **one file**: `ttl.py` → `pricing:1, version:7, leadership:30, law:30, other:7, stable:None`.

## 9. Connections that keep bugs low

1. **One contract file** (`models.py`). Every service takes and returns those models. No loose dicts across modules.
2. **One place per concern:** TTLs in `ttl.py`, prompts in `prompts.py`, settings in `config.py`, scores in `scoring.py`.
3. **LLM decides meaning, code decides numbers.** LLM returns type + verdict. Code assigns TTL, score, expiry.
4. **LLM output is always parsed through Pydantic.** Bad shape → repair retry → fallback value.
5. **Services never import each other.** Only `pipeline.py` wires them.
6. **Frontend reads only `/api/*` JSON.** No logic duplication in JS.

## 10. Environment variables (`.env.example`)

```
BIFROST_URL=http://localhost:8080
PRIMARY_MODEL=groq/<model-name>
FALLBACK_MODEL=gemini/<model-name>
WEAK_MODEL=groq/<small-model-name>
TAVILY_API_KEY=tvly-xxxx
MAX_CLAIMS=8
MAX_PARALLEL=4
REQUEST_TIMEOUT_S=25
CACHE_DB=ttl_cache.db
```
Provider API keys (Groq, Gemini) are entered in the Bifrost UI, not in this app.

## 11. Run commands

```bash
# terminal 1
npx -y @maximhq/bifrost            # then open http://localhost:8080 and add providers
# terminal 2
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
# open http://localhost:8000
```

`requirements.txt`: `fastapi`, `uvicorn[standard]`, `httpx`, `pydantic>=2`, `pydantic-settings`, `python-dotenv`, `pytest`, `pytest-asyncio`, `respx`.
