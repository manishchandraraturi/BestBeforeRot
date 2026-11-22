# FactTTL benchmark — 40 hand-labelled claims

Generated: 2026-11-22 · wall time 225 s

Every claim was sent through the real pipeline (`app.pipeline.verify`) one at a time with `use_cache=False`, against a bench-local SQLite file that is deleted before the run, so every verdict below comes from a live Tavily search and a live judge call.

Models via Bifrost: extraction `groq/openai/gpt-oss-20b`, judge `groq/openai/gpt-oss-120b`, fallback `gemini/gemini-3.5-flash-lite`.
Labels were set by hand from the official source in `truth_url` before the run.

## Summary

| Metric | Value |
|---|---|
| Claims tested | 40 (15 stale · 15 fresh · 10 unverifiable) |
| Stale recall | 14/15 (93.3%) |
| Stale precision | 14/16 (87.5%) |
| False-alarm rate | 0/15 fresh claims called stale (0.0%) |
| Unverifiable handling | 7/10 said "can't verify" (70.0%) |
| Fresh claims confirmed | 14/15 (93.3%) |
| Claim-level accuracy | 87.5% |
| Tavily credits used | 38 |
| "Search everything" baseline | 40 credits (1 per claim) |
| Search credits saved | 5.0% (2 of 40) |
| Avg latency per claim (cold) | 4.4 s (median 3.2 s) |
| Claims skipped as stable | 2 |
| Pipeline errors | 0 |

## Confusion matrix

| label \ verdict | stale | fresh | unverifiable | skipped_stable | error |
|---|---|---|---|---|---|
| stale | 14 | 1 | 0 | 0 | 0 |
| fresh | 0 | 14 | 0 | 1 | 0 |
| unverifiable | 2 | 0 | 7 | 1 | 0 |

## Per-claim results

| # | label | verdict | type | conf | sources | ms | claim |
|---|---|---|---|---|---|---|---|
| 1 | stale | stale | pricing | 0.99 | 3 | 6615 | The Notion Plus plan costs $5 per member per month. |
| 2 | stale | stale | pricing | 0.98 | 4 | 3185 | Spotify Premium Individual costs $9.99 per month in the United States. |
| 3 | stale | stale | pricing | 0.98 | 3 | 2928 | The standard Netflix plan costs $15.49 per month in the United States. |
| 4 | stale | stale | pricing | 0.98 | 3 | 3338 | Amazon Prime costs $119 per year in the United States. |
| 5 | stale | stale | version | 0.95 | 3 | 4195 | GPT-4 is OpenAI's most capable model. |
| 6 | stale | stale | version | 0.97 | 3 | 3175 | Claude 2 is Anthropic's newest model. |
| 7 | stale | fresh ✗ | version | 0.93 | 2 | 3189 | Gemini 1.5 Pro is Google's latest Gemini model. |
| 8 | stale | stale | version | 0.90 | 1 | 3332 | Python 3.11 is the latest stable release of Python. |
| 9 | stale | stale | version | 0.97 | 4 | 3861 | Node.js 18 is the current LTS version of Node.js. |
| 10 | stale | stale | version | 0.90 | 1 | 3300 | The iPhone 14 is Apple's newest iPhone. |
| 11 | stale | stale | leadership | 1.00 | 1 | 2881 | Tim Cook is the CEO of Apple. |
| 12 | stale | stale | leadership | 0.98 | 2 | 2725 | Jack Dorsey is the CEO of Twitter. |
| 13 | stale | stale | leadership | 0.78 | 2 | 29488 | Parag Agrawal is the CEO of Twitter. |
| 14 | stale | stale | law | 0.98 | 2 | 4622 | The EU AI Act entered into force in 2021. |
| 15 | stale | stale | law | 0.97 | 5 | 3905 | GDPR fines are capped at 10 million euros or 2% of global annual turnover. |
| 16 | fresh | fresh | pricing | 1.00 | 4 | 2261 | The Notion Plus plan costs $10 per member per month when billed yearly. |
| 17 | fresh | fresh | pricing | 0.99 | 5 | 3570 | ChatGPT Plus costs $20 per month. |
| 18 | fresh | fresh | pricing | 1.00 | 5 | 3125 | Claude Pro costs $20 per month. |
| 19 | fresh | fresh | pricing | 0.99 | 5 | 3208 | GitHub Copilot Pro costs $10 per month. |
| 20 | fresh | fresh | pricing | 1.00 | 5 | 1907 | Spotify Premium Individual costs $12.99 per month in the United States. |
| 21 | fresh | fresh | pricing | 0.99 | 3 | 27131 | The standard Netflix plan costs $19.99 per month in the United States. |
| 22 | fresh | fresh | pricing | 0.99 | 3 | 1736 | Amazon Prime costs $139 per year in the United States. |
| 23 | fresh | fresh | version | 0.95 | 3 | 4188 | GPT-6.2 Astra is OpenAI's flagship model. |
| 24 | fresh | fresh | version | 1.00 | 3 | 3627 | Claude Fable 5.2 is Anthropic's most capable model. |
| 25 | fresh | fresh | version | 0.97 | 4 | 4021 | Python 3.15 is the latest stable release of Python. |
| 26 | fresh | fresh | version | 1.00 | 1 | 4115 | Node.js 26 is the current Active LTS version of Node.js. |
| 27 | fresh | fresh | leadership | 0.99 | 3 | 2994 | John Ternus is the CEO of Apple. |
| 28 | fresh | fresh | leadership | 1.00 | 4 | 4178 | Satya Nadella is the CEO of Microsoft. |
| 29 | fresh | skipped_stable ✗ | law | — | 0 | 625 | The EU AI Act became applicable on 2 August 2026. |
| 30 | fresh | fresh | law | 0.97 | 4 | 3501 | The EU AI Act's obligations for general-purpose AI model providers apply from 2 August 2025. |
| 31 | unverifiable | unverifiable | pricing | 1.00 | 0 | 3110 | Acme Cloud's Team plan costs $19 per seat per month. |
| 32 | unverifiable | stale ✗ | other | 1.00 | 2 | 3040 | Loam Labs has 14 employees as of November 2026. |
| 33 | unverifiable | unverifiable | version | 0.20 | 0 | 2725 | The internal codename for Notion's 2027 desktop client is Harbor. |
| 34 | unverifiable | unverifiable | other | 1.00 | 0 | 2729 | Tesla will hold its 2027 annual shareholder meeting in Austin on 14 May 2027. |
| 35 | unverifiable | unverifiable | pricing | 0.20 | 0 | 2505 | Nordwind Analytics' enterprise plan includes 250 seats. |
| 36 | unverifiable | unverifiable | pricing | 1.00 | 0 | 2661 | The average price of a flat white in Reykjavik in October 2026 was 640 ISK. |
| 37 | unverifiable | skipped_stable ✗ | other | — | 0 | 813 | The city of Tartu issued 37 building permits for data centres in 2025. |
| 38 | unverifiable | unverifiable | other | 0.90 | 0 | 2819 | Brightline Robotics raised $18 million in its Series B round in March 2026. |
| 39 | unverifiable | stale ✗ | other | 0.90 | 2 | 2662 | The University of Tartu Library holds exactly 3,412,000 volumes. |
| 40 | unverifiable | unverifiable | other | 1.00 | 0 | 3528 | Harborlight Bank's premium account charges a 3 euro monthly fee. |

## Misses and false alarms

| # | label | verdict | claim | corrected | reason |
|---|---|---|---|---|---|
| 7 | stale | fresh | Gemini 1.5 Pro is Google's latest Gemini model. | Gemini 1.5 Pro is Google's latest Gemini model. | checked |
| 29 | fresh | skipped_stable | The EU AI Act became applicable on 2 August 2026. | — | skipped_stable |
| 32 | unverifiable | stale | Loam Labs has 14 employees as of November 2026. | Loam Labs has 6 employees as of November 2026. | checked |
| 37 | unverifiable | skipped_stable | The city of Tartu issued 37 building permits for data centres in 2025. | — | skipped_stable |
| 39 | unverifiable | stale | The University of Tartu Library holds exactly 3,412,000 volumes. | The University of Tartu Library holds approximately 3.7 million to 4 million volumes. | checked |
