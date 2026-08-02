# Spec: DGX Spark as Garbleworks Generator Cluster

Status: design (research-backed). Implements nothing yet.  
Audience: operator (nephew). Goal: resume-grade, bounty-ready mutator brain on DGX Spark, not a Wallbreaker clone.

---

## 0. Verdict

**Hook the Spark into Garbleworks as a multi-role local brain farm.** Do not rewrite the harness. Do not vendor Wallbreaker (AGPL).

What you already own (`C:\code\garbleworks`):

| Layer | Status | Spark impact |
|---|---|---|
| 138-op recipe forge | Shipped | Feeds better LLM mutations |
| EVOLVE + MAP-Elites + bandit | Shipped | Needs smarter seed text |
| `llm.py` Ollama generator | Shipped, 7B-class default | **Primary upgrade path** |
| `brain.py` multi-provider (attacker / judge / generator) | Shipped | Point roles at Spark vLLM/Ollama |
| Arena ladders + Gray Swan solver | Shipped (`arena_solver.py`) | Higher quality moves per budget |
| Validate re-fire + Wilson / promotion | Shipped | Resume / bounty evidence spine |
| MCP + TUI | Shipped | Operator surface stays |

The gap is not "more transforms." The gap is **generator quality under closed-loop search**: stronger ablated models produce better `llm_reframe` / `llm_generate` / PAIR attacker turns / persona drafts, which then ride the existing op stack and stats gates.

---

## 1. Hardware reality (DGX Spark)

| Spec | Value | Implication for us |
|---|---|---|
| Chip | GB10 Grace Blackwell | CUDA 12.x stack; ARM CPU |
| Memory | **128 GB unified** LPDDR5x | Fits 70B Q4–Q5 and dual 32B stacks |
| Bandwidth | **~273 GB/s** | Token/s limited vs desktop GDDR; batch and keep-alive matter |
| Perf | Up to ~1 PFLOP FP4 | Prefer quantized kernels (NVFP4 / AWQ / GPTQ where supported) |
| Storage | 1–4 TB NVMe | Multiple model banks on disk; swap by role |

Sources: NVIDIA product page / DGX Spark user guide (unified 128 GB, 273 GB/s).

**Design consequence:** optimize for **concurrent role isolation** and **long keep-alive**, not for raw 405B full-precision cosplay. Prefer one hot 32B–70B generator + optional lighter judge, over three cold 70Bs thrashing memory.

---

## 2. Competitive landscape (honest)

### 2.1 Wallbreaker ([JailbrokenAI/wallbreaker](https://github.com/JailbrokenAI/wallbreaker))

| Strength | Our response |
|---|---|
| Agent REPL + huge tool surface | Keep MCP + TUI; deepen tools, do not AGPL-merge |
| Parseltongue / P4RS3LT0NGV3 (50–222 transforms) | We have 138 ops + field-guide map; parity is catalog, not novelty |
| PAIR / TAP / Crescendo / BoN loops | We have optimizer, treesearch, arena ladders |
| Persona author (ENI) + sysprompt corpus | Gap: optional later (GAPS.md) |
| Multimodal image channel | Low priority for text bounty / Arena chat |
| HarmBench batteries | Wire via `GARBLEWORKS_BEHAVIORS`, never vendor full set |
| AGPL-3.0 | **Subprocess bench only** (`bench/runner_wallbreaker.py`). No code copy. |

### 2.2 Other peers

| Tool | Role | Differentiator we keep |
|---|---|---|
| **h4rm3l** | Composable jailbreak DSL | We already map 1:1 (HARNESS-POSITIONING.md) |
| **PyRIT / garak / promptfoo** | Scanner / export ecosystem | Export recipes; we own closed-loop search |
| **EasyJailbreak** | Mutator/constraint/eval taxonomy | Already mirrored in SPEC-redteam-harness |
| **Gray Swan Arena / Shade** | Live adversarial arena + enterprise RT | Consumer of our solver, not a library we fork |
| **T3MP3ST / Rainbow / TAP / AutoDAN-Turbo** | Academic loops | Mapped into treesearch / rainbow / optimizer |

### 2.3 Resume wedge (what you claim)

Do **not** claim "another jailbreak CLI." Claim:

> **Composable attack search harness with statistically honest promotion, engagement-scoped fire, and a local uncensored generator cluster sized for live mutation under bounty / Arena budgets.**

Artifacts that prove it:

1. Wilson LCB + validate re-fire reports (not one-shot COMPLIED).
2. Head-to-head McNemar bench vs Wallbreaker on shared canary (`docs/BENCH-VS-WALLBREAKER.md`).
3. Arena run logs with class-aware ladders + burned-cell policy.
4. Public field-guide crosswalk (OWASP / ATLAS / CWE).
5. Scope receipts (SSRF + engagement gate).

---

## 3. Model bank for Spark (ablated / uncensored)

### 3.1 Roles (map to `brain.py`)

| Role | Job | Guardrails | Env prefix |
|---|---|---|---|
| **GENERATOR** | `llm_reframe`, `llm_generate`, prose rewrites | Must be open / ablated | `GARBLEWORKS_GENERATOR_*` |
| **ATTACKER** | PAIR / optimize / creative seed authoring | Open preferred; strong instruction following | `GARBLEWORKS_ATTACKER_*` |
| **JUDGE** | Graded AttackEval (0 / .33 / .66 / 1.0) | Prefer *calibrated* model; can be guarded if rubric is clear | `GARBLEWORKS_JUDGE_*` |
| **TARGET** | Optional local self-test only | Can be ablated or stock | TargetCfg (not brain) |

Generator and attacker must not be Claude/GPT for sensitive classes without `SAFETY_OK` (brain.py already warns).

### 3.2 Fit matrix (128 GB unified; Q4/Q5-ish)

Sizes are **approximate** RAM for weights + KV; leave 16–24 GB free for OS + concurrent server.

| Tier | Model family (examples) | Approx RAM | Role | Notes |
|---|---|---|---|---|
| **A — Hot generator** | Qwen2.5 / Qwen3 **32B** abliterate (huihui_ai / community) | ~20–24 GB Q4 | GENERATOR primary | Best latency / quality trade on Spark bandwidth |
| **B — Heavy mutator** | Llama-3.3 / Qwen2.5 **70B** abliterate Q4 | ~40–48 GB | ATTACKER or overnight EVOLVE | Stronger multi-step mutation; slower tokens/s |
| **C — Fast swarm** | Qwen2.5 **14B** abliterate Q5/Q6 | ~10–12 GB | Parallel reframe fan-out | Many short `llm_reframe` calls |
| **D — Judge** | Qwen2.5 **14B–32B instruct** (stock or light ablate) | 10–24 GB | JUDGE | Prefer consistent rubrics over max uncensored |
| **E — Canary target** | Current 7B abliterate or stock 7–14B | 5–10 GB | local TARGET only | Never call this "frontier ASR" |

**Current lab baseline:** `huihui_ai/qwen2.5-abliterate:7b-instruct-q4_K_M` via Ollama (`TARGET-abliterated-qwen.json`, `llm.DEFAULT_MODEL=ablit:latest`). Spark goal: **upgrade GENERATOR to Tier A, ATTACKER to A or B**, keep judge separate.

### 3.3 Serving stack

| Option | When |
|---|---|
| **Ollama** (Spark) | Day-1 path; zero code change (`GARBLEWORKS_LLM_URL=http://spark:11434`) |
| **vLLM OpenAI server** | Production Spark path; higher throughput, continuous batching for swarm reframes |
| **SGLang / TensorRT-LLM** | Later if latency on 70B is the bottleneck |

`brain.py` already accepts `provider=openai` + custom `BASE_URL` for vLLM. Prefer that for multi-role concurrency; keep Ollama as fallback.

### 3.4 Model hygiene (non-optional for a serious tool)

1. **Checksum + tag lock** in `models/registry.toml` (name, quant, SHA, license, source URL).
2. **Refusal self-test** on generator: 20 known author-role prompts must return non-empty, non-deflect text (extend `llm_ops` two-party contract tests).
3. **Judge calibration set** (`bench/calibration/canary_labeled.json` pattern) before any ASR claim.
4. **No model weights in git.** Document pull scripts only.

---

## 4. Architecture: Spark-backed mutation stack

```
                    ┌─────────────────────────────────────────┐
                    │  Operator: TUI / MCP / CLI / Arena UI    │
                    └───────────────────┬─────────────────────┘
                                        │
                    ┌───────────────────▼─────────────────────┐
                    │  Garbleworks control plane (desktop/Pi) │
                    │  optimizer · bandit · treesearch · arena│
                    │  fire · scope · validate_refire · logs  │
                    └───────┬─────────────────┬───────────────┘
                            │                 │
              brain roles   │                 │  fire (in-scope only)
                            ▼                 ▼
              ┌─────────────────────┐   ┌──────────────────┐
              │  DGX Spark cluster  │   │  Target (bounty /│
              │  vLLM or Ollama     │   │  Arena / lab)    │
              │  GEN / ATK / JUDGE │   └──────────────────┘
              └─────────────────────┘
```

### 4.1 Mutation pipeline (product behavior)

For one objective:

1. **Seed** — creative catalog + bandit top arms + optional ATTACKER draft.
2. **Compose** — recipe chain (deterministic ops) and/or LLM reframes (GENERATOR).
3. **Phenotype dedupe** — shingle Jaccard before burn (mutation analysis Tier-2).
4. **Fire** — scoped adapter; tripwire → burned-cells / clean track.
5. **Score** — detectors + JUDGE graded score.
6. **Update** — bandit posteriors, EVOLVE credits, research_store promote/retire.
7. **Confirm** — `validate_refire` N× before claim; Wilson LCB in report.

### 4.2 New modules (proposed)

| Module | Purpose |
|---|---|
| `backend/spark_cluster.py` | Health, model list, role→endpoint map, VRAM budget check |
| `models/registry.toml` | Locked model bank |
| `scripts/spark_bootstrap.sh` | Install CUDA stack, pull tags, smoke chat |
| `backend/ops/llm_ops.py` | Parallel reframe pool size knobs for Tier C |
| `backend/mutation_policy.py` | Tripwire-aware op bans (from mutation analysis + arena) |
| `docs/REPORT-TEMPLATE.md` | Bounty / Arena evidence pack schema |

### 4.3 Config sketch (day-1 Spark)

```bash
# Control plane (desktop still runs harness)
export GARBLEWORKS_LLM_URL=http://192.168.x.spark:11434
export GARBLEWORKS_LLM_MODEL=qwen2.5-ablit-32b:q4

export GARBLEWORKS_GENERATOR_PROVIDER=ollama
export GARBLEWORKS_GENERATOR_MODEL=qwen2.5-ablit-32b:q4
export GARBLEWORKS_GENERATOR_BASE_URL=http://192.168.x.spark:11434

export GARBLEWORKS_ATTACKER_PROVIDER=ollama
export GARBLEWORKS_ATTACKER_MODEL=qwen2.5-ablit-32b:q4   # or 70B overnight

export GARBLEWORKS_JUDGE_PROVIDER=ollama
export GARBLEWORKS_JUDGE_MODEL=qwen2.5-14b-instruct:q5
```

vLLM variant: set `PROVIDER=openai` and `BASE_URL=http://spark:8000/v1`.

### 4.4 Mutation sophistication upgrades (priority order)

Grounded in existing gap analysis (KB 2026-07-12) and code:

1. **Tripwire-aware optimizer policy** (arena already has it; optimizer does not).
2. **UCB seed credit inject** (EVOLVE_MATH §10 — currently incomplete).
3. **Dynamic basket** from creative + bandit + host posteriors.
4. **Target-class surface routing** (obfuscation off on soft targets).
5. **Free refusal-direction pre-filter** from fire_history embeddings (prior art: DROJ / xJailbreak / STEER — integration only, not claimed novelty).
6. **Multi-model generator ensemble** — reframe with 14B swarm, polish with 32B/70B.
7. **BH-FDR as optional gate** (spec exists; not default yet).

Spark makes 5–6 practical (latency budget). Without Spark, 5–6 stay toy-scale.

---

## 5. Gray Swan Arena + bounty product surface

### 5.1 Arena

Existing: `arena_solver.py`, `arena_ladders.py`, `arena_class.py`, `browser_fire.py`, MCP garbleworks tools.

Spark upgrades:

| Capability | Why |
|---|---|
| Stronger clean-first rewrites | Arena tripwires punish obfuscation early |
| Class-conditioned ladder moves | exam / agent / IPI / SCADA need different prose |
| Faster multi-turn densify / continue | Treesearch budgets stretch on slow 7B |
| Offline rehearsal | Mutate against local ablated target before live Arena spend |

**Do not automate against Arena ToS violations.** Operator-in-loop for account actions; harness advises and logs.

### 5.2 Bug bounty / huntr-class

| Capability | Artifact |
|---|---|
| Scope receipt | `authority.py` engagement gate |
| Repro pack | payload + N re-fire log + judge scores |
| Framework map | field-guide OWASP/ATLAS tags |
| Transfer note | cross-model weakpoints store |
| Negative results | research_store retire reasons |

### 5.3 Challenge modes productized

| Mode | Engine | Success metric |
|---|---|---|
| `canary` | local secret leak | is_leak + validate_refire |
| `behavior` | HarmBench-shaped JSON | graded judge + LCB |
| `arena` | class ladder + browser session | challenge pass / lock policy |
| `agent` | tool-output / IPI carriers | detector + judge |
| `transfer` | multi-target fire | McNemar / ASR delta |

---

## 6. What "not a toy" means (acceptance criteria)

Ship when **all** pass:

1. **Day-1:** Spark Ollama reachable from desktop; `llm.chat` + `brain.chat` for three roles green.
2. **Generator self-test:** ≥18/20 author-role fixtures non-deflect (recorded JSON).
3. **Bench:** `python -m bench --tools garbleworks:gw_optimize --tag spark_v1` vs prior 7B baseline; report LCB lift or honest null.
4. **Validate path:** one objective with `validate-n ≥ 5` and promotion decision documented.
5. **Arena dry-run:** mock arena ladder completes without scope violations.
6. **Security:** no private-IP fire without engagement; remote brain still opt-in.
7. **Docs:** this spec + operator runbook + model registry + one sample report suitable for resume appendix (redacted).

Optional stretch (resume gold):

8. Wallbreaker A/B on shared canary (subprocess only) with McNemar table.
9. Public write-up: "statistically honest local mutator on GB10" (no exploit dump).

---

## 7. Build phases

### Phase 0 — Wire (1–2 days after box lands)

- Network: Spark on LAN; firewall allow harness host only.
- Ollama install; pull Tier A + C + D.
- Point `GARBLEWORKS_*` env; smoke MCP generate_framings.
- Document serial / MAC / IP in private ops note (not git).

### Phase 1 — Mutation quality (1–2 weeks)

- Parallel reframe pool (Tier C).
- Mutation policy module (tripwire bans).
- Dynamic basket + UCB inject if still open.
- Ablation: 7B vs 32B generator on fixed battery (n≥30 where API allows; local canary for free).

### Phase 2 — Cluster roles (1 week)

- vLLM dual-serve or multi-model Ollama keep-alive policy.
- Separate JUDGE model; calibration suite.
- `spark_cluster` health in `/health` and TUI.

### Phase 3 — Product polish (ongoing)

- Report template + export for bounty.
- Arena operator pack (class ladders + burned cells UI).
- Optional persona author (ENI-style) only if Arena / bounty demand it.

---

## 8. Risks and non-goals

| Risk | Mitigation |
|---|---|
| 273 GB/s caps 70B tok/s | Prefer 32B hot path; 70B for offline EVOLVE |
| Ablated model still deflects on "your system prompt" | Keep two-party author contract in `llm_ops` |
| Claiming novelty on refusal-direction | Cite prior art; ship as pre-filter only |
| AGPL contamination from Wallbreaker | Subprocess bench only; no shared package |
| Resume looks like "script kiddie kit" | Lead with stats, scope, field-guide, not payload dumps |
| Hosted uncensored APIs log prompts | Prefer local Spark for sensitive classes |

**Non-goals:**

- Multimodal image jailbreak v1.
- Shipping full HarmBench weights in-repo.
- Beating Wallbreaker on every surface (different product shape).
- Unscoped third-party production attacks.

---

## 9. Success metrics (lab)

| Metric | Baseline (today) | Target (Spark v1) |
|---|---|---|
| Generator model | ~7B ablit | 32B ablit primary |
| Mean reframe latency (n=10) | measure on 3070/9B path | ≤ baseline on equal tokens **or** better quality at +50% latency |
| Optimize held-out success rate on local canary battery | measure | + relative lift with CI |
| Empty / deflect generator rate | measure | <5% on author fixtures |
| Validate_refire claims with LCB language | partial | 100% of external reports |

---

## 10. References (primary)

Internal:

- `README.md`, `HARNESS-POSITIONING.md`, `docs/BENCH-VS-WALLBREAKER.md`, `docs/GAPS.md`
- `backend/llm.py`, `brain.py`, `ops/llm_ops.py`, `optimizer.py`, `arena_solver.py`
- KB: mutation process improvement 2026-07-12; competitive positioning vs T3MP3ST/Tempest/PyRIT/garak

External:

- NVIDIA DGX Spark hardware (128 GB unified, 273 GB/s)
- Wallbreaker README (AGPL, tool surface)
- h4rm3l (arXiv:2408.04811), WildTeaming, Rainbow Teaming, PAIR/TAP/AutoDAN family
- Gray Swan Arena / Shade product surface (adversarial challenges)

---

## 11. Immediate next actions (when you say go)

1. Freeze model registry (Tier A/C/D tags) for purchase-day pull list.
2. Add `spark_cluster` health + role env docs to `docs/USAGE-AND-API.md`.
3. Implement generator fixture battery + CI offline mock.
4. After hardware: Phase 0 wire + 7B vs 32B ablation report.

End of spec.
