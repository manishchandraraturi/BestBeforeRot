# 01 · PRD — FactTTL

> **Every fact has an expiry date.**
> A stale-answer detector for AI apps. Built for Global AI Hackathon · Problem Statement 06 (Tavily) · uses Tavily + Bifrost.

**Deadline:** the hackathon page shows the elimination round closing **21 Nov 2026, 11:59 PM**. Treat **20 Nov night** as the real deadline. Re-check the page.

---

## 1. Problem

LLMs state old facts with full confidence: old prices, old API versions, old laws, old CEOs.
Users cannot tell which sentence in an AI answer has gone bad.
Existing fix = "search the web for everything." That is slow and burns search credits on facts that never change.

## 2. Solution

FactTTL sits between an LLM answer and the user.

1. **Splits** the answer into single claims.
2. **Tags** each claim with a volatility type (price, version, law, leadership, stable).
3. **Checks only the claims that can age** against the live web (Tavily).
4. **Judges** each: `Fresh`, `Stale`, or `Can't verify`, with source links.
5. **Fixes** stale claims in the text, with citations.
6. **Scores** freshness (0–100) per claim and for the whole answer.
7. **Gives every checked fact its own expiry timer.** Price = 1 day, version = 7 days. Repeat questions hit the cache until the timer ends.

Bifrost routes every model call, falls back if a provider fails, and reports cost.

## 3. Target users

| User | Pain | What FactTTL gives |
|---|---|---|
| **Primary: developers shipping LLM apps / chatbots / RAG** | Their bot quotes old prices and APIs; support tickets follow | A drop-in verification layer (`POST /api/verify`) |
| **Secondary: students, analysts, founders using AI answers** | Can't tell what is outdated | Red / green claims with sources |
| **Judges** | Want a clear problem, real tech use, a demo in 60 seconds | See section 10 |

## 4. Requirement traceability (strict — nothing missed)

| Problem statement requirement | Our feature | Where |
|---|---|---|
| **1. Claim Identification** | LLM claim splitter → JSON claims | `services/claims.py` |
| **2. Freshness Detection** | Volatility type + TTL per claim; only volatile claims flagged | `services/claims.py`, `ttl.py` |
| **3. Live Verification** | Tavily search per flagged claim, evidence + dates | `services/tavily_client.py` |
| **4. Freshness Scoring** | Deterministic score per claim + overall | `services/scoring.py` |
| **Mandatory: Tavily meaningfully used** | Live evidence for every verdict; no verdict without evidence | pipeline |
| **Mandatory: Bifrost meaningfully used** | All LLM calls via Bifrost; fallback chain; cost + provider shown in UI | `services/bifrost_client.py` |
| **Domains named: pricing, API versions, laws, leadership** | All four are claim types | claim schema |
| **Expected outcome: working system, users see which claims are supported** | Web app + API + benchmark | whole repo |

## 5. Features

### MUST (MVP — demo dies without these)
- Paste an AI answer **or** ask a question (we generate the answer with a weak model, then verify it).
- Claim cards: original text, verdict, corrected text, source links, confidence, TTL ring.
- Corrected answer view (side by side: original vs. fixed, with changes highlighted).
- Freshness score (per claim + overall).
- Per-fact TTL cache (SQLite). Second run is instant.
- Stats strip: claims found, searched, skipped, cache hits, Tavily credits used vs. saved, latency.
- "Routed via" badge: which provider Bifrost used. **Simulate outage** toggle to show fallback.
- Sample answers (3 one-click stale examples).
- Benchmark script + results table in README.

### SHOULD (only if MUST is done and tested)
- NDJSON streaming so claim cards appear one by one.
- Copy-as-JSON / copy corrected answer button.
- Cache viewer page (facts + time left on each timer).

### WON'T (do not build)
- Login, payments, database server, deployment, browser extension, hardware, multi-language.

## 6. Innovation (what to say to judges)

1. **Per-fact expiry (TTL).** Every fact ages at its own speed. Prices expire in a day, history never. Nobody else will cache by *fact volatility*.
2. **Spend search only where facts can rot.** Stable claims are skipped. We show "credits saved" live.
3. **Evidence-locked verdicts.** The judge model may only use Tavily evidence, never its own memory. No evidence = `Can't verify`, never a guess.
4. **Gateway-native reliability.** Bifrost fallback is visible in the UI, not just claimed.
5. **Honest numbers.** Public benchmark: stale caught, false alarms, search credits saved.

## 7. Freshness score (deterministic, explainable)

Per claim (computed in code, **not** by the LLM):

| Verdict | Score |
|---|---|
| `fresh` | `80 + 10×confidence + 10 if ≥2 independent sources agree` |
| `stale` | `15` |
| `unverifiable` | `40` |
| `stable` (never changes) | not scored |

Overall = weighted mean of scored claims (fast-changing claims weight 1.5, slow 1.0).
UI bands: **80–100 Fresh**, **50–79 Mixed**, **0–49 Risky**.

## 8. User flow

1. Land on hero → scroll/click **Try it**.
2. Paste answer or pick a sample.
3. Press **Verify**.
4. See progress → claim cards animate in → corrected answer → score.
5. Re-run → "from cache" badges, near-zero latency.
6. Flip **Simulate outage** → still works, badge shows fallback provider.

## 9. Success metrics

- End-to-end verify in **< 20 s** for a 6-claim answer (cold), **< 2 s** (warm cache).
- Benchmark on **≥ 40 hand-labeled claims** (15 stale · 15 fresh · 10 unverifiable). Report: stale recall, false-alarm rate, credits saved vs. "search everything".
- Zero unhandled crashes in the demo path.

## 10. Judging criteria → our answer

| Criterion | Our answer |
|---|---|
| Innovation | Per-fact TTL + volatility-gated search + evidence-locked verdicts |
| Technical execution | Typed pipeline, cache, fallback, benchmark script, tests |
| Problem & impact | Every LLM app has this bug; dev-facing API |
| Use of AI | Claim extraction, judging, rewriting, all via Bifrost |
| User experience | Minimal black/white UI, live cards, side-by-side fix |
| Scalability | Stateless API, cache layer, model-agnostic gateway, TTL policy is config |

## 11. 90-second demo script

1. (10s) "AI says Product X costs $29." Problem in one line.
2. (25s) Paste answer → Verify → red claim strikes through → green corrected value + source.
3. (15s) Overall freshness score counts up. Point at "3 of 7 claims searched, 4 skipped, 4 credits saved".
4. (15s) Run again → instant, "from cache · expires in 23h".
5. (15s) Toggle **Simulate outage** → Bifrost fallback badge.
6. (10s) Show benchmark table. Close: "Every fact has an expiry date."

## 12. Risks

| Risk | Fix |
|---|---|
| Free LLM rate limits | Two providers via Bifrost; cache; max 8 claims per answer |
| Tavily credits (free plan) | Basic depth only; cache search results; skip stable claims |
| LLM returns bad JSON | Strip fences, one repair retry, then mark claim `unverifiable` |
| Time | Follow `05-TASKS.md` cut list. Backend working by end of Day 1 |
