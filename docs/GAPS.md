# Garbleworks gaps (honest, vs Wallbreaker-class products)

Last updated with stats-honesty + validate_refire + behavior batteries.

## Shipped (was gap, now filled)

| Gap | Status |
|-----|--------|
| One-shot success = “bypass” | **Closed:** `validate_refire` requires N re-fires + Wilson LCB bar |
| No HarmBench-shaped battery ingest | **Closed:** `behaviors.load_behaviors` + sample JSON (full HB is operator-supplied) |
| Tiny-n promotions | **Closed:** `promotion_decision`, live efficacy n≥30 design |
| tool_error counted as ASR=0 | **Closed:** complete-case outcomes |
| Docs claim BH-FDR as live | **Corrected:** see below |

## Still open

| Gap | Priority | Notes |
|-----|----------|--------|
| Full interactive TUI like Wallbreaker | **Shipped (v0.1)** | OpenTUI React: `cd tui && bun start` - Attack/Validate/Sessions/Bench; not a full agent REPL yet |
| Multimodal image-edit attack channel | Low for text-first lab | Out of scope until needed |
| Full HarmBench 400 in-repo | Won’t ship | License/size; use `GARBLEWORKS_BEHAVIORS` |
| BH-FDR on strategy claims | Medium | Spec in EVOLVE_MATH.md; **not** a default production gate yet |
| LCB success gate under optimizer defaults | Known | Held-out mean is product success; LCB ranks only (Job A) |
| Powered frontier ASR scoreboard (n≥30 live) | Operator | `python -m bench.live_efficacy --n 30` (API cost) |
| Persona author (ENI) / sysprompt corpus mimicry | Low | WB specialty; GW uses personas.json + ops |
| Agentic IPI + dual harm/conceal scorer | **High** | Spec: `SPEC-agentic-ipi-improvements.md` (not built yet) |
| Delivery/ingest as first-class outcome | **High** | Same spec; unread inject must not score as no_harm |
| Document/CSV IPI template library on spine | Medium | Port from `bug-bounty/grayswan` kits |
| MCP 1:1 onto spine (chat + agentic) | Medium | Spine chat path exists; agentic + MCP = later phase |

## Claim discipline

- Plumbing canary ASR≈1.0 ≠ jailbreak efficacy.
- Prefill n=1 = existence (`EXISTENCE_LATEST`), not confirmatory (`SUCCESS_LATEST` only if promote).
- Do not cite McNemar UNDERPOWERED pairs as superiority.
