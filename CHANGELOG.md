# Changelog

All notable changes to Garbleworks are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once it cuts a
tagged release.

## [Unreleased]

### Added
- **Visible-CoT mutation suite** (`ops/framing_ops.py`): expand `cot_hijack`
 with modes `forge` / `safety_script` / `dilution` / `no_decode` / `hybrid` /
 `fanout`; new ops `cot_dilution`, `cot_no_decode`, `cot_forge_verdict`.
 Recipes `rt-cot-visible-reasoner.json`, `rt-obfuscate-then-cot.json`
 (Amazigh → CoT hybrid). Targets reasoners that decode obfuscation then refuse.
- **CoT/Amazigh wired into fire path**: unbanned `cot_hijack` from soft signature
 ban; PRIORITY + COMPOSITE seeds; creative.SEED framing/language/jailbreak;
 language-before-jailbreak stack order; strategies.json + arena ladders;
 bandit seed cats include language; default basket max 96. Soft baskets now
 emit cot_* / amazigh / multi-op stacks so evolve actually fires them.
- **Methodical breadth mutator** (`evolve.random_recipe`): stratified methods
 - coverage_walk (under-hit ops/families), family_diverse (WildTeaming),
 category_focus, library_stack (curated multi-hop across taxonomy), free_form.
 Coverage ledger prefers cold ops so ~full offline catalog (~140 ops) is used
 over a long run. Nest-ordered stages. CoT/Amazigh remain one library stratum,
 not a monoculture. Seed basket pulls per-category caps for vast array.
- **`amazigh_obfuscate` language op** (`ops/lang_ops.py`): Amazigh (Tamazight) /
 Tifinagh low-resource PI obfuscation - modes `hybrid`, `wrap_latin`,
 `wrap_tifinagh`, `tifinagh`, `translate`, `fanout`. Tifinagh also on
 `transliterate` script=`tifinagh`. Recipe `rt-amazigh-obfuscate.json`.
 Wired into `technique_ops.json` multilingual / low-resource pivot group.
- **local_fn target** (`local_target.py` + `fire.fire_once` short-circuit + MCP
 `fire_local`): in-process Python callable fire with gate adjudication
 (`attr_true:ok`, `tuple_ok_true`, …). No HTTP, no SSRF scope. For Finbot-class
 `sanitize_input` / `validate_url` / `validate_tool_args` unit campaigns.
- **Heuristic-evasion seed arm** (`ops/heuristic_ops.py`): `heuristic_soft`,
 `heuristic_evasion`, `homoglyph_soft`, `decode_obey_soft`, `heuristic_strip`.
 Wired first in `optimizer.build_basket` and `seed_basket.PRIORITY_STRATEGIES`.
 `evolve_seeds(expanded=True)` uses the expanded basket by default.
- **Multi-layer attempt log**: outcomes `gate_bypass` / `gate_block` /
 `tool_accept` / `tool_deny` / `model_comply`; longer payload previews +
 `params.payload_full` for `local_fn`/`unit`/`finbot_agent`; `query_attempts`
 returns parsed params for re-fire; success_rates counts multi-layer wins.
- Public GitHub documentation set: front-page `README.md`, `SECURITY.md`,
 `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue/PR templates, and a CI workflow.
- `docs/` index and preserved usage/API reference (`docs/USAGE-AND-API.md`).

### Planned (roadmap)
- Standard-battery adapters (HarmBench / JailbreakBench / StrongREJECT / AdvBench)
 and a multi-model ASR report with Wilson CIs and paired McNemar vs baselines.
- Multimodal / vision attack channel (image-carrier ops + VLM adapter + vision judge).
- `pip install garbleworks` packaging and a `garble` CLI.
- Native-format mimicry and a from-scratch generative persona author.
- Purple-team mode: ASR before/after each defense.

## [0.x] - pre-release (current state)

The engine and intelligence layer are built and in active use against a local
self-test target. Highlights of what already ships:

### Added
- **Forge:** 138 composable ops across 12 families (encoding, character, template,
 jailbreak, structure, prose, sampler, stego, language, carrier, llm), each tagged
 with a tactic `family`. Full StegOFF text-method parity (14/14).
- **Recipe DSL** and `apply_recipe` runtime; 15+ recipe presets.
- **Search:** EVOLVE genetic optimizer on the probability simplex, MAP-Elites
 quality-diversity (`rainbow.py`), Thompson-bandit deck with probation/active/retired
 lifecycle, `strategy_discover`, and multi-turn beam tree search (`treesearch.py`).
- **Measurement:** graded `llm_judge` (AttackEval 4-level); Wilson / empirical-Bernstein
 bounds, successive-halving racing, winner's-curse re-estimation; Benjamini-Hochberg
 FDR is specified in EVOLVE_MATH (not a default CLI gate yet); register / `L(x)`
 refusal-feature analytics (`register.py`). Validate re-fire + HarmBench-shaped
 behavior ingest closed product gaps vs Wallbreaker-class tools (see `docs/GAPS.md`).
- **Benchmarks:** head-to-head A/B vs wallbreaker with paired McNemar
 (`bench/ab_wallbreaker.py`); offline math-audit suite (`benchmark_harness.py`).
- **Reach:** MCP server (`backend/mcp_server.py`); field-guide crosswalk to
 OWASP LLM Top 10 / MITRE ATLAS / NIST / CWE; export to promptfoo / garak / PyRIT.
- **Safety rails:** SSRF-guarded firing, engagement receipt scope (`SCOPE DENIED`),
 localhost-locked CORS, request-size and fan-out caps, defenses family + `neutralize`.

[Unreleased]: https://github.com/SamsonCyber/garbleworks/compare/main...HEAD
