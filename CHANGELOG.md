# Changelog

All notable changes to Garbleworks are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project aims to
follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) once it cuts a
tagged release.

## [Unreleased]

### Changed
- **Repo cleanup:** removed dead one-off scripts (`refine.py`,
  `backend/compare_surface_vs_old.py`, `backend/persona_echo.py`), dropped
  superseded root meta (`ADDITIONS.md`, `STATUS.md`), moved research dumps
  and draft specs under `docs/archive/`, moved `LAYERING.md` and
  `HARNESS-POSITIONING.md` into `docs/`. Operator path is README +
  `docs/HOW_IT_WORKS.md` + `docs/USAGE-AND-API.md`. Tightened `.gitignore`
  for caches and operator residue. Product fire path unchanged.

### Added
- **Procedural technique scan** (`backend/scan_campaign.py`, `scan_deep.py`):
  coverage-first playbook map (`run_scan` / MCP `run_scan`), opposite of
  stop-on-win. Phases A–F + language under one fire budget; writes
  `target_attack_map` JSON with Wilson live/dead cells and checkpoint resume.
  Docs: `docs/SCAN-CAMPAIGN.md`. Tests: `test_scan_campaign.py`. README section
  on the home page.
- **2026-08 gap ship v2** (`ops/gap_ops_v2.py` + 10 FG techniques): SLIP
  lexical self-jailbreak, CoT puzzle hijack / refusal dilution, SMT moderation
  traces, JAWS workspace seeds, S2C cloaking, HILL learning-style, agent
  decompose/combine, ContextualJailbreak mutators, Odysseus protocol seed;
  Claudini FG-only (meta). Recipes `rt-slip-lexical`, `rt-cot-puzzle-hijack`,
  `rt-hill-learning`, `rt-s2c-stack`, `rt-smt-moderation`, `rt-gap-v2-fanout`.
  Report: `docs/archive/GAP-TECHNIQUES-2026-08-v2.md`.
- **2026-08 gap ship** (10 field-guide techniques + 9 ops in `ops/gap_ops.py`):
  STAC, X-Teaming, Mastermind, Red Queen, Conjunctive multi-agent, Tag-Along/
  Slingshot, agent-only perceptual, industry domain laundering, Shadow Alignment
  (FG only), Overthinking. Ops: `red_queen_frame`, `industry_reframe`,
  `stac_chain`, `tag_along_seed`, `conjunctive_split`, `mastermind_seed`,
  `x_teaming_seed`, `overthinking_frame`, `agent_only_perceptual`. Recipes
  `rt-red-queen`, `rt-industry-reframe`, `rt-stac-chain`, `rt-gap-ship-fanout`.
  Report: `docs/archive/GAP-TECHNIQUES-2026-08.md`.
- **Language bypass expansion** (`ops/lang_ops.py`): 40+ localized lead-ins
  (Zulu, Scots Gaelic, Hmong, Irish, Haitian Creole, Yoruba, Amharic, …);
  new ops `code_switch`, `low_resource_pivot`, `answer_in_lang`, `nested_lang`,
  `script_mix`, `romanization_frame`. Recipes `rt-low-resource-sweep`,
  `rt-code-switch`, `rt-lang-bypass-stack`. Seeded + creative reasoner stacks.
- **Opus 5 role-slip delimiter** (`ops/struct_ops.py` `role_slip_delimiter`):
  poem / identity / truth+`opus:` / free_verse / cipher_dash / bare / fanout
  surfaces from the 2026-07 Claude Opus 5 public reports (X: camhberg,
  AlexKrusz, timfduffy, _machi47, atlanticesque). Field-guide technique
  `Role-slip delimiter (Opus 5 / 'this is a poem')` + recipe
  `rt-opus5-role-slip.json`. Mapped in `technique_ops.json`.
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
