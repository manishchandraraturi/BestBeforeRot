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
| P0 | Setup & keys | TODO | | |
| P1 | Skeleton | TODO | | |
| P2 | Bifrost client + fallback | TODO | | |
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

**Bifrost raw response (first call):**
```
(paste here)
```
Provider field location: `(fill)` · Fallback request field: `(fill)`

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

## 6. Working commands (add as they are proven)

```bash
npx -y @maximhq/bifrost
uvicorn app.main:app --reload --port 8000
pytest -q
```

## 7. Environment (names only, never values)

`BIFROST_URL, PRIMARY_MODEL, FALLBACK_MODEL, WEAK_MODEL, TAVILY_API_KEY, MAX_CLAIMS, MAX_PARALLEL, REQUEST_TIMEOUT_S, CACHE_DB`

Actual model names in use: `PRIMARY=(fill) FALLBACK=(fill) WEAK=(fill)`

## 8. Known issues / gotchas

- (none yet)

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
