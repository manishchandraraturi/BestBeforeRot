# 04 · DESIGN — FactTTL

**Feel:** quiet, sharp, a little playful. Black and white. Thin lines. Hand-drawn doodle accents. Everything moves smoothly. Almost no colour.

**Inspiration (not to copy):** the shared images use thin black outlines, dashed connector lines, sparkle stars, tiny window/UI frames, a big soft circle behind the art, and people at laptops. **Draw our own original doodles** in the same spirit: line-art only. Do NOT reuse those illustrations, people, or logos.

---

## 1. Design tokens

```css
:root {
  /* colour — dark default */
  --bg: #0a0a0a;
  --bg-2: #111111;
  --surface: #141414;
  --line: rgba(255,255,255,.12);
  --line-strong: rgba(255,255,255,.28);
  --fg: #fafafa;
  --fg-2: #a3a3a3;
  --fg-3: #6b6b6b;

  /* the ONLY colours: tiny dots, underlines, rings */
  --fresh: #4ade80;
  --stale: #f87171;
  --unsure: #fbbf24;

  /* type */
  --font-display: "Space Grotesk", system-ui, sans-serif;
  --font-serif: "Instrument Serif", Georgia, serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;

  /* shape */
  --r-sm: 10px; --r-md: 16px; --r-lg: 24px; --r-pill: 999px;

  /* motion */
  --ease: cubic-bezier(.16, 1, .3, 1);       /* smooth out-expo */
  --ease-in-out: cubic-bezier(.65, 0, .35, 1);
  --t-fast: .2s; --t-med: .5s; --t-slow: .9s;
}
```
Light section (used once, for "How it works", to create contrast): `--bg:#fafafa; --fg:#0a0a0a; --line:rgba(0,0,0,.12)`.

Rules: **no gradients, no shadows with colour, no coloured buttons.** Primary button = white fill, black text. Secondary = 1px outline. Verdict colours appear only as 8px dots, 2px underlines, and TTL rings.

## 2. Typography (modern, not formal)

Load from Google Fonts: **Space Grotesk** (400, 500, 700), **Instrument Serif** (italic 400), **JetBrains Mono** (400, 500).

| Role | Font | Size (fluid) | Weight | Notes |
|---|---|---|---|---|
| Hero headline | Space Grotesk | `clamp(3rem, 9vw, 8rem)` | 500 | tracking `-0.04em`, line-height `.95` |
| Hero accent words | Instrument Serif *italic* | same size | 400 | e.g. "Every fact has an *expiry date.*" |
| Section title | Space Grotesk | `clamp(2rem, 5vw, 4rem)` | 500 | tracking `-0.03em` |
| Card title / claim | Space Grotesk | `1.125rem` | 500 | |
| Body | Space Grotesk | `1rem` / 1.6 | 400 | colour `--fg-2` |
| Labels, tags, numbers, URLs | JetBrains Mono | `.75rem` | 500 | UPPERCASE, tracking `.08em` |
| Big score number | Space Grotesk | `clamp(4rem, 12vw, 9rem)` | 500 | tabular nums |

Mix sizes on purpose: huge headline + tiny mono labels = the "designed" look.

## 3. Doodle / illustration rules

- All art is **inline SVG**, stroke `currentColor`, `stroke-width: 1.5`, `fill: none`, round caps/joins.
- Reusable doodles to draw (own versions): **sparkle star (4-point)**, **tiny browser window with dots**, **magnifying glass**, **clock/ring**, **dashed arrow connector**, **calendar with a cross**, **document with lines**.
- Hero art (right side or behind): a big thin circle (soft, `--line`), a few tiny floating windows (one with code lines, one with a calendar/expiry ring), a magnifier, sparkles. Dashed lines connect them.
- Doodles **float slowly** (translateY ±8px, 6–9s ease-in-out infinite, offsets differ) and **stroke-draw** on load (`stroke-dasharray` + animate `stroke-dashoffset`).
- Keep it sparse: 4–6 doodles in hero, 1–2 per other section.

## 4. Layout (single page, 5 sections)

### Nav (sticky, blurred)
`FactTTL ✦` logo left · links: Try it · How it works · Results · GitHub (outline pill). Background `rgba(10,10,10,.7)` + `backdrop-filter: blur(12px)`, bottom 1px line appears after scroll.

### 1. Hero (100vh)
- Mono label top: `GLOBAL AI HACKATHON · STALE-ANSWER DETECTOR`
- Headline: **Every fact has an *expiry date.***
- Sub (max 2 lines): "AI answers go stale. FactTTL finds the claims that expired, checks them on the live web, and fixes them."
- Buttons: **Try it →** (white) · **See how it works** (outline)
- Right/behind: doodle cluster (section 3).
- Bottom: slow marquee of fact types: `PRICES ✦ API VERSIONS ✦ LAWS ✦ LEADERSHIP ✦ PLANS ✦ LIMITS ✦` (mono, `--fg-3`).

### 2. Console ("Try it") — the product
Two columns on desktop, stacked on mobile.
- **Left: Input card.** Tabs: `Paste answer` | `Ask a question`. Large textarea. Sample chips (`Pricing`, `API version`, `CEO`). Toggles (pill switches): `Use cache`, `Simulate outage`. Button **Verify**.
- **Right: Result panel.**
  - Top: **Score ring** (big number counts up 0→N, ring stroke animates) + band label.
  - Stat strip (mono, 4–6 cells): `CLAIMS 7 · SEARCHED 3 · SKIPPED 4 · CACHE 0 · CREDITS SAVED 4 · 8.2s`.
  - Badge row: `ROUTED VIA groq` / `FALLBACK → gemini` (with a tiny dashed-arrow icon).
  - **Claim cards** (stagger in, 80ms apart): dot + type tag + claim text; if stale, old value is struck through then new value types/fades in below with a left 2px `--fresh` line; sources as mono link chips; **TTL ring** (small circle showing time left, e.g. `23h`).
  - **Corrected answer** block: tabs `Original | Corrected | Diff`. Diff highlights changes with underline (no background colours).
  - Copy buttons: `Copy corrected`, `Copy JSON`.

### 3. How it works (light section — inverted colours)
Four steps in a row, connected by a **dashed line that draws in on scroll**: `01 Split` → `02 Flag` → `03 Verify (Tavily)` → `04 Fix + Expire`. Each has a small doodle. Below: a "Bifrost + Tavily" two-cell card: *Tavily = the proof. Bifrost = the reliability.*

### 4. Results
Benchmark table (mono numbers), 3 big stat numbers (`STALE CAUGHT 14/15`, `FALSE ALARMS 1`, `SEARCH CREDITS SAVED 57%`) using real values from `bench/results.md`. Honest footnote: "40 hand-labeled claims, Nov 2026."

### 5. Footer
Giant outlined wordmark "FactTTL" (stroke only, `-webkit-text-stroke: 1px var(--line-strong)`), GitHub link, team names, "Built for Global AI Hackathon 2026".

## 5. Components

| Component | Spec |
|---|---|
| Button primary | bg `--fg`, text `--bg`, radius pill, padding `14px 26px`, hover: translateY(-2px) + arrow slides 4px |
| Button outline | 1px `--line-strong`, hover bg `rgba(255,255,255,.06)` |
| Card | bg `--surface`, 1px `--line`, radius `--r-lg`, padding 24px; hover border `--line-strong` |
| Pill switch | 40×22, thumb slides with `--ease` |
| Verdict dot | 8px circle; fresh/stale/unsure colours; stale dot gently pulses |
| Tag | mono 11px uppercase, 1px outline, radius pill |
| TTL ring | SVG circle r=14, stroke `--line`, progress stroke in verdict colour, label inside in mono |
| Source chip | mono 11px, `domain.com ↗`, underline on hover |
| Skeleton | animated shimmer on `--surface` (opacity wave, no colour) |

## 6. Motion spec (smooth, never slow)

| What | How |
|---|---|
| Page load | Hero words reveal line by line: `translateY(100%)→0` inside `overflow:hidden` wrappers, 80ms stagger, `--ease`, .9s |
| Doodles | stroke-draw 1.2s, then slow float |
| Scroll reveal | `IntersectionObserver` adds `.in`; elements fade + rise 24px, `--ease`, .7s |
| Nav | border + blur fade in after 40px scroll |
| Buttons | magnetic hover (follow cursor ≤ 8px) on primary hero button |
| Verify click | button becomes spinner ring; progress ticker cycles `Splitting claims → Checking the live web → Judging evidence → Writing fixes` |
| Claim cards | stagger in 80ms, rise 16px |
| Stale fix | strike-through animates left→right (scaleX 0→1, .5s), then new text fades in |
| Score | count-up 0→N over 1.2s (`requestAnimationFrame`), ring `stroke-dashoffset` animates same time |
| Tab switch | content cross-fade 200ms, underline slides |
| Cursor | subtle custom dot that grows over links (desktop only, optional) |

```css
.reveal { opacity: 0; transform: translateY(24px); transition: opacity .7s var(--ease), transform .7s var(--ease); }
.reveal.in { opacity: 1; transform: none; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
```

## 7. States (design every one)

- **Empty:** muted doodle + "Paste an AI answer to begin."
- **Loading:** skeleton cards + progress ticker.
- **Error:** card with 1px `--stale` left line, plain sentence, `Try again` button.
- **Gateway offline:** top banner "Bifrost gateway is offline" with run command in mono.
- **No volatile claims:** friendly "Nothing here can go stale ✦ all claims are stable."
- **From cache:** mono tag `FROM CACHE · EXPIRES IN 23H`.

## 8. Responsive

- Breakpoints: `640px`, `1024px`. Console stacks under 1024.
- Tap targets ≥ 44px. Textarea min-height 180px on mobile.
- Hero headline never overflows (fluid clamp). Test at 375px width.

## 9. Voice / copy

Short. Confident. Lowercase-friendly. No jargon walls. Examples: "Facts expire. Now your AI knows." · "3 searched. 4 skipped. 4 credits saved." · "Can't verify" (not "Unverifiable error").

## 10. Accessibility

Contrast ≥ 4.5:1 for body (`--fg-2` on `--bg` passes). Verdict is never colour-only: dot + word. Focus ring `2px solid var(--fg)` offset 3px. All doodles `aria-hidden="true"`. Respect reduced motion.
