# Garbleworks

![Garbleworks - recipe alchemy](assets/banner-back.jpg)

**Authorized LLM red-team harness.** Compose attacks as recipes, scan the technique catalog, search with a **history-guided mutator** (not pure random), run standard batteries (HarmBench + JBB/StrongREJECT-shaped loaders) and agentic IPI trials, fire under scope gates, measure with re-fire and confidence bounds. HTTP API, MCP, CLI, and TUI.

[![python](https://img.shields.io/badge/python-3.11%2B-blue)](#end-to-end-first-safe-run)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![ops](https://img.shields.io/badge/ops-179-orange)](#recipe-dsl)
[![interface](https://img.shields.io/badge/interface-HTTP%20%2B%20MCP%20%2B%20CLI%20%2B%20TUI-purple)](#interfaces-quick-start)
[![ci](https://img.shields.io/github/actions/workflow/status/SamsonCyber/garbleworks/ci.yml?branch=main)](https://github.com/SamsonCyber/garbleworks/actions)

> **Authorized security testing only.** Use on models you own or run locally, in-scope bounty targets, written pentests, CTFs, and labs you control. Do not use this to defeat third-party production safety without authorization. See [SECURITY.md](SECURITY.md).

| Maturity | State |
|----------|--------|
| Implemented | Recipe DSL, one fire path, HTTP/MCP/CLI/TUI, history-guided mutator, HarmBench campaign (+ judge plug), multi-dataset loaders, agentic IPI dual scorer + tools-loop, procedural scan, claim gates, dry-run scoreboard (`live_asr.v1`), exporters |
| Independently validated | `python scripts/repro.py` (security tests + math audit, no live model); mutator A/B offline (`mutator compare`) |
| Maintained | Public under [SamsonCyber/garbleworks](https://github.com/SamsonCyber/garbleworks), Apache-2.0 |

---

## What this solves

Fixed jailbreak lists rot. One lucky hit is not a finding. LLM chat sessions dig **one** path and never leave it. Production safety work needs:

1. **Composition** of small transforms (not one opaque string).
2. **Search** over that space (genetic, bandit, QD, tree) plus **history-guided approach mutation** (switch style after refuse/stagnation, with a stated reason).
3. **Outbound fire gates** so a bad or injected target URL cannot hit private LAN or cloud instance-metadata endpoints (SSRF protection on the fire path).
4. **Measured success rates** with confidence bounds (re-fire N times, Wilson intervals). One lucky chat reply is not a finding.
5. **Standards map** so findings land in auditor language (OWASP LLM Top 10, MITRE ATLAS, CWE).
6. **Standard batteries** (official HarmBench download-on-first-use; JBB/StrongREJECT-shaped loaders) so results are not hand-picked prompts.
7. **Agentic IPI** scoring (harm tool x conceal x delivery) so canary plumbing and unread injects are not mislabeled as technique fail.

Garbleworks is that closed loop. The op/recipe idea is not novel (h4rm3l, WildTeaming). The product claim is **search + honest measurement + enforced outbound policy + batteries + agentic surfaces on one spine**.

How the loop runs:

1. Set an **objective** and a **target** (local Ollama, OpenAI-compatible endpoint, or in-process callable).
2. Build attacks as **recipes**, **templates**, a **battery sample**, or the next **reasoned mutation**.
3. **Scan** (coverage map), **search** (stop-on-win / EVOLVE / mutator loop), **campaign** (HarmBench ladder), or **agentic IPI** (tools-loop + dual scorer).
4. **Fire** only through `fire.py`: block private/metadata ranges; MCP engagement host allowlist when a receipt is present.
5. **Score** with detectors, optional graded LLM judge, heuristic or `judge_fn` on HB campaign, or agentic multi-channel outcomes.
6. **Re-fire** winners N times; report rates with Wilson-style bounds; refuse promote on delivery_fail-heavy or plumbing-only estimands.
7. **Map** findings to OWASP / ATLAS / NIST / CWE; **export** to promptfoo / garak / PyRIT shapes.

Core unit (chat / recipe path):

```text
synonym:limit=3 homoglyph:coverage=0.5 zero_width:every=2 tag_wrap
```

Four primitives, one composed candidate. The harness searches compositions instead of sampling a static list.

---

## The tool (what you get)

| Surface | Start | Role |
|---------|-------|------|
| CLI | `python -m garbleworks` | One harness: `scan`, `modules`, `harmbench`, `mutator`, `auto`, `serve`, `mcp` |
| HTTP + web UI | `powershell -File run.ps1` | Human operator at `http://127.0.0.1:9877` |
| MCP | `python backend/mcp_server.py` | **Agent-first** operator + scope receipt |
| TUI | `cd tui && bun start` | v0.1 console (not a full agent REPL) |

There is **one fire path** (`backend/fire.py`). No second unchecked outbound path.

| Capability | How you run it |
|------------|----------------|
| Recipe compose / mutate | HTTP UI, MCP `apply_recipe`, ops catalog (~179 ops) |
| **History-guided mutator** (not pure random) | `python -m garbleworks mutator compare\|loop\|propose`; MCP `reasoned_mutate` / `mutator_compare` |
| Procedural technique scan | MCP `run_scan` ([docs/SCAN-CAMPAIGN.md](docs/SCAN-CAMPAIGN.md)) |
| Stop-on-win auto ladder | `python -m garbleworks auto -- --auto "..." --target local` |
| **HarmBench battery** | `python -m garbleworks harmbench ensure\|sample\|campaign` |
| Multi-dataset loaders | `list_behaviors(source=jailbreakbench\|strongreject\|harmbench)` |
| **Agentic IPI dual scorer** | `python -m spine.ipi_cli`, MCP `run_agentic_ipi` ([docs/IPI-AGENT.md](docs/IPI-AGENT.md)) |
| Tools-loop agent | `agent=openai_tools` / `tools_loop` (offline `chat_fn` or live `base_url`) |
| Claim gates | Wilson LCB, delivery_fail majority reject, optional BH-FDR, dual `success` / `claim_ready` |
| Dry-run scoreboard (`live_asr.v1`) | `python -m bench.live_efficacy --scoreboard --n 30 --dry-run` |
| Validate re-fire | MCP `validate_refire`, agent_loop `--validate` |
| Field guide + crosswalk | MCP `field_guide_*` |
| Offline math + SSRF audit | `python scripts/repro.py` |

```bash
git clone https://github.com/SamsonCyber/garbleworks.git
cd garbleworks
python scripts/repro.py
# expects: REPRO_OK garbleworks security + math audit

cd backend
python -m garbleworks harmbench ensure
python -m garbleworks harmbench campaign -n 5 --dry-run
python -m garbleworks mutator compare --budget 16 --seed 0
python -m spine.ipi_cli run --agent mock_obey --templates report_fill --budget 4
python -m bench.live_efficacy --scoreboard --n 30 --dry-run
```

**Primary tree:** [docs/PRIMARY.md](docs/PRIMARY.md) · **Gaps (honest):** [docs/GAPS.md](docs/GAPS.md)

**Read next:** [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) · [docs/BENCHMARKS.md](docs/BENCHMARKS.md) · [docs/USAGE-AND-API.md](docs/USAGE-AND-API.md) · [docs/IPI-AGENT.md](docs/IPI-AGENT.md) · [Pliny (optional)](#pliny-corpus-optional)

---

## History-guided mutator (not pure random)

LLM chat digs one trench. This mutator is the **relentless multi-approach** layer: next style/family is conditioned on attempt history, each proposal carries a **machine-readable reason**, and a **failure streak on one family forces an approach switch**.

| Policy | Role |
|--------|------|
| `reasoned` (default) | Counter-refuse, escalate partial, exploit success, stagnation switch |
| `random` | Uniform baseline for offline A/B only |

```bash
cd backend
python -m garbleworks mutator compare --budget 20 --seed 7
python -m reasoned_mutator loop --policy reasoned --budget 12
python -m reasoned_mutator propose --history '[{"family":"framing","outcome":"refuse","recipe":[]}]'
```

MCP: `reasoned_mutate(history=[...])`, `mutator_compare(...)`.

Offline A/B (fixed seed/budget, family-selective mock target) is the gating proof that reasoned **beats** uniform random on `successes + 0.25 * unique_success_families`. That is **not** a live frontier ASR claim. Wire a real `fire_fn` for live targets under the same history loop.

Module: `backend/reasoned_mutator.py`. Tests: `test_reasoned_mutator.py`.

---

## HarmBench (standard battery)

Pull the **real** [HarmBench](https://github.com/centerforaisafety/HarmBench) text behavior set into the attack loop (download on first use; CSV cached under `backend/library/`, **not** vendored in git).

| Command | What it does |
|---------|----------------|
| `python -m garbleworks harmbench ensure` | Download/cache official CSV |
| `python -m garbleworks harmbench status` | Path, count, categories |
| `python -m garbleworks harmbench sample -n 8` | Stratified sample |
| `python -m garbleworks harmbench campaign -n 5 --dry-run` | Plan battery + technique ladder |
| `python -m garbleworks harmbench campaign -n 5 --target URL` | Fire ladder at a scoped target |
| `python -m agent_loop --harmbench-campaign --harmbench-n 8` | Agent-loop flags |

MCP: `ensure_harmbench`, `sample_harmbench`, `run_harmbench_campaign`, `list_behaviors(source="harmbench")`.

**Grading:** default = non-refusal **heuristic**. For AttackEval-style scoring: `grade_mode="judge"` + `judge_fn(objective, reply) -> float` in `harmbench_campaign.run_campaign` (CLI `--grade-mode judge` when a judge is wired; tests use stubs). Heuristic stays for CI with no model.

Override cache: `GARBLEWORKS_HARMBENCH_CSV`. Operator JSON: `GARBLEWORKS_BEHAVIORS`.

### Multi-dataset loaders (shared select path)

| `source` | Meaning |
|----------|---------|
| `harmbench` | Official HB CSV (download-on-first-use) |
| `jailbreakbench` | JBB-shaped JSON (fixture + `GARBLEWORKS_JBB`) |
| `strongreject` | StrongREJECT-shaped JSON (fixture + `GARBLEWORKS_STRONGREJECT`) |
| `sample` / `json` | In-repo sample or operator path |

```python
from behaviors import resolve_behaviors
resolve_behaviors(source="jailbreakbench")
resolve_behaviors(source="strongreject")
```

Full corpora are **not** vendored in git (same honesty pattern as HarmBench).

---

## Agentic IPI (dual scorer)

Chat canary is not tool-agent red-team. Agentic mode scores three channels:

| Channel | Meaning |
|---------|---------|
| **Delivery** | Did the inject enter model-visible context? Fail → `delivery_fail` (not technique fail) |
| **Harm** | Did a hard-matched tool call fire (`HarmToolSpec`)? |
| **Conceal** | Did user-visible text avoid forbidden tokens? |

Outcomes: `success`, `harm_only`, `conceal_only` / `no_harm`, `delivery_fail`, `injection_detected`, plus error classes. Claim gate refuses promote when delivery_fail is all or majority of completed trials.

| Entry | Notes |
|-------|--------|
| `python -m spine.ipi_cli list-templates` | tool_result / CSV / report_fill / email / file carriers |
| `python -m spine.ipi_cli run --agent mock_obey` | Offline mocks |
| `python -m spine.ipi_cli run --agent openai_tools --base-url ...` | Live tools-loop |
| MCP `run_agentic_ipi` / `list_ipi_templates` | Same spine path |

Agents: `mock_obey`, `mock_summarize`, `mock_snitch`, `mock_no_ingest`, `mock_detect`, `openai_tools` / `tools_loop`. Full notes: [docs/IPI-AGENT.md](docs/IPI-AGENT.md).

---

## How it works end-to-end

```text
objective + target
        |
        +-- recipe path ---- compose/apply --> fire (scoped) --> detectors/judge
        |                         ^                    |
        |                         |                    v
        |              EVOLVE / bandit / MAP-Elites     re-fire + Wilson
        |              reasoned_mutator (history)              |
        |                                                      v
        |                                          claim gate + export + field guide
        |
        +-- batteries ---- HB / JBB / StrongREJECT sample --> ladder --> fire --> grade
        |
        +-- agentic IPI -- templates/tools-loop --> dual scorer (delivery/harm/conceal)
```

| Stage | What happens | Code |
|-------|----------------|------|
| Compose | Ordered op chain (UI, MCP, optimizer) | `core.run_recipe`, `ops/*` |
| Mutate | History-guided approach + reason; random baseline for A/B | `reasoned_mutator.py` |
| Battery | HarmBench CSV + multi-dataset resolve | `harmbench*.py`, `datasets.py`, `behaviors.py` |
| Agentic | Document carriers + tools-loop | `spine/scorer_agentic.py`, `tools_loop_agent.py` |
| Fire | HTTP or local callable under shared policy | `fire.py`, `targets.py` |
| Detect / score | Multi-signal, LLM judge, dual channels, HB judge plug | `detectors.py`, `spine/*`, `harmbench_campaign.py` |
| Search | Prefer recipes that work; retire ones that do not | `evolve.py`, `optimizer.py`, `rainbow.py`, `bandit.py`, `treesearch.py` |
| Measure | Wilson bounds, validate re-fire, dual success/claim_ready, scoreboard artifact | `validate_refire.py`, `bench/metrics.py`, `bench/live_efficacy.py` |
| Map / export | Framework crosswalk + tool shapes | field guide JSON, `exporters.py` |

Longer walkthrough: **[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)**.

---

## Procedural scan mode (coverage map)

Stop-on-win optimizers (`auto_attack`, bandit, EVOLVE) hunt a **hit**.  
**Procedural scan** walks the **playbook** under a hard fire budget and writes a
**`target_attack_map`**: which techniques are live, dead, or untried for *this*
objective + target.

| | Stop-on-win (`auto_attack` / EVOLVE) | Procedural scan (`run_scan`) |
|---|---|---|
| Goal | Find something that works | Map what works / fails across the catalog |
| Stop | First solid win (or budget) | Budget exhausted or full ladder complete |
| Output | Winning recipe / payload | `target_attack_map` JSON (cells, Wilson bounds, resume) |
| Resume | Re-run search | Checkpoint skips finished cells |

### Phases (one budget)

| Mode | What it does |
|------|----------------|
| `phase_a` | Catalog sweep (one op at a time) |
| `phase_b` | Logical complementary mixes (not random stacks) |
| `phase_c` … `phase_f` | Deeper stacks, nesting, long-turn roleplay, Pliny kit |
| `language` | Language mutators (code-switch, low-resource pivot, nested hop, …) |
| `deep` | C–F + language only |
| `full` | A → B → C → D → E → F → language under one budget |

Fire path is the same scoped path as everything else. Live targets need authorization.

### Quick start (offline echo)

```bash
cd backend
python -c "
from scan_campaign import run_scan
r = run_scan(
    objective='say the secret',
    target=None,  # local echo
    success_substrings=['OBJECTIVE_ACHIEVED'],
    techniques=['base64', 'tag_wrap'],
    budget=8,
    mode='phase_a',
    map_path='map.json',
)
print(r.summary if hasattr(r, 'summary') else r)
"
```

Full phase table and schema: **[docs/SCAN-CAMPAIGN.md](docs/SCAN-CAMPAIGN.md)**.

### Scope and SSRF (non-negotiable)

All outbound HTTP shares `backend/fire.py`:

1. `http` / `https` only.
2. Cloud metadata and other reserved ranges blocked.
3. Loopback / RFC-1918 allowed by default for local labs; `GARBLEWORKS_BLOCK_PRIVATE=1` tightens.
4. No redirects after validation.
5. MCP fire requires host in `authorized_scope` (default `127.0.0.1` / `localhost`).
6. Body and fan-out caps.

HTTP API is unauthenticated: bind **127.0.0.1 only**. See [SECURITY.md](SECURITY.md).

---

## Why this over alternatives (honest)

The composable-recipe idea is not novel ([h4rm3l](https://arxiv.org/abs/2408.04811), [WildTeaming](https://arxiv.org/abs/2406.18510)).
**The product is the closed loop:** search, scoped fire, re-fire, reportable bounds, standards map, standard batteries, history-guided multi-approach mutation, and agentic multi-channel scoring on one fire path.

Peers below are different jobs. Rows are "has a first-class operator path today," not marketing fluff.

| Capability | Fixed lists | garak / PyRIT | h4rm3l | Wallbreaker-class agent REPL | **Garbleworks** |
|---|:---:|:---:|:---:|:---:|:---:|
| Composable attack DSL | - | partial | yes | transforms / Parseltongue | **yes** (~179 ops) |
| Genetic + quality-diversity search | - | - | bandit synth | attack loops | **EVOLVE + MAP-Elites** |
| History-guided approach switch + reasons | - | - | - | agent judgment | **yes** (`reasoned_mutator`) |
| Thompson bandit + recipe lifecycle | - | - | - | partial | **yes** |
| Multi-turn beam tree search | - | partial | - | multi-turn loops | **yes** |
| Procedural coverage scan (`target_attack_map`) | - | probe dump | - | scan tools | **yes** (`run_scan`) |
| Wilson / complete-case ASR + promotion gates | - | partial | - | validate re-fire | **yes** (dual `success` / `claim_ready`) |
| Validate re-fire (N times) | - | yes | - | yes | **yes** |
| Delivery_fail ≠ technique fail (claim gate) | - | - | - | operator judgment | **enforced** |
| Agentic IPI dual scorer (harm x conceal x delivery) | - | agent probes | - | tool agent UX | **yes** (spine + mocks + tools-loop) |
| Official HarmBench battery in attack loop | - | adapters | - | **yes** (in-tree) | **yes** (download-on-first-use + campaign) |
| JBB / StrongREJECT-shaped loaders | - | adapters | - | datasets package | **yes** (fixtures + env) |
| Graded LLM judge (4-level) + HB judge plug | - | partial | - | judge | **yes** |
| Dry-run scoreboard schema (`live_asr.v1`) | - | - | - | - | **yes** (plumbing only) |
| OWASP / ATLAS / NIST / CWE crosswalk + export | - | partial | - | - | **yes** |
| Enforced SSRF + MCP scope receipt | - | policy only | - | config | **enforced on every fire** |
| Offline math + plumbing audit you can re-run | - | - | - | - | **yes** (`repro.py`) |
| Full interactive agent REPL (Claude Code-style) | - | - | - | **yes** | partial (MCP-first + TUI v0.1) |
| Persona author (ENI) / sysprompt corpus mimicry | - | - | - | **yes** | low / optional personas |
| Multimodal image-edit attack channel | - | partial | - | **yes** | not shipped (text-first) |
| Full HB-400 **vendored in git** | - | - | - | often yes | **no** (cache on first use) |

### Where Garbleworks leads

- **Measurement honesty:** complete-case ASR, delivery_fail not folded into no_harm, dual mean vs LCB flags, optional BH-FDR, offline math audit.
- **Operator-owned search** on a composable DSL (genetic + QD + bandit + tree) plus **history-guided multi-approach mutation** that beats pure random offline.
- **Hard fire policy** on every path (HTTP, MCP, campaign, auto, mutator).
- **Two estimands on one spine:** chat/recipe efficacy and agentic IPI.
- **HarmBench + multi-dataset path** without AGPL merge and without shipping full corpora in git.

### Where peers still win (do not paper over)

- **garak / PyRIT:** huge community probe libraries and enterprise packaging.
- **Wallbreaker-class REPL:** full interactive agent UX, persona author (ENI), multimodal image channel, HB often in-tree for zero-setup UX.
- **Published multi-model ASR leaderboards:** GW has dry-run schema + operator runbook; live powered tables remain operator-funded ([docs/LIVE-ASR-RUNBOOK.md](docs/LIVE-ASR-RUNBOOK.md)).

Positioning: [docs/HARNESS-POSITIONING.md](docs/HARNESS-POSITIONING.md). Residual gaps: [docs/GAPS.md](docs/GAPS.md).

---

## Benchmarks (offline, re-runnable)

Full tables: **[docs/BENCHMARKS.md](docs/BENCHMARKS.md)**.

**What we publish:** math golden checks, Wilson coverage Monte Carlo, open/closed-loop echo latency and hit rates, genetic optimizer audit, export structural checks, SSRF/scope rejects, dual success/claim_ready hygiene, mutator vs-random offline A/B.
**What we do not claim as product defaults:** multi-provider live ASR leaderboard numbers (operator runbook only).

### Snapshot (2026-08-02T20:29:46Z, Python 3.11, full suite ~31 s)

| Suite | Result | Headline metrics |
|-------|--------|------------------|
| Math closed form | pass | 14 / 14 formula checks |
| Wilson coverage MC | pass | mean coverage **0.9085** (nominal 0.9); min 0.849 |
| LCB gate audit | pass | dual flags: mean `success` vs LCB `claim_ready` |
| Open loop (echo) | pass | 80 fires; plaintext hit rate 1.0; **p50 ~2 ms** (loopback) |
| Closed loop | pass | 10 runs; hit rate 1.0; p50 ~568 ms |
| Optimizer GA | pass | success_flag_rate 1.0; LCB claim path documented separately |
| Export | pass | promptfoo + garak + PyRIT structural OK |
| Security | pass | 6 / 6 SSRF + scope checks |

```bash
python scripts/publish_offline_benchmarks.py
cd backend && python benchmark_harness.py --fail-on-regression
python scripts/repro.py
python -m garbleworks mutator compare --budget 16 --seed 0
```

---

## Recipe DSL

```json
[
  {"op": "synonym", "params": {"limit": 3}},
  {"op": "homoglyph", "params": {"coverage": 0.5}},
  {"op": "zero_width", "params": {"every": 2}},
  {"op": "tag_wrap", "params": {}}
]
```

Live registry after `import ops`: on the order of **~179** ops across encoding, character, template, jailbreak, structure, prose, sampler, stego, language, carrier, llm, gap techniques, Pliny frames.
Coverage notes: [COVERAGE.md](COVERAGE.md).

### Targets

| Adapter | Use |
|---------|-----|
| `raw` | HTTP with `{payload}` body template + JSON `response_path` |
| Provider helpers | Anthropic / Gemini-style shapes on a permitted endpoint |
| Local callable | In-process dry run |
| Tools-loop | OpenAI-compatible chat+tools (`openai_tools` agent) |

---

## Interfaces (quick start)

### Operator surface (MCP-first)

Agent operators should prefer **MCP** (`python backend/mcp_server.py`): one fire path, engagement receipt, tools for compose/scan/HarmBench/mutator/agentic IPI. CLI covers scripts and CI. **TUI is v0.1** and is **not** a full Wallbreaker-style interactive agent REPL. Multimodal/image is out of scope.

### CLI (primary)

```bash
cd backend
python -m garbleworks scan
python -m garbleworks harmbench status
python -m garbleworks harmbench campaign -n 5 --dry-run
python -m garbleworks mutator compare --budget 16 --seed 0
python -m garbleworks auto -- --auto "authorized objective" --target local --mode local
python -m spine.ipi_cli run --agent mock_obey --templates report_fill
python -m bench.live_efficacy --scoreboard --n 30 --dry-run
```

### HTTP API + web UI

```powershell
powershell -ExecutionPolicy Bypass -File run.ps1
# http://127.0.0.1:9877
```

### MCP

```powershell
pip install "mcp>=1.2,<2"
python backend/mcp_server.py
```

Copy [.mcp.json.example](.mcp.json.example).

| Cluster | Tools (examples) |
|---------|------------------|
| Compose / search | `apply_recipe`, `optimize`, `auto_attack`, `pack_hunt*`, `reasoned_mutate`, `mutator_compare` |
| Coverage | `run_scan` |
| Measurement | `validate_refire`, `rank_strategy_claims`, scoreboard via CLI/`live_efficacy` |
| Batteries | `ensure_harmbench`, `sample_harmbench`, `run_harmbench_campaign`, `list_behaviors` |
| Agentic IPI | `list_ipi_templates`, `run_agentic_ipi`, `score_document_detectability` |
| Map | `field_guide_*`, `mcp_spine_map` |

### TUI

```powershell
cd tui
bun install
bun start
```

---

## Pliny corpus (optional)

Builtin Pliny-family **structure** ships with the repo: GODMODE / NEW PARADIGM anchors, ResponseFormat split, Family-27 misdirection, operator signature chrome. No dump required.

Optional **external** dumps (L1B3RT4S, CL4R1T4S) load as **composable frames**, not opaque mega-prompt paste. They become extra recipe steps on the same fire path.

```bash
python scripts/pliny_plug.py doctor
python scripts/pliny_plug.py apply builtin.godmode "authorized objective"

# optional external dump (never committed)
git clone --depth 1 https://github.com/elder-plinius/L1B3RT4S.git corpora/L1B3RT4S
python scripts/pliny_plug.py list --source corpus
```

```bash
export GARBLEWORKS_PLINY_CORPUS=/path/to/L1B3RT4S   # POSIX
# $env:GARBLEWORKS_PLINY_CORPUS = "D:\datasets\L1B3RT4S"  # Windows
```

| Source | In Garbleworks |
|--------|----------------|
| Builtin kit | Always on (`pliny_frame`, phase F) |
| L1B3RT4S / CL4R1T4S | Drop into `corpora/…` or set env |
| G0DM0D3 / OBLITERATUS | Not string adapters (UI / weight surgery) |
| GLOSSOPETRAE | Language ideas map to in-tree lang ops |

Details: [corpora/README.md](corpora/README.md) · ops `pliny_frame` / `pliny_list_frames`.

---

## End-to-end: first safe run

1. Install backend (Python 3.11+):

```powershell
git clone https://github.com/SamsonCyber/garbleworks.git
cd garbleworks\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Echo target (no model):

```powershell
python echo_target.py 9001
```

3. API on loopback:

```powershell
cd ..
powershell -ExecutionPolicy Bypass -File run.ps1
```

4. Fire a trivial recipe at `http://127.0.0.1:9001/` from the UI.

5. Battery + mutator + agentic offline checks:

```powershell
cd backend
python -m garbleworks harmbench ensure
python -m garbleworks harmbench campaign -n 3 --dry-run
python -m garbleworks mutator compare --budget 16 --seed 0
python -m spine.ipi_cli run --agent mock_obey --templates report_fill --budget 3
python -m bench.live_efficacy --scoreboard --n 30 --dry-run
python -m pytest -q test_security.py test_harmbench.py test_agentic_ipi.py test_tools_loop_agent.py test_reasoned_mutator.py test_gap_residual_1_4.py
python benchmark_harness.py --fail-on-regression
```

Env: copy [.env.example](.env.example). Keys: `GARBLEWORKS_SCOPE`, `GARBLEWORKS_BLOCK_PRIVATE`, `GARBLEWORKS_FIELDGUIDE`, `GARBLEWORKS_LLM_URL`, `GARBLEWORKS_HARMBENCH_CSV`, `GARBLEWORKS_BEHAVIORS`, `GARBLEWORKS_JBB`, `GARBLEWORKS_STRONGREJECT`.

---

## Repository map

```text
garbleworks/
|-- README.md
|-- SECURITY.md
|-- EVOLVE_MATH.md
|-- COVERAGE.md
|-- docs/
|   |-- HOW_IT_WORKS.md, USAGE-AND-API.md, SCAN-CAMPAIGN.md
|   |-- BENCHMARKS.md, GAPS.md, IPI-AGENT.md, PRIMARY.md
|   |-- LIVE-ASR-RUNBOOK.md, HARNESS-POSITIONING.md
|-- scripts/repro.py, scripts/pliny_plug.py
|-- backend/
|   |-- app.py, fire.py, core.py, ops/, mcp_server.py
|   |-- harmbench.py, harmbench_campaign.py, harness_cli.py
|   |-- reasoned_mutator.py, datasets.py, behaviors.py
|   |-- scan_campaign.py, agent_loop.py
|   |-- spine/   # campaign, dual scorer, IPI templates, tools-loop
|   |-- bench/   # live_efficacy, battery fixtures, metrics
|   |-- optimizer.py, rainbow.py, bandit.py, treesearch.py
|   `-- test_*.py
|-- tui/
|-- frontend/
|-- corpora/     # optional Pliny dumps (gitignored content)
```

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) | End-to-end operator walkthrough |
| [docs/USAGE-AND-API.md](docs/USAGE-AND-API.md) | HTTP/UI reference |
| [docs/IPI-AGENT.md](docs/IPI-AGENT.md) | Agentic IPI dual scorer + templates |
| [docs/SCAN-CAMPAIGN.md](docs/SCAN-CAMPAIGN.md) | Procedural technique scan |
| [docs/BENCHMARKS.md](docs/BENCHMARKS.md) | Offline metrics + re-run |
| [docs/LIVE-ASR-RUNBOOK.md](docs/LIVE-ASR-RUNBOOK.md) | Operator live ASR path |
| [docs/GAPS.md](docs/GAPS.md) | Closed vs open gaps (honest) |
| [docs/HARNESS-POSITIONING.md](docs/HARNESS-POSITIONING.md) | Literature positioning |
| [EVOLVE_MATH.md](EVOLVE_MATH.md) | Optimizer statistics |
| [CHANGELOG.md](CHANGELOG.md) | Unreleased notes |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribute |

---

## Roadmap (residual)

**Shipped (off this list):** history-guided mutator + offline A/B vs random; HB judge plug; multi-dataset loaders; dry-run scoreboard n≥30; MCP-first docs; HarmBench campaign; agentic IPI dual scorer; dual claim flags.

Still intentionally open:

- [ ] Powered multi-model **live** ASR leaderboard numbers (operator keys/budget)
- [ ] Full interactive agent **REPL** UX (MCP-first stance; not building REPL here)
- [ ] Multimodal / vision channel (skipped)
- [ ] Persona author (ENI) / sysprompt corpus mimicry
- [ ] Production-calibrated live LLM judge wiring (plug ships; model/env is operator)
- [ ] `pip install garbleworks` packaged CLI on PyPI
- [ ] Purple-team mode: ASR with each defense enabled

See [docs/GAPS.md](docs/GAPS.md).

---

## References

- HarmBench: Mazeika et al. 2024, [arXiv:2402.04249](https://arxiv.org/abs/2402.04249) · [github.com/centerforaisafety/HarmBench](https://github.com/centerforaisafety/HarmBench)
- h4rm3l: Doumbouya et al. 2024, [arXiv:2408.04811](https://arxiv.org/abs/2408.04811)
- WildTeaming: Jiang et al. 2024, [arXiv:2406.18510](https://arxiv.org/abs/2406.18510)
- Rainbow Teaming: Samvelyan et al. 2024, [arXiv:2402.16822](https://arxiv.org/abs/2402.16822)
- Tempest: Zhou & Arel 2025, [arXiv:2503.10619](https://arxiv.org/abs/2503.10619)

---

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

Built by [SamsonCyber](https://github.com/SamsonCyber). Field-guide data from [llm-injection-field-guide](https://github.com/SamsonCyber/llm-injection-field-guide).
