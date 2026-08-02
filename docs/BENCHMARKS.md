# Offline benchmarks (published)

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

## Published snapshot

- **Captured:** 2026-08-02T20:29:46Z
- **Python:** 3.11.15
- **Overall ok:** True
- **Wall time:** 30.8 s (full suite unless otherwise noted)
- **Entry:** `python backend/benchmark_harness.py`

### Summary

| Suite | OK | Seconds | Key metrics |
|---|---|---|---|
| `math_closed_form` | yes | 0.0053 | checks_passed=14 / 14 |
| `math_coverage` | yes | 0.1017 | mean_coverage=0.9085; min_coverage=0.849; cells_below_0.82=0 |
| `math_lcb_gate` | yes | 0.0001 | lcb_success_reachable_under_defaults=**False**; n_needed_perfect=80 |
| `open_loop` | yes | 0.3637 | fires=80; hit_rate_plaintext=1.0; latency_p50_ms=1.82; registry_ops=152 |
| `closed_loop` | yes | 3.731 | runs=10; hit_rate=1.0; latency_p50_ms=567.59 |
| `optimizer_ga` | yes | 25.99 | success_flag_rate=1.0; lcb_stop_rate=0.0; mean_queries=40 |
| `export` | yes | 0.0001 | formats_ok=3 |
| `security` | yes | 0.6022 | checks_passed=6 / 6 |

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
