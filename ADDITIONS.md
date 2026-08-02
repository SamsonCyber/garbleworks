# Garbleworks - Distilled Additions

The actionable companion to `RESEARCH-DISTILLATION.md`. That doc mapped 21 papers +
4 repos to the pipeline. This one separates *what to actually build* from *what already
ships*, verified against the live registry on 2026-07-03.

## STATUS - implemented 2026-07-03

All genuine additions below are built, wired, and tested (`test_additions.py`, 15/15).
Registry is now **138 ops**. Skipped Section A entirely (already shipped).

| Item | What landed | Where |
|---|---|---|
| B1 complexify | LLM op, +26% ASR booster, offline pass-through | `ops/adaptive_ops.py` |
| B2 llm_judge | AttackEval 0/.33/.66/1.0 detector; `graded_score` persisted | `detectors.py`, `history.py` |
| B5 family | `Operation.family` + `tactic_family`, exposed on `/ops` | `core.py` |
| B7 variance | Furina hit-rate-variance analytic | `history.py`, `GET /history/analytics/variance` |
| B8 ops | fragment_scene, disguise_reconstruct, crescendo_ladder, positional_insert | `ops/adaptive_ops.py` |
| B3 thompson_deck | Beta-posterior bandit over history + family diversity | `bandit.py`, `GET /deck/thompson`, `/deck/arms` |
| B4 lifecycle | probation/active/retired derived from history | `bandit.py` |
| B6 strategy_discover | model-proposed recipes, bandit fallback | `discover.py`, `GET /deck/discover` |
| B9 export | promptfoo / garak / PyRIT serializers | `exporters.py`, `POST /export/recipe` |

Deferred (needs live data, not code): running a real-target deck to populate the
bandit with non-uniform posteriors - the arms are all on the cold prior until a
graded fire happens against something harder than the local abliterated 7B.

## Headline finding (read this first)

`RESEARCH-DISTILLATION.md` was written against a stale view of the codebase. Its own
"Current ops" line (line 8) lists ~5 op groups: rewriter, translate, llm_reframe,
llm_generate, jailbreak_ops. The live registry is **132 ops across 11 categories**
(encoding 27, character 22, template 17, jailbreak 15, structure 14, prose 10,
sampler 9, stego 6, language 5, carrier 5, llm 2).

Consequence: **12 of the ~18 proposed "new ops" already exist.** Building them would
either raise `duplicate operation name` in `core.register()` or duplicate working
behavior. The real additions are almost entirely the **measure → select → discover**
layer - the closed loop that is Garbleworks' actual differentiator over a pure payload
forge (Parseltongue, CyberChef). Garbleworks does not need more mutators. It needs the
intelligence layer around the mutators it already has.

---

## Section A - Already shipped. DO NOT build these.

| Proposed op (paper) | Already exists as | Note |
|---|---|---|
| `flip` (FlipAttack) | `flip_word`, `word_reverse`, `reverse` | `flip_word` already has the "un-reverse then comply" guidance - that *is* FlipAttack |
| `cipher` (CipherChat/SelfCipher) | `rot13`, `caesar`, `vigenere`, `atbash`, `rot47` + `cipher_persona` | `cipher_persona` is the CipherChat persona wrapper, incl. a private "self" cipher |
| `base64_encode` / `rot13` / `leet_speak` | `base64`, `rot13`, `leetspeak` | verbatim |
| `typo` | `typo_inject` (keyboard-adjacency, seeded) | verbatim |
| `code_wrap` (code modality) | `codeblock_execute`, `function_call`, `code_chameleon` | code-completion laundering already covered by `code_chameleon` |
| `ascii_art` (ArtPrompt) | `ascii_art_mask` | verbatim technique |
| `many_shot` (Many-shot JB) | `manyshot_seed` (N exchanges, escalate) | verbatim |
| `encrypt_wrap` (CodeChameleon) | `code_chameleon` (encrypt_fn + decrypt) | verbatim |
| `nested_inception` (DeepInception) | `deep_inception` (params: scene, **layers**, characters) | the K-layer depth the doc asked for is already a param |
| `persuasion` (PAP) | `persuasion_reframe` (authority/evidence/expert/…) | verbatim |
| `translate_chain` | `roundtrip` (EN→pivot→EN, double pivot) | multi-hop already supported |
| `multiturn` (Crescendo) | `multiturn_seed` (2-turn split) | partial: no auto-escalation ladder yet (see B8) |

Also already present and worth noting because the doc treats them as missing:
`bad_likert_judge`, `policy_puppetry`, `past_tense`, `cot_hijack`, `refusal_suppression`,
`decode_execute_wrap`, `bon_augment`, `response_format_split`, plus the full
`carrier` layer (indirect injection: `email_wrap`, `editor_note_inject`,
`reference_link_exfil`, `memory_seed`, `write_primitive_frame`).

**Phase 1 of the roadmap is effectively already done.** Skip it.

---

## Section B - Genuine additions, ranked by impact / effort.

Verified absent from the registry: `complexify`, `thompson_deck`, `strategy_discover`,
`fragment_scene`, `positional_insert`, `disguise_reconstruct`, `feature_compose`, and
any LLM-judge detector (detector kinds today: contains, not_contains, regex, not_regex,
status_eq, status_in, refusal_bank, secret_regex, min_length - 9 total, all binary).

### B1 - `complexify` op · effort: LOW (~50 lines) · BUILD FIRST
Source: Bandit Jailbreaks / Average Jane (2.3). +26% ASR, proven, no target access.
- New op, `category="prose"` or `"llm"`. One call through `llm.py` (Ollama generator).
- Params: `mode` (select: multistep / jargon / compound_conditions), `n` (variants).
- Rewrites a simple ask into a technically complex, multi-step, jargon-dense version.
- Pass-through to `[text]` when Ollama is unreachable, same pattern as `llm_reframe`.
- Why first: smallest genuinely-new op, biggest documented single-op ASR lift, and it
 unblocks Recipe Rule 2 (the only rule that has zero existing coverage today).

### B2 - `llm_judge` detector (AttackEval 4-level) · effort: MED (~100 lines)
Source: AttackEval (3.1). Turns the scoreboard from binary hit/miss into a graded signal.
- New detector kind in `detectors.py`: `llm_judge`. Feeds `(payload, response)` to
 `llm.py` and returns the AttackEval scale: 0.0 full-reject / 0.33 partial-reject /
 0.66 partial-obey-with-caveats / 1.0 full-obey.
- The detector response already carries a `score` field and a `combine="score"` mode - 
 wire the 4-level value into it; no schema break.
- Store the graded score alongside `hit` in `fire_results`. This is the **reward signal
 the bandit (B3) needs**. Build it before B3.

### B3 - `thompson_deck` adaptive selector · effort: MED-HIGH (~150 lines) · THE LEVER
Source: JailbreakOPT (2.1) + Bandit Jane (2.3). Single biggest ASR-per-query win.
- Not an op - a new selection mode for `/fire_deck`. Maintain a Beta(α, β) posterior per
 (op *or* recipe, target host).
- Training signal already exists: join `op_attribution` (leaf-op per variant) to
 `fire_results.hit` (or the B2 graded score). Seed posteriors from `/history` on startup.
- Loop: sample each arm → pick the chain with highest expected reward → fire → update
 α/β from the observed result. Persist posteriors in a new small table or recompute
 from history each session.
- Works on binary `hit` today; works *better* once B2 lands. Order: B2 → B3.

### B4 - Recipe lifecycle states · effort: MED (~80 lines)
Source: MemoAttack (2.2). 98% ASR, 45.9% fewer queries by retiring dead skills.
- Add `state` (probation / active / retired) + `evidence` (targets hit, ASR, patterns)
 to recipe JSON files. `thompson_deck` skips `retired`, prioritizes `active`, samples
 `probation` occasionally to discover new winners. Natural pair with B3.

### B5 - Op `family` labels + diversity-constrained `compose_deck` · effort: MED (~100 lines)
Source: WildTeaming (1.5). Composed multi-tactic recipes ≈ 4.6× single-tactic.
- Add a `family` field to `Operation` (authority / persona / encoding / fragmentation /
 code / translation / hypothetical / attention-shift). The 11 existing *categories*
 already approximate this - mostly a relabel.
- `compose_deck` builds 3-5-op chains under the constraint "no two adjacent ops share a
 family." This auto-enforces Recipe Rules 1 (dual-direction) and 3 (diversity).

### B6 - `strategy_discover` meta-op · effort: HIGH (~200 lines) · closes the loop
Source: AutoDAN-Turbo (2.4) + Claudini (2.5). The self-exploration piece garbleworks lacks.
- Meta-op: reads `/history` failure/success patterns, uses `llm.py` to propose *new
 recipe chains built from existing ops* ("ops X,Y failed on target A but hit target B - 
 propose a variant for A"). Emits candidate recipes into `probation` state (B4).
- Do this after B2/B3 exist - it needs the graded scoreboard to reason over.

### B7 - Response variance signal · effort: LOW (~40 lines)
Source: Furina (1.2) + Recipe Rule 5. High output variance = target in the instability
region = near breakthrough.
- Fire each recipe K times (K=3 default), record response variance as a `fire_runs`
 column. Surface it in analytics. `sample_n`/`repeat` can approximate the K-fire today;
 this just makes variance a first-class scoreboard feature.

### B8 - Genuinely-new individual ops (lower priority, real but niche)
- `positional_insert` (SlotGCG VSS, 1.1) - score insertion points by Ollama perplexity
 delta, inject at the best slot instead of always suffixing. ~150 lines, needs logprobs.
 Real novelty; unblocks Recipe Rule 4.
- `fragment_scene` (Furina, 1.2) - split into N scene-anchored fragments. Distinct enough
 from `split_join` / `response_format_split` to justify. ~100 lines.
- `disguise_reconstruct` (DRA) - wrap the ask as a reconstruction task. Absent. ~60 lines.
- `crescendo_ladder` - extend `multiturn_seed` into an N-turn auto-escalation. ~80 lines.
- `feature_compose` (UNIATTACK, 2.6) - overlaps B5; defer until `compose_deck` exists.

### B9 - Ecosystem export · effort: MED
Source: 5.3. Recipe → promptfoo YAML / garak probe / PyRIT orchestrator, and calibrate
against JailbreakBench / HarmBench. This is the "prove it against real targets" move - 
converts the biggest current weakness (validated only against one local abliterated 7B)
into data no pure forge can produce.

---

## Section C - Recipe rules you can apply TODAY with existing ops.

The 7 synthesized rules, mapped to current capability. 4 of 7 need zero new code.

| Rule | Buildable now? | With |
|---|---|---|
| 1. Dual-direction (HARC) | **Yes** | refusal-suppress (`deep_inception`/`persuasion_reframe`/`cipher_persona`) + harm-suppress (`base64`/`code_chameleon`/`roundtrip`) |
| 2. Complexity booster | **No** | needs `complexify` (B1) - the one rule with no coverage |
| 3. Diversity (WildTeaming) | **Yes (manual)** | pick ops from different categories; auto-enforced later by B5 |
| 4. Positional (SlotGCG) | **No** | suffix-only today; needs `positional_insert` (B8) |
| 5. Variance (Furina) | **Approx** | `sample_n`/`repeat` K× today; first-class via B7 |
| 6. Cross-episode learning | **No** | needs `thompson_deck` (B3) |
| 7. Surrogate transfer (Claudini) | **Yes** | develop on `ablit:latest` target, transfer to API adapters - infra exists |

---

## Section D - Build order

1. **B1 `complexify`** - 1 hr, proven +26%, unblocks Rule 2. Ship today.
2. **B2 `llm_judge` / AttackEval scoring** - graded scoreboard; prerequisite for a real bandit.
3. **B3 `thompson_deck` + B4 lifecycle** - the adaptive selector. Biggest lever.
4. **B5 family labels + `compose_deck`** - auto-enforce dual-direction + diversity.
5. **B7 variance signal** - cheap, high-signal eval add.
6. **B6 `strategy_discover`** - the discovery loop, once the graded scoreboard exists.
7. **B8 niche ops + B9 exports** - as capacity allows; B9 is what generates real-target proof.

Everything above B6 is measure/select - the moat. The individual ops (B8) are the smallest
part of the remaining work, which inverts the roadmap's Phase-1-heavy ordering.
