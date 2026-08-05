# Garbleworks gap-fill specification

**Kind:** analysis / design (no implementation in this goal)  
**Date:** 2026-08-05  
**Sources:** `docs/GAPS.md`, `docs/BENCHMARKS.md`, `docs/IPI-AGENT.md`, `docs/HARNESS-POSITIONING.md`, `docs/archive/BEYOND_LCB_MEAN_SPEC.md`, `EVOLVE_MATH.md`, `SPEC-agentic-ipi-improvements.md` (payload-mutator path; referenced by GAPS), spine modules, prior peer matrix + offline scrutiny  
**Inventory log:** `{SCRATCH}/gaps_source_inventory.txt`

---

## 0. How to use this doc

1. Treat **closed** gaps as done. Do not reopen them as roadmap filler.
2. For each **open** gap: problem → approach (outcomes) → acceptance → effort/risk → non-ship.
3. Execute by **phase** (P0 → P1 → P2). Phase "done when" is the only gate.
4. Prefer **integrate peer** over re-building garak/PyRIT/promptfoo where that is the honest fill.

**Product north star (unchanged):** closed loop of compose → scoped fire → detect/judge → search → re-fire → standards map. Gaps that dilute that into "another probe dump" are deprioritized or deferred.

---

## 1. Already closed (do not re-spec as open)

From `docs/GAPS.md` "Shipped" + tree checks:

| Gap title (GAPS) | Evidence of closed | Residual only |
|------------------|--------------------|---------------|
| One-shot success = "bypass" | `validate_refire`, Wilson LCB promotion bar | Operators must still call re-fire before claims |
| No HarmBench-shaped battery ingest | `behaviors.load_behaviors` + sample JSON | Full 400 HB stays external (`GARBLEWORKS_BEHAVIORS`) |
| Tiny-n promotions | `promotion_decision`, live efficacy n≥30 design | Live runs still cost API |
| tool_error counted as ASR=0 | Complete-case outcomes | Agentic path must keep complete-case |
| Docs claim BH-FDR as live | Corrected: math-spec only, not default gate | Wiring BH-FDR remains open (below) |
| Full interactive TUI like Wallbreaker | **Shipped v0.1** (`tui/`, OpenTUI React) | Not a full agent REPL; residual is P2 polish |

**Partial ship (measurement subset of agentic IPI), not full close:**

From `SPEC-agentic-ipi-improvements.md` + `docs/IPI-AGENT.md` + `backend/spine/`:

- Detectability chrome scoring, outcome taxonomy helpers, claim gate on delivery_fail / injection_detected, complete-case stats, campaign wiring, response_signals.
- **Still open:** live multi-step tool agent driver, dual harm/conceal scorer loop, document template bank, MCP `run_agentic_ipi`.

---

## 2. Open gaps from GAPS.md → fill plans

### G1. Agentic IPI + dual harm/conceal scorer  
**Priority in GAPS:** High · **Phase:** P0

| Field | Spec |
|-------|------|
| **Problem** | Chat canary ≠ agent IPI. Without tool-call harm ontology + conceal channel, you cannot measure dual-win (harm tool + clean user text) or refuse wrong estimands. |
| **Approach (outcomes)** | (1) First-class campaign mode `agentic_ipi` on shared spine. (2) Dual scorer: delivery × harm (deterministic tool matchers) × conceal (forbidden tokens / soft stealth). (3) Outcome taxonomy: success, harm_only, conceal_only, no_harm, delivery_fail, injection_detected, policy_refuse, tool_error, incomplete. (4) Mock agents: obey / summarize / snitch / no-ingest drive scorer tests. (5) Reuse existing claim_gate and complete-case. |
| **Acceptance ("filled")** | Mock agent battery: delivery_fail never promotes as no_harm; dual-win only when harm+conceal+delivery; at least 4 outcome labels asserted by tests on real spine scorer; docs in IPI-AGENT updated; no live Gray Swan required. |
| **Effort / risk** | L / med-high (ontology mistakes poison all ASR). |
| **Non-ship** | Live arena APIs; browser/screenshot agents; genetic document evolve (v1.1). |

Depends on: existing spine claim_gate / outcomes (done). Unblocks: G2 templates, G3 MCP agentic.

---

### G2. Delivery/ingest as first-class outcome  
**Priority in GAPS:** High · **Phase:** P0 (tightly coupled to G1)

| Field | Spec |
|-------|------|
| **Problem** | Unread inject scored as technique fail. Wrong estimand; kills claim honesty (Kill Crops / wipe lessons). |
| **Approach** | Mandatory delivery probe before harm credit. Markers / unique canary in model-visible context. `require_delivery=true` default for agentic. Separate rates: P(delivery_ok), P(success\|completed). Claim gate already refuses promote when delivery_fail majority; extend so **all** agentic reports surface `n_delivery_fail` by default. |
| **Acceptance** | Any agentic run without ingest evidence → `delivery_fail` only; promotion path refuses; unit tests cover no-ingest mock; operator checklist remains in IPI-AGENT. |
| **Effort / risk** | S–M / med (false delivery_ok if markers too loose). |
| **Non-ship** | Treating delivery_fail as zero ASR efficacy in published tables without a separate row. |

---

### G3. Document/CSV IPI template library on spine  
**Priority in GAPS:** Medium · **Phase:** P0.5 (after G1 scorer exists)

| Field | Spec |
|-------|------|
| **Problem** | Real IPI lives in docs/CSV/tool returns; ad-hoc outside harness → non-reproducible. |
| **Approach** | Template bank (not genetic first): garage-door / report-fill / control-panel / CSV cell / email tool_result shapes. Each template: user_task, document_body slots, harm_tools, delivery_markers, conceal_forbidden. Optional Stage-B string ops on **document body only**. Port shapes from authorized grayswan kits as **structure only** (no proprietary content). |
| **Acceptance** | ≥5 templates loadable as CampaignObjective; each runs through mock agent scorer; detectability scores attached; Unicode Tags opt-in only (not default). |
| **Effort / risk** | M / low-med. |
| **Non-ship** | Full 400-behavior HB corpus; live GS API. |

---

### G4. LCB success gate under optimizer defaults  
**Priority in GAPS:** Known · **Phase:** P0 (measurement honesty)

| Field | Spec |
|-------|------|
| **Problem** | Product `success` uses held-out mean; LCB rarely reachable under default `n_max` (harness: `lcb_success_reachable_under_defaults=False`, `n_needed_perfect=80`). Easy to over-claim "confidence-bounded wins." |
| **Approach** | Split **search job** vs **claim job** in API/CLI responses always: `search_stop_reason`, `success_flag` (mean), `claim_ready` (LCB≥θ after n_final or always-valid bound). Raise default claim path: either (A) increase `n_final` / `n_max` when `claim_mode=strict`, or (B) ship two flags with docs forbidding single-flag marketing. Prefer path from `BEYOND_LCB_MEAN_SPEC`: multi-dim evidence later; **minimum P0** is dual flags + strict mode. |
| **Acceptance** | Optimizer JSON always includes `success_rule`, `success` (mean), `lcb_claim` or `claim_ready`; offline harness asserts strict mode needs n in line with math audit; README/BENCHMARKS one paragraph on how to cite. |
| **Effort / risk** | S–M / low (product messaging). |
| **Non-ship** | Pretending LCB already equals success under old defaults. Full e-process always-valid (P2 / BEYOND spec). |

---

### G5. BH-FDR on strategy claims  
**Priority in GAPS:** Medium · **Phase:** P1

| Field | Spec |
|-------|------|
| **Problem** | Many techniques × targets → false discovery. EVOLVE_MATH §14 specifies BH-FDR; not a default production gate (CHANGELOG / GAPS). Positioning still says "BH-FDR-grade" in places; wire or soft-claim. |
| **Approach** | Implement BH procedure on **per-strategy / per-cell claim batch** after a campaign map or scan. Default: optional flag `fdr_q=0.10`. CI: unit test on synthetic p-values. Docs: "FDR gate available; not default until N strategies ≥ K." Soften HARNESS-POSITIONING language if still overstated. |
| **Acceptance** | Function + tests for BH on strategy score list; CLI/MCP flag; GAPS row can move to "optional gate shipped"; default remains off until calibrated. |
| **Effort / risk** | S–M / low. |
| **Non-ship** | FDR as silent always-on that empties every report under small n. |

---

### G6. Powered frontier ASR scoreboard (n≥30 live)  
**Priority in GAPS:** Operator · **Phase:** P1 (runbook + automation, not free ASR)

| Field | Spec |
|-------|------|
| **Problem** | Offline echo ASR ≠ frontier efficacy. BENCHMARKS: multi-provider leaderboard is roadmap. Peers look "more real" with live tables. |
| **Approach** | (1) Operator runbook: authorized targets only, keys, budget, `python -m bench` / live_efficacy n≥30. (2) Result schema: model, technique, n, successes, Wilson LCB, complete-case notes, date, engagement id. (3) Publish **only** with claim_gate pass. (4) Optional nightly job skeleton (no keys in repo). Do **not** ship fake leaderboard from mocks. |
| **Acceptance** | Runbook doc + JSON schema + one dry-run against echo proves plumbing; live fill is operator action with REPRO-like checklist. GAPS can say "operator path documented" without claiming numbers you did not run. |
| **Effort / risk** | M / high cost if live; low code risk. |
| **Non-ship** | In-repo secret keys; marketing "beats model X" without battery artifact. |

---

### G7. MCP 1:1 onto spine (chat + agentic)  
**Priority in GAPS:** Medium · **Phase:** P1

| Field | Spec |
|-------|------|
| **Problem** | Multiple entry surfaces risk dual spine / incomparable ASR@budget. MCP has many tools; agentic not 1:1 on spine. |
| **Approach** | Inventory MCP tools → map each fire path to spine campaign or shared fire policy. Add `run_agentic_ipi` (or equivalent) only after G1. Chat canary already on spine: document mapping. Deprecate or wrap any second outcome ontology. |
| **Acceptance** | Matrix MCP tool → spine entry; every fire still hits `fire.py` scope; agentic MCP tool uses dual scorer; one integration test with local adapter. |
| **Effort / risk** | M / med (API churn for MCP clients). |
| **Non-ship** | Renaming every tool for aesthetics without spine unification. |

---

### G8. Full interactive TUI like Wallbreaker (residual)  
**Priority in GAPS:** Shipped v0.1 · **Phase:** P2 residual

| Field | Spec |
|-------|------|
| **Problem** | v0.1 has Attack/Validate/Sessions/Bench; not full agent REPL / Wallbreaker-class session depth. |
| **Approach** | Only after P0 agentic works: session tree, delivery_fail visibility, claim_ready badges. No TUI feature if HTTP/MCP already exposes it unless keyboard ops need it. |
| **Acceptance** | Operator can run validate_refire + see claim_ready without leaving TUI; agentic outcomes visible if G1 shipped. |
| **Effort / risk** | M / low product risk. |
| **Non-ship** | Rewriting TUI as the only control plane. |

---

### G9. Multimodal image-edit attack channel  
**Priority in GAPS:** Low · **Phase:** P2 defer / integrate peer

| Field | Spec |
|-------|------|
| **Problem** | PyRIT wins multimodal; GW is text-first lab. |
| **Approach** | **Do not chase** as core. If needed: thin adapter that sends image-bearing requests through same fire policy + export to PyRIT converters. Prefer "interop" over building image mutator catalog. |
| **Acceptance** | Either documented defer, or one adapter + security tests on URL policy for multimodal endpoints. |
| **Effort / risk** | L if built full · **Defer default**. |
| **Non-ship** | Competing with PyRIT multimodal depth in v1. |

---

### G10. Full HarmBench 400 in-repo  
**Priority in GAPS:** Won't ship · **Phase:** permanent non-ship

| Field | Spec |
|-------|------|
| **Problem** | License/size. |
| **Approach** | Keep loader + env `GARBLEWORKS_BEHAVIORS`. Document how to point at operator-held HB/JBB JSON. Optional: thin adapter that imports garak probe names as **labels only**. |
| **Acceptance** | Docs + loader test with fixture ≥3 behaviors; no 400-file dump in git. |
| **Effort / risk** | S / none. |
| **Non-ship** | Vendoring full HB into repo. |

---

### G11. Persona author (ENI) / sysprompt corpus mimicry  
**Priority in GAPS:** Low · **Phase:** P2 / optional

| Field | Spec |
|-------|------|
| **Problem** | Wallbreaker specialty; GW has personas.json + ops. |
| **Approach** | Expand personas only when a target family needs it; else **do not chase**. Prefer recipe templates + register neutralization. |
| **Acceptance** | Explicit defer unless a bounty requires a persona pack. |
| **Effort / risk** | M if pursued · **Defer**. |
| **Non-ship** | Building an ENI product line. |

---

## 3. Peer-gap section (vs public tools)

| Peer delta | Fill path | Or: do not chase |
|------------|-----------|------------------|
| **Probe library breadth (vs garak)** | (A) Export + import bridges already exist (`to_garak`); grow **op/recipe coverage map** from field guide, not 1:1 probe clone. (B) Optional: "run garak pack under GW fire policy" wrapper. | Do **not** reimplement garak's entire probe/detector library. Win on search + claim discipline. |
| **Multi-turn / enterprise (vs PyRIT)** | (A) Ship G1 agentic + treesearch already present for erosion. (B) Memory/session export compatible with PyRIT-ish JSON. (C) Azure packaging = out of band. | Do **not** rebuild Azure Foundry glue or full multimodal converter zoo. |
| **CI / YAML native (vs promptfoo)** | Add a minimal **campaign YAML** schema: objective, target, budget, detectors, recipe/seed list → calls spine/CLI; exit codes for CI. Reuse exporters `to_promptfoo` for round-trip. | Do **not** become a full promptfoo replacement SaaS. |
| **Live multi-model ASR leaderboard** | G6 runbook + schema; publish only gated results. Optional head-to-head when Wallbreaker sibling installed (BENCHMARKS already notes). | Do **not** ship mock numbers as leaderboard. |
| **Measurement LCB / BH-FDR** | G4 dual flags + strict claim mode; G5 optional FDR gate. Align positioning prose with reality. | Do not claim FDR "always on" until default. |
| **h4rm3l DSL novelty** | Already matched; keep honest positioning. | Do not spend roadmap on "more DSL primitives only." |
| **Multimodal** | G9 defer / thin interop. | Integrate PyRIT when needed. |
| **Enterprise adoption gravity** | Docs, repro.py, Apache-2.0, MCP for agents — enough for lab/bounty. | Do not chase Microsoft/NVIDIA distribution channels as a gap "fill." |

---

## 4. Phased roadmap

```text
P0  Measurement honesty + agentic core
    G4 LCB/claim dual flags
    G1 dual scorer + mock agents
    G2 delivery first-class (wired into G1)
    G3 template bank (starts after scorer interface freezes)
         │
         ▼
P1  Claims at scale + surfaces
    G5 BH-FDR optional gate
    G6 live ASR runbook + schema (operator fills numbers)
    G7 MCP 1:1 onto spine (+ agentic tool)
    CI YAML thin campaign (peer promptfoo gap)
         │
         ▼
P2  Polish / optional / defer
    G8 TUI residual (claim_ready, agentic outcomes)
    G9 multimodal defer or thin adapter
    G11 persona ENI only if needed
    BEYOND_LCB_MEAN multi-dim archive (e-process, hierarchical) as research track
```

### Phase dependencies

| Phase | Depends on | Blocks if skipped |
|-------|------------|-------------------|
| P0 | Spine claim_gate (exists) | P1 agentic MCP, honest agent ASR |
| P1 | P0 outcome ontology stable | Published multi-strategy claims, CI agentic |
| P2 | P0–P1 as needed | Nothing critical for "real tool" bar |

### Phase "done when"

| Phase | Done when |
|-------|-----------|
| **P0** | (1) Optimizer/API exposes claim_ready separate from mean success; harness green. (2) Mock agentic battery: delivery_fail / dual-win / snitch outcomes on real scorer. (3) ≥5 document templates load and score. (4) GAPS.md updated: agentic+delivery rows → partial/closed with evidence; LCB row notes dual flags. |
| **P1** | (1) BH-FDR optional on campaign claim batch + tests. (2) Live ASR runbook + result schema checked in; no fake numbers. (3) MCP tool matrix maps to spine; agentic MCP path uses dual scorer. (4) Minimal campaign YAML runs in CI smoke. |
| **P2** | Documented deferrals for multimodal/ENI/full HB; TUI shows claim_ready if built; BEYOND_LCB tracked as research not blocking ship. |

---

## 5. Effort band summary

| ID | Gap | Phase | Effort | Risk |
|----|-----|-------|--------|------|
| G1 | Agentic IPI dual scorer | P0 | L | med-high |
| G2 | Delivery first-class | P0 | S–M | med |
| G3 | Doc/CSV templates | P0.5 | M | low-med |
| G4 | LCB vs mean claim hygiene | P0 | S–M | low |
| G5 | BH-FDR gate | P1 | S–M | low |
| G6 | Live ASR scoreboard path | P1 | M | cost high |
| G7 | MCP ↔ spine 1:1 | P1 | M | med |
| G8 | TUI residual | P2 | M | low |
| G9 | Multimodal | P2 defer | L if full | — |
| G10 | HB 400 in-repo | non-ship | — | — |
| G11 | Persona ENI | P2 defer | M | — |

---

## 6. Claim discipline (carry forward from GAPS)

- Plumbing canary ASR ≈ 1.0 ≠ jailbreak efficacy.
- Prefill n=1 = existence, not confirmatory success.
- delivery_fail is not technique ASR=0.
- Do not cite UNDERPOWERED McNemar as superiority.
- Do not publish multi-strategy wins without FDR or pre-registered small set.
- Offline harness green ≠ frontier leaderboard.

---

## 7. Suggested first implementation slice (when coding starts; not this goal)

1. **G4** dual success/claim flags (small, unblocks honest talking points).  
2. **G1+G2** mock dual scorer + delivery_fail tests (highest product delta vs peers for agent security work).  
3. **G3** five templates.  
4. Then G5/G7/G6 in any order driven by operator need.

---

## 8. Explicit non-goals of the gap-fill program

- Becoming garak, PyRIT, or promptfoo clones.
- Full HarmBench 400 vendored in git.
- Multimodal as a near-term P0.
- Live ASR numbers without authorization, budget, and claim_gate.
- Softening security gates to green a scoreboard.
- Implementing BEYOND_LCB_MEAN entire archive before dual flags ship.

---

## 9. Mapping checklist (verifier)

Every GAPS "Still open" row addressed:

| GAPS row | Spec section |
|----------|--------------|
| Full interactive TUI… | §1 closed v0.1 + G8 residual |
| Multimodal image-edit… | G9 |
| Full HarmBench 400… | G10 |
| BH-FDR on strategy claims | G5 |
| LCB success gate under optimizer defaults | G4 |
| Powered frontier ASR scoreboard… | G6 |
| Persona author (ENI)… | G11 |
| Agentic IPI + dual harm/conceal scorer | G1 |
| Delivery/ingest as first-class outcome | G2 |
| Document/CSV IPI template library… | G3 |
| MCP 1:1 onto spine… | G7 |

Peer section: §3. Phases: §4. Closed not reopened: §1.
