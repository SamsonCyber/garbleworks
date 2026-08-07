# Gap report: proven techniques missing from the field guide / Garbleworks

**Date:** 2026-08-02  
**Status:** **SHIPPED** - all 10 ranked techniques are in `field-guide.json`; 9 executable ops in `ops/gap_ops.py` (Shadow Alignment is model-level FG only).  
**Baseline at research:** 326 techniques / 159 ops. **After ship:** see live registry.  
**Match method:** casefold title equality, distinctive substring, and mechanism keywords against `title` + `what` + `fam` + op map. Keyword-only "stac" hits were discarded as false positives on the word *stack*.

Ops: `red_queen_frame`, `industry_reframe`, `stac_chain`, `tag_along_seed`, `conjunctive_split`, `mastermind_seed`, `x_teaming_seed`, `overthinking_frame`, `agent_only_perceptual`.

---

## Executive answer

The catalog is already dense on single-turn mutators, classic multi-turn (Crescendo, FITD, Echo Chamber, ActorAttack, GOAT, RACE), MCP/tool-result poison, and multimodal IPI. The **high-impact holes** cluster in three places:

1. **Agent tool-sequence composition** (benign steps -> harmful end state).  
2. **Multi-agent routing / privilege piggybacking** (split triggers, tag-along, planner swarms).  
3. **Semantic cover that is not PAP/persona** (industry dialect laundering; "prevent harm" concealment).

Below: ranked true gaps only. Each is implementable without re-researching the source.

---

## Ranked gaps (impact x novelty for Garbleworks)

Score is informal 1-5 for each of **impact** (measured ASR / class of targets) and **novelty** (new mechanism vs existing FG family). **Priority** = impact + novelty.

### 1. STAC - Sequential Tool Attack Chaining  
**Priority: 10/10** * **Lane: both** (FG writeup + multi-turn agent recipe / harness mode)

| Field | Detail |
|-------|--------|
| Mechanism | Individually harmless tool calls chained so the harmful effect appears only at the last execution step. Pipeline synthesizes executable chains, validates in-environment, reverse-engineers stealthy multi-turn user prompts that induce the chain. |
| Why not covered | Catalog has tool-result poison, tool-description poison, MCP rug-pull/shadowing, confused-deputy. None model **cumulative benign tool sequences** as the attack unit. |
| Impact | Average final ASR **91.2%** on eight SOTA agents; 483 cases, 1,352 interaction sets, 10 failure modes. Prompt defenses weak; ToolShield more durable. |
| Source | Li et al., arXiv:2509.25624, https://arxiv.org/abs/2509.25624 * code: amazon-science/MultiTurnAgentAttack |
| Implement next | FG entry under multiturn/indirect. Op-worthy as recipe stages that emit turn plans + expected tool traces; fire path needs tool-using target (agent seat), not pure string mutator. |

### 2. X-Teaming (adaptive multi-agent multi-turn red team)  
**Priority: 9/10** * **Lane: both** (FG + orchestration layer; not a single string op)

| Field | Detail |
|-------|--------|
| Mechanism | Collaborative agents for **planning**, **attack optimization** (TextGrad), and **verification** generate diverse multi-turn escalations from the same harmful behavior. |
| Why not covered | GOAT, ActorAttack, Crescendo, RACE exist as techniques. Missing is the **named multi-agent planner/optimizer/verifier swarm** with measured diversity gains (+153% plan diversity vs ActorAttack). |
| Impact | ASR up to **98.1%**; **96.2%** on Claude 3.7 Sonnet; closed-source HarmBench ~**94.3%**. XGuard-Train: 30k multi-turn pairs (~20x prior). |
| Source | Rahman et al., arXiv:2504.13203, https://arxiv.org/abs/2504.13203 |
| Implement next | FG entry (optimization / multiturn). Wire as arena ladder profile: planner LLM + attacker LLM + judge, not a `lang_ops` transform. |

### 3. Mastermind (knowledge-driven multi-turn)  
**Priority: 9/10** * **Lane: both** (FG + bandit/knowledge-repo loop)

| Field | Detail |
|-------|--------|
| Mechanism | Closed loop **plan -> execute -> reflect**. Hierarchical goals keep long-horizon coherence. Knowledge repository stores successful patterns and recombines them. |
| Why not covered | AutoDAN-Turbo (self-discovering agent) and bandit selection exist. Mastermind's **persistent attack-knowledge graph + hierarchical decoupling of strategy vs tactics** is not catalogued. |
| Impact | Paper reports substantial ASR/harm gains vs Crescendo, ActorAttack, X-Teaming, Siren on frontier models including GPT-5 and Claude 3.7 Sonnet. |
| Source | Li et al., arXiv:2601.05445, https://arxiv.org/abs/2601.05445 |
| Implement next | FG multiturn. Op-worthy as evolve/bandit extension that persists winning framings across runs (research_store already near this). |

### 4. Red Queen Attack (conceal under "prevent harm")  
**Priority: 8/10** * **Lane: both** (FG + framing op / multiturn seed)

| Field | Detail |
|-------|--------|
| Mechanism | Multi-turn roleplay where the user asks the model to help **stop** or **defend against** a harmful act, so the model generates the attack plan as "prevention advice." |
| Why not covered | Crescendo escalates intensity; FITD uses small commitments; Deceptive Delight camouflages topics. Red Queen's **defensive/prevention guise** is a distinct concealment strategy. |
| Impact | **87.62%** ASR GPT-4o; **75.4%** Llama3-70B; 40 scenarios x 14 harm categories -> 56k dialogues. Larger models more vulnerable. |
| Source | Jiang et al., arXiv:2409.17458, https://arxiv.org/abs/2409.17458 * ACL 2025 Findings |
| Implement next | FG multiturn + `red_queen_frame` op (scenario templates). Trivial offline string/recipe; high ROI. |

### 5. Conjunctive prompt attacks (multi-agent routing)  
**Priority: 8/10** * **Lane: field-guide + agent harness** (not pure string op)

| Field | Detail |
|-------|--------|
| Mechanism | Attack splits into (a) a **trigger key** in the user query and (b) a **hidden adversarial template** in one compromised remote agent. Alone, each is benign; routing joins them into harm. |
| Why not covered | Multi-agent worm / Morris II is self-replication. MCP shadowing is name collision. Conjunctive is **composition across routing topology** (star/chain/DAG). |
| Impact | Routing-aware optimization beats non-optimized baselines; PromptGuard, Llama-Guard, tool restrictions fail when no single component looks malicious. ACL 2026 Main. |
| Source | Arif et al., arXiv:2604.16543, https://arxiv.org/abs/2604.16543 |
| Implement next | FG multiagent/indirect. Harness: multi-agent testbed with injectable agent templates + trigger placement search. |

### 6. Tag-Along Attacks / Slingshot  
**Priority: 8/10** * **Lane: both** (FG + agent RL attacker seat)

| Field | Detail |
|-------|--------|
| Mechanism | Tool-less adversary rides a trusted Operator's tool privileges through conversation only ("tag-along"). Slingshot: cold-start RL that discovers short, instruction-like attack strings (often not long persuasion). |
| Why not covered | Confused-deputy and tool-call injection via chat templates exist. Missing is **tool-less peer that hijacks another agent's privileges** as a first-class threat model with verifiable tool outcomes. |
| Impact | **67.0%** success on held-out extreme tasks vs Qwen2.5-32B Operator (baseline **1.7%**); attempts-to-first-success 52.3 -> 1.3. Zero-shot transfer: Gemini 2.5 Flash **56%**, Meta-SecAlign-8B **39.2%**. |
| Source | Nellessen & Kachman, arXiv:2602.02395, https://arxiv.org/abs/2602.02395 |
| Implement next | FG agentic. Op/recipe: short syntactic "tag-along" seeds + agent_loop target with tool allowlist. |

### 7. Agent-only perceptual injection (mobile VLM)  
**Priority: 7/10** * **Lane: field-guide first** (vision pipeline later)

| Field | Detail |
|-------|--------|
| Mechanism | Exploit near-zero contact touch signals of automated agents: show jailbreak UI/content only on agent interaction paths so human users do not readily perceive the payload. HG-IDA* one-shot optimizes prompts under mobile constraints. |
| Why not covered | Image-based IPI, FigStep, agent-environment pop-ups/hidden DOM exist. Missing is **human-invisible / agent-only perceptual channel** on mobile agents. |
| Impact | Unauthorized cross-app actions: **82.5%** planning, **75.0%** execution hijack (GPT-4o). |
| Source | Ding et al., arXiv:2510.07809, https://arxiv.org/abs/2510.07809 |
| Implement next | FG multimodal/agent. Op deferred until vision/mobile harness; catalog the channel now. |

### 8. Legitimate industry reframing (domain laundering)  
**Priority: 7/10** * **Lane: both** (FG + cheap framing op)

| Field | Detail |
|-------|--------|
| Mechanism | Do not name the banned weapon/agent. Speak the **commercial dialect** that already owns the chemistry/physics: OSCP/pentest education (cyber), pandemic biodefense (bio), agrochemistry (chem), mining/commercial blasting (weapons), legal historiography (fraud). Amplifiers: many-shot priming, prefill. |
| Why not covered | PAP authority/expert and academic/historical misdirection exist. Missing is **CBRN/cyber domain-laundering as a named, measured family** that beats values checks after keyword defenses. |
| Impact | Public measured report on Claude Opus 5 (2026-07): cyber **83%**, bio/chem/weapons **100%**, fraud **83%** average reliability ~93%; many classic ops failed (persuasion 0/16 weapons, DrAttack blocked, cipher/persona partial). Confidence on exact %: **PROBABLE** (public post, not peer review). |
| Source | https://x.com/SingulCore/status/2080744870420083157 |
| Implement next | FG semantic/persuasion. Op `industry_reframe` with domains {cyber_edu, biodefense, agrochem, mining_blast, legal_hist}; stack with `manyshot_seed` + prefill. |

### 9. Shadow Alignment (fine-tune jailbreak of aligned models)  
**Priority: 6/10** * **Lane: field-guide only** (modellevel; not a prompt op)

| Field | Detail |
|-------|--------|
| Mechanism | Fine-tune a safety-aligned open (or FaaS) model on a small set of harmful instruction pairs; refusal collapses while general capability largely remains. |
| Why not covered | Refusal-direction ablation / abliteration is weight-surgery. Shadow Alignment is **data-efficient SFT undoing of alignment** - different attacker capability model. |
| Impact | Foundational result: order of ~10² examples can subvert aligned open models; underpins later FaaS attacks (TrojanPraise et al. stealth variants). |
| Source | Yang et al. Shadow Alignment line (e.g. arXiv:2310.02949 family); see also TrojanPraise arXiv:2601.12460 for modern stealth fine-tune |
| Implement next | FG modellevel writeup + defense notes (moderation of fine-tune sets). No garbleworks string op. |

### 10. Overthinking (extra reasoning budget helps the attacker)  
**Priority: 6/10** * **Lane: field-guide + reasoner fire config**

| Field | Detail |
|-------|--------|
| Mechanism | Empirically, **higher reasoning effort** on thinking models can increase jailbreak success (more chance to invent a benign framing that still satisfies the ask). |
| Why not covered | Catalog has Reasoning Interruption (force *less* think) and H-CoT hijack. Missing is the inverted finding: **more think can be worse** for defenders. |
| Impact | Yang et al. multi-turn analysis: higher reasoning effort -> higher StrongREJECT scores for reasoners (single- and multi-turn). |
| Source | https://arxiv.org/abs/2508.07646 |
| Implement next | FG decoding/reasoning. Harness: `reasoning_effort` axis on targets; do not assume "max think = safer." |

---

## Classification summary

| Lane | Techniques |
|------|------------|
| **Both** (FG + executable path) | STAC, X-Teaming, Mastermind, Red Queen, Tag-Along/Slingshot, Industry reframing |
| **FG + agent harness** (not pure mutator) | Conjunctive multi-agent, Agent-only perceptual |
| **FG only / model-level** | Shadow Alignment |
| **FG + config** | Overthinking |

---

## Explicitly not gaps (do not re-implement)

RACE, Echo Chamber, Deceptive Delight, FITD, ActorAttack, GOAT, Morris II / multi-agent worms, Bad Likert, Policy Puppetry, Crescendo, Many-shot, Prefill, Role-slip delimiter, Amazigh/Tifinagh, code-switch, DRA (covers DrAttack-class decompose/reassemble), MCP rug-pull, tool-result poison, CamoLeak, FigStep, Image Hijacks, AutoDAN-Turbo, Imprompter, Fun-Tuning, Weak-to-Strong, Context Compliance Attack, WordGame, Puzzler, ReNeLLM, BEAST, COLD-Attack, PLeak, MASTERKEY, abliteration, circuit breakers, constitutional classifiers, PoisonedRAG, AgentPoison, BadChain.

---

## Implementation status (shipped 2026-08)

| Technique | FG | Op / seed |
|-----------|----|-----------|
| STAC | yes | `stac_chain` + `rt-stac-chain.json` |
| X-Teaming | yes | `x_teaming_seed` |
| Mastermind | yes | `mastermind_seed` |
| Red Queen | yes | `red_queen_frame` + `rt-red-queen.json` |
| Conjunctive | yes | `conjunctive_split` |
| Tag-Along / Slingshot | yes | `tag_along_seed` |
| Agent-only perceptual | yes | `agent_only_perceptual` |
| Industry reframing | yes | `industry_reframe` + `rt-industry-reframe.json` |
| Shadow Alignment | yes | FG only (model-level) |
| Overthinking | yes | `overthinking_frame` |

Composite recipe: `rt-gap-ship-fanout.json`. Live agent fire (tool targets, multi-agent routing) remains a harness follow-on; offline seeds are in the registry.

---

## Verification notes

- Baseline counts written to session scratch `gap_baseline.txt`.  
- Every ranked gap has a non-empty primary URL and impact number or structural claim.  
- Cross-check dropped candidates listed above with mechanism (not title-only) reasons.  
- In-repo structural test: `backend/test_gap_techniques_absent.py` asserts the named gap titles are still absent from the live FG JSON (so the report does not rot silently if someone adds them later under the same name).
