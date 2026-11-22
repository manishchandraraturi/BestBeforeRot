"""P8 benchmark: run every hand-labelled claim through the real pipeline, cache off.

    python bench/run_bench.py

Reads bench/claims.jsonl, calls pipeline.verify() once per claim with use_cache=False,
waits between claims so the free Tavily/LLM tiers are not hammered, and writes
bench/results.md with a per-claim table plus the headline metrics.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import time
from datetime import date
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
CLAIMS_PATH = BENCH_DIR / "claims.jsonl"
RESULTS_PATH = BENCH_DIR / "results.md"
# A bench-local DB keeps the demo cache untouched and guarantees every search is live
# (a warm search cache would make "credits used" a lie).
DB_PATH = BENCH_DIR / ".bench_cache.db"
os.environ["CACHE_DB"] = str(DB_PATH)
# `python bench/run_bench.py` puts bench/ on sys.path, not the repo root.
PROJECT_ROOT = str(BENCH_DIR.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.config import settings  # noqa: E402
from app.models import Claim, ClaimStatus  # noqa: E402
from app.pipeline import verify  # noqa: E402
from app.services import bifrost_client, tavily_client  # noqa: E402

SLEEP_S = 1.2
MAX_ATTEMPTS = 2
RETRY_SLEEP_S = 5.0
# The Windows console defaults to cp1252; claim text and model output are not.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class Row:
    """One claim's benchmark outcome."""

    def __init__(self, index: int, item: dict) -> None:
        self.index = index
        self.text: str = item["text"]
        self.label: str = item["label"]
        self.type: str = item.get("type", "other")
        self.truth_url: str | None = item.get("truth_url")
        self.verdict: str = "none"
        self.status: str = ""
        self.confidence: float | None = None
        self.corrected: str | None = None
        self.sources: int = 0
        self.latency_ms: int = 0
        self.credits: int = 0
        self.error: str | None = None

    @property
    def hit(self) -> bool:
        """True when the pipeline said exactly what the hand label says."""
        return self.verdict == self.label


def _load() -> list[dict]:
    """Read and validate claims.jsonl before any credit is spent."""
    items: list[dict] = []
    for number, line in enumerate(CLAIMS_PATH.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        if item.get("label") not in ("stale", "fresh", "unverifiable"):
            raise SystemExit(f"claims.jsonl line {number}: bad label {item.get('label')!r}")
        if not str(item.get("text", "")).strip():
            raise SystemExit(f"claims.jsonl line {number}: empty text")
        items.append(item)
    return items


def _words(text: str) -> set[str]:
    """Lowercase word set, punctuation stripped, for matching an answer back to its claim."""
    return {"".join(char for char in word.lower() if char.isalnum()) for word in text.split()}


def _best_claim(claims: list[Claim], text: str) -> Claim | None:
    """Pick the extracted claim that overlaps the benchmark sentence the most."""
    if not claims:
        return None
    wanted = _words(text)
    return max(claims, key=lambda claim: len(wanted & _words(claim.text)))


async def _run_one(index: int, item: dict) -> Row:
    """Verify one claim (cache off) and copy the verdict onto a Row; never raise."""
    row = Row(index, item)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        started = time.perf_counter()
        try:
            result = await verify(item["text"], use_cache=False)
        except Exception as exc:  # one bad claim must not end the benchmark
            row.latency_ms = int((time.perf_counter() - started) * 1000)
            row.error = f"{type(exc).__name__}: {exc}"[:200]
            print(f"  ! {type(exc).__name__}: {exc} (attempt {attempt})", flush=True)
            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(RETRY_SLEEP_S)
                continue
            row.verdict = "error"
            return row

        claim = _best_claim(result.claims, item["text"])
        row.latency_ms = result.stats.latency_ms
        row.credits = result.stats.tavily_credits_used
        row.error = None
        if claim is None:
            row.verdict = "no-claim"
            row.status = "no-claim"
            return row
        row.status = str(claim.status)
        row.confidence = claim.confidence
        row.corrected = claim.corrected_text
        row.sources = len(claim.sources)
        if claim.status is ClaimStatus.SKIPPED_STABLE or claim.verdict is None:
            row.verdict = "skipped_stable"
        else:
            row.verdict = str(claim.verdict)
        return row
    return row


def _pct(numerator: int, denominator: int) -> str:
    """Percentage with one decimal, or an em dash when the denominator is zero."""
    if not denominator:
        return "—"
    return f"{100 * numerator / denominator:.1f}%"


def _metrics(rows: list[Row]) -> dict:
    """Compute the confusion matrix and the headline numbers from the rows."""
    stale_rows = [row for row in rows if row.label == "stale"]
    fresh_rows = [row for row in rows if row.label == "fresh"]
    unverifiable_rows = [row for row in rows if row.label == "unverifiable"]

    caught = [row for row in stale_rows if row.verdict == "stale"]
    called_stale = [row for row in rows if row.verdict == "stale"]
    false_alarms = [row for row in fresh_rows if row.verdict == "stale"]
    fresh_ok = [row for row in fresh_rows if row.verdict == "fresh"]
    abstained = [row for row in unverifiable_rows if row.verdict == "unverifiable"]

    latencies = [row.latency_ms for row in rows if row.error is None and row.latency_ms]
    credits = sum(row.credits for row in rows)
    errors = [row for row in rows if row.error]
    skipped = [row for row in rows if row.verdict == "skipped_stable"]
    return {
        "total": len(rows),
        "stale_total": len(stale_rows),
        "fresh_total": len(fresh_rows),
        "unverifiable_total": len(unverifiable_rows),
        "caught": len(caught),
        "stale_recall": _pct(len(caught), len(stale_rows)),
        "false_alarms": len(false_alarms),
        "false_alarm_rate": _pct(len(false_alarms), len(fresh_rows)),
        "stale_precision": _pct(len(caught), len(called_stale)),
        "called_stale": len(called_stale),
        "fresh_ok": len(fresh_ok),
        "fresh_rate": _pct(len(fresh_ok), len(fresh_rows)),
        "abstained": len(abstained),
        "abstain_rate": _pct(len(abstained), len(unverifiable_rows)),
        "unverifiable_called_stale": len([r for r in unverifiable_rows if r.verdict == "stale"]),
        "unverifiable_called_fresh": len([r for r in unverifiable_rows if r.verdict == "fresh"]),
        "credits": credits,
        "baseline_credits": len(rows),
        "credits_saved_pct": _pct(len(rows) - credits, len(rows)),
        "latency_avg": round(statistics.mean(latencies)) if latencies else 0,
        "latency_median": round(statistics.median(latencies)) if latencies else 0,
        "skipped": len(skipped),
        "errors": len(errors),
        "accuracy": _pct(sum(1 for row in rows if row.hit), len(rows)),
    }


def _cell(text: str | None) -> str:
    """One safe Markdown table cell."""
    if not text:
        return "—"
    return " ".join(str(text).split()).replace("|", "\\|")[:160]


def _render(rows: list[Row], m: dict, wall_s: float) -> str:
    """Build bench/results.md from the run."""
    lines: list[str] = [
        "# FactTTL benchmark — 40 hand-labelled claims",
        "",
        f"Generated: {date.today().isoformat()} · wall time {wall_s:.0f} s",
        "",
        "Every claim was sent through the real pipeline (`app.pipeline.verify`) one at a time "
        "with `use_cache=False`, against a bench-local SQLite file that is deleted before the run, "
        "so every verdict below comes from a live Tavily search and a live judge call.",
        "",
        f"Models via Bifrost: extraction `{settings.WEAK_MODEL or settings.PRIMARY_MODEL}`, "
        f"judge `{settings.PRIMARY_MODEL}`, fallback `{settings.FALLBACK_MODEL}`.",
        "Labels were set by hand from the official source in `truth_url` before the run.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Claims tested | {m['total']} ({m['stale_total']} stale · {m['fresh_total']} fresh · {m['unverifiable_total']} unverifiable) |",
        f"| Stale recall | {m['caught']}/{m['stale_total']} ({m['stale_recall']}) |",
        f"| Stale precision | {m['caught']}/{m['called_stale']} ({m['stale_precision']}) |",
        f"| False-alarm rate | {m['false_alarms']}/{m['fresh_total']} fresh claims called stale ({m['false_alarm_rate']}) |",
        f"| Unverifiable handling | {m['abstained']}/{m['unverifiable_total']} said \"can't verify\" ({m['abstain_rate']}) |",
        f"| Fresh claims confirmed | {m['fresh_ok']}/{m['fresh_total']} ({m['fresh_rate']}) |",
        f"| Claim-level accuracy | {m['accuracy']} |",
        f"| Tavily credits used | {m['credits']} |",
        f"| \"Search everything\" baseline | {m['baseline_credits']} credits (1 per claim) |",
        f"| Search credits saved | {m['credits_saved_pct']} ({m['baseline_credits'] - m['credits']} of {m['baseline_credits']}) |",
        f"| Avg latency per claim (cold) | {m['latency_avg'] / 1000:.1f} s (median {m['latency_median'] / 1000:.1f} s) |",
        f"| Claims skipped as stable | {m['skipped']} |",
        f"| Pipeline errors | {m['errors']} |",
        "",
        "## Confusion matrix",
        "",
        "| label \\ verdict | stale | fresh | unverifiable | skipped_stable | error |",
        "|---|---|---|---|---|---|",
    ]
    for label in ("stale", "fresh", "unverifiable"):
        counts = {
            verdict: sum(1 for row in rows if row.label == label and row.verdict == verdict)
            for verdict in ("stale", "fresh", "unverifiable", "skipped_stable", "error")
        }
        lines.append(
            f"| {label} | {counts['stale']} | {counts['fresh']} | {counts['unverifiable']} "
            f"| {counts['skipped_stable']} | {counts['error']} |"
        )

    lines += [
        "",
        "## Per-claim results",
        "",
        "| # | label | verdict | type | conf | sources | ms | claim |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        confidence = "—" if row.confidence is None else f"{row.confidence:.2f}"
        mark = "" if row.hit else " ✗"
        lines.append(
            f"| {row.index} | {row.label} | {row.verdict}{mark} | {row.type} | {confidence} "
            f"| {row.sources} | {row.latency_ms} | {_cell(row.text)} |"
        )

    misses = [row for row in rows if not row.hit]
    lines += ["", "## Misses and false alarms", ""]
    if not misses:
        lines.append("None — every claim matched its hand label.")
    else:
        lines.append("| # | label | verdict | claim | corrected | reason |")
        lines.append("|---|---|---|---|---|---|")
        for row in misses:
            lines.append(
                f"| {row.index} | {row.label} | {row.verdict} | {_cell(row.text)} "
                f"| {_cell(row.corrected)} | {_cell(row.error or row.status)} |"
            )
    lines.append("")
    return "\n".join(lines)


async def main() -> int:
    """Run the whole benchmark and write results.md."""
    items = _load()
    for suffix in ("", "-wal", "-shm"):
        Path(str(DB_PATH) + suffix).unlink(missing_ok=True)

    print(f"CLAIMS: {len(items)} ({CLAIMS_PATH})")
    print(f"CACHE: off · DB {DB_PATH} (deleted before the run)")
    print(f"MODELS: extract={settings.WEAK_MODEL or settings.PRIMARY_MODEL} judge={settings.PRIMARY_MODEL}")
    print("")

    started = time.perf_counter()
    rows: list[Row] = []
    for index, item in enumerate(items, 1):
        row = await _run_one(index, item)
        rows.append(row)
        context = f"{row.latency_ms / 1000:5.1f}s {row.credits}c src={row.sources}"
        if row.error:
            context += f" ERROR {row.error}"
        print(
            f"[{index:2d}/{len(items)}] {row.label:<12} -> {row.verdict:<14} {context}  {row.text[:58]}",
            flush=True,
        )
        if index < len(items):
            await asyncio.sleep(SLEEP_S)
    wall_s = time.perf_counter() - started

    metrics = _metrics(rows)
    RESULTS_PATH.write_text(_render(rows, metrics, wall_s), encoding="utf-8")

    print("")
    print(f"STALE RECALL:      {metrics['caught']}/{metrics['stale_total']} ({metrics['stale_recall']})")
    print(f"STALE PRECISION:   {metrics['caught']}/{metrics['called_stale']} ({metrics['stale_precision']})")
    print(
        f"FALSE ALARMS:      {metrics['false_alarms']}/{metrics['fresh_total']} "
        f"({metrics['false_alarm_rate']})"
    )
    print(
        f"UNVERIFIABLE:      {metrics['abstained']}/{metrics['unverifiable_total']} "
        f"({metrics['abstain_rate']})"
    )
    print(f"ACCURACY:          {metrics['accuracy']}")
    print(f"TAVILY CREDITS:    {metrics['credits']} used vs {metrics['baseline_credits']} baseline ({metrics['credits_saved_pct']} saved)")
    print(f"LATENCY:           avg {metrics['latency_avg']} ms · median {metrics['latency_median']} ms")
    print(f"ERRORS:            {metrics['errors']}")
    print(f"WROTE:             {RESULTS_PATH}")

    await tavily_client.aclose()
    await bifrost_client.aclose()
    return 0 if metrics["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
