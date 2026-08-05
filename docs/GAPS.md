# Garbleworks gaps (honest, vs Wallbreaker-class products)

Last updated: residual cut 1–4 (HB judge path, scoreboard artifact, MCP-first honesty, multi-dataset loaders). Multimodal/image skipped.

## Operator surface stance

- **MCP-first** for agent operators (`backend/mcp_server.py`): compose, scan, HarmBench, agentic IPI, field guide, **reasoned mutator**.
- **CLI** (`python -m garbleworks`, `spine.ipi_cli`, `harmbench`, `mutator`) for scripts and CI.
- **TUI v0.1** exists; it is **not** a Claude-Code-style interactive agent REPL. Do not claim Wallbreaker REPL parity.
- **Multimodal / image-edit** remains out of scope (text-first lab).
- **Default mutation is history-guided** (`reasoned_mutator`, policy=`reasoned`): next style/approach is conditioned on refuse/partial/success history and forces a family switch after a failure streak. Uniform-random remains an A/B baseline only (`policy=random`). LLM chat "one path forever" is **not** the mutator model.

## Shipped (was gap, now filled)

| Gap | Status |
|-----|--------|
| One-shot success = "bypass" | **Closed:** `validate_refire` + Wilson LCB bar |
| HarmBench-shaped + **official** HB battery | **Closed:** download-on-first-use CSV + campaign ladder |
| HB campaign **LLM/judge grade path** | **Closed:** `grade_mode=judge` + pluggable `judge_fn` (AttackEval-style 0–1); heuristic remains default |
| Tiny-n promotions / dual claim flags | **Closed:** `success` vs `claim_ready`; `promotion_decision` |
| tool_error counted as ASR=0 | **Closed:** complete-case outcomes |
| Delivery_fail first-class | **Closed:** claim gate refuses promote on all/majority delivery_fail |
| Agentic IPI dual scorer + templates + tools-loop | **Closed:** spine + MCP/CLI |
| Live ASR schema + dry-run scoreboard artifact | **Closed:** `live_asr.v1` via `bench.live_efficacy` / `build_scoreboard_claim` (n≥30 plumbing; not a frontier leaderboard) |
| JailbreakBench-shaped + StrongREJECT-shaped loaders | **Closed:** `datasets.py` + fixtures; `resolve_behaviors(source=…)` |
| BH-FDR optional multi-strategy gate | **Closed (optional):** default off |
| MCP → spine map | **Closed:** `spine/mcp_map.py` |
| Thin CI campaign YAML | **Closed:** `campaigns/ci_*.json` |
| History-guided mutator (beats random offline) | **Closed:** `reasoned_mutator.py` — reasons on proposals, stagnation approach-switch, `compare` A/B vs uniform baseline; MCP `reasoned_mutate` / `mutator_compare`; CLI `python -m garbleworks mutator compare` |

## Still open

| Gap | Priority | Notes |
|-----|----------|--------|
| Full interactive agent **REPL** like Wallbreaker | Medium | Explicit non-goal this cut; MCP-first + TUI v0.1 only |
| Multimodal image-edit channel | Low | Skipped / text-first |
| Powered multi-model **live** ASR numbers | Operator | Schema + dry-run artifact ship; live needs keys/budget/auth |
| Calibrated live LLM judge on HB campaign | Operator | Plug is shipped; production judge wiring is operator env |
| Persona author (ENI) / sysprompt corpus | Low | WB specialty |
| Full corpora **vendored in git** (HB/JBB/SR) | Won't ship | Cache / fixture / env path pattern |
| Always-valid multi-dim evidence archive | Research | Dual flags ship |
| BH-FDR as **default** production gate | Known | Optional only |
| `pip install garbleworks` / purple-team matrix | Packaging | Residual roadmap |

## Claim discipline

- Plumbing canary ASR ≈ 1.0 ≠ jailbreak efficacy.
- Prefill n=1 = existence, not confirmatory success.
- Unread inject → `delivery_fail`, not technique-fail / `no_harm`.
- `success` (mean) ≠ `claim_ready` (LCB).
- dry_run / mock all-leak scoreboard is **not** a multi-provider frontier leaderboard.
- Heuristic HB grade is not confirmatory ASR; use `grade_mode=judge` + real judge for claim-grade work.
- Do not claim full Wallbreaker REPL parity from MCP + tools-loop alone.
