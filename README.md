# Garbleworks

![Garbleworks scoped fire and recipe mutation](assets/banner.jpg)

**Flagship authorized LLM red-team harness.**  
Compose attacks as recipes, search the composition space, fire under scope gates, measure with re-fire and confidence bounds. HTTP API, MCP, and TUI.

[![python](https://img.shields.io/badge/python-3.11%2B-blue)](#end-to-end-first-safe-run)
[![license](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![ops](https://img.shields.io/badge/ops-152-orange)](#recipe-dsl)
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

**Read next:** [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) (full loop) Ãƒâ€šÂ· [docs/BENCHMARKS.md](docs/BENCHMARKS.md) (offline numbers) Ãƒâ€šÂ· [STATUS.md](STATUS.md)

---

## Why this exists

Fixed jailbreak lists go stale. One lucky hit is not a result.

Garbleworks is a **search-and-measurement engine** over a composable attack DSL:

1. Set an **objective** and a **target** (local Ollama, OpenAI-compatible endpoint, or in-process callable).
2. Build attacks as **recipes**: ordered chains of parameterized ops (encoding, confusables, templates, jailbreak frames, stego carriers, and more).
3. **Search** the composition space (genetic EVOLVE, MAP-Elites, Thompson bandit, multi-turn tree search).
4. **Fire** only through one policy module: SSRF gates + MCP engagement receipt.
5. **Score** with multi-signal detectors and optional graded LLM judge.
6. **Re-fire** winners and report Wilson-style rates, not screenshots.
7. **Map** findings to OWASP LLM Top 10 / MITRE ATLAS / NIST / CWE via the field guide; **export** to promptfoo / garak / PyRIT shapes.

Core unit:

```text
synonym:limit=3 homoglyph:coverage=0.5 zero_width:every=2 tag_wrap
```

Four primitives, one composed candidate. The harness searches compositions instead of sampling a static list.

---

## How it works end-to-end

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
| Measure | Wilson bounds, validate re-fire (N times) | `validate_refire.py`, `benchmark_harness.py` |
| Map / export | Framework crosswalk + tool shapes | field guide JSON, `exporters.py` |

Longer walkthrough (scope rules, detector table, search math honesty): **[docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)**.

### Three operator surfaces, one fire path

| Surface | Start | Role |
|---------|-------|------|
| HTTP + web UI | `powershell -File run.ps1` ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ `http://127.0.0.1:9877` | Human operator |
| MCP | `python backend/mcp_server.py` | Agent operator + scope receipt |
| TUI | `cd tui && bun start` | Keyboard console (backend only) |

There is no second, unchecked fire path.

### Scope and SSRF (non-negotiable)

All outbound HTTP shares `backend/fire.py`:

1. `http` / `https` only.
2. Cloud metadata and other reserved ranges blocked.
3. Loopback / RFC-1918 allowed by default for local labs; `GARBLEWORKS_BLOCK_PRIVATE=1` tightens.
4. No redirects after validation.
5. MCP fire requires host ÃƒÂ¢Ã‹â€ Ã‹â€  `authorized_scope` (default `127.0.0.1` / `localhost`).
6. Body and fan-out caps.

HTTP API is unauthenticated: bind **127.0.0.1 only**. See [SECURITY.md](SECURITY.md).

---

## Why this over alternatives (honest)

The composable-recipe idea is not novel ([h4rm3l](https://arxiv.org/abs/2408.04811), [WildTeaming](https://arxiv.org/abs/2406.18510)).
**The closed loop is the product:** search, scoped fire, re-fire, reportable bounds, standards map.

| Capability | Fixed payload lists | garak / PyRIT | h4rm3l | Garbleworks |
|---|:---:|:---:|:---:|:---:|
| Composable attack DSL | - | partial | yes | yes |
| Genetic + quality-diversity search | - | - | bandit synth | EVOLVE + MAP-Elites |
| Wilson / complete-case ASR + promotion gates | - | partial | - | yes (see gaps) |
| Validate re-fire (N times) | - | yes | - | yes |
| Graded LLM judge (4-level) | - | partial | - | yes |
| Thompson bandit + recipe lifecycle | - | - | - | yes |
| Multi-turn beam tree search | - | partial | - | yes |
| OWASP / ATLAS / NIST / CWE crosswalk + export | - | partial | - | yes |
| Enforced SSRF + MCP scope receipt | - | policy only | - | **enforced** |
| Offline math + plumbing audit you can re-run | - | - | - | **yes** |

Where peers often win: large community probe libraries (garak), enterprise packaging, or published multi-model leaderboards.
Where Garbleworks is built to win: **operator-owned search**, **measurement honesty** (including the mean-vs-LCB audit finding), and **hard fire policy** on every path.

Positioning detail: [HARNESS-POSITIONING.md](HARNESS-POSITIONING.md). Gaps: [docs/GAPS.md](docs/GAPS.md).

---

## Benchmarks (offline, re-runnable)

Full tables and interpretation: **[docs/BENCHMARKS.md](docs/BENCHMARKS.md)**.

**What we publish:** math golden checks, Wilson coverage Monte Carlo, open/closed-loop echo latency and hit rates, genetic optimizer audit, export structural checks, SSRF/scope rejects.
**What we do not claim yet:** multi-provider live ASR leaderboard (roadmap).

### Snapshot (2026-08-02T20:29:46Z, Python 3.11, full suite ~31 s)

| Suite | Result | Headline metrics |
|-------|--------|------------------|
| Math closed form | pass | 14 / 14 formula checks |
| Wilson coverage MC | pass | mean coverage **0.9085** (nominal 0.9); min 0.849 |
| LCB gate audit | pass | `lcb_success_reachable_under_defaults=**false**`; n_needed_perfect=80 |
| Open loop (echo) | pass | 80 fires; plaintext hit rate 1.0; **p50 ~2 ms** (loopback); **152** registered ops |
| Closed loop | pass | 10 runs; hit rate 1.0; p50 ~568 ms |
| Optimizer GA | pass | success_flag_rate 1.0; **lcb_stop_rate 0.0** (mean-based success confirmed) |
| Export | pass | promptfoo + garak + PyRIT structural OK |
| Security | pass | 6 / 6 SSRF + scope checks |

Numbers regenerate via `python scripts/publish_offline_benchmarks.py`. Full detail in [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

Re-run and refresh the published section:

```bash
python scripts/publish_offline_benchmarks.py
# or

cd backend && python benchmark_harness.py --fail-on-regression
```

Independent gate (CI-class):

```bash
python scripts/repro.py
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

Live registry after `import ops`: **152** ops across encoding, character, template, jailbreak, structure, prose, sampler, stego, language, carrier, llm.
Coverage notes: [COVERAGE.md](COVERAGE.md).

### Targets

| Adapter | Use |
|---------|-----|
| `raw` | HTTP with `{payload}` body template + JSON `response_path` |
| Provider helpers | Anthropic / Gemini-style shapes on a permitted endpoint |
| Local callable | In-process dry run |

Example Ollama (loopback only) is in [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) and `backend/TARGET-*.json` samples.

---

## Interfaces (quick start)

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

Copy [.mcp.json.example](.mcp.json.example). Tools include `apply_recipe`, `optimize`, `validate_refire`, `auto_attack`, `field_guide_*`, pack-hunt suite.

### TUI

```powershell
cd tui
bun install
bun start
```

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

5. Security + math:

```powershell
cd backend
python -m pytest -q test_security.py
python benchmark_harness.py --fail-on-regression
```

Env: copy [.env.example](.env.example). Keys: `GARBLEWORKS_SCOPE`, `GARBLEWORKS_BLOCK_PRIVATE`, `GARBLEWORKS_FIELDGUIDE`, `GARBLEWORKS_LLM_URL`.

---

## Repository map

```text
garbleworks/
|-- README.md
|-- docs/HOW_IT_WORKS.md      # full loop narrative
|-- docs/BENCHMARKS.md        # published offline metrics
|-- STATUS.md                 # maturity + REPRO_OK contract
|-- SECURITY.md
|-- scripts/repro.py
|-- scripts/publish_offline_benchmarks.py
|-- backend/
|   |-- app.py, fire.py, core.py, ops/
|   |-- mcp_server.py, detectors.py
|   |-- evolve.py, optimizer.py, rainbow.py, bandit.py
|   |-- benchmark_harness.py, bench/
|   `-- test_security.py
|-- tui/
`-- frontend/
```

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) | End-to-end operator walkthrough |
| [docs/BENCHMARKS.md](docs/BENCHMARKS.md) | Offline metrics + re-run |
| [STATUS.md](STATUS.md) | Maturity labels |
| [docs/USAGE-AND-API.md](docs/USAGE-AND-API.md) | HTTP/UI reference |
| [EVOLVE_MATH.md](EVOLVE_MATH.md) | Optimizer statistics |
| [HARNESS-POSITIONING.md](HARNESS-POSITIONING.md) | Literature positioning |
| [docs/GAPS.md](docs/GAPS.md) | Known gaps |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribute |

---

## Roadmap (not built yet)

- [ ] Multi-model battery (HarmBench / JailbreakBench / StrongREJECT / AdvBench) with published Wilson CIs
- [ ] Multimodal / vision channel in the recipe DSL
- [ ] `pip install garbleworks` + CLI entry point
- [ ] Purple-team mode: ASR with each defense enabled
- [ ] Default LCB promotion gate wired to search stop (today: audited as mean-based)

---

## References

- h4rm3l: Doumbouya et al. 2024, [arXiv:2408.04811](https://arxiv.org/abs/2408.04811)
- WildTeaming: Jiang et al. 2024, [arXiv:2406.18510](https://arxiv.org/abs/2406.18510)
- Rainbow Teaming: Samvelyan et al. 2024, [arXiv:2402.16822](https://arxiv.org/abs/2402.16822)
- Tempest: Zhou & Arel 2025, [arXiv:2503.10619](https://arxiv.org/abs/2503.10619)

---

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

Built by [SamsonCyber](https://github.com/SamsonCyber). Field-guide data from [llm-injection-field-guide](https://github.com/SamsonCyber/llm-injection-field-guide).
