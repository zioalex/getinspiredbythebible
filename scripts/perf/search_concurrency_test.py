#!/usr/bin/env python3
"""
Search concurrency / degradation test for scripture vector search.

Hammers ``GET {base}/api/v1/scripture/search`` at increasing concurrency levels and
reports latency percentiles, throughput, and error rate per level, flagging the
concurrency at which p95 latency degrades. That endpoint is public, NOT rate-limited
(rate limiting is chat-only), and LLM-free, so it isolates the per-translation partial
HNSW index + Postgres capacity that Phase 2 Step B tunes (migration 007, B2s SKU).

Two workload shapes answer "same vs different language/bible":
  same   - every request uses ONE translation (single partial index, best cache case)
  multi  - requests round-robin across translations (many partial indexes compete for
           the DB buffer cache: the thrash case that exposes an undersized box)
  both   - run ``same`` then ``multi`` and print both tables

Example:
  python scripts/perf/search_concurrency_test.py \\
      --base-url https://api.voxquieta.org \\
      --mode both --concurrency 1,2,4,8,16,32,64 --requests-per-level 200

Exit code is non-zero when degradation is detected (handy for CI gating).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass

import httpx

# Default translation -> language-matched query. Override with --translations / a
# JSON file via --queries-file. The query language need not match the translation
# (embeddings are cross-lingual), but matching keeps `multi` mode realistic.
TRANSLATION_QUERIES: dict[str, str] = {
    "web": "I feel anxious about my future",
    "kjv": "comfort for grief and loss",
    "schlachter": "Was sagt die Bibel über Geld?",
    "valera": "versículos sobre el perdón",
    "ita1927": "conforto nel dolore",
    "ls1910": "versets sur l'espérance",
    "almeida": "paz interior e ansiedade",
    "synodal": "стихи о любви и прощении",
    "arabicsv": "آيات عن الصبر",
    "cuv": "关于宽恕的经文",
    "hindi": "क्षमा के बारे में वचन",
    "krv": "용서에 관한 성경 구절",
}


@dataclass
class LevelResult:
    mode: str
    concurrency: int
    requests: int
    ok: int
    errors: int
    error_rate: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    mean_ms: float
    throughput_rps: float
    degraded: bool


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolated percentile (p in 0..100)."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


async def _one_request(
    client: httpx.AsyncClient,
    url: str,
    q: str,
    translation: str,
    max_verses: int,
    max_passages: int,
    sem: asyncio.Semaphore,
    timeout: float,
) -> tuple[float, bool]:
    """Issue one search request; return (latency_ms, ok)."""
    params = {
        "q": q,
        "translation": translation,
        "max_verses": max_verses,
        "max_passages": max_passages,
    }
    async with sem:
        start = time.perf_counter()
        try:
            resp = await client.get(url, params=params, timeout=timeout)
            ok = resp.status_code == 200
        except Exception:
            ok = False
        return (time.perf_counter() - start) * 1000.0, ok


def _select(mode: str, i: int, translations: list[str], queries: list[str]) -> tuple[str, str]:
    """Pick (query, translation) for request i according to the workload mode."""
    if mode == "same":
        # Fixed translation (first entry), rotate the query pool to vary embeddings.
        return queries[i % len(queries)], translations[0]
    # multi: round-robin translations, language-matched query when available.
    t = translations[i % len(translations)]
    return TRANSLATION_QUERIES.get(t, queries[i % len(queries)]), t


async def run_level(
    client: httpx.AsyncClient,
    url: str,
    mode: str,
    concurrency: int,
    n: int,
    translations: list[str],
    queries: list[str],
    max_verses: int,
    max_passages: int,
    timeout: float,
) -> tuple[list[float], int, int, float]:
    """Run n requests bounded to `concurrency`. Returns (latencies, ok, err, wall_s)."""
    sem = asyncio.Semaphore(concurrency)
    tasks = []
    for i in range(n):
        q, t = _select(mode, i, translations, queries)
        tasks.append(
            _one_request(client, url, q, t, max_verses, max_passages, sem, timeout)
        )
    wall_start = time.perf_counter()
    results = await asyncio.gather(*tasks)
    wall_s = time.perf_counter() - wall_start
    latencies = [lat for lat, ok in results if ok]
    ok = sum(1 for _, ok in results if ok)
    err = n - ok
    return latencies, ok, err, wall_s


async def run_mode(
    client: httpx.AsyncClient,
    url: str,
    mode: str,
    levels: list[int],
    n: int,
    translations: list[str],
    queries: list[str],
    args: argparse.Namespace,
) -> list[LevelResult]:
    print(f"\n=== mode={mode}  translations={'/'.join(translations) if mode == 'multi' else translations[0]} ===")
    header = f"{'conc':>5} {'req':>5} {'ok':>5} {'err':>4} {'p50':>8} {'p95':>9} {'p99':>9} {'max':>9} {'rps':>8} {'p95/base':>9}"
    print(header)
    print("-" * len(header))

    results: list[LevelResult] = []
    baseline_p95: float | None = None
    for conc in levels:
        lat, ok, err, wall_s = await run_level(
            client, url, mode, conc, n, translations, queries,
            args.max_verses, args.max_passages, args.timeout,
        )
        p50 = percentile(lat, 50)
        p95 = percentile(lat, 95)
        p99 = percentile(lat, 99)
        mx = max(lat) if lat else 0.0
        mean = statistics.fmean(lat) if lat else 0.0
        rps = n / wall_s if wall_s > 0 else 0.0
        err_rate = err / n if n else 0.0

        if baseline_p95 is None:
            baseline_p95 = p95 if p95 > 0 else None
        ratio = (p95 / baseline_p95) if baseline_p95 else 0.0
        degraded = (ratio >= args.degradation_factor) or (err_rate > args.max_error_rate)

        print(
            f"{conc:>5} {n:>5} {ok:>5} {err:>4} {p50:>7.0f}m {p95:>8.0f}m "
            f"{p99:>8.0f}m {mx:>8.0f}m {rps:>8.1f} {ratio:>8.2f}x"
            + ("  <-- DEGRADED" if degraded else "")
        )
        results.append(LevelResult(
            mode=mode, concurrency=conc, requests=n, ok=ok, errors=err,
            error_rate=round(err_rate, 4), p50_ms=round(p50, 1), p95_ms=round(p95, 1),
            p99_ms=round(p99, 1), max_ms=round(mx, 1), mean_ms=round(mean, 1),
            throughput_rps=round(rps, 2), degraded=degraded,
        ))

    first = next((r for r in results if r.degraded), None)
    if first:
        print(f"--> DEGRADATION at concurrency={first.concurrency} "
              f"(p95={first.p95_ms:.0f}ms, {first.p95_ms / (baseline_p95 or 1):.1f}x baseline, "
              f"err_rate={first.error_rate:.1%})")
    else:
        print("--> no degradation detected across tested levels")
    return results


def write_summary(all_results: list[LevelResult]) -> None:
    """Append a markdown table to GITHUB_STEP_SUMMARY if running in CI."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = ["## Search Concurrency Test\n",
             "| mode | conc | ok | err | p50 | p95 | p99 | rps | degraded |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in all_results:
        lines.append(
            f"| {r.mode} | {r.concurrency} | {r.ok} | {r.errors} | {r.p50_ms:.0f} | "
            f"{r.p95_ms:.0f} | {r.p99_ms:.0f} | {r.throughput_rps:.1f} | "
            f"{'⚠️' if r.degraded else '✅'} |"
        )
    with open(path, "a") as f:
        f.write("\n".join(lines) + "\n")


async def main_async(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    url = f"{base}/api/v1/scripture/search"
    levels = [int(x) for x in args.concurrency.split(",") if x.strip()]
    translations = [t.strip() for t in args.translations.split(",") if t.strip()]
    if args.translation:  # explicit same-mode translation goes first
        translations = [args.translation] + [t for t in translations if t != args.translation]
    queries = list(TRANSLATION_QUERIES.values())

    modes = ["same", "multi"] if args.mode == "both" else [args.mode]
    max_conn = max(levels) + 10

    print(f"Target: {url}")
    print(f"Levels: {levels}  requests/level: {args.requests_per_level}  warmup: {args.warmup}")
    print(f"Degradation: p95 >= {args.degradation_factor}x baseline OR err_rate > {args.max_error_rate:.0%}")

    all_results: list[LevelResult] = []
    limits = httpx.Limits(max_connections=max_conn, max_keepalive_connections=max_conn)
    async with httpx.AsyncClient(limits=limits, follow_redirects=True) as client:
        if args.warmup > 0:
            # Warm DB cache, connection pool, and HTTP keep-alive before measuring.
            await run_level(
                client, url, modes[0], min(4, max(levels)), args.warmup,
                translations, queries, args.max_verses, args.max_passages, args.timeout,
            )
        for mode in modes:
            all_results += await run_mode(
                client, url, mode, levels, args.requests_per_level, translations, queries, args,
            )

    with open(args.out, "w") as f:
        json.dump([asdict(r) for r in all_results], f, indent=2)
    print(f"\nResults written to {args.out}")
    write_summary(all_results)

    return 1 if any(r.degraded for r in all_results) else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default=os.environ.get("BACKEND_URL", ""),
                   help="API base URL, e.g. https://api.voxquieta.org (or set BACKEND_URL)")
    p.add_argument("--mode", choices=["same", "multi", "both"], default="both")
    p.add_argument("--concurrency", default="1,2,4,8,16,32,64",
                   help="Comma-separated concurrency levels")
    p.add_argument("--requests-per-level", type=int, default=200)
    p.add_argument("--warmup", type=int, default=10, help="Warmup requests before measuring")
    p.add_argument("--translations", default=",".join(TRANSLATION_QUERIES.keys()),
                   help="Comma-separated translation codes for `multi` mode")
    p.add_argument("--translation", default="",
                   help="Translation for `same` mode (default: first of --translations)")
    p.add_argument("--max-verses", type=int, default=10)
    p.add_argument("--max-passages", type=int, default=2,
                   help="Set 0 to isolate the verses partial index")
    p.add_argument("--timeout", type=float, default=30.0, help="Per-request timeout (s)")
    p.add_argument("--degradation-factor", type=float, default=2.0,
                   help="Flag a level when its p95 >= this multiple of the baseline p95")
    p.add_argument("--max-error-rate", type=float, default=0.05,
                   help="Flag a level when its error rate exceeds this fraction")
    p.add_argument("--out", default="search_perf_results.json")
    return p.parse_args(argv)


def main() -> int:
    args = parse_args()
    if not args.base_url:
        print("error: --base-url (or BACKEND_URL env) is required", file=sys.stderr)
        return 2
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
