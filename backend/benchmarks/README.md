# Garbleworks offline benchmarks

Runnable measurement suite for math transfer and harness plumbing. No external
APIs. Echo target + mock judges only.

## Run

```powershell
cd C:\code\garbleworks\backend
.\.venv\Scripts\python.exe benchmark_harness.py
.\.venv\Scripts\python.exe benchmark_harness.py --quick
.\.venv\Scripts\python.exe benchmark_harness.py --suite math_lcb_gate,optimizer_ga
.\.venv\Scripts\python.exe benchmark_harness.py --fail-on-regression
```

Results land in `backend/benchmarks/results/`:

- `benchmark-latest.json` / `.md` - last run
- `benchmark-<UTC timestamp>.json` / `.md` - archived run

## Suites

| Suite | What it measures |
|---|---|
| `math_closed_form` | EB / Hoeffding / Wilson / LSE / softmax golden checks |
| `math_coverage` | Monte Carlo Wilson LCB coverage vs nominal ~90% |
| `math_lcb_gate` | Whether LCB can clear θ under default optimizer hyperparams |
| `open_loop` | Recipe + fire latency / hit rate on echo |
| `closed_loop` | Adaptive refine hit rate (`campaign_runner`) |
| `optimizer_ga` | GA success_flag rate vs LCB stop rate (math audit check) |
| `export` | promptfoo / garak / PyRIT structural export |
| `security` | SSRF + receipt scope rejects |

## Interpreting the math audit metrics

If `math_lcb_gate.lcb_success_reachable_under_defaults` is **false** and
`optimizer_ga.lcb_stop_rate` is ~0 while `success_flag_rate` is high, the
harness is optimizing on held-out **means**, not confidence-bounded LCB
success. That is the intended diagnostic from the math audit.

## Not in scope (yet)

- Live frontier-model ASR (Haiku / GPT / etc.)
- Cross-tool comparison to garak/promptfoo on shared public targets
- Multi-hour budget sweeps

Those need explicit authorization and API keys; this suite stays offline and
repeatable.
