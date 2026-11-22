# BestBeforeRot — Pitch Deck (7 slides)

**How to use this file:** each slide below is one copy-paste block. Paste the *On slide* text into
PowerPoint / Canva / Google Slides, then follow the *Visual* line. *Speaker notes* are what you say
out loud (~30–40 s per slide, ~4 min total; cut to 90 s by dropping the bolded optional lines).

**Style:** black background `#0B0B0B`, white type, one accent red `#E5484D` for stale and one green
`#2FA36B` for fresh. Headline font Space Grotesk, body font Inter. No stock photos — the product UI
is the only imagery.

---

## Slide 1 — Title & Team

**On slide**

> # BestBeforeRot
> ### Every fact has an expiry date.
>
> A stale-answer detector for AI apps.
>
> **Tavily** · live evidence   **Bifrost** · model routing & fallback
>
> Global AI Hackathon 2026 — Problem Statement 06
> Manish Chandra Raturi · solo build

**Visual:** full-bleed black. Product wordmark left, a thin red strike-through crossing the word
"Rot", one green dot after "date.". No screenshots yet — keep this slide empty and confident.

**Speaker notes**
"Every AI answer you have ever read has an expiry date. Some of it has already passed. This is
BestBeforeRot — it finds the sentences that went bad, and fixes them with live sources."

---

## Slide 2 — The Problem

**On slide**

> ### The model can't tell you what it forgot.
>
> An AI answer from last year still sounds certain:
>
> ~~"The Notion Plus plan costs $5 per month."~~ → it's **$10**
> ~~"Jack Dorsey is the CEO of Twitter."~~ → he isn't
>
> - Models are trained once, then answer for years.
> - Every sentence carries the same confidence — stale or not.
> - The only current fix: **search the web for everything** → slow, and wasteful.
>
> **"Salt doesn't spoil. Milk does. Nobody asks which one."**

**Visual:** two lines of white text; the stale halves get a red hand-drawn strike (the same
word-by-word strike the product animates). Bottom-right: a small "1 credit" coin icon crossed out.

**Speaker notes**
"The failure isn't that the model is wrong — it's that it's *equally confident* when it's wrong.
And the workaround, searching every sentence, spends money on facts that never change."

---

## Slide 3 — The Solution

**On slide**

> ### Give every claim its own best-before date.
>
> 1. **Split** the answer into claims
> 2. **Type** each one — pricing · version · leadership · law · stable
> 3. **Skip** what can't rot, **search** what can
> 4. **Judge** against live evidence only
> 5. **Rewrite** stale claims in place, with citations
> 6. **Cache** each verdict until *its* TTL expires
>
> | pricing | version | leadership | law | stable |
> |---|---|---|---|---|
> | 1 day | 7 days | 30 days | 30 days | never searched |
>
> **Spend search credits only where facts rot.**

**Visual:** horizontal "shelf life" strip — five cards, each with a TTL ring (same ring component
as the UI). Stable card is greyed out with a diagonal "not searched" slash.

**Speaker notes**
"The unit of truth isn't the answer, it's the claim. A price rots in a day; a company founder in a
month; history never. So we only pay for searches where the answer can actually go bad — and we
remember every verdict until it expires."

---

## Slide 4 — Architecture & Tech

**On slide**

> ### Two APIs, two jobs, one pipeline.
>
> ```
> Browser ──POST /api/verify──► FastAPI (:8000)
>                                  │
>                     ┌────────────┴────────────┐
>                     ▼                         ▼
>            Tavily  (live evidence)     Bifrost  (:8080)
>                     │                         │
>                     │                    Groq primary
>                     │                    Gemini fallback
>                     └────────► judge ◄────────┘
>                                  │
>                     corrected answer + sources + score
> ```
>
> - **Tavily** = the only source of truth. Max 5 results per claim, 1 credit, 6 h query cache.
> - **Bifrost** = every LLM call: extraction, judging, rewriting. Fallback is visible in the UI.
> - **Deterministic scoring in code.** The model decides meaning; code decides numbers.

**Visual:** the diagram above as boxes and arrows, Tavily in purple, Bifrost in warm brown, the
verdict step highlighted in green. One line under it: `0 → 100 freshness score`.

**Speaker notes**
"Tavily answers 'what is true right now'. Bifrost answers 'which model is alive right now', and
gives us token cost and a fallback we can actually show. Neither key ever reaches the browser."

---

## Slide 5 — The Live Demo

**On slide**

> ### Paste. Verify. Watch it rot — then get fixed.
>
> - Claim cards: verdict, TTL ring (`1d` / `30d` / `∞`), confidence, real source links
> - Stale text **struck through**, corrected value fades in, Diff tab shows `<s>$5</s> <u>$10</u>`
> - One freshness score for the answer: **49 / 100 · risky**
> - Second run: **from cache**, credits spent **0**
> - *Simulate outage* → badge flips to **FALLBACK → GEMINI**, still HTTP 200
>
> `SEARCHED 2 · SKIPPED 1 · CACHE 0 · 4.7 s`

**Visual:** two stacked screenshots side by side — left: paste + Verify; right: result panel with
one red claim and one green claim. Add a small arrow labelled "same answer, 1.6 s warm".

**Speaker notes**
"Everything you see is live: the Notion price is struck out, the corrected price fades in next to
real sources, and the score drops into red. Run it again — instant, from cache. Turn on the outage
toggle — Bifrost fails over, the badge says Gemini, the request still succeeds."

> **Demo tip:** run `curl -X DELETE http://127.0.0.1:8000/api/cache` right before this slide.

---

## Slide 6 — Benchmark Results

**On slide**

> ### 40 hand-labelled claims. 0 false alarms.
>
> | Metric | Result |
> |---|---|
> | Stale recall | **14/15 (93.3%)** |
> | Stale precision | 14/16 (87.5%) |
> | False alarms on fresh claims | **0/15 (0.0%)** |
> | Unverifiable handled correctly | 7/10 (70.0%) |
> | Claim-level accuracy | 87.5% |
> | Tavily credits | 38 vs 40 "search everything" |
> | Avg latency (cold) | 4.4 s (median 3.2 s) |
> | Pipeline errors | **0** |
>
> Every claim a live search, cache off, labels fixed from official sources before the run.

**Visual:** big number "93%" left in white on black, "0" false alarms in green beneath it; the
table small on the right. Footnote: `bench/results.md`.

**Speaker notes**
"We labelled forty claims by hand — fifteen stale, fifteen fresh, ten unverifiable — and ran each
one through the real pipeline with the cache off. It caught fourteen of fifteen stale claims and
raised zero false alarms on fresh ones. The credit saving is only 5% here because every benchmark
sentence is volatile by design; on a normal answer we search a third of the claims."

---

## Slide 7 — Roadmap & Conclusion

**On slide**

> ### Today: a working verifier. Next: a standard.
>
> **Now** — claim-level TTL cache · evidence-locked verdicts · visible Bifrost fallback ·
> public 40-claim benchmark
>
> **Next**
> - `topic: "news"` + `time_range` so every source carries a publish date
> - Streaming NDJSON — claims appear as they are judged
> - Cache inspector: every fact and its remaining seconds
> - TTL policy as config per customer; batch endpoint for RAG pipelines
> - 500-claim benchmark with per-type recall
>
> ### "Sounds right" is not the same as "is still right."
>
> **Try it:** github.com/manishchandraraturi/BestBeforeRot

**Visual:** two columns — "Now" (white) and "Next" (grey), with the closing line full-width at the
bottom in large type. Keep the repo URL visible for judges who photograph the slide.

**Speaker notes**
"Nothing here is a mock: the pipeline, the UI, the cache and the benchmark all run today. The next
step is making the evidence itself dated and the benchmark bigger. Every fact has an expiry date —
and now your AI answers say so."

---

### Deck checklist

- [ ] 7 slides, black/white, one red and one green accent only
- [ ] Numbers on slide 6 match `bench/results.md` exactly (14/15 · 14/16 · 0/15 · 87.5% · 38 credits)
- [ ] Screenshots on slide 5 taken after `DELETE /api/cache` so the cold run is real
- [ ] Export to PDF as a backup to the PPTX
- [ ] Repo URL and demo URL both visible in the last slide
