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
| P3 | Tavily client | DONE (tests passed) | 2026-11-20 | 7 mocked tests; 2a live (5 results, 2 493 ms), 2b cache hit (1 ms, no API call) |
| P4 | Claim extraction | DONE (tests passed) | 2026-11-20 | 10 mocked tests; live run extracted 3/3 claims with pricing→1d, leadership→30d, stable→None |
| P5 | Verify pipeline | DONE (tests passed) | 2026-11-20 | 27 tests; live: stale $5 → stale + 4 real sources → corrected $10, stable skipped, overall 58 mixed; bad key → unverifiable, exit 0 |
| P6 | Cache + rewrite + stats + endpoints | DONE (tests passed) | 2026-11-21 | 11 cache/rewrite tests, 74 total; cold 7 386 ms `cache_hits=0` → warm 718 ms `cache_hits=1`, `tavily_credits_used=0` → fallback `fallback_triggered=true` on gemini; all HTTP 200 |
| P7a | UI shell | DONE (tests passed) | 2026-11-21 | `web/index.html` rewritten, `web/styles.css` new, `web/app.js` created empty; fonts 200 from Google, 0 console errors, no horizontal scroll at 1440 or 375 |
| P7b | UI console | DONE (tests passed) | 2026-11-21 | Marquee gap fixed (8 spans, 0→-50%); console cards + `fetch /api/verify`; gate answer → 49 risky, Notion stale/red with `$12`, Sam Altman fresh/green, Eiffel Tower skipped; 0 console errors |
| P7c | UI results polish | DONE (tests passed) | 2026-11-21 | Word-by-word strike → fix fade, TTL rings, Original/Corrected/Diff tabs, Copy corrected, scroll reveals, Results placeholder; 3 demo runs cold 4.7 s / warm 1.6 s / fallback 1.7 s, 0 console errors |
| P8 | Benchmark | DONE (tests passed) | 2026-11-22 | 40 hand-labelled claims (15 stale · 15 fresh · 10 unverifiable), cache off, every claim a live Tavily search; stale recall 14/15, stale precision 14/16, false alarms 0/15, unverifiable 7/10, 38 credits vs 40 baseline, avg 4.4 s, 0 errors; `bench/results.md` written and the UI Numbers section updated |
| P9 | README / deck / video / submit | DONE | 2026-11-22 | `README.md` rewritten (hero + badges, problem, TTL solution, Tavily + Bifrost roles, Mermaid flow, the real 40-claim benchmark table, setup, AI usage, honest limits) and `docs/PITCH_DECK.md` created (7 slides with speaker notes and a deck checklist); the demo video and the submission form are the human's remaining steps, not agent output |

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

**Tavily raw response (real call, 2026-11-20, `POST /search`, `search_depth: basic`, HTTP 200, 2 493 ms):**
```json
{
  "query": "Notion Plus plan price per month",
  "follow_up_questions": null,
  "answer": null,
  "images": [],
  "results": [
    {
      "url": "https://thedigitalprojectmanager.com/tools/notion-pricing",
      "title": "Notion Pricing Tiers & Costs",
      "content": "The Plus Plan, at $10 per seat/month, is suited for small to medium-sized teams needing more advanced features. It offers unlimited blocks, file uploads, and a 30-day page history. ... (multi-paragraph text; our client keeps the first 600 chars)",
      "score": 0.8440237,
      "raw_content": null,
      "id": "4bb286-00"
    },
    {"url": "https://www.notion.com/pricing", "title": "Notion Pricing Plans: Free, Plus, Business, & Enterprise.", "score": 0.806, "raw_content": null, ...},
    {"url": "https://www.activepieces.com/blog/notion-pricing-2026-plans-ai-and-what-each-costs", "title": "Notion Pricing 2026: Plans, AI and What Each Costs", "score": 0.800, ...},
    {"url": "https://www.youtube.com/watch?v=6uSN7Labj3Q", "title": "Notion Pricing Explained: Why It’s Worth the Money", "score": 0.510, ...},
    {"url": "https://www.notion.com/help/upgrade-or-downgrade-your-plan", "title": "Change your Notion plan | Notion Help – Notion Help Center", "score": 0.501, ...}
  ]
}
```
- Each result carries exactly `url, title, content, score, raw_content, id`. **There is no `published_date` key at all** on these five results: with `search_depth: "basic"` and no `topic`/`time_range`, Tavily simply omits it. So `Evidence.published_date` stays `None` and the judge prompt's `published` column will be empty for most claims until we ask for news/date-filtered results (a P5 decision — the frozen P3 body is unchanged).
- `answer` is `null` (we send `include_answer: false`), `images` is `[]`, `follow_up_questions` is `null`.
- `score` is a float already sorted descending (~0.50–0.84); it is relevance, not freshness — never use it as a date signal.
- Top-level `response_time` is also present (truncated out of the snippet above).

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
| 10 | Search cache key = `sha1(query.strip().lower())` in the shared `ttl_cache.db` (`searches` table) | case/spacing variants reuse one row; one DB file holds both caches (§8) | P3 |
| 11 | `try_tavily` reads a module-level `last_raw` for the raw payload | shows the real shape without spending a second Tavily credit | P3 |
| 12 | Timeout gets exactly one retry with 1 s backoff; 401/403/429 fail immediately | 03-RULES §D: one retry, never a retry storm | P3 |
| 13 | Extraction uses `WEAK_MODEL` (fallback to `PRIMARY_MODEL` if unset) | cheapest/fastest call: 3 claims in ~2.1 s, no need for the 120b model | P4 |
| 14 | The extraction user message is `TODAY: <date>\nANSWER:\n<answer>` (`CLAIMS_SYSTEM` itself stays byte-identical to 03-RULES §C) | without a date the model wrote `search_query: "…2024"` from its training year, which would return stale evidence in P5 | P4 |
| 15 | `search_query` lives in `claims.last_queries[id]`, not on `Claim` | `Claim` has no `search_query` field in the frozen contract (§5) and P4 may not edit `models.py`; P5 must consume the map or log a contract change | P4 |
| 16 | `judge.Verdict` is a Pydantic result model; the enum `models.Verdict` is imported there as `VerdictKind` | the P5 spec asks for `judge() -> Verdict` holding corrected text/sources, but `models.Verdict` is the 3-value enum and `models.py` is frozen | P5 |
| 17 | `score_claims` writes `claim.score` and returns the PRD §7 weighted mean; weights fast 1.5 / slow 1.0, stable and unjudged rows skipped | one place decides score numbers (02-ARCHITECTURE §9.3); P6 only formats them | P5 |
| 18 | An answer with no scored claims (all stable / empty) scores **100 fresh** | nothing can go stale, and 0/risky would punish a history-only answer | P5 |
| 19 | A crashed claim gets `status=error`, `verdict=unverifiable`, `reason="error"`, score 40 | matches 03-RULES §D and the P5 spec; the exception type/message goes to the log only | P5 |
| 20 | The `MAX_PARALLEL` semaphore wraps search **and** judge together | §4 says the claim step is capped at 4 at once; capping only the search still floods the LLM | P5 |
| 21 | Judge-cited urls are filtered against the evidence before becoming `Source` | 03-RULES §C.4/§C.5: the judge may only cite what Tavily returned, so code enforces it | P5 |
| 22 | The fact cache stores the whole judged `Claim` (`model_dump_json`) under `sha1(normalised text)` | a hit can restore verdict, correction, reason, confidence, sources and `expires_at` without a second Tavily or LLM call (§8) | P6 |
| 23 | A cache hit copies the archived verdict onto today's claim and sets `from_cache=True`; the claim keeps its own id, text and `ttl_days` | the response shape stays the same on cold and warm runs, so the UI needs no branch | P6 |
| 24 | Per-request stats come from two additive `ContextVar`s in `bifrost_client` (`usage_sink`, `simulated_outage`) | `pipeline.verify` needs the real `ChatResult`s (tokens/providers/fallback) and a way to force the fallback without changing the frozen `chat()` signature. **This edit is outside the P6 file list** and is additive only: unset means the old behaviour | P6 |
| 25 | `tavily_credits_used = claims_searched`, `credits_saved = cache_hits + claims_skipped_stable` | one basic search = one credit; the two ways of not searching are both savings (§5 stats strip) | P6 |
| 26 | `POST /api/ask` is included, with `AskRequest {question}` and `ASK_SYSTEM` local to `main.py` | 05-TASKS P6 do-list and 02-ARCHITECTURE §5 both list it, but `prompts.py` is frozen until P8, so the prompt cannot live there | P6 |
| 27 | Cache SQLite calls retry a locked DB 3× (0.05 s) with a 1.0 s busy timeout; any other `sqlite3.Error` only logs and the request runs uncached | 03-RULES §D: bounded retry, never a failure the user sees | P6 |
| 28 | Row expiry is compared as ISO-8601 UTC strings (`expires_at > now.isoformat()`), the same rule as the search cache | one timestamp format in one DB file; no timezone mixups on a Windows host | P6 |
| 29 | The UI brand is **BestBeforeRot** (nav, `<title>`, footer wordmark), not the `FactTTL` name used inside the docs | the repo, README and assets already say BestBeforeRot; the P7a prompt names the footer wordmark explicitly | P7a |
| 30 | All P7a motion is CSS-only (hero word reveal, doodle draw + float, marquee); `app.js` ships empty | the phase must not add JS; scroll-reveal, count-up and the tab logic are P7b/P7c | P7a |
| 31 | The nav keeps only `Try it · How it works · GitHub` and the Results section is not built yet | 04-DESIGN lists a Results link, but the section is P7c work — a dead anchor is worse than one missing link | P7a |
| 32 | The marquee is **8 identical spans** inside `.marquee-track` and still animates `0 → -50%` | 8 spans = two identical halves; the half is 2 386 px, so the strip covers any viewport up to that width and the loop has no blank right edge (measured `seamless: true` at 1 423 px) | P7b |
| 33 | The three sample chips write a local `SAMPLES` string into the textarea instead of calling `GET /api/samples` | the phase says the chips only need to be styled; a local fill costs no request and keeps them from being dead buttons | P7b |
| 34 | Score count-up + ring use `requestAnimationFrame`, but a `setTimeout` at `duration + 150` ms snaps both to their final value | rAF does not fire while the Freebuff window is minimised/covered — the gate showed `data-value="49"` with the number stuck at `0`; the timeout makes the result correct even with no frames | P7b |
| 35 | Claim cards are built with `createElement` + `textContent` (never `innerHTML`) | claim text, reasons and source URLs come from the LLM and the web; text nodes make markup injection impossible | P7b |
| 36 | A stale claim's strike is drawn **word by word** (one `span.strike-word` per word, `::after` scaleX 0→1, 45 ms stagger ≈ .5 s) instead of `text-decoration: line-through` | `text-decoration` cannot animate left-to-right, and one overlay line on the paragraph cuts through the gap between wrapped lines; per-word lines follow the text at any width | P7c |
| 37 | The TTL ring's progress = time left ÷ (`ttl_days` × 24 h) from `expires_at`, and its label is the TTL (`1d` / `7d` / `30d` / `∞`) | the phase asks for the TTL label; the arc is what shows time actually remaining. A `23h` style countdown label is still possible later from the same `expires_at` | P7c |
| 38 | The Diff tab is computed in the browser with a word-level LCS: removed words `<s>`, added words `<u>`, no backgrounds | 04-DESIGN §4 asks for underline-only highlighting; the API has no diff field, so the browser derives it from `original_answer` and `corrected_answer` | P7c |
| 39 | Scroll reveal keeps `IntersectionObserver` as the primary trigger **plus** an `revealInView()` pass on load, scroll and resize | IO only fires while frames render; the scroll pass keeps content visible if frames are throttled, without adding a library | P7c |
| 40 | `Copy corrected` uses `navigator.clipboard.writeText` with a hidden-textarea `execCommand` fallback; the label flips to `Copied!` for 2 s | works on `127.0.0.1` and on hosts where the async clipboard is denied; no dependency | P7c |
| 41 | Each benchmark claim is sent to `pipeline.verify()` **on its own**, `use_cache=False`, with `asyncio.sleep(1.2)` between claims | one claim per call makes the label↔verdict mapping exact (no answer-level splitting or claim-cap effects) and the sleep keeps the free Groq/Tavily tiers under their limits; 40 claims took 225 s | P8 |
| 42 | `run_bench.py` points `CACHE_DB` at `bench/.bench_cache.db` and deletes it before the run | `use_cache=False` only skips the fact cache; the **search** cache in the same DB would still answer and make `tavily_credits_used=0` a lie. A bench-local DB also keeps the demo cache intact | P8 |
| 43 | The benchmark records `stats.tavily_credits_used` per claim, not `llm_calls`; its baseline is 1 credit × 40 claims | the PRD quotes credits saved, and the baseline is what "search every sentence" would cost | P8 |
| 44 | Prompts were **not** changed after the benchmark; the one stale miss (row 7) and the two "unverifiable → stale" rows are reported as-is in `results.md` | 05-TASKS P8 says fix prompts only if a bug is clear; one judge disagreement is not a clear bug, and 03-RULES prompts are frozen after P8 | P8 |

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
# P3 gate (verified 2026-11-20, all three exit 0)
python -m scripts.try_tavily "Notion Plus plan price per month"   # 1st: source: live Tavily call, 5 results, 2 493 ms
python -m scripts.try_tavily "Notion Plus plan price per month"   # 2nd: source: cache (no API call), 1 ms
pytest tests/test_tavily_mocked.py -q                              # 7 passed
# P4 gate (verified 2026-11-20, both exit 0)
pytest tests/test_claims_parse.py -q                 # 10 passed
python -m scripts.try_claims '<answer text>'        # 3 claims, ~2.1 s, pricing/leadership/stable
# P5 gate (verified 2026-11-20, all exit 0)
pytest tests/test_scoring.py tests/test_pipeline_mocked.py -q   # 27 passed
python -m scripts.try_pipeline samples/pricing.txt           # 3 claims, 8 624 ms, stale w/ 4 urls, overall 58 mixed
# 2c bad key WITHOUT touching .env (env var beats .env, throwaway cache DB forces a live call)
TAVILY_API_KEY=bad-key CACHE_DB=ttl_cache_badkey.db python -m scripts.try_pipeline samples/pricing.txt  # both claims unverifiable, exit 0
rm -f ttl_cache_badkey.db
# P6 gate (verified 2026-11-21, all exit 0)
pytest tests/test_cache.py -q                                   # 11 passed
pytest -q                                                      # 74 passed (P1–P6)
python -m uvicorn app.main:app --port 8000                     # 127.0.0.1:8000
curl -X POST http://127.0.0.1:8000/api/verify -H "Content-Type: application/json" -d "{\"answer\":\"The Notion Plus plan costs $5 per month.\"}"
#   cold: HTTP 200, cache_hits=0, tavily_credits_used=1, llm_calls=2, latency_ms=7386, corrected "…$10 per month."
#   same curl again (warm): HTTP 200, cache_hits=1, tavily_credits_used=0, latency_ms=718, claims[0].from_cache=true
curl -X POST http://127.0.0.1:8000/api/verify -H "Content-Type: application/json" -d "{\"answer\":\"The Notion Plus plan costs $5 per month.\",\"force_fallback\":true,\"use_cache\":false}"
#   fallback: HTTP 200, fallback_triggered=true, providers_used=["gemini"], latency_ms=6221
curl http://127.0.0.1:8000/api/cache       # {"count":1,"facts":[{… "seconds_left":86399}]}
curl http://127.0.0.1:8000/api/samples     # 3 samples: pricing / version / leadership
curl -X DELETE http://127.0.0.1:8000/api/cache   # {"deleted":n}  (route exists; not exercised in the gate — do not clear the demo cache mid-run)
# P7a gate (verified 2026-11-21, all exit 0)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/          # 200
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/styles.css # 200
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/app.js     # 200
# then in the browser: 1440x900 and 375x812, console empty, fonts.gstatic 200 for all three families
# P7b gate (verified 2026-11-21, all HTTP 200, 0 console messages)
node --check web/app.js                     # JS OK
# browser at 127.0.0.1:8000, paste "The Notion Plus plan costs $5 per month. Sam Altman is the CEO of OpenAI.
#   The Eiffel Tower is in Paris." and click Verify:
#   loading -> state=loading, ticker + 4 skeletons + button spinner
#   result  -> score 49 (band risky, red ring 224.31/439.82), CLAIMS 3 · SEARCHED 0 · SKIPPED 1 · CACHE 2 · LATENCY 1.5s,
#              ROUTED VIA GROQ + FROM CACHE, claims: stale (struck, fix "…$12 per month.", 3 links),
#              fresh (green dot, 4 links), skipped_stable (grey dot)
# marquee: 8 spans, track 4 771 px, half 2 386 px >= 1 440; at translateX(-50%) content covers 0..1789 with no gap
# 375x812: scrollWidth 358, panels stacked 318/318, textarea 180, chips/toggles 44, verify 46, stats no overflow
# error paths (fetch stubbed in the page, no server change): short text, 503 body, network reject -> state=error + Try again
# P7c gate (verified 2026-11-21, 0 console messages all the way through)
curl -X DELETE http://127.0.0.1:8000/api/cache          # {"deleted":2}, then the 3-run demo script (01-PRD.md §11)
# run 1 cold:    4.7 s, CLAIMS 3 · SEARCHED 2 · SKIPPED 1 · CACHE 0, 49 risky, ROUTED VIA GROQ
# run 2 warm:    1.6 s, SEARCHED 0 · CACHE 2, FROM CACHE badge, same 3 verdicts and TTL rings 1d / 30d / infinity
# run 3 fallback: 1.7 s with Simulate outage ON -> FALLBACK -> GEMINI badge, still 200 + 3 claim cards
# strike: 8 .strike-word spans on the stale claim, ::after animationName=strike, end transform scaleX(1)
# fix: animationDelay 0.61 s, ends opacity 1 with the 2px --fresh bar
# TTL rings: 1d (stale ring, red), 30d (fresh, green), infinity (stable, grey); dashoffset ~0 because the clocks just started
# tabs: Corrected default; Original -> $5 text, Diff -> <s>$5</s> <u>$10</u>, Corrected -> $10; aria-selected follows
# copy: clipboard.writeText spy captured the exact corrected_answer; label 'Copied!' -> back to 'Copy corrected' after 2 s
# reveals: all 8 .reveal elements get .in by the bottom of the page (results section + placeholder footnote visible)
# 375x812: scrollWidth 358, tabs 44 px, copy 44 px, result stats single column, answer text 281 px no overflow
# which model IDs the gateway really serves (check before trusting .env)
curl -s localhost:8080/v1/models | python -c "import sys,json;[print(m['id']) for m in json.load(sys.stdin)['data']]"
# P8 gate (verified 2026-11-22, exit 0, 40/40 claims, 0 pipeline errors)
npx -y @maximhq/bifrost          # gateway needed: every verify() call goes through Bifrost
python bench/run_bench.py       # 225 s wall, 38 Tavily credits, writes bench/results.md
#   STALE RECALL 14/15 (93.3%) · STALE PRECISION 14/16 (87.5%) · FALSE ALARMS 0/15 (0.0%)
#   UNVERIFIABLE 7/10 (70.0%) · ACCURACY 87.5% · CREDITS 38 vs 40 baseline (5.0% saved)
#   LATENCY avg 4438 ms · median 3187 ms · ERRORS 0 · skipped_stable 2
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
- Tavily with `search_depth: "basic"` returns **no `published_date`** (verified on all 5 results), so `Evidence.published_date` is `None` today and freshness must come from content wording, not metadata. Fixing that needs `topic: "news"` or a `time_range`, which the frozen P3 body does not allow — decide in P5.
- The search cache and the fact cache share `ttl_cache.db`; a second identical CLI run printed `source: cache (no API call)` with `elapsed_ms=1` vs `2493` cold — that timing gap is the proof no credit was spent.
- SQLite failures in `tavily_client` are swallowed to a logged warning (cache read/write only), so search still works with an unusable DB file. No retry loop there by design.
- `.env` is read at import time: a new key needs a fresh `python -m ...` process, not a running one.
- `CLAIMS_SYSTEM` (frozen) asks for "the year/current wording" but never says what year it is; asked without a date the model answered `Notion Plus plan price 2024`. Fixed by putting `TODAY: <date>` in the user message (decision 14) — full re-run then produced `…2026`.
- `claims.last_queries` and `claims.last_raw` are module state reset at the start of every `extract()` call: safe for the CLI, but two concurrent requests would overwrite each other. P5 should read the queries right after its own `extract()` await, or propose the `Claim.search_query` contract change.
- The model still returns a `search_query` for `stable` claims even though the prompt says to leave it empty; harmless, because P5 skips stable claims, and it is kept verbatim for debugging.
- Requests cost 2 calls only on the repair path: `raw model reply (repair_retry=False)` in the script is the proof a single call was enough.
- **Do not rename `TAVILY_API_KEY` inside `.env` to test the 401 path**: the file is unreadable to the agent, so the real key could not be restored. `TAVILY_API_KEY=bad-key ... python -m ...` overrides it for one process (env beats `.env` in pydantic-settings) and leaves the file alone.
- A bad-key run must also point `CACHE_DB` at a throwaway file (`CACHE_DB=ttl_cache_badkey.db`), otherwise the 6-hour search cache answers first, no Tavily call happens and the claims come back fresh instead of `unverifiable`.
- `judge.py` duplicates the ~8-line `_strip_fences` helper from `claims.py` because services may not import each other (02-ARCHITECTURE §9.5) and P5's file list has no shared util; if a third caller appears, move it into `prompts.py` or a utils module.
- Tavily `basic` still returns no `published_date`, so every `Source.published` in a live run is `None`. The judge is told the evidence has no dates and still judged correctly (stale $5 → $10), so this is cosmetic for the demo; only `topic: "news"`/`time_range` would fix it, which the frozen search body forbids.
- Free-tier latency: `samples/pricing.txt` cold took 8 624 ms for 3 claims (2 searched, 1 skipped) — inside the PRD's <20 s budget but with little room if the gemini fallback hop triggers.
- `tests/test_scoring.py` first asserted 68 for the fast/slow mean; the correct value is 65 ((99*1.5+15)/2.5). Recompute by hand before "fixing" the code when a weighted-mean test fails.
- **On this Windows host `curl http://localhost:8000/...` did not connect** while uvicorn listened on `127.0.0.1:8000` (no `::1` listener; `localhost` resolved to the IPv6 loopback). Every gate command here uses `127.0.0.1`; run `uvicorn ... --host 0.0.0.0` instead only if a second machine must reach it.
- A warm run still shows `llm_calls=1`, not 0: extraction always runs (the answer must be re-parsed). The fact cache skips only the per-claim Tavily search **and** the judge call, which is why the warm latency was 718 ms instead of 7 386 ms and `tavily_credits_used=0`.
- A cached correction is frozen until its row expires (1 day for pricing), so re-running the demo minutes later keeps yesterday's wording. `DELETE /api/cache` is the demo reset; expiry is not deleted from the table, it is just filtered out by `get_fact` and `GET /api/cache`.
- `/api/verify` needs Bifrost up. With the gateway down the route answers `503 {"error":"Bifrost unreachable at http://localhost:8080"}` (every other upstream failure is 502) — `curl` without showing the body would hide that body entirely.
- `_apply_cached` copies the archived `expires_at` onto today's claim, so the warm response shows the original expiry (2026-11-22), not `now + ttl`; that is what makes `seconds_left` in `GET /api/cache` match the row.
- `tests/test_cache.py` and `tests/test_pipeline_mocked.py` point `settings.CACHE_DB` at a `tmp_path` file per test; without that the developer's real `ttl_cache.db` would serve across tests and a warm hit would break the cold-run assertions.
- The `bifrost_client` `ContextVar`s are set and reset in a `finally` inside `verify()`; a task created outside `verify()` (a future P7 background job) sees the default `None` sink and counts nothing.
- P7a hero: the headline is split into two `.line` wrappers with `white-space: nowrap`, so the font size (`clamp(2.75rem, 7vw, 6.25rem)`) must stay small enough for "Every fact has" to fit the left grid column. Raising it re-breaks the design into 3–4 lines at 1440px.
- The hero is `calc(100svh - 92px)`, not `100svh`: the sticky nav is in normal flow, so a full-viewport hero pushes the fact-type marquee past the fold (verified by measuring `marquee.bottom` = 877 < 900).
- The footer wordmark is sized by measurement, not by eye: the outline text is 6.45 × the font size wide, so at 375px anything above ~12.6vw overflows the 318px content box (`scrollWidth` 327 vs 318 at 13.5vw).
- Doodles are absolutely positioned inside `.doodles`; on ≤640px only the ring and one sparkle stay visible, otherwise the browser/clock/magnifier sit on top of the headline and hurt legibility.
- `preview_screenshot` on this host returns blank frames while the page is scrolled and the Freebuff window is minimised/covered (the `.hero` paints, later sections do not). Layout was verified with `preview_evaluate` rects in that case, not screenshots.
- With the Freebuff window covered, `preview_screenshot` refuses with "it has not been drawn yet", and a real mouse click from `preview_click` on `#verify` did not fire the handler even though `elementFromPoint` at the same coordinates returned the button label. A programmatic `document.getElementById('verify').click()` drove every gate step; the button itself is not blocked (hit test passes).
- The score/ring animation freezes at `0` in a hidden window because rAF is paused — decision 34's `setTimeout` snap is what makes the painted number and `stroke-dashoffset` arrive anyway.
- `.stats` renders one `span` per cell plus a `span.stats-sep` holding `·`, with the label and value in separate nodes; `textContent` therefore reads `CLAIMS 3·SEARCHED 0…`, which is why the strip is a flex row and not one string.
- The left card is `min-height: 560px` and the result card grows with its claims; `.console-grid` is `align-items: start` so the shorter input card does not stretch into a tall empty box (the Verify button sits after the note, not pinned to the bottom).
- `preview_click` coordinates are reported in viewport space after scrolling; the button's y moves once the result panel changes height, so measure with `getBoundingClientRect()` before trusting a click point.
- While the Freebuff window is covered, CSS animations and `IntersectionObserver` callbacks do not advance at all: right after a result the strike `::after` reads `scaleX(0)` and the fix reads `opacity: 0`. `document.getAnimations().forEach(a => a.finish())` jumps them to their end states, which is how the P7c gate checked `scaleX(1)` / `opacity: 1`.
- Same cause made every `.reveal` stay at `opacity: 0` after the first P7c load. Fixed by decision 39's scroll/load `revealInView()` pass; the scroll handler fires even when frames are paused.
- `navigator.clipboard.readText()` is refused (`NotAllowedError`) in the automated preview, so the copy path was proven with a spy on `writeText` instead; the label change alone does not prove the write.
- `preview_screenshot` returned an all-black frame for the scrolled Results section while the window was covered, even though `preview_evaluate` reported opacity 1 and real rects for the same elements — measurements are the reliable check in that state.
- The tabs and `Copy corrected` only reach the 44 px tap target inside the ≤640 px media query; on desktop they stay 26/30 px tall so the underline sits right against the text.
- `python bench/run_bench.py` puts `bench/` (not the repo root) on `sys.path`, so the first run died on `ModuleNotFoundError: app`; the script now inserts its parent directory explicitly. `scripts/*` never hit this because they run as `python -m scripts.x`.
- `use_cache=False` disables only the **fact** cache; `tavily_client.search` still reads the 6-hour `searches` table in `CACHE_DB`, so a benchmark against the demo DB would report `0` credits while spending none. The runner points `CACHE_DB` at `bench/.bench_cache.db` and deletes it first.
- Two claims in the P8 run took ~27–29 s (fallback hop to gemini), which is why the mean latency (4.4 s) is far above the median (3.2 s). Quote the median when comparing claim-level cost.
- The P8 run had one stale miss (`Gemini 1.5 Pro is Google's latest Gemini model` → `fresh`, conf 0.93) and two made-up-company claims judged `stale` with confident corrections (Loam Labs, Tartu library volumes). The first is a judge/evidence miss; the second is search returning a real, same-named entity. Both are reported as-is — prompts stay frozen (decision 44).
- Extraction typed two benchmark sentences as `stable` (the EU AI Act applicability date, the Tartu permit count) and the pipeline therefore skipped them: a fixed historical date is a permanent fact under the product's own volatility table, so a “fresh law” label only matches when the sentence states a changeable rule. Keep that in mind before calling it a recall bug.
- `bench/.bench_cache.db*` and `bench/run.log` are local artefacts; the DB is deleted at the start of every run and neither should be committed.

## 9. Benchmark snapshot (filled in P8)

| Metric | Value |
|---|---|
| Claims tested | 40 · 15 stale · 15 fresh · 10 unverifiable (`bench/claims.jsonl`) |
| Stale recall | 14/15 (93.3%) |
| Stale precision | 14/16 (87.5%) |
| False-alarm rate | 0/15 fresh claims called stale (0.0%) |
| Unverifiable handling | 7/10 correctly `unverifiable`; 2 called stale, 1 skipped as stable |
| Claim-level accuracy | 87.5% (35/40) |
| Avg latency (cold) | 4 438 ms — median 3 187 ms, 29.5 s worst (one fallback hop) |
| Tavily credits used / baseline | 38 / 40 (5.0% saved; 2 claims skipped as stable, 0 cache hits by design) |
| Why savings look low here | every benchmark sentence is volatile by construction, so volatility gating can skip only 2 of 40; a normal mixed answer (demo) searches 2 of 3 claims |
| Run details | 2026-11-22, 225 s wall, cache off, 0 pipeline errors; full table in `bench/results.md` |

## 10. Do-not-touch after freeze
- Prompts (after P8)
- `models.py` field names
- TTL table
- Benchmark labels (after P8)
