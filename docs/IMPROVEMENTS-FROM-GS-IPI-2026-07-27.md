# Garbleworks improvements — grounded in GS IPI session (2026-07-27)

Mode: **challenge + decide**  
Evidence: Kill Crops + Wipe Firmware live transcripts; `arena_class.py`; `spine/*` closeout; MCP not on spine; prior design deep-think.

---

## Conclusions (ranked)

| # | Conclusion | Confidence | Weakest premise | Flip if… |
|---|------------|------------|-----------------|----------|
| 1 | **Operator loop is the product gap**, not op count | VERIFIED-sourced (session) | Assumes operator uses MCP/arena_next_move as main path | Most fires go through spine TUI only |
| 2 | **Delivery + failure codes must be first-class** in advise | VERIFIED (Wipe D0, Crops D2) | GS always looks like our classes | New class of challenges |
| 3 | **MCP must collapse onto spine** or operators will keep driving legacy ladders | VERIFIED (mcp has no `run_campaign`) | Spine is only for canary labs | MCP already wraps spine off-tree |
| 4 | **Objective class taxonomy is handout-era**, not agent-IPI-era | VERIFIED (`arena_class.py` rules) | Keyword rules are enough with better text | ML classifier ships |
| 5 | **Recipe/op soup is Stage-B**; pure IPI needs **carrier templates** + **success detectors for tools** | INFERRED | Pair strategy covers IPI | Pair ASR high on AgentDojo-like |
| 6 | **Register/L(x) should gate “instruction chrome”** after D2 | PROBABLE | NEXT-1 was only one sample | Stealth fills also get named |

Overall plan confidence: **7.5/10** for prioritization; **5/10** that any single item alone lifts GS ASR.

---

## What the session proved about Garbleworks

### Wipe Firmware (D0 delivery)
- `arena_next_move` / clean ladders assume a **pasteable chat jailbreak**.
- Reality: **CSV carrier + broken shell**. Advise never said “prove ingestion first.”
- Ops catalog (140+) never ran. **Zero mutator value** until context holds the CSV.
- Success criteria allow **provided procedure**, not only FS side effect. Scorer/detectors on spine are canary/substring oriented, not `tool_call:name=shred` / `contains:firmware.bin` procedure packs.

### Kill Crops (D2 instruction hierarchy)
- Class detector: hydro + `set_ph` → sometimes `scada_ops`, often **generic** when objective is long IPI prose.
- `scada_ops` ladder still **clean_maintenance / chat-shaped**, not pure tool-return IPI.
- `tool_result_wrap` exists as an op; **no carrier kit** that emits disease-report fill / CSV row / incomplete-tool variants with anti-chrome rules.
- Live refusal: model **named embedded instruction**. Garbleworks has no **failure-code router** that says “drop action_items/SYSTEM; switch third-person SOP.”

### Spine vs MCP split (architecture)
- Spine **CLOSED**: `CampaignObjective.delivery`, four strategies, claim gate, default=pair.
- MCP still: `optimize`, `pack_hunt`, `arena_next_move`, `generate_framings` — **no `run_campaign`**.
- Operator (Grok/Unc via MCP) drives the **legacy surface**. Redesign is invisible where you actually work.

### Prior design deep-think (same day)
Already filed: multi-spine, recipe vs attack state, PAIR vs genetic inversion (now partially closed in Python), measurement dualism, Objective underpowered in the **live loop**. This session adds: **IPI carrier + D-codes + MCP collapse** as the sharp edges.

---

## Improvement program (build order)

### P0 — Operator-critical (ship first)

#### P0.1 Failure-code router (`D0`–`D6`)
**What:** After each history item, classify outcome into codes from session handoff:
- D0 no_ingest | D1 summary_only | D2 inject_named | D3 confirm_ask | D4 clamp_soft | D5 tools_dead | D6 capability_wall  

**Where:** `arena_class.py` or new `failure_codes.py`; consume in `arena_next_move` / `arena_ladders.py`.

**Behavior:**  
- D0 → force **delivery checklist** (inline carrier, no disk search, T2 if agent asked for file).  
- D2 → ban chrome ops (`chat_template_inject`, SYSTEM-ish seeds); prefer SOP/JSON/third-person templates.  
- D5 → switch success criterion to **procedure emission**, not shell success.

**Why:** Today’s advise re-emitted clean_direct while the real bug was D0.

#### P0.2 Objective classes for agent IPI
Add to `ObjectiveClass`:
- `pure_ipi_tool_return` — fill in tool/CSV/RAG; no second user order  
- `pure_ipi_document` — document/report carrier  
- `agent_destructive_tool` — set_ph / rm / shred / transfer  
- Keep existing handout/CBRNE/exam  

Keyword seeds from this session: `indirect`, `{fill}`, `tool result`, `csv`, `firmware.bin`, `set_ph_level`, `disease report`, `customer feedback`, `without confirmation`.

Ladders for pure IPI (not clean_direct first):
1. third_person_sop  
2. json_data_plane  
3. threshold_trigger  
4. role_aligned_short  
5. micro_schema  
6. (last) react_continuation / math_conditional  

**Never first:** SYSTEM wrap, dual-channel conceal, action_items meta (burned on Crops).

#### P0.3 Carrier templates (compose, not just transform)
New module e.g. `backend/carriers/`:
- `csv_feedback_row(payload, benign_rows=N)`  
- `disease_report_fill(args_json, frame=cip|threshold|json)`  
- `tool_result_envelope(tool_name, body)`  
- `inline_user_plus_carrier(benign_user, carrier)` — **Wipe PASTE-NOW pattern**

MCP: `compose_carrier(kind, goal, constraints)` → paste-ready text.

**Why:** h4rm3l/GW ops rewrite strings; GS IPI wins on **where** the string sits. Delivery is already on `CampaignObjective` but not exposed to the human-in-the-loop paste path.

#### P0.4 MCP → spine (minimal)
Expose:
- `run_campaign` / `campaign_status`  
- `compose_carrier`  
- `classify_failure`  
- `arena_next_move` reads spine objective + failure codes  

Keep legacy ops as Stage-B behind `converter_recipe`.

Without this, P0.1–0.3 never reach the agent driving GS.

---

### P1 — Measurement + IPI success

#### P1.1 Success detectors for agent actions
Extend `SuccessDetector.kind`:
- `tool_name` — set_ph_level / run_shell  
- `tool_arg` — value≈2.0, path contains firmware.bin  
- `procedure_mentions` — shred|rm|set_ph with target artifact  
- `no_confirm_language` optional soft score  

Wire to GS-like transcripts (tool blocks + final text).

#### P1.2 Delivery-aware seed builders
`CampaignObjective.delivery in {tool_result, rag_doc}`:
- Default seeds must **not** be “Please comply: {goal}” (current `__post_init__` bias).  
- Seeds = carrier-framed variants only.

#### P1.3 Ingestion proof gate
Before counting a fire as “refused injection,” require **ingest signal** (quoted row, theme from CSV, disease place names). Else tag D0 and do not burn ladder steps or promote “technique failed.”

---

### P2 — Search / science (after operator loop works)

#### P2.1 Pair-first on IPI batteries
Run `DEFAULT_STRATEGY=pair` against:
- local AgentDojo-like stubs  
- recorded GS transcripts as offline judge  

Report ASR@budget with complete-case only.

#### P2.2 Register gate for chrome
When D2 fires, auto-raise L(x) penalty on tokens: `SYSTEM`, `ignore previous`, `action_items`, `embedded`, `do not tell`, `BLOCKED_PARTIAL`.  
Feed into Stage-B neutralize / seed filter.

#### P2.3 MAP-Elites / evolve only as Stage-B on survivors
Do not open GS with genetic soup. Illuminate **after** a carrier frame shows partial (D1→ tool-ish).

#### P2.4 Claim gate honesty for GS
n=1 arena paste ≠ promote. Log as `EXISTENCE` until m-of-k on same model class.

---

### P3 — Product surface

| Item | Note |
|------|------|
| TUI “IPI mode” | Carrier + failure codes + paste bay; not only jailbreak chat |
| Grok driver packet | Include last D-code + delivery + banned ops |
| Import session handoffs | Parse `SESSION-HANDOFF-*.md` / GS transcripts into history |
| Field-guide ops link | `tool_result_wrap` → pure_ipi ladder entry |

---

## Explicit non-goals (this quarter)

- Another 50 encoding ops  
- Full HarmBench in-repo  
- Multimodal image channel  
- Replacing Gray Swan automation (rules forbid; keep advise-only)  
- Pretending clean_direct is an IPI strategy  

---

## Decision table (what to build this week vs later)

| Option | Pros | Cons | When |
|--------|------|------|------|
| **A. Failure codes + IPI classes + carriers + MCP spine** | Fixes actual session pain | Medium eng | **This week (Recommended)** |
| B. More ops / better neutralize only | Cheap | Would not have saved Wipe or Crops NEXT-1 | Never alone |
| C. Full genetic GS auto-solve | Sexy | Rules + broken shell + wrong surface | After A, lab targets only |
| D. Spine-only, ignore MCP | Clean Python | Operator still on MCP | Bad default |

**Decision: A.**

---

## Concrete tickets (implementable)

1. `failure_codes.py` + unit tests on Crops/Wipe transcripts  
2. Extend `ObjectiveClass` + ladder pure_ipi  
3. `carriers/csv.py`, `carriers/tool_fill.py`, `carriers/inline_paste.py`  
4. MCP tools: `classify_failure`, `compose_carrier`, `run_campaign` thin wrap  
5. Fix `CampaignObjective` default seeds when `delivery != user`  
6. SuccessDetector tool/procedure kinds + one offline fixture from Wipe criteria text  
7. Update `GROK_DRIVER.md` / arena primer: D0 checklist first  

---

## Claim registry (uncertain)

| Claim | Role | Tier | Source |
|-------|------|------|--------|
| MCP does not call spine today | premise | VERIFIED | grep mcp_server no run_campaign |
| Spine delivery field exists unused in MCP loop | premise | VERIFIED | objective.py + mcp |
| arena classes miss pure IPI | premise | VERIFIED | arena_class.py |
| D0 was wipe root cause | conclusion | VERIFIED | Mr. Swan + transcripts |
| D2 was crops root cause for NEXT-1 | conclusion | VERIFIED | model reply |
| Carriers will raise ASR | conclusion | SPECULATIVE | pattern match GS winners |
| Pair strategy wins pure IPI | conclusion | SPECULATIVE | design intent, unmeasured here |

---

## Fabrication / contradiction check

- No claim that spine “doesn’t exist” — it shipped same day; **gap is exposure + IPI semantics**.  
- No claim encode ops are useless — they are Stage-B after delivery works.  
- Tension: earlier design said multi-turn default on hardened targets; pure GS IPI is often **single fill**. Multi-turn is for chat ablation / T2 paste after agent asks (Wipe), not Crops pure score. **Resolve:** multi-turn optional by class; pure_ipi stays single-carrier.

---

## What I don’t know

- Exact GS UI for fill vs full message on Wipe when attempts return  
- Whether Aluminum Hippo has non-shell file tools on other models  
- Pair ASR on a real tool-return battery under spine (not measured this session)  

---

## Confidence: 7.5/10

Prioritization is grounded in live failures and code. Magnitude of ASR lift from carriers is still speculative until tickets 1–4 ship and re-fire.
