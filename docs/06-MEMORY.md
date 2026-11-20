# 06 · MEMORY — FactTTL (living file)

**Purpose:** the single source of truth so the AI never forgets or invents things.
**Agent rule:** read this file at the start of every phase. After a phase passes its test gate, update it. If something is not here or in the other docs, ask. Never guess.

---

## 1. Frozen facts

- **Project:** FactTTL — "Every fact has an expiry date."
- **Hackathon:** Global AI Hackathon (Geek Room / HackCulture). Problem Statement **06 · Tavily · Stale-Answer Detector**.
- **Must use:** Tavily (live verification) + Bifrost by Maxim AI (all LLM calls, fallback, cost).
- **Core requirements:** claim identification · freshness detection · live verification · freshness scoring.
- **Claim types:** pricing, version, law, leadership, stable, other.
- **TTL days:** pricing 1 · version 7 · leadership 30 · law 30 · other 7 · stable never.
- **Stack:** Python 3.11, FastAPI, httpx, Pydantic v2, SQLite, vanilla HTML/CSS/JS.
- **Ports:** Bifrost `8080` · App `8000`.
- **Free only.** No paid services.
- **Deadline:** page shows 21 Nov 2026 11:59 PM. Target submit by 20 Nov night.
- **Submit as:** primary theme = Problem Statement 06 (Tavily).

## 2. Frozen contracts
- API request/response: see `02-ARCHITECTURE.md` §5.
- Score rules: see `01-PRD.md` §7.
- Prompts: see `03-RULES.md` §C.
- Any change → add a line in the Decision log first.

## 3. Phase status

| Phase | Name | Status | Date | Notes |
|---|---|---|---|---|
| P0 | Setup & keys | DONE (tests passed) | 2026-11-20 | Groq + Gemini keys in the Bifrost UI; `.env` present locally (gitignored); proven by the P2 live gate |
| P1 | Skeleton | DONE (tests passed) | 2026-11-19 | 13 tests pass; `/api/health` + `/` verified |
| P2 | Bifrost client + fallback | DONE (tests passed) | 2026-11-20 | 6 unit tests; 2b = groq / `fallback_triggered=False`, 2c = gemini / `fallback_triggered=True`, both HTTP 200 |
| P3 | Tavily client | TODO | | |
| P4 | Claim extraction | TODO | | |
| P5 | Verify pipeline | TODO | | |
| P6 | Cache + endpoints | TODO | | |
| P7a | UI shell | TODO | | |
| P7b | UI console | TODO | | |
| P7c | UI results polish | TODO | | |
| P8 | Benchmark | TODO | | |
| P9 | README / deck / video / submit | TODO | | |

Status values: `TODO` · `DOING` · `DONE (tests passed)` · `BLOCKED`.

## 4. Real API shapes (fill in P0 / P2 / P3 — paste actual output)

**Bifrost raw response (first call, v2.6.0, no providers configured — real, 2026-11-20):**
```json
{
  "is_bifrost_error": false,
  "error": {
    "error": "failed to get config for provider groq: not found",
    "message": "failed to get config for provider groq: not found"
  },
  "extra_fields": {
    "routing_info": {},
    "provider": "groq",
    "original_model_requested": "llama-3.3-70b-versatile",
    "resolved_model_used": "llama-3.3-70b-versatile",
    "request_type": "chat_completion",
    "fallback_attempts": [{"provider": "gemini", "model": "gemini-2.0-flash", "skipped": true}]
  }
}
```
Headers on the same response: `x-bifrost-request-id`, `x-bifrost-trace-id`, `x-bifrost-provider: groq`,
`x-bifrost-original-model`, `x-bifrost-resolved-model`, `x-bifrost-request-type`.

- Provider that answered: `extra_fields.routing_info.provider` (documented); deprecated copy at `extra_fields.provider`; headers `x-bifrost-routing-info-provider` / `x-bifrost-provider`.
- Fallback indicator: `extra_fields.routing_info.is_fallback` (true) and header `x-bifrost-routing-info-is-fallback: true`, plus `x-bifrost-fallback-index`. Our client reads body first, then headers.
- Fallback request field: `"fallbacks": ["provider/model"]` in the request body — confirmed accepted by the gateway.
- Success envelope confirmed on the real primary answer (`python -m scripts.try_bifrost "Say hello"`, HTTP 200):
```json
{
  "id": "chatcmpl-efcafeb2-4b3d-4437-bc9a-95f1a308654b",
  "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "Hello! \ud83d\udc4b How can I assist you today?", "reasoning": "The user says \"Say hello\"..."}}],
  "model": "openai/gpt-oss-120b",
  "usage": {"prompt_tokens": 73, "completion_tokens": 40, "total_tokens": 113,
            "completion_tokens_details": {"reasoning_tokens": 20}},
  "extra_fields": {
    "request_type": "chat_completion",
    "routing_info": {"provider": "groq", "model": "openai/gpt-oss-120b", "key": "Groq Free",
                     "requested_provider": "groq", "requested_model": "openai/gpt-oss-120b"},
    "provider": "groq", "original_model_requested": "openai/gpt-oss-120b",
    "resolved_model_used": "openai/gpt-oss-120b", "latency": 550, "upstream_latency": 550
  }
}
```
So `choices[0].message.content` + `usage.prompt_tokens/completion_tokens` are exactly as assumed; no `routing_info.is_fallback` key is present on the primary path (our client defaults it to false).

- Fallback envelope confirmed on the forced-outage run (`--force-fallback`, HTTP 200):
```json
{
  "model": "gemini-3.5-flash-lite",
  "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "Hello! How can I help you today?"}}],
  "usage": {"prompt_tokens": 3, "completion_tokens": 9, "total_tokens": 12},
  "extra_fields": {
    "routing_info": {"provider": "gemini", "model": "gemini-3.5-flash-lite", "key": "Gemini Free",
                     "is_fallback": true, "primary_provider": "groq", "primary_model": "invalid-model-name",
                     "requested_provider": "groq", "requested_model": "invalid-model-name"},
    "provider": "gemini", "original_model_requested": "invalid-model-name",
    "resolved_model_used": "gemini-3.5-flash-lite", "latency": 7029
  }
}
```
Headers on that answer: `x-bifrost-routing-info-provider: gemini`, `x-bifrost-routing-info-is-fallback: true`,
`x-bifrost-routing-info-primary-provider: groq`, `x-bifrost-fallback-index: 1`, `x-bifrost-upstream-latency-ms: 7288.518`.
`is_fallback: true` really is in the body on the fallback path, so the body-first read in `_routing()` is correct.

**Two refusals seen on the way to a working call (2026-11-20), both useful for error handling:**
```json
{"type": "virtual_key_required", "is_bifrost_error": false, "status_code": 401,
 "error": {"message": "virtual key is required. Provide a virtual key via the x-bf-vk header."},
 "extra_fields": {"routing_info": {}, "provider": "groq", "request_type": "chat_completion"}}
```
```json
{"is_bifrost_error": false, "status_code": 404,
 "error": {"type": "invalid_request_error", "code": "model_not_found",
           "message": "The model `llama-3.3-70b-versatile` does not exist or you do not have access to it."},
 "extra_fields": {"routing_info": {"provider": "groq", "model": "llama-3.3-70b-versatile", "key": "Groq Free", ...},
                  "fallback_attempts": [{"provider": "gemini", "model": "gemini-2.0-flash", "status_code": 404,
                                          "type": "NOT_FOUND", "message": "This model models/gemini-2.0-flash is no longer available..."}]}}
```
Note the 404 envelope: Bifrost *does* attempt the fallback when the primary model is missing, and the router still reports `routing_info.provider` for the attempt that answered with the error. Both refusals are HTTP >= 400, so `chat()` raises `UpstreamError` — correct behaviour.

**Tavily raw response (first call):**
```
(paste here)
```

## 5. Decision log

| # | Decision | Why | Phase |
|---|---|---|---|
| 1 | Use `httpx` for Bifrost and Tavily instead of SDKs | one client, full control, fewer version bugs | pre |
| 2 | LLM decides type/verdict; code decides TTL/score/expiry | deterministic, explainable | pre |
| 3 | Own SQLite TTL cache instead of Bifrost semantic cache | faster to build, shows per-fact TTL idea | pre |
| 4 | Vanilla JS frontend, no build step | fewer bugs in 2 days | pre |
| 5 | Add `pytest.ini` with `pythonpath = .` | `pytest tests/test_ttl.py -q` cannot import `app` otherwise | P1 |
| 6 | `Claim.expires_at` typed as `datetime \| None`, serialized ISO-8601 | keeps expiry typed, matches contract string shape | P1 |
| 7 | Turn off Bifrost `client.enforce_auth_on_inference` instead of sending `x-bf-vk` | keeps the frozen P2 contract (no auth header, no new env var, no secret in `.env`) | P2 |
| 8 | Use live model IDs `groq/openai/gpt-oss-120b`, `gemini/gemini-3.5-flash-lite`, `groq/openai/gpt-oss-20b` | the originally planned IDs are retired on both providers and 404 | P2 |
| 9 | `try_bifrost` prints the raw body on every run and forces UTF-8 stdout | the fallback raw envelope is the evidence; cp1252 console crashed on an emoji | P2 |

## 6. Working commands (add as they are proven)

```bash
npx -y @maximhq/bifrost
uvicorn app.main:app --reload --port 8000
pytest -q
# P1 gate (verified 2026-11-19)
pytest tests/test_ttl.py -q                 # 13 passed
uvicorn app.main:app --port 8000 &
curl localhost:8000/api/health              # {"ok":true,"bifrost":...,"tavily_key_set":...}
curl -s localhost:8000/ | head -n 5         # serves web/index.html
# P2 gate (verified 2026-11-20, all three exit 0)
pip install respx                            # test dep, was missing locally
pytest tests/test_bifrost.py -q              # 6 passed
python -m scripts.try_bifrost "Say hello"                 # HTTP 200 provider=groq fallback_triggered=False
python -m scripts.try_bifrost "Say hello" --force-fallback  # HTTP 200 provider=gemini fallback_triggered=True
# which model IDs the gateway really serves (check before trusting .env)
curl -s localhost:8080/v1/models | python -c "import sys,json;[print(m['id']) for m in json.load(sys.stdin)['data']]"
```

## 7. Environment (names only, never values)

`BIFROST_URL, PRIMARY_MODEL, FALLBACK_MODEL, WEAK_MODEL, TAVILY_API_KEY, MAX_CLAIMS, MAX_PARALLEL, REQUEST_TIMEOUT_S, CACHE_DB`

Actual model names in use: `PRIMARY=groq/openai/gpt-oss-120b FALLBACK=gemini/gemini-3.5-flash-lite WEAK=groq/openai/gpt-oss-20b`
Provider keys live in the Bifrost UI (`http://localhost:8080`), never in `.env`.
Bifrost inference auth is **off** (`client.enforce_auth_on_inference = false`), so no `x-bf-vk` header is sent.

## 8. Known issues / gotchas

- This checkout has no `.env`, so `tavily_key_set` is `false` until P0 keys are added locally.
- Bifrost not running during the P1 run → `bifrost: false` (expected; endpoint never raises). Branch proven with a stub listener on :8080 → `bifrost: true`.
- `respx` is not installed globally; needed only from P3/P5 — `pip install -r requirements.txt`.
- Local interpreter is Python 3.14 (docs say 3.11+); everything used so far is compatible.
- Bifrost rejects a model with no `provider/` prefix outright (`400 could not auto resolve a provider`), so the simulated outage must send a prefixed-but-nonexistent model: `invalid_model()` returns `<primary-provider>/invalid-model-name`.
- Bifrost dashboard/API calls return 403 until a `setup_token` is configured (`config.json` or `BIFROST_SETUP_TOKEN`). Add provider keys in the UI at `http://localhost:8080`.
- Bifrost v2.6.0 with zero providers: `/v1/models` → `{"data":[]}` and every `/v1/chat/completions` call is `400 failed to get config for provider <name>: not found`.
- `client.enforce_auth_on_inference: true` makes every inference call (and `/v1/models`) `401 virtual_key_required`. The dashboard also locks `/api/providers` and `/api/config` (403 with no setup token, then 401 `Unauthorized` once dashboard auth exists). Turning enforcement off in the UI applies within ~2 minutes, no restart needed.
- Free-tier model IDs rot fast: `groq/llama-3.3-70b-versatile`, `gemini/gemini-2.0-flash`, `gemini/gemini-2.5-flash-lite` are all retired (404 `model_not_found` / `no longer available`). Always read `/v1/models` before trusting `.env`.
- Gemini free tier returns `503 UNAVAILABLE "This model is currently experiencing high demand"` on busy models (`gemini-3.8-flash`, `gemini-3.1-flash-lite`); `gemini-3.5-flash-lite` answered. A fallback hop therefore costs real time — measured 7 029 ms — which eats most of the 25 s `REQUEST_TIMEOUT_S` budget.
- The fallback response's `usage` counts only the provider that answered (3 in / 9 out on the gemini hop). The failed groq attempt is not counted, so P8 cost numbers must not read `usage` as the cost of the whole routed request.
- `try_bifrost` prints the raw body before calling `chat()`, so every run makes two gateway calls; on the slow fallback path the first call can hit the 25 s read timeout (`httpx.ReadTimeout` traceback). Just rerun — it is upstream load, not a code bug.

## 9. Benchmark snapshot (fill in P8)

| Metric | Value |
|---|---|
| Claims tested | |
| Stale recall | |
| Stale precision | |
| False-alarm rate | |
| Avg latency (cold) | |
| Tavily credits used / baseline | |

## 10. Do-not-touch after freeze
- Prompts (after P8)
- `models.py` field names
- TTL table
- Benchmark labels (after P8)
