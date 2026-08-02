<div align="center">

# Garbleworks

**Authorized LLM red-team harness: composable attack recipes, evolve/search, scoped fire, MCP + TUI.**

</div>

![python](https://img.shields.io/badge/python-3.11%2B-blue)
![license](https://img.shields.io/badge/license-Apache--2.0-blue)
![ops](https://img.shields.io/badge/ops-138-orange)
![interface](https://img.shields.io/badge/interface-HTTP%20%2B%20MCP%20%2B%20TUI-purple)

> [!WARNING]
> **Authorized security testing only.** Use on models you own or run locally, in-scope bug bounty targets, written pentest engagements, CTFs, and labs you control. Do not use this to defeat third-party production safety controls without authorization. See [`SECURITY.md`](SECURITY.md).

**Maturity:** implemented · independently validated · maintained. See [STATUS.md](STATUS.md).  
**Reproduce (no model):** `bash scripts/repro.sh` or `powershell -File scripts/repro.ps1` (expects `REPRO_OK`).


---



## What this tool is

Most jailbreak tooling ships fixed payload lists. Garbleworks is a **search-and-measurement engine** over a composable attack DSL.

You give it:

1. An **objective** (what you want the model to do or leak in a controlled test).
2. A **target** (local Ollama, OpenAI-compatible endpoint, Anthropic-style adapter, or a local callable).
3. Optional **detectors** and **budgets**.

It then:

1. **Composes** candidate attacks as *recipes* (ordered chains of parameterized ops).
2. **Fires** them under SSRF + engagement scope gates.
3. **Grades** responses with multi-signal detectors and an optional AttackEval LLM judge.
4. **Searches** the composition space (genetic EVOLVE, MAP-Elites, Thompson bandit, multi-turn tree search).
5. **Reports** attack-success rates with Wilson / complete-case confidence, not a single lucky hit.
6. **Crosswalks** findings to OWASP LLM Top 10, MITRE ATLAS, NIST, and CWE via the field guide, and can export recipes to promptfoo / garak / PyRIT shapes.

The core unit is a **recipe**: an ordered composition of string transforms.

```
synonym:limit=3   homoglyph:coverage=0.5   zero_width:every=2   tag_wrap
```

That chain rewords lexically, swaps confusable glyphs, injects invisible characters, then wraps structure. Four primitives, one composed candidate. The harness searches over compositions instead of sampling a static list.

---

## How an engagement run works

```text
objective + target
       |
       v
 compose recipe ----> apply_recipe ----> variants
       ^                                    |
       |                                    v
 search loop                          fire (scoped)
 EVOLVE / MAP-Elites /                      |
 Thompson bandit / tree search              v
       |                             target adapter
       |                                    |
       |                                    v
       |                           detectors + judge
       |                                    |
       +------------ history / bandit <-----+
                          |
                          v
              report + export + field-guide crosswalk
```

| Stage | What happens | Where in code |
|-------|----------------|---------------|
| Compose | Build an ordered op chain (UI, MCP, or optimizer) | `core.run_recipe`, `ops/*` |
| Apply | Expand one input into many variants (fan-out caps apply) | `core.py`, `app.py` |
| Fire | POST/GET the variant to a target URL or local callable | `fire.py`, `targets.py` |
| Detect | Multi-signal hit rules (contains, regex, secret_regex, refusal_bank, llm_judge, ...) | `detectors.py` |
| Search | Prefer recipes that work; retire ones that do not | `evolve.py`, `optimizer.py`, `rainbow.py`, `bandit.py`, `treesearch.py` |
| Measure | Wilson / Bernstein bounds, validate re-fire (Nx), optional McNemar A/B | `validate_refire.py`, `benchmark_harness.py` |
| Map | Technique titles -> frameworks + executable ops | field guide JSON + MCP `field_guide_*` |
| Export | Recipe -> promptfoo YAML / garak probe / PyRIT orchestrator shapes | `exporters.py` |

---

## Recipe DSL (depth)

A recipe is a list of steps. Each step is an op name plus a parameter map.

```json
[
  {"op": "synonym", "params": {"limit": 3}},
  {"op": "homoglyph", "params": {"coverage": 0.5}},
  {"op": "zero_width", "params": {"every": 2}},
  {"op": "tag_wrap", "params": {}}
]
```

- Ops are **deterministic and pure** on strings unless marked otherwise (sampler / llm families).
- Every op has a tactic **family** used by diversity-aware selectors (Thompson deck will not stack five encoding-only arms by accident).
- Register a new op by adding a module under `backend/ops/` and importing it from `backend/ops/__init__.py`.
- Saved recipes live in `backend/recipes/`. Decks (input sets) live in `backend/decks/`.

### Op families (138 ops)

| Family | Count | Role |
|--------|------:|------|
| encoding | 27 | base64/32/58/85, hex, morse, braille, classical ciphers, jwt-style split |
| character | 23 | confusables, invisible chars (ZWSP/ZWNJ/BiDi/VS), leet, fullwidth, zalgo |
| template | 18 | chat-template roles, persona/DAN, delimiter collision, JSON inject, few-shot |
| jailbreak | 18 | deep-inception, cipher-persona, code-chameleon, bad-likert, policy-puppetry |
| structure | 14 | tag/markdown/json/yaml/latex wraps, function-call frames, split-join |
| prose | 10 | synonym (WordNet), backtranslate, translate, paraphrase, typo-inject |
| sampler | 9 | sample_n, distinct_n, diverse_k, mmr_select, seed_sweep |
| stego | 6 | emoji-binary, variation-selector channel, whitespace stego |
| language | 5 | multilingual pivot, roundtrip, transliterate, pseudo-locale |
| carrier | 5 | indirect injection carriers (email, editor-note, memory-seed, ...) |
| llm | 3 | llm-reframe, llm-generate, complexify (local model; pass-through if offline) |

Full technique coverage and StegOFF text-method parity: [`COVERAGE.md`](COVERAGE.md).

---

## Fire path and scope

All server-side outbound HTTP shares **one** policy module: `backend/fire.py`.

1. **URL policy** (`validate_target_url`)
   - Scheme must be `http` or `https`.
   - Link-local / cloud metadata (`169.254.0.0/16`), multicast, reserved, and unspecified addresses are blocked.
   - Loopback and RFC-1918 stay allowed by default so local and LAN model servers work.
   - Set `GARBLEWORKS_BLOCK_PRIVATE=1` to also block loopback and private ranges.
2. **No redirects.** A 302 cannot pivot into a blocked internal host after validation.
3. **Engagement receipt (MCP).** Fire tools also require the host to match `authorized_scope`. Default scope is `local-selftest` (`127.0.0.1`, `localhost`). Off-scope hosts get `SCOPE DENIED`.
4. **Caps.** Request bodies capped (4 MB). Fan-out bounded (`max_variants <= 2000`, deck inputs <= 1000).

The HTTP API has **no authentication**. Bind to `127.0.0.1` only. CORS allows only localhost origins. Details: [`SECURITY.md`](SECURITY.md).

### Targets

Adapters in `targets.py` (and local callables) include:

| Adapter | Use |
|---------|-----|
| `raw` | Arbitrary HTTP with `{payload}` body template and JSON `response_path` |
| Anthropic / Gemini-style helpers | Provider message shapes when you point at a permitted endpoint |
| Local callable | In-process Python target for dry runs without network |

Example local Ollama target (also in `backend/TARGET-abliterated-qwen.json`, loopback only):

```json
{
  "adapter": "raw",
  "url": "http://127.0.0.1:11434/v1/chat/completions",
  "method": "POST",
  "headers": {"Content-Type": "application/json"},
  "opts": {
    "body": "{\"model\":\"your-model\",\"messages\":[{\"role\":\"user\",\"content\":\"{payload}\"}],\"stream\":false}",
    "body_type": "json",
    "response_path": "choices.0.message.content"
  }
}
```

---

## Detectors and measurement

Fire requests take a detector list and a combine mode (`all` / `any` / `score`).

Built-in kinds include:

| Kind | Meaning |
|------|---------|
| `contains` / `not_contains` | Substring present or absent |
| `regex` / `not_regex` | Pattern match |
| `status_eq` / `status_in` | HTTP status |
| `secret_regex` | Common secret shapes in the response (API keys, tokens, PEM, JWT, ...) |
| `refusal_bank` | Model refusal phrases (positive = refused) |
| `llm_judge` | AttackEval grades 0 / 0.33 / 0.66 / 1.0 |
| `min_length` | Snippet length floor |
| `decomposition` | Blue-team Pack Hunt scaffold detector |

**Validate re-fire** (`validate_refire`): re-fire a winning payload N times and report Wilson ASR. A single lucky hit is not a claim.

**Search + stats stack:**

| Mechanism | Job |
|-----------|-----|
| EVOLVE | Genetic search on the probability simplex (Aitchison geometry). Spec: [`EVOLVE_MATH.md`](EVOLVE_MATH.md) |
| MAP-Elites (`rainbow.py`) | Quality-diversity over a behavior x obfuscation grid |
| Thompson bandit | Beta posterior per (op/recipe, target); `probation -> active -> retired` lifecycle |
| Tree search (`treesearch.py`) | Multi-turn beam search for erosion paths the single-turn DSL misses |
| Register `L(x)` (`register.py`) | Lexical loadedness model; estimates which features track refusal |

Honest positioning vs h4rm3l / WildTeaming and known gaps: [`HARNESS-POSITIONING.md`](HARNESS-POSITIONING.md), [`docs/GAPS.md`](docs/GAPS.md).

---

## Interfaces

### 1. HTTP API + web UI

```powershell
powershell -ExecutionPolicy Bypass -File run.ps1
# http://127.0.0.1:9877
```

Serves the single-page UI and REST endpoints for ops, recipes, fire, history, decks, export. Full endpoint map: [`docs/USAGE-AND-API.md`](docs/USAGE-AND-API.md).

### 2. Operator TUI (OpenTUI / Bun)

```powershell
cd tui
bun install
bun start
```

Tabs: Attack, Validate, Sessions, Bench, Help. Bridges to the Python backend only (no second fire path). Keys: `1`-`5` tabs, `Ctrl+R` run, `Ctrl+C` quit. See [`tui/README.md`](tui/README.md).

### 3. MCP server (agent operator)

```powershell
pip install "mcp>=1.2,<2"
python backend/mcp_server.py
```

Copy [`.mcp.json.example`](.mcp.json.example) into your MCP client and set `cwd` to the repo root.

**Executable tools (representative):**

| Tool | Purpose |
|------|---------|
| `generate_framings` | Objective -> one framed payload per named technique |
| `apply_recipe` | Run an ordered op chain |
| `list_techniques` | Op catalog (name, category, description, params) |
| `chat_template_inject` | Wrap payload in chat-template special tokens |
| `prefill_attack` | Multi-turn assistant prefill / response priming |
| `pack_hunt` / `pack_hunt_decompose` / `pack_hunt_detect` | Decomposition attack + blue-team detect |
| `optimize` | Genetic evolve against a scoped live target |
| `validate_refire` | Nx re-fire + Wilson ASR |
| `auto_attack` | Multi-strategy ladder (baseline -> pack_hunt -> optimize -> prefill) |
| `start_run` / arena helpers | Closed-loop operator sessions |

**Field-guide tools:**

| Tool | Purpose |
|------|---------|
| `field_guide_search` | Full-text search over techniques |
| `field_guide_get` | Full technique writeup |
| `field_guide_crosswalk` | Framework IDs + tool hooks + ops |
| `field_guide_ops` | Catalog technique -> executable ops |
| `op_technique` | Reverse: op -> technique |
| `field_guide_by_framework` / `field_guide_by_tool` | Index by OWASP/ATLAS/CWE or garak/promptfoo/PyRIT |

Catalog data is vendored at `backend/data/field-guide.json` (from [llm-injection-field-guide](https://github.com/SamsonCyber/llm-injection-field-guide)). Overview: [`docs/FIELD-GUIDE.md`](docs/FIELD-GUIDE.md).

---

## End-to-end: first safe run

1. **Install backend** (Python 3.11+):

```powershell
git clone https://github.com/SamsonCyber/garbleworks.git
cd garbleworks
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. **Start an echo target** (no real model required):

```powershell
python echo_target.py 9001
```

3. **Launch the API** (loopback only):

```powershell
cd ..
powershell -ExecutionPolicy Bypass -File run.ps1
```

4. **Fire a trivial recipe** at `http://127.0.0.1:9001/` from the UI, or via MCP `apply_recipe` + a scoped fire tool.

5. **Security regression suite:**

```powershell
cd backend
python -m pytest -q test_security.py
```

6. **Offline math audit** (no external APIs):

```powershell
python benchmark_harness.py --fail-on-regression
```

Optional prose/NLP extras:

```powershell
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
# MarianMT (~2GB) for backtranslate/translate:
# pip install transformers torch sentencepiece
```

Env knobs: copy [`.env.example`](.env.example) to `.env`. Common keys: `GARBLEWORKS_SCOPE`, `GARBLEWORKS_BLOCK_PRIVATE`, `GARBLEWORKS_FIELDGUIDE`, `GARBLEWORKS_LLM_URL`.

---

## Repository map

```text
garbleworks/
|-- README.md                 # this file
|-- SECURITY.md               # authorized use + host hardening
|-- NOTICE.md                 # attributions
|-- LICENSE                   # Apache-2.0
|-- run.ps1                   # Windows loopback launcher
|-- backend/
|   |-- app.py                # FastAPI UI + HTTP API
|   |-- fire.py               # SSRF + scope single source of truth
|   |-- core.py               # recipe engine + registry
|   |-- ops/                  # transform families
|   |-- spine/                # campaign / scoring spine
|   |-- mcp_server.py         # MCP operator surface
|   |-- detectors.py          # hit detection + secret_regex bank
|   |-- evolve.py / optimizer.py / rainbow.py / bandit.py
|   |-- validate_refire.py
|   |-- recipes/  decks/  personas/  rubrics/
|   |-- data/field-guide.json
|   `-- test_security.py      # SSRF / scope regressions
|-- tui/                      # OpenTUI operator console
|-- frontend/                 # static web UI assets (served by app)
`-- docs/                     # deep specs and API reference
```

---

## Why it is different (honest table)

Garbleworks does not win on transform count alone. The edge is **search discipline**, **measurement honesty**, and **standards mapping**.

| Capability | garak / PyRIT | wallbreaker | h4rm3l | Garbleworks |
|---|:---:|:---:|:---:|:---:|
| Composable attack DSL | - | partial | yes | yes |
| Genetic + quality-diversity search | - | - | bandit synth | EVOLVE + MAP-Elites |
| Wilson / complete-case ASR + promotion gates | - | partial | - | yes (see gaps) |
| Validate re-fire (Nx) | - | yes | - | yes |
| Graded LLM judge (4-level) | partial | yes | - | yes |
| Thompson bandit + recipe lifecycle | - | - | - | yes |
| Register / `L(x)` refusal analytics | - | - | - | yes |
| Multi-turn beam tree search | - | Crescendo | - | Tempest-style |
| OWASP / ATLAS / NIST / CWE crosswalk + export | - | partial | - | yes |
| Enforced SSRF + MCP scope receipt | - | policy only | - | enforced |
| Attack and defense-reduction evaluation | - | - | - | yes |

The composable-recipe idea is not novel ([h4rm3l](https://arxiv.org/abs/2408.04811), [WildTeaming](https://arxiv.org/abs/2406.18510)). This project closes the loop: search, validate re-fire, register analytics, and reportable bounds. BH-FDR is specified in EVOLVE_MATH but is not a default production gate yet.

---

## Documentation

| Doc | Contents |
|-----|----------|
| [`docs/USAGE-AND-API.md`](docs/USAGE-AND-API.md) | Full HTTP/UI reference: endpoints, adapters, detectors, recipes, troubleshooting |
| [`COVERAGE.md`](COVERAGE.md) | Technique coverage, StegOFF parity, field-guide crosswalk |
| [`docs/FIELD-GUIDE.md`](docs/FIELD-GUIDE.md) | Injection field guide overview and technique->op bridge |
| [`EVOLVE_MATH.md`](EVOLVE_MATH.md) | Optimizer and statistics, formal |
| [`HARNESS-POSITIONING.md`](HARNESS-POSITIONING.md) | Positioning vs composable-jailbreak literature |
| [`docs/GAPS.md`](docs/GAPS.md) | Known gaps and honesty notes |
| [`docs/BENCH-VS-WALLBREAKER.md`](docs/BENCH-VS-WALLBREAKER.md) | Head-to-head A/B methodology |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`SECURITY.md`](SECURITY.md) | Contribute · responsible use and disclosure |

---

## Roadmap (not built yet)

- [ ] Standard multi-model battery (HarmBench / JailbreakBench / StrongREJECT / AdvBench) with published Wilson CIs
- [ ] Multimodal / vision channel inside the recipe DSL
- [ ] `pip install garbleworks` + `garble` CLI
- [ ] Purple-team mode: ASR with each defense enabled, report reduction
- [ ] Native-format mimicry and generative persona author ops

---

## References

- h4rm3l: Doumbouya et al. 2024, [arXiv:2408.04811](https://arxiv.org/abs/2408.04811)
- WildTeaming: Jiang et al. 2024, [arXiv:2406.18510](https://arxiv.org/abs/2406.18510)
- Rainbow Teaming: Samvelyan et al. 2024, [arXiv:2402.16822](https://arxiv.org/abs/2402.16822)
- Tempest: Zhou & Arel 2025, [arXiv:2503.10619](https://arxiv.org/abs/2503.10619)
- HarmBench, JailbreakBench, StrongREJECT

---

## License

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md).

## Acknowledgements

Built by [SamsonCyber](https://github.com/SamsonCyber). Field-guide data from [llm-injection-field-guide](https://github.com/SamsonCyber/llm-injection-field-guide). Transform and safety literature catalogued in [`COVERAGE.md`](COVERAGE.md).
