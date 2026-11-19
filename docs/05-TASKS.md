# 05 · TASKS — FactTTL (2-day plan)

**Rule:** one phase → run its test gate → paste real output → update `06-MEMORY.md` → next phase. No gate pass = no next phase.

**Day 1 = backend works end to end (P0–P6). Day 2 = UI + proof + submit (P7–P9).**

## Phase prompt template (for DeepSeek → Freebuff agent)

When you ask DeepSeek to write the agent prompt, give it this:

```
You are writing ONE build prompt for a coding agent. Context files are in /docs
(01-PRD, 02-ARCHITECTURE, 03-RULES, 04-DESIGN, 05-TASKS, 06-MEMORY).
Current state: <paste 06-MEMORY status table>.
Write the prompt for PHASE <N> only, exactly as defined in 05-TASKS.md.
The prompt must: (1) tell the agent to read the docs first, (2) list the files to
create/edit, (3) state the exact test gate commands, (4) tell it to print real
outputs, update 06-MEMORY.md, and STOP. No extra features.
```

---

## Day 1 — backend

### P0 · Setup & keys (≈1h)
**Do**
- Create repo `fact-ttl`, folder structure from `02-ARCHITECTURE.md`, copy 6 docs into `docs/`, add `.gitignore` (`.env`, `.venv`, `*.db`, `__pycache__`).
- Make free keys: Tavily, Groq, Gemini.
- Run Bifrost (`npx -y @maximhq/bifrost`), open `http://localhost:8080`, add Groq + Gemini providers with keys.
- Create `.env` from `.env.example` with real model names (copy exact names from each provider's current free model list).

**Test gate**
```bash
# Bifrost works
curl -s http://localhost:8080/v1/chat/completions -H "Content-Type: application/json" \
 -d '{"model":"groq/<model>","messages":[{"role":"user","content":"say hi"}]}'
# Tavily works
curl -s https://api.tavily.com/search -H "Authorization: Bearer $TAVILY_API_KEY" \
 -H "Content-Type: application/json" -d '{"query":"current CEO of OpenAI","max_results":3}'
```
✅ Both return JSON with content/results. Save both raw outputs into `06-MEMORY.md` (shapes!).

### P1 · Skeleton (≈45m)
**Do:** `config.py`, `models.py` (all contracts from architecture §5), `ttl.py`, `main.py` with `GET /api/health`, static mount serving a placeholder `web/index.html`.
**Test gate**
```bash
pytest tests/test_ttl.py -q          # pricing→1, version→7, stable→None
uvicorn app.main:app --port 8000 &
curl localhost:8000/api/health       # {"ok":true,"bifrost":true,"tavily_key_set":true}
```

### P2 · Bifrost client + fallback (≈1h)
**Do:** `bifrost_client.chat(messages, model=None, force_fallback=False) -> ChatResult(text, tokens_in, tokens_out, provider, fallback_triggered)`. Shared `httpx.AsyncClient`, timeout, one network retry. Print the raw response once and match real field names.
**Test gate**
```bash
python -m scripts.try_bifrost "Say hello"                 # normal: provider = groq
python -m scripts.try_bifrost "Say hello" --force-fallback # provider = gemini, fallback_triggered=True
```
✅ Both work and show correct provider. If fallback field is wrong, fix per Bifrost docs before moving on.

### P3 · Tavily client (≈45m)
**Do:** `tavily_client.search(query) -> list[Evidence]` (basic depth, max 5, content trimmed to ~600 chars, date if present). Typed errors (`SearchError` for 401/429/timeout). Search cache table (6h).
**Test gate**
```bash
python -m scripts.try_tavily "Notion Plus plan price per month"   # prints 5 results with urls
python -m scripts.try_tavily "Notion Plus plan price per month"   # 2nd run: "from cache"
pytest tests/test_tavily_mocked.py -q   # 429 → SearchError, no crash
```

### P4 · Claim extraction (≈1.5h)
**Do:** `prompts.py` (Prompt 1 from `03-RULES.md`), `claims.extract(answer) -> list[Claim]`. Strip fences, Pydantic parse, one repair retry, validate each `text` exists in the answer, assign `volatility` + `ttl_days` from `ttl.py`, cap at `MAX_CLAIMS`.
**Test gate**
```bash
pytest tests/test_claims_parse.py -q     # fenced JSON, bad JSON repair, missing text
python -m scripts.try_claims "<paste 1 of the sample answers>"
```
✅ On 5 hand-made answers: every price/version/leader sentence is found, history sentences are `stable`. Paste output for review.

### P5 · Verify pipeline: Tavily + judge + score (≈2h)
**Do:** `judge.py` (Prompt 2), `scoring.py`, `pipeline.verify()` for steps 1–5 of architecture §4 (parallel, semaphore, per-claim error isolation). No cache yet.
**Test gate**
```bash
pytest tests/test_scoring.py tests/test_pipeline_mocked.py -q
python -m scripts.try_pipeline samples/pricing.txt   # prints claims, verdicts, sources, score
```
✅ A known-stale price is `stale` with a real source URL. A stable claim is skipped. Kill Tavily key → claims become `unverifiable`, request still returns 200.

### P6 · Cache + rewrite + stats + endpoints (≈1.5h)
**Do:** `cache.py` (facts table with `expires_at`), wire into pipeline; `rewrite.apply()` (exact-substring replace, else "Corrections" list); stats (credits used/saved, cache hits, providers, latency); routes `/api/verify`, `/api/ask`, `/api/samples`, `/api/cache` (GET/DELETE).
**Test gate**
```bash
pytest tests/test_cache.py -q           # hit before expiry, miss after
curl -X POST localhost:8000/api/verify -H "Content-Type: application/json" \
  -d '{"answer":"<sample>"}'            # cold: latency_ms ~ seconds, cache_hits 0
# run the SAME curl again               # warm: cache_hits > 0, latency far lower
curl -X POST localhost:8000/api/verify -d '{"answer":"<sample>","force_fallback":true,"use_cache":false}' -H "Content-Type: application/json"
                                         # fallback_triggered true
```
🏁 **End of Day 1 checkpoint:** API matches the frozen contract, commit + push. If not reached, cut from the Cut List (below) tonight.

---

## Day 2 — UI, proof, submit

### P7 · Frontend (≈3.5h) — follow `04-DESIGN.md`
Split into 3 small agent prompts (one at a time):
- **P7a Shell:** fonts, tokens, nav, hero (headline reveal, doodle SVGs, marquee), footer. *Gate: looks right at 1440px and 375px; no console errors.*
- **P7b Console:** input card, tabs, samples, toggles, Verify → `fetch /api/verify`, loading ticker, error + offline states. *Gate: real response renders raw cards.*
- **P7c Results polish:** score ring + count-up, stat strip, badges, claim cards (strike → fix animation, TTL ring, source chips), corrected/diff tabs, copy buttons, scroll reveals, How-it-works section, results section placeholder. *Gate: full demo script from PRD §11 runs without a glitch, 3 times in a row.*

### P8 · Benchmark (≈2h)
**Do**
- `bench/claims.jsonl`: **≥ 40 claims**, each `{text, label: fresh|stale|unverifiable, truth_url}`. Mix: 15 stale, 15 fresh, 10 unverifiable. Include all 4 types. **Labels are set by hand, from official sources, today.** Stale examples: take answers from an older/small model and check them yourself.
- `run_bench.py`: runs each claim through the pipeline (cache off), writes `bench/results.md` with a table: stale recall, stale precision, false-alarm rate, unverifiable handling, avg latency, credits used vs. "search everything".

**Test gate:** `python bench/run_bench.py` finishes without crashing, writes `results.md`. Read ≥ 5 wrong rows manually; fix prompts only if a bug is clear. Then **freeze prompts**.
Budget note: 40 claims × 1 credit ≈ 40 Tavily credits. Fine on the free plan.

### P9 · Polish, README, deck, video, submit (≈3h)
1. **README.md:** hero line, screenshot/GIF, problem, solution, how Tavily is used, how Bifrost is used, architecture diagram, setup (3 commands), env vars, API example, benchmark table (real numbers), AI-usage statement (which tools helped), limitations (honest), license, team.
2. **Pitch deck (PDF/PPTX):** problem → solution → architecture (Tavily vs Bifrost roles) → live prototype screenshots → innovation (TTL, evidence-locked, credits saved) → benchmark → roadmap. Black/white to match the site.
3. **Demo video (≤ 2 min):** follow PRD §11. Clear cache first.
4. **Repo hygiene:** public, no `.env`, `.env.example` present, `docs/` included, clean commit history.
5. **Submission form:** primary theme = **Problem Statement 06 (Tavily, Stale-Answer Detector)**. Tick the Bifrost checkbox/section only if the form asks how Bifrost is used; do **not** pick a Bifrost extension statement. Explain each tech's role. Paste repo link, deck, video.
6. **Join the hackathon Discord** (rules require it) and check announcements.
7. Submit **at least 3 hours before** the deadline. Re-open the submission to confirm it saved.

---

## Cut List (cut in this order if behind)
1. Streaming / NDJSON.
2. Cache viewer page, Copy JSON.
3. Diff tab (keep Original | Corrected).
4. Custom cursor, magnetic button.
5. Ask-a-question tab (keep Paste only).
6. Benchmark down to 30 claims.

**Never cut:** Tavily verification, Bifrost routing + fallback badge, freshness score, TTL cache, corrected answer, benchmark table, README, video.

## Final submission checklist
- [ ] Repo public, README complete, `.env` not committed
- [ ] Runs from scratch following README (test in a fresh folder)
- [ ] Both Tavily and Bifrost visibly used in the demo
- [ ] Benchmark table with real numbers
- [ ] Deck exported
- [ ] Demo video uploaded and link works
- [ ] Submission form saved and confirmed
