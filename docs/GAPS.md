# Garbleworks gaps (honest, vs Wallbreaker-class products)

Last updated: P0 dual-claim + agentic IPI + P1 BH-FDR / live ASR schema / MCP spine map / campaign YAML.

## Shipped (was gap, now filled)

| Gap | Status |
|-----|--------|
| One-shot success = "bypass" | **Closed:** `validate_refire` requires N re-fires + Wilson LCB bar |
| No HarmBench-shaped battery ingest | **Closed:** `behaviors.load_behaviors` + sample JSON (full HB is operator-supplied) |
| Tiny-n promotions | **Closed:** `promotion_decision`, live efficacy n>=30 design |
| tool_error counted as ASR=0 | **Closed:** complete-case outcomes |
| Docs claim BH-FDR as live | **Corrected:** optional gate only (G5); default off |
| Agentic IPI + dual harm/conceal scorer | **Closed:** `spine/scorer_agentic.py`, `HarmToolSpec`, `mode=agentic_ipi`, strategy `ipi_template` |
| Delivery/ingest as first-class outcome | **Closed:** delivery probe → `delivery_fail` (never folded into `no_harm`); claim gate refuses promote on all/majority delivery_fail |
| Document/CSV IPI template library on spine | **Closed:** five templates in `spine/ipi_templates/` (tool_result, csv, report_fill, email_body, file_content) |
| Live multi-step tool agent driver | **Closed (tools-loop):** `OpenAIToolsLoopAgent` (`openai_tools`); offline via `chat_fn`. Not a full agent REPL. |
| MCP / CLI agentic IPI surface | **Closed:** `list_ipi_templates`, `run_agentic_ipi`, `run_campaign_tool`, `score_document_detectability` |
| LCB vs mean claim hygiene (G4) | **Closed (dual flags):** `success` = held-out mean; `claim_ready` = held-out LCB; `claim_mode=strict` raises n_final |
| BH-FDR optional multi-strategy gate (G5) | **Closed (optional):** `benjamini_hochberg` / `rank_strategies(fdr_q=...)`; default off |
| Live ASR dry-run + schema (G6) | **Closed (plumbing):** `python -m bench.live_efficacy --dry-run`; runbook `docs/LIVE-ASR-RUNBOOK.md`. Live multi-model numbers remain operator. |
| MCP → spine map (G7) | **Closed:** `spine/mcp_map.py` + MCP `mcp_spine_map` / `rank_strategy_claims` |
| Thin CI campaign YAML/JSON | **Closed:** `campaign_yaml.py` + `campaigns/ci_*.json` |

## Still open (explicit non-parity / non-goals)

| Gap | Priority | Notes |
|-----|----------|--------|
| Full interactive agent REPL like Wallbreaker | Medium | TUI v0.1 + MCP tools; not Claude-Code-style chat REPL |
| Multimodal image-edit attack channel | Low | Out of scope for text-first lab |
| Full HarmBench 400 in-repo | **Download-on-first-use** | Official CSV cached via `python -m harmbench ensure` / MCP `ensure_harmbench`; not vendored in git. Campaign: `python -m harmbench campaign` or `--harmbench-campaign` |
| Powered frontier multi-model ASR leaderboard (live numbers) | Operator | Schema + dry-run shipped; live needs auth, keys, budget. Do not publish dry-run as leaderboard. |
| Persona author (ENI) / sysprompt corpus mimicry | Low | WB specialty; GW uses personas.json + ops |
| HarmBench LLM-judge ASR (not heuristic) | Operator | Campaign grades non-refusal by default; pair with live judge / live_efficacy for confirmatory claims |
| Always-valid / multi-dim evidence (BEYOND_LCB_MEAN) | Research | Dual flags ship; full archive is research track |

## Matched vs bypassed (Wallbreaker-class)

| Capability | Status |
|------------|--------|
| Multi-step tools-loop agent on IPI path | **Matched** (adapter + dual scorer) |
| Operator list/run agentic IPI | **Matched** (MCP + CLI → spine) |
| Dual harm/conceal + delivery honesty | **Leads** (claim gate; WB UX does not own this ontology) |
| Full agent REPL UX | **Not claimed** |
| Persona ENI / multimodal / HB-400 in-tree | **Not claimed** |

## Claim discipline

- Plumbing canary ASR ≈ 1.0 ≠ jailbreak efficacy.
- Prefill n=1 = existence, not confirmatory success.
- Unread inject → `delivery_fail`, not technique-fail / `no_harm`.
- `success` (mean) ≠ `claim_ready` (LCB). Do not cite mean alone as confidence-bounded.
- Multi-strategy winners: enable BH-FDR (`fdr_q=0.10`) before publishing a leaderboard of techniques.
- Do not claim full Wallbreaker REPL parity from tools-loop + MCP alone.
