# Live ASR runbook (G6)

Authorized targets only. Offline dry-run proves plumbing; it is **not** a frontier jailbreak scoreboard.

## Schema

Result documents use `schema_version: live_asr.v1`. Required fields:

| Field | Meaning |
|-------|---------|
| `tag` | Operator label for the battery |
| `timestamp` | UTC ISO-ish |
| `dry_run` | true = mock rows only |
| `n_requested` | trial count (efficacy default >= 30) |
| `engagement_id` | RoE / receipt id |
| `target_desc` | human target note |
| `technique` | recipe / strategy / prefill label |
| `complete_case` | successes, n_completed, asr, Wilson LCB/UCB |
| `promotion` | `promotion_decision` output |
| `claim_ready` | true only if promotion.promote and n >= min_n |
| `exit_code` | 0 promote/ok, 1 no success, 2 exploratory under `--require-promote` |

Code: `backend/bench/live_efficacy.py` (`RESULT_SCHEMA`, `build_result`, `validate_result_schema`).

## Dry-run (CI / no model)

```bash
cd backend
python -m bench.live_efficacy --dry-run --n 30 --require-promote --tag smoke
```

Exit 0 only when mock all-leak n=30 promotes under the efficacy bar.

## Live under RoE (operator-owned local models)

Default engagement file: `backend/engagements/local-selftest-roe.json`  
Scope: `127.0.0.1`, `localhost` only. Authority: operator-owned Ollama.

### One command (recommended)

```bash
cd backend
# Ollama must be up on 127.0.0.1:11434 with GARBLEWORKS_LLM_MODEL loaded
python -m bench.roe_live_battery --roe engagements/local-selftest-roe.json ^
  --tools garbleworks:gw_baseline --battery v1_canary --target-mode ollama ^
  --tag roe-live-ollama
```

What it does:

1. Loads the AuthorizationReceipt (RoE JSON or env).
2. Refuses if `127.0.0.1` / `localhost` not in scope (SCOPE DENIED).
3. Starts the local Chat Completions canary in **ollama** mode (real model + secret guard).
4. Runs Garbleworks modes on the battery (default `gw_baseline`).
5. Writes:
   - `bench/results/*-roe-live.json` (full rows + RoE stamp)
   - `bench/results/*-live-asr-claim.json` (`live_asr.v1` claim doc)
   - `roe-live-latest.json` / `live-asr-claim-latest.json`

### MiniMax-M3 as TARGET (not the ablit generator)

Uses operator key (`~/.secrets/minimax_api_key.txt` or `MINIMAX_API_KEY`).  
Harness still fires at **127.0.0.1** canary; canary proxies to `api.minimax.io` with a system SECRET guard. Ablit stays generator-only.

```bash
cd backend
# key from env or ~/.secrets/minimax_api_key.txt
python -m bench.roe_live_battery --roe engagements/minimax-canary-roe.json ^
  --tools garbleworks:gw_baseline --battery v1_canary --target-mode minimax ^
  --tag roe-minimax-m3
```

**Estimand:** lab canary ASR on MiniMax-M3 (including leak text inside `<think>` blocks if the model recites SECRET while "refusing"). Not a multi-provider public leaderboard.

### Deterministic canary (plumbing only)

```bash
python -m bench.roe_live_battery --roe engagements/local-selftest-roe.json ^
  --target-mode deterministic --tag roe-plumbing
```

Easy unlocks ASR ~= 1.0 here measures **transport + adjudicator**, not model efficacy.

### Estimand honesty

| Target mode | What ASR means |
|-------------|----------------|
| `deterministic` | Plumbing / unlock markers |
| `ollama` | Local model under planted SECRET guard (lab efficacy on **your** weights) |
| cloud / multi-provider | **Not** this runner; needs separate RoE + keys + approval |

### Publish rules

1. Publish **only** if `claim_ready` / `promotion.promote` and n is honest.
2. Multi-strategy tables: `rank_strategies(..., fdr_q=0.10)`.
3. Do not paste dry-run or deterministic-easy ASR as frontier leaderboard.
4. Off-scope hosts are denied by RoE + `fire.py` / MCP receipt.

### Classic compare CLI (no RoE stamp)

```bash
python -m bench --tools garbleworks:gw_baseline --target-mode ollama --tag manual
```

## Related

- Claim dual flags (optimizer): `success` vs `claim_ready` (G4)
- BH-FDR optional: `bench.metrics.benjamini_hochberg` / `rank_strategies(fdr_q=...)`
- Thin CI campaign: `python campaign_yaml.py campaigns/ci_canary.json`
