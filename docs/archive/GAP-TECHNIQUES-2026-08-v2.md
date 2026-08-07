# Gap report v2: techniques still missing after the 2026-08 ship

**Date:** 2026-08-02 (second pass)  
**Status:** **SHIPPED** - all 10 v2 techniques are in `field-guide.json`; 9 ops in `ops/gap_ops_v2.py` (Claudini FG-only meta; Odysseus has protocol text seed).  
**Baseline at research:** 336 techniques / 168 ops. **After ship:** 346 techniques / 177 ops (see live registry).  
**Prior ship (v1):** STAC, X-Teaming, Mastermind, Red Queen, Conjunctive, Tag-Along, Agent-only perceptual, Industry reframing, Shadow Alignment, Overthinking - all present.  
**Method:** web/arXiv harvest of high-ASR 2025-2026 attacks -> mechanism match against `title`+`what`+`fam` (not title-only). False friends noted under "Near misses."

### Implementation map

| Technique | Op / note |
|-----------|-----------|
| SLIP | `slip_lexical_insert` + `rt-slip-lexical.json` |
| CoT Hijacking (puzzle) | `cot_puzzle_hijack` + `rt-cot-puzzle-hijack.json` |
| SMT | `smt_moderation_trace` + `rt-smt-moderation.json` |
| JAWS | `jaws_workspace_seed` (offline regime seed) |
| S2C | `s2c_stack` + `rt-s2c-stack.json` |
| HILL | `hill_learning_frame` + `rt-hill-learning.json` |
| Agent multi-turn decomp | `agent_decompose_combine` |
| ContextualJailbreak | `contextual_jailbreak_seed` |
| Claudini | FG only (meta autoresearch bar) |
| Odysseus | `odysseus_seed` (protocol text; no image stego) |

---

## Executive answer

After the first ship, the remaining **high-impact holes** are not "another Crescendo." They cluster as:

1. **Self-jailbreak without a second attacker model** (SLIP lexical insertion).  
2. **Reasoning-trace length / benign-puzzle dilution** (CoT Hijacking != H-CoT != Overthinking).  
3. **Function-calling state machines** (SMT simulated moderation traces).  
4. **Code-agent / workspace executability** (JAWS).  
5. **Semantic reconstruction delay** (S2C cloaking stack).  
6. **Learning-style helpfulness** (HILL).  
7. **Multi-agent decompose -> answer -> combine** (safe-in-isolation).  
8. **Meta: autoresearch discovers attack algorithms** (Claudini).

---

## Ranked true gaps (impact x novelty)

### 1. SLIP - Self-Jailbreaking via Lexical Insertion Prompting  
**Priority: 10/10** * **Lane: both**

| Field | Detail |
|-------|--------|
| Mechanism | Threat model: the **target guides its own compromise**. Black-box BFS over multi-turn dialogues; each step inserts missing content words from the attack goal into still-benign prompts, using the target as the guide (no external red-team LLM). |
| Why not covered | **IRIS** is a self-jailbreak *loop* (refuse -> explain -> rewrite). SLIP is **lexical insertion tree search** with ~7.9 calls avg and no separate attacker model. Different control structure. |
| Impact | AdvBench/HarmBench avg ASR **~94.7%** across 11 models (GPT-5.1, Claude-Sonnet-4.5, Gemini-2.5-Pro, DeepSeek-V3, ...); 3-6x fewer queries than many priors; 100% on several models. |
| Source | arXiv:2601.02670 - https://arxiv.org/abs/2601.02670 |
| Next | FG multiturn/optimization + op/recipe `slip_lexical_insert` (BFS seed + insert schedule). Wire into evolve/treesearch. |

### 2. CoT Hijacking (prolonged benign puzzle -> refusal dilution)  
**Priority: 10/10** * **Lane: both**

| Field | Detail |
|-------|--------|
| Mechanism | Force LRMs into **very long benign puzzle-solving** CoT (often minutes) so attention shifts off the harmful ask and the low-dimensional refusal signal weakens (**refusal dilution**), then elicit compliance. |
| Why not covered | **H-CoT** forges *safety-reasoning* that already concluded "benign." **Overthinking** only asks for more budget. This attack **pads with unrelated hard puzzles** then pivots. Paper mechanisms (probing, attention) are distinct. |
| Impact | HarmBench ASR **99%** Gemini 2.5 Pro, **94%** o4 Mini, **100%** Grok 3 Mini, **94%** Claude 4 Sonnet - well above Mousetrap/H-CoT/AutoRAN baselines in-paper. |
| Source | arXiv:2510.26418 - https://arxiv.org/abs/2510.26418 |
| Next | FG decoding/reasoning + op `cot_puzzle_hijack` (benign puzzle pad + delayed payload). Stack with `overthinking_frame`. |

### 3. SMT - Simulated Moderation Traces (function-calling jailbreak)  
**Priority: 9/10** * **Lane: both**

| Field | Detail |
|-------|--------|
| Mechanism | In stateful function-calling apps, build a multi-turn trajectory that **simulates a moderation/audit workflow**: fabricated moderation frame uses red-team pretext; validation feedback treats refusals as execution failures and "refines" until harmful output appears. Distributes intent across schemas, args, tool outputs, and history. |
| Why not covered | **Function-Calling Jailbreak** coerces harmful *tool-argument generation*. SMT is a **multi-turn simulated moderation/audit playbook** over the whole tool context. |
| Impact | Highest average ASR and HarmScore vs baselines on commercial models from five providers (two safety benchmarks); near-minimal query count. |
| Source | arXiv:2607.00481 - https://arxiv.org/abs/2607.00481 |
| Next | FG agentic/decoding + multi-turn recipe `smt_moderation_trace`; needs tool/function-calling target for live fire. |

### 4. JAWS - Jailbreaks Across WorkSpaces (code agents)  
**Priority: 9/10** * **Lane: FG + agent harness** (executable judge)

| Field | Detail |
|-------|--------|
| Mechanism | Attack surface is the **code agent workspace** (empty -> single-file -> multi-file). Success is not "said something bad" but **compile + run** deployable harm. Wrapping an LLM in an agent **1.6x** ASR vs prompt-only by overturning refusals during planning/tool use. |
| Why not covered | Catalog has tool-result poison, STAC tool chains, code framing. Missing is **workspace-regime escalation + executable-aware success** (JAWS-0/1/M + four-level judge). |
| Impact | JAWS-0: 61% compliance, 27% end-to-end runnable. JAWS-1: ~100% compliance on strong models, mean ASR ~**71%**. JAWS-M: mean ASR ~**75%**, 32% runnable. Agent-agnostic (OpenHands, SWE-Agent, Codex). |
| Source | arXiv:2510.01359 - https://arxiv.org/abs/2510.01359 |
| Next | FG agentic/code. Harness: workspace fixtures + executability judge. Op seed: `jaws_workspace_seed` (regime param empty/single/multi). |

### 5. S2C - Structured Semantic Cloaking  
**Priority: 8/10** * **Lane: both**

| Field | Detail |
|-------|--------|
| Mechanism | Delay full malicious-intent reconstruction until multi-step inference: (1) **Contextual Reframing**, (2) **Content Fragmentation**, (3) **Clue-Guided Camouflage** with recoverable markers. Defeats latent semantic safety that recovers obfuscated intent. |
| Why not covered | DRA/payload-split/misdirection exist as pieces. S2C is a **named three-axis stack** aimed at latent reconstruction, with measured gains over CodeChameleon SOTA. |
| Impact | +12.4% HarmBench / +9.7% JBB over prior SOTA; avg ASR **89.4%**; large gains on GPT-5-mini (+26% JBB vs strongest baseline). |
| Source | arXiv:2603.16192 - https://arxiv.org/abs/2603.16192 |
| Next | FG semantic + composite recipe chaining reframe/split/camouflage ops already in registry; optional `s2c_stack` meta-op. |

### 6. HILL - Hiding Intention by Learning from LLMs (learning-style queries)  
**Priority: 8/10** * **Lane: both**

| Field | Detail |
|-------|--------|
| Mechanism | Deterministic reframing into **learning-style / educational** queries: key concept -> exploratory transformation -> detail-oriented inquiry -> optional hypotheticality. Exploits helpfulness alignment; looks like ordinary teaching questions. |
| Why not covered | **Red Queen** is prevent/defend. **Industry reframing** is commercial dialect. HILL is **pedagogical learning-style** structure with fixed four-component template. |
| Impact | Strong ASR across AdvBench + many models; defenses often weak or even increase ASR; exposes helpfulness vs safety tension. |
| Source | arXiv:2509.14297 - https://arxiv.org/abs/2509.14297 |
| Next | FG semantic/persuasion + op `hill_learning_frame` (4-component template). |

### 7. Agent-driven multi-turn decomposition (safe in isolation, dangerous together)  
**Priority: 8/10** * **Lane: both**

| Field | Detail |
|-------|--------|
| Mechanism | Multi-agent roles: **Question Decomposer**, **Sub-Question Answerer**, **Answer Combiner**. Harmful query split into benign sub-tasks; each answer is safe alone; recombination yields prohibited content. Often **no classical prompt obfuscation**. |
| Why not covered | DRA is single-thread decompose/reassemble. This is **role-separated multi-agent** pipeline with >90% ASR claims vs common jailbreaks. |
| Impact | Often **>90%** ASR on GPT-3.5-Turbo, Gemma-2-9B, Mistral-7B; highest among compared techniques in-paper. |
| Source | Srivastav & Zhang, REALM 2025 - https://aclanthology.org/2025.realm-1.13/ * https://github.com/devansh-srivastav/agents-decomposition-jailbreak |
| Next | FG multiagent + three-stage recipe / arena seats for decomposer/answerer/combiner. |

### 8. ContextualJailbreak - evolutionary simulated conversational priming  
**Priority: 7/10** * **Lane: both** (optimization layer)

| Field | Detail |
|-------|--------|
| Mechanism | Evolutionary search over a **simulated multi-turn primed dialogue** with graded 0-5 harm feedback. Mutators: roleplay, scenario, expand, **troubleshooting**, **mechanistic** (last two novel). Single-shot delivery of the optimized primed context. |
| Why not covered | Crescendo/GOAT/X-Teaming/Mastermind exist. Missing is this **mutator set + graded in-loop judge + simulated priming** package with transfer numbers. |
| Impact | 100% ASR on gpt-oss:20B, qwen3-8B, llama3.1:70B; 90% gpt-oss:120B; +31-96 pp vs baselines. Transfer 70-90% to GPT-4o-mini/GPT-5/Gemini-3-flash; weak on Claude Opus/Sonnet 4.x (~15-17.5%). |
| Source | arXiv:2605.02647 - https://arxiv.org/abs/2605.02647 |
| Next | FG optimization + evolve mutators `troubleshooting` / `mechanistic`; recipe for single-shot primed dump. |

### 9. Claudini - autoresearch discovers attack algorithms  
**Priority: 7/10** * **Lane: FG + meta-harness** (not a string op)

| Field | Detail |
|-------|--------|
| Mechanism | Frontier coding agents in an **autoresearch loop** with 30+ prior attacks + fixed eval budget discover **new white-box algorithms** that beat the library. Methods trained on surrogates transfer to robust targets. |
| Why not covered | AutoDAN-Turbo / strategy_discover exist as *in-process* discovery. Claudini is **external agentic autoresearch over attack code**, with lineage tracing - a different product shape. |
| Impact | GPT-OSS-Safeguard CBRN: up to **80%** ASR vs &lt;50% priors. Meta-SecAlign-70B prompt injection: **100%** ASR vs 82% best prior automated. |
| Source | arXiv:2603.24511 - https://arxiv.org/abs/2603.24511 |
| Next | FG optimization/meta. Optional: document as evaluation bar for defenses; integrate as "attack algorithm discovery" mode in harness docs. |

### 10. Odysseus - dual steganography on commercial MLLM systems  
**Priority: 6/10** * **Lane: FG multimodal first**

| Field | Detail |
|-------|--------|
| Mechanism | Dual steganography: embed malicious **query** into image; coerce model to embed **response** into a carrier image; decode offline. Bypasses filters that assume malice is visible in plaintext I/O. |
| Why not covered | Image IPI, FigStep, stego channels exist. Missing is **dual (query+response) stego pipeline** against commercial MLLM *systems* with I/O filters. |
| Impact | Up to **99%** ASR on GPT-4o, Gemini-2.0-pro/flash, Grok-3 (NDSS 2026). |
| Source | NDSS 2026 Odysseus paper PDF / project refs (dual steganography MLLM) |
| Next | FG multimodal. Op deferred (needs image stego pipeline). |

---

## Near misses (do not re-add)

| Candidate | Why not a gap |
|-----------|----------------|
| H-CoT | Already catalogued - forged *safety* CoT, not puzzle pad |
| Overthinking | Already shipped - budget request only |
| IRIS | Already catalogued - different self-jailbreak loop |
| Function-Calling Jailbreak | Already catalogued - tool-arg coercion != SMT moderation traces |
| DRA / payload split | Covers single-thread decompose; multi-agent role pipeline still gap (#7) |
| Crescendo / X-Teaming / Mastermind / Red Queen / STAC / Industry / ... | Shipped in v1 |
| Constrained Decoding Attack | Present (schema/grammar) |
| Bad Likert, Policy Puppetry, ActorAttack, GOAT, Echo Chamber, FITD, Morris II, ... | Present |

---

## Classification summary

| Lane | Techniques |
|------|------------|
| **Both** (FG + op/recipe) | SLIP, CoT Hijacking (puzzle), SMT, S2C, HILL, Agent multi-turn decomposition, ContextualJailbreak |
| **FG + harness** | JAWS (code agents), Claudini (meta) |
| **FG first / vision later** | Odysseus |

---

## Recommended build order (implementation goal)

1. **`hill_learning_frame` + `cot_puzzle_hijack`** - pure offline string ops, highest immediate deck value.  
2. **`slip_lexical_insert`** - BFS/tree seed; pairs with existing treesearch.  
3. **`s2c_stack` recipe** - mostly compose existing ops.  
4. **`smt_moderation_trace` multi-turn** - function-calling targets.  
5. **Agent decomposition recipe** (decomposer/answerer/combiner seats).  
6. **JAWS workspace harness** - executability judge.  
7. **ContextualJailbreak mutators** in evolve.  
8. **Claudini / Odysseus** - docs + deferred heavy pipelines.

---

## Explicit non-goals of this pass

- Re-listing v1 gaps already shipped.  
- Benchmarks alone (MultiBreak) without a new attack mechanism.  
- Defense-only papers unless they define a new attack surface.
