# Garbleworks

**Flagship authorized LLM red-team harness.**  
Compose attacks as recipes, search the composition space, fire under scope gates, measure with re-fire and confidence bounds. HTTP API, MCP, and TUI.

[![python](https://img.shields.io/badge/python-3.11%2B-blue)](#end-to-end-first-safe-run)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![ops](https://img.shields.io/badge/ops-138-orange)](#recipe-dsl)
[![interface](https://img.shields.io/badge/interface-HTTP%20%2B%20MCP%20%2B%20TUI-purple)](#interfaces)
[![ci](https://img.shields.io/github/actions/workflow/status/SamsonCyber/garbleworks/ci.yml?branch=main)](https://github.com/SamsonCyber/garbleworks/actions)

> **Authorized security testing only.** Use on models you own or run locally, in-scope bounty targets, written pentests, CTFs, and labs you control. Do not use this to defeat third-party production safety without authorization. See [SECURITY.md](SECURITY.md).

| Maturity | State |
|----------|--------|
| Implemented | HTTP API, recipe DSL, fire path, MCP, TUI, exporters |
| Independently validated | `python scripts/repro.py` (security tests + math audit, no live model) |
| Maintained | Public under [SamsonCyber/garbleworks](https://github.com/SamsonCyber/garbleworks), Apache-2.0 |

```bash
git clone https://github.com/SamsonCyber/garbleworks.git
cd garbleworks
python scripts/repro.py
# expects: REPRO_OK garbleworks security + math audit
```

Also: `bash scripts/repro.sh` or `powershell -File scripts/repro.ps1`. Details: [STATUS.md](STATUS.md).

---

## Why this exists

Most jailbreak tooling ships fixed payload lists. You sample a set, get a hit rate, and ship a blog claim.

Garbleworks is a **search-and-measurement engine** over a composable attack DSL:

1. You set an **objective** and a **target** (local Ollama, OpenAI-compatible endpoint, or in-process callable).
2. Attacks are **recipes**: ordered chains of parameterized ops (encoding, confusables, templates, jailbreak frames, stego carriers, and more).
3. The harness **searches** the composition space (genetic EVOLVE, MAP-Elites, Thompson bandit, multi-turn tree search).
4. Every fire path shares one **scope gate** (`fire.py`): SSRF policy + MCP engagement receipt.
5. Wins are **re-fired** and reported with Wilson / complete-case style bounds, not a single lucky sample.
6. Findings **map** to OWASP LLM Top 10, MITRE ATLAS, NIST, and CWE via the vendored field guide, and can **export** to promptfoo / garak / PyRIT shapes.

Core unit: a recipe.

```text
synonym:limit=3 homoglyph:coverage=0.5 zero_width:every=2 tag_wrap
```

Four primitives, one composed candidate. The harness searches compositions instead of sampling a static list.

---

## How a run works

```text
objective + target
        |
        v
   compose recipe ----> apply_recipe ----> variants
        ^                                      |
        |                                      v
   search loop                          fire (scoped)
   EVOLVE / MAP-Elites /                       |
   Thompson bandit / tree search               v
        |                               target adapter
        |                                      |
        |                                      v
        +--------- history / bandit <--- detectors + judge
                                               |
                                               v
                              report + export + field-guide crosswalk
```

| Stage | What happens | Code |
|-------|----------------|------|
| Compose | Ordered op chain (UI, MCP, or optimizer) | `core.run_recipe`, `ops/*` |
| Apply | Expand one input into variants (fan-out caps) | `core.py`, `app.py` |
| Fire | HTTP or local callable under shared policy | `fire.py`, `targets.py` |
| Detect | Multi-signal hit rules + optional LLM judge | `detectors.py` |
| Search | Prefer recipes that work; retire ones that do not | `evolve.py`, `optimizer.py`, `rainbow.py`, `bandit.py`, `treesearch.py` |
| Measure | Wilson bounds, validate re-fire (N times), optional McNemar A/B | `validate_refire.py`, `benchmark_harness.py` |
| Map | Technique titles to frameworks + executable ops | field guide JSON + MCP `field_guide_*` |
| Export | Recipe to promptfoo / garak / PyRIT shapes | `exporters.py` |

---

## What sets it apart (honest)

The composable-recipe idea is not novel ([h4rm3l](https://arxiv.org/abs/2408.04811), [WildTeaming](https://arxiv.org/abs/2406.18510)). The closed loop is the product: search, scoped fire, re-fire, reportable bounds, standards map.

| Capability | garak / PyRIT | wallbreaker | h4rm3l | Garbleworks |
|---|:---:|:---:|:---:|:---:|
| Composable attack DSL | - | partial | yes | yes |
| Genetic + quality-diversity search | - | - | bandit synth | EVOLVE + MAP-Elites |
| Wilson / complete-case ASR + promotion gates | - | partial | - | yes (see gaps) |
| Validate re-fire (N times) | - | yes | - | yes |
| Graded LLM judge (4-level) | partial | yes | - | yes |
| Thompson bandit + recipe lifecycle | - | - | - | yes |
| Register / `L(x)` refusal analytics | - | - | - | yes |
| Multi-turn beam tree search | - | Crescendo | - | Tempest-style |
| OWASP / ATLAS / NIST / CWE crosswalk + export | - | partial | - | yes |
| Enforced SSRF + MCP scope receipt | - | policy only | - | enforced |

Positioning detail: [HARNESS-POSITIONING.md](HARNESS-POSITIONING.md). Known gaps: [docs/GAPS.md](docs/GAPS.md). BH-FDR is specified in EVOLVE_MATH but is not a default production gate yet. HarmBench-style multi-model leaderboard battery is roadmap, not shipped.

---

## Recipe DSL

A recipe is an ordered list of steps. Each step is an op name plus a parameter map.

```json
[
  {"op": "synonym", "params": {"limit": 3}},
  {"op": "homoglyph", "params": {"coverage": 0.5}},
  {"op": "zero_width", "params": {"every": 2}},
  {"op": "tag_wrap", "params": {}}
]
```

- Ops are deterministic and pure on strings unless marked otherwise (sampler / llm families).
- Every op has a tactic family used by diversity-aware selectors.
- Register a new op under `backend/ops/` and import it from `backend/ops/__init__.py`.
- Saved recipes: `backend/recipes/`. Decks: `backend/decks/`.

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

Full technique coverage: [COVERAGE.md](COVERAGE.md).

---

## Fire path and scope

All server-side outbound HTTP shares one policy module: `backend/fire.py`.

1. **URL policy** (`validate_target_url`)
   - Scheme must be `http` or `https`.
   - Link-local / cloud metadata (`169.254.0.0/16`), multicast, reserved, and unspecified addresses are blocked.
   - Loopback and RFC-1918 stay allowed by default so local and LAN model servers work.
   - Set `GARBLEWORKS_BLOCK_PRIVATE=1` to also block loopback and private ranges.
2. **No redirects.** A 302 cannot pivot into a blocked internal host after validation.
3. **Engagement receipt (MCP).** Fire tools require the host to match `authorized_scope`. Default scope is `local-selftest` (`127.0.0.1`, `localhost`). Off-scope hosts get `SCOPE DENIED`.
4. **Caps.** Request bodies capped (4 MB). Fan-out bounded (`max_variants <= 2000`, deck inputs <= 1000).

The HTTP API has **no authentication**. Bind to `127.0.0.1` only. CORS allows only localhost origins. Details: [SECURITY.md](SECURITY.md).

### Targets

| Adapter | Use |
|---------|-----|
| `raw` | Arbitrary HTTP with `{payload}` body template and JSON `response_path` |
| Provider helpers | Anthropic / Gemini-style message shapes on a permitted endpoint |
| Local callable | In-process Python target for dry runs without network |

Example local Ollama target (loopback only):

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

| Kind | Meaning |
|------|---------|
| `contains` / `not_contains` | Substring present or absent |
| `regex` / `not_regex` | Pattern match |
| `status_eq` / `status_in` | HTTP status |
| `secret_regex` | Common secret shapes in the response |
| `refusal_bank` | Model refusal phrases (positive = refused) |
| `llm_judge` | AttackEval grades 0 / 0.33 / 0.66 / 1.0 |
| `min_length` | Snippet length floor |
| `decomposition` | Blue-team Pack Hunt scaffold detector |

**Validate re-fire** (`validate_refire`): re-fire a winning payload N times and report Wilson ASR. A single lucky hit is not a claim.

| Mechanism | Job |
|-----------|-----|
| EVOLVE | Genetic search on the probability simplex (Aitchison geometry). Spec: [EVOLVE_MATH.md](EVOLVE_MATH.md) |
| MAP-Elites (`rainbow.py`) | Quality-diversity over a behavior x obfuscation grid |
| Thompson bandit | Beta posterior per (op/recipe, target); probation / active / retired lifecycle |
| Tree search (`treesearch.py`) | Multi-turn beam search for erosion paths the single-turn DSL misses |
| Register `L(x)` (`register.py`) | Lexical loadedness model; features that track refusal |

---

## Interfaces

### 1. HTTP API + web UI

```powershell
powershell -ExecutionPolicy Bypass -File run.ps1
# http://127.0.0.1:9877
```

Serves the single-page UI and REST endpoints for ops, recipes, fire, history, decks, export. Full map: [docs/USAGE-AND-API.md](docs/USAGE-AND-API.md).

### 2. Operator TUI (OpenTUI / Bun)

```powershell
cd tui
bun install
bun start
```

Tabs: Attack, Validate, Sessions, Bench, Help. Bridges to the Python backend only (no second fire path). Keys: `1`-`5` tabs, `Ctrl+R` run, `Ctrl+C` quit. See [tui/README.md](tui/README.md).

### 3. MCP server (agent operator)

```powershell
pip install "mcp>=1.2,<2"
python backend/mcp_server.py
```

Copy [.mcp.json.example](.mcp.json.example) into your MCP client and set `cwd` to the repo root.

| Tool | Purpose |
|------|---------|
| `generate_framings` | Objective to one framed payload per named technique |
| `apply_recipe` | Run an ordered op chain |
| `list_techniques` | Op catalog |
| `optimize` | Genetic evolve against a scoped live target |
| `validate_refire` | N-time re-fire + Wilson ASR |
| `auto_attack` | Multi-strategy ladder |
| `field_guide_search` / `field_guide_get` / `field_guide_crosswalk` | Technique library and framework map |
| `pack_hunt` / decompose / detect | Decomposition attack + blue-team detect |

Catalog data is vendored at `backend/data/field-guide.json` (from [llm-injection-field-guide](https://github.com/SamsonCyber/llm-injection-field-guide)). Overview: [docs/FIELD-GUIDE.md](docs/FIELD-GUIDE.md).

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

Env knobs: copy [.env.example](.env.example) to `.env`. Common keys: `GARBLEWORKS_SCOPE`, `GARBLEWORKS_BLOCK_PRIVATE`, `GARBLEWORKS_FIELDGUIDE`, `GARBLEWORKS_LLM_URL`.

---

## Repository map

```text
garbleworks/
|-- README.md              # this file
|-- SECURITY.md            # authorized use + host hardening
|-- STATUS.md              # maturity + repro contract
|-- LICENSE                # Apache-2.0
|-- run.ps1                # Windows loopback launcher
|-- scripts/repro.py       # independent offline validation
|-- backend/
|   |-- app.py             # FastAPI UI + HTTP API
|   |-- fire.py            # SSRF + scope single source of truth
|   |-- core.py            # recipe engine + registry
|   |-- ops/               # transform families
|   |-- mcp_server.py      # MCP operator surface
|   |-- detectors.py       # hit detection
|   |-- evolve.py / optimizer.py / rainbow.py / bandit.py
|   |-- validate_refire.py
|   |-- data/field-guide.json
|   `-- test_security.py
|-- tui/                   # OpenTUI operator console
|-- frontend/              # static web UI assets
`-- docs/                  # deep specs and API reference
```

---

## Documentation

| Doc | Contents |
|-----|----------|
| [STATUS.md](STATUS.md) | Maturity labels and repro contract |
| [docs/USAGE-AND-API.md](docs/USAGE-AND-API.md) | HTTP/UI reference |
| [COVERAGE.md](COVERAGE.md) | Technique coverage and StegOFF parity |
| [docs/FIELD-GUIDE.md](docs/FIELD-GUIDE.md) | Injection field guide bridge |
| [EVOLVE_MATH.md](EVOLVE_MATH.md) | Optimizer and statistics |
| [HARNESS-POSITIONING.md](HARNESS-POSITIONING.md) | Positioning vs literature |
| [docs/GAPS.md](docs/GAPS.md) | Known gaps |
| [CONTRIBUTING.md](CONTRIBUTING.md) / [SECURITY.md](SECURITY.md) | Contribute / disclosure |

---

## Roadmap (not built yet)

- [ ] Standard multi-model battery (HarmBench / JailbreakBench / StrongREJECT / AdvBench) with published Wilson CIs
- [ ] Multimodal / vision channel inside the recipe DSL
- [ ] `pip install garbleworks` + CLI entry point
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

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

Built by [SamsonCyber](https://github.com/SamsonCyber). Field-guide data from [llm-injection-field-guide](https://github.com/SamsonCyber/llm-injection-field-guide).
