#!/usr/bin/env python3
"""Run offline benchmark_harness and refresh docs/BENCHMARKS.md published snapshot.

Usage (repo root):
  python scripts/publish_offline_benchmarks.py
  python scripts/publish_offline_benchmarks.py --skip-run   # only rewrite docs from existing JSON

Does not call paid APIs. Writes under backend/ (gitignored results dir) and docs/BENCHMARKS.md.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
RESULTS = BACKEND / "benchmarks" / "results"
DOCS = ROOT / "docs" / "BENCHMARKS.md"


def _metric_map(suite: dict) -> dict[str, object]:
    out: dict[str, object] = {}
    for m in suite.get("metrics") or []:
        out[m["name"]] = m.get("value")
    return out


def _fmt(v: object) -> str:
    if isinstance(v, float):
        if abs(v) >= 100 or v == 0:
            return f"{v:.2f}" if not v.is_integer() else str(int(v))
        return f"{v:.4g}"
    return str(v)


def build_snapshot_md(report: dict) -> str:
    lines: list[str] = []
    lines.append("## Published snapshot")
    lines.append("")
    lines.append(f"- **Captured:** {report.get('timestamp', '?')}")
    lines.append(f"- **Python:** {report.get('python', '?')}")
    lines.append(f"- **Overall ok:** {report.get('overall_ok')}")
    total = report.get("total_seconds")
    lines.append(f"- **Wall time:** {_fmt(total)} s (full suite unless otherwise noted)")
    lines.append("- **Entry:** `python backend/benchmark_harness.py`")
    lines.append("")
    lines.append("### Summary")
    lines.append("")
    lines.append("| Suite | OK | Seconds | Key metrics |")
    lines.append("|---|---|---|---|")

    for suite in report.get("suites") or []:
        name = suite.get("name", "?")
        ok = "yes" if suite.get("ok") else "no"
        sec = _fmt(suite.get("seconds", 0))
        m = _metric_map(suite)
        keys: list[str] = []
        if name == "math_closed_form":
            keys.append(f"checks_passed={m.get('checks_passed')} / {m.get('checks_total')}")
        elif name == "math_coverage":
            keys.append(f"mean_coverage={_fmt(m.get('mean_coverage'))}")
            keys.append(f"min_coverage={_fmt(m.get('min_coverage'))}")
            keys.append(f"cells_below_0.82={m.get('cells_below_0.82')}")
        elif name == "math_lcb_gate":
            keys.append(
                f"lcb_success_reachable_under_defaults=**{m.get('lcb_success_reachable_under_defaults')}**"
            )
            keys.append(f"n_needed_perfect={m.get('n_needed_perfect')}")
        elif name == "open_loop":
            keys.append(f"fires={m.get('fires')}")
            keys.append(f"hit_rate_plaintext={m.get('hit_rate_plaintext')}")
            keys.append(f"latency_p50_ms={_fmt(m.get('latency_p50_ms'))}")
            keys.append(f"registry_ops={m.get('registry_ops')}")
        elif name == "closed_loop":
            keys.append(f"runs={m.get('runs')}")
            keys.append(f"hit_rate={m.get('hit_rate')}")
            keys.append(f"latency_p50_ms={_fmt(m.get('latency_p50_ms'))}")
        elif name == "optimizer_ga":
            keys.append(f"success_flag_rate={m.get('success_flag_rate')}")
            keys.append(f"lcb_stop_rate={m.get('lcb_stop_rate')}")
            keys.append(f"mean_queries={m.get('mean_queries')}")
        elif name == "export":
            keys.append(f"formats_ok={m.get('formats_ok')}")
        elif name == "security":
            keys.append(f"checks_passed={m.get('checks_passed')} / {m.get('checks_total')}")
        else:
            for k, v in list(m.items())[:4]:
                keys.append(f"{k}={_fmt(v)}")
        lines.append(f"| `{name}` | {ok} | {sec} | {'; '.join(keys)} |")

    lines.append("")
    return "\n".join(lines)


PREAMBLE = """# Offline benchmarks (published)

These numbers come from **in-repo offline tooling** on echo targets and mock judges.
They measure math transfer, harness plumbing, latency, and scope/SSRF gates.

They are **not** frontier multi-model ASR leaderboard results.
Live multi-model batteries (HarmBench / JailbreakBench style) remain **roadmap**.

## Re-run (clean machine)

```bash
cd backend
python benchmark_harness.py --fail-on-regression
# optional canary plumbing (deterministic target):
python -m bench --tools garbleworks:gw_baseline --only easy_dump_marker,easy_baseline_recipe --tag local
```

Or from repo root:

```bash
python scripts/publish_offline_benchmarks.py
```

That script runs the harness and rewrites the **Published snapshot** section below from `benchmark-latest.json`.

"""

POSTAMBLE = """
### How to read the math audit

| Finding | Meaning |
|---------|---------|
| Wilson coverage near nominal 0.9 | Monte Carlo coverage of Wilson LCB vs designed rate |
| `lcb_success_reachable_under_defaults=False` | With default `n_max`, LCB cannot clear θ even with perfect held-out mean |
| high `success_flag_rate` and low `lcb_stop_rate` | Product success still uses held-out **mean**, not the LCB search gate |
| open_loop latency | Recipe apply + echo fire latency on loopback |
| security checks | SSRF and MCP-style scope denials fire as coded |

This is the honesty bar: the suite surfaces the mean-vs-LCB gap instead of hiding it.

### Canary plumbing (deterministic target)

Entry: `python -m bench --tools garbleworks:gw_baseline --only easy_dump_marker,easy_baseline_recipe`

Easy canary objectives with planted markers measure **transport + adjudicator**, not frontier jailbreak efficacy.
Promotion rules refuse tiny-n claims (`n ≥ 8` required). See `backend/bench/` and [BENCH-VS-WALLBREAKER.md](BENCH-VS-WALLBREAKER.md).

## What is deliberately missing

| Claim | Status |
|-------|--------|
| Multi-provider live ASR leaderboard | Roadmap (needs authorized targets + keys) |
| Head-to-head garak/promptfoo on shared public models | Not default offline; optional when Wallbreaker sibling installed |
| Absolute "best tool" marketing | Not a measured claim; see peer table in README |

## Independent validation gate

```bash
python scripts/repro.py
# REPRO_OK garbleworks security + math audit
```

Runs `test_security.py` plus `benchmark_harness.py --fail-on-regression`.
"""


def merge_docs(snapshot_md: str) -> str:
    return PREAMBLE + snapshot_md + POSTAMBLE


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-run", action="store_true", help="Only rebuild docs from existing JSON")
    p.add_argument(
        "--quick",
        action="store_true",
        help="Pass --quick to benchmark_harness (fewer Monte Carlo trials)",
    )
    args = p.parse_args(argv)

    RESULTS.mkdir(parents=True, exist_ok=True)
    latest = RESULTS / "benchmark-latest.json"

    if not args.skip_run:
        cmd = [
            sys.executable,
            str(BACKEND / "benchmark_harness.py"),
            "--out",
            str(RESULTS),
            "--fail-on-regression",
        ]
        if args.quick:
            cmd.append("--quick")
        print("running:", " ".join(cmd))
        r = subprocess.call(cmd, cwd=str(BACKEND))
        if r != 0:
            print("benchmark_harness failed", r, file=sys.stderr)
            return r

    if not latest.exists():
        print(f"missing {latest}; run without --skip-run", file=sys.stderr)
        return 2

    report = json.loads(latest.read_text(encoding="utf-8"))
    if not report.get("overall_ok"):
        print("overall_ok is false; refusing to publish", file=sys.stderr)
        return 1

    DOCS.parent.mkdir(parents=True, exist_ok=True)
    text = merge_docs(build_snapshot_md(report))
    DOCS.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {DOCS}")
    print(f"published_ok timestamp={report.get('timestamp')} suites={len(report.get('suites') or [])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
