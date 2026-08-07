# Procedural technique scan (`scan_campaign`)

Coverage-first campaign: walk executable playbook techniques, logical mixes,
then deep phases (nesting, roleplay, Pliny, language). Not stop-on-win
(`auto_attack`) and not posterior sampling (`bandit_self_improve`).

## Entry points

- Python: `from scan_campaign import run_scan, run_scan_as_dict`
- Deep templates: `scan_deep.py`
- MCP: `run_scan` (SSRF + receipt scope on live targets)

## Phases

| Phase | Mode | What |
|-------|------|------|
| A | `phase_a` | Catalog sweep (one op at a time) |
| B | `phase_b` | Logical complementary mixes |
| C | `phase_c` | Slightly further: double-frame, denser stacks |
| D | `phase_d` | Russian nesting (`deep_inception` L7-9), nested_lang hops, heavy obfuscation |
| E | `phase_e` | Long-turn roleplay: crescendo, manyshot, multiturn, long CoT |
| F | `phase_f` | Full Pliny kit via atomic ops + `pliny_frame` adapter cells (builtin; optional local corpus) |
| Lang | `language` | Language mutators + mixes |
| all deep | `deep` | C-F + lang only |
| all | `full` | A -> B -> C -> D -> E -> F -> lang under one budget |

## Language mutators (GLOSSOPETRAE-mapped)

Pliny's [GLOSSOPETRAE](https://github.com/elder-plinius/GLOSSOPETRAE) studies
languages optimized for **LLM acquisition** (opacity can help models, hurt
humans). We do not vendor the JS engine; the scan maps those ideas onto
in-tree ops:

| Idea | Garbleworks ops |
|------|-----------------|
| forLLM / opaque pivot | `low_resource_pivot`, `amazigh_obfuscate`, `nested_lang` |
| Code-switch channel | `code_switch`, `answer_in_lang` |
| Script mutators | `script_mix`, `transliterate`, `romanization_frame` |
| Nested hop | `nested_lang` (hops=1-2) + CoT no-decode stacks |

Map artifact includes a `language` block with ops + `glossopetrae_map`.

## Pliny corpus boundary

Builtin structural frames and optional local dumps: `backend/pliny_adapter.py`.
Set `GARBLEWORKS_PLINY_CORPUS` to a local L1B3RT4S-style tree to discover extra
frames; leave unset for builtin only. Op: `pliny_frame`. Full dumps are not
shipped in this repository (see SECURITY.md).

## Budget knobs

| Knob | Default | Meaning |
|------|---------|---------|
| `budget` | 120 (MCP) | Hard max target fires; multi-phase **reserves** shares so deep/lang are not starved |
| `mode` | `full` | See phase table above |
| `reps_per_technique` | 1 | Fires per technique/combo/deep cell |
| `combo_depth` | 2 | Max ops in a phase-B stack (2-4) |
| `max_deep` | 80 | Cap deep-phase templates |
| `max_combos` | 64 | Cap phase-B mixes |
| `techniques` | catalog | Explicit subset, else registry |
| `category` | None | Registry category filter |
| `exclude_model_backed` | true | Skip ML/LLM-backed ops |
| `rng_seed` | 0 | Deterministic combo pick |
| `dead_min_trials` | 2 | Min n before dead |
| `dead_ucb` | 0.35 | Dead if s=0 and Wilson UCB below this |
| `checkpoint_path` | None | Resume map JSON path |
| `map_path` | None | Output map path (defaults to checkpoint) |
| `secret` / `success_substrings` | - | Success adjudication |

## Artifact: `target_attack_map`

JSON schema version `1.0`, `kind: target_attack_map`. Fields:

- `objective`, `target_ref`, `mode`
- `budget`: `{limit, used, remaining}`
- `knobs`: frozen knob snapshot
- `techniques[]`: `{id, family, status, n, s, lcb, ucb, best_payload, best_payload_ref, last_outcome, phase}`
- `combos[]`: same + `stack` + `mix` (phase `b` or deep `c`/`d`/`e`/`f`/`lang`)
- `language`: ops list, glossopetrae_map, source URL
- `attempts[]`: recent fire trail (`cell`, `phase`, `outcome`, `score`, `mix`, `q`)
- `knobs.phase_caps` / `phase_fires`: reserved budget shares vs used
- `summary`: coverage counts, `deep_by_phase`, `stop_reason`
- `completed_cells`, `skipped_on_resume`

Production notes: default catalog is live `REGISTRY` (minus model-backed/sampler).
Phase A prioritizes jailbreak -> template -> language families when budget is tight.
`log_attempt` records each fire when the logs DB is available.

Status values: `live` | `dead` | `untried` | `error` | `skipped_illegal`.

Resume: re-open the same `checkpoint_path`; cells in `completed_cells` are not re-fired.

## Layering and logical mixes

Phase B does **not** pair techniques at random. It builds stacks from:

1. **Named templates** (e.g. `b64+fenced`, `past_tense+cot`, `policy+tag`)
2. **Complementary family recipes** (`frame+envelope`, `frame+encode`,
   `surface+encode`, `lang+frame`, depth-3 `frame+encode+envelope`, ...)
3. Phase-A winners/near-misses as preferred anchors inside those roles

Apply order: content -> character -> encoding -> structure. Stacks that apply
character/stego after encoding are illegal (`is_legal_stack` / [LAYERING.md](LAYERING.md)).
Combo rows in the map include a `mix` label naming the recipe used.

## Offline test path

```python
run_scan(objective, target=None, success_substrings=["OBJECTIVE_ACHIEVED"],
         techniques=["base64", "tag_wrap"], budget=8, map_path="map.json")
```

With `target=None`, a local echo server starts (hit when payload contains `secret`).
