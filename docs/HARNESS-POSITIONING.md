# Garbleworks vs h4rm3l: the composable-jailbreak-DSL comparison

Positioning note for write-ups. The closest published analog to the Garbleworks
op/recipe layer is **h4rm3l** (Doumbouya et al., 2024, *"h4rm3l: A Dynamic
Benchmark of Composable Jailbreak Attacks for LLM Safety Assessment"*, arXiv:2408.04811).
h4rm3l represents jailbreaks as programs that compose parameterized string-
transformation primitives, and synthesizes novel attacks with a bandit-guided
few-shot program synthesizer. That is the same core idea as a Garbleworks recipe:
an ordered composition of parameterized ops. This note states the mapping and the
differentiators, so any external write-up positions honestly instead of claiming
novelty h4rm3l already owns.

## The recipe DSL (formal)

A Garbleworks attack is a **recipe**: an ordered op-chain over an input string.

```
recipe := step ( WS step )*
step := op_name ( ":" params )?
params := kv ( "," kv )*
kv := key "=" value
value := int | float | bool | str ; coerced to the op's declared type
op_name := <a registered op in one of 20 families>
```

Denotationally, a recipe is a composition of transformations

```
R = op_k ∘ ... ∘ op_2 ∘ op_1 , R : str -> set<str>
```

where each `op_i` is a parameterized map from a string to one or more variant
strings (fan-out is capped per stage). Families: character, encoding, structure,
prose, template, sampler, language, jailbreak, stego, carrier, llm, register.
The catalog is 140 executable ops across those families; `list_techniques()` /
`apply_recipe()` are the runtime.

Example (a layered evasion program):

```
synonym:limit=3 homoglyph:coverage=0.5 zero_width:every=2 tag_wrap
```

= reword lexically, then swap half the Latin glyphs for confusables, then inject
invisible zero-width chars every 2 chars, then wrap in markup. Four primitives,
one composed attack - structurally a h4rm3l program.

## Mapping to h4rm3l

| h4rm3l concept | Garbleworks equivalent |
|---|---|
| primitive transformation | **op** (registered, parameterized, `family`-tagged) |
| composed attack program | **recipe** (ordered op-chain) |
| DSL for composing primitives | the recipe mini-language (above) + `apply_recipe` |
| program synthesizer (bandit few-shot) | the **EVOLVE genetic optimizer** + **Thompson arm bandit** |
| synthesized-attack benchmark/dataset | the per-target **hypothesis store** (`research_store`) + fire-history logs |
| primitive parameters | op params (typed, validated against the live registry) |

The one-to-one correspondence is real: if you strip Garbleworks to its op/recipe
layer, it *is* an h4rm3l-style composable-jailbreak DSL with a synthesizer on top.
Say so.

## Where Garbleworks differs (the honest delta)

Four things h4rm3l does not do, in rough order of importance:

1. **Search method.** h4rm3l synthesizes programs with a bandit-guided few-shot
 LLM. Garbleworks searches the composition space with a **genetic optimizer on
 the probability simplex** (Aitchison geometry, logistic-normal mutation,
 credit-assignment bandits - `EVOLVE_MATH`) and, now, **MAP-Elites
 quality-diversity** over a (behavior x obfuscation) grid (`rainbow.py`). The
 recipe space is searched, not just sampled.

2. **Statistical rigor.** h4rm3l reports ASR. Garbleworks treats fitness as a
 random variable: **Wilson / empirical-Bernstein confidence bounds**,
 **successive-halving racing**, **winner's-curse held-out re-estimation**, and
 optional **Benjamini-Hochberg FDR** on multi-strategy claim batches
 (`rank_strategies(fdr_q=...)`, EVOLVE_MATH sec 14; **default off**). Dual product
 flags separate mean success from LCB `claim_ready`. A cross-model weak-point
 dataset is only bounty-actionable if "technique X breaks family Y" claims
 survive re-fire + (when multi-test) FDR correction.

3. **The register / L(x) analytical layer.** A morpheme-loadedness model with a
 live `p_refuse(L) = σ(α₀ + α₁L)` calibration that names *which lexical features*
 a target's safety layer over-weights (`EVOLVE_MATH` sec 3, `register.py`). No
 h4rm3l analog; it turns "it refused" into a finding.

4. **Closed adaptive loop + persistence.** h4rm3l is benchmark-generation-first.
 Garbleworks runs a live compose -> fire -> judge -> evolve loop (`optimize`), a
 per-target hypothesis store with promote/retire/compose lifecycle, and - new - 
 a **multi-turn beam tree search** (Tempest-style, `treesearch.py`) for the
 erosion attacks the single-turn DSL cannot reach.

## The honest caveat to include

The op/recipe DSL is not novel; h4rm3l (and, upstream, WildTeaming's
"composition beats singletons" finding) established composable jailbreaks. The
Garbleworks contribution is the **search + measurement discipline on top**:
genetic/QD illumination of the composition space, Wilson/BH-FDR-grade statistics,
the register analytics, and the multi-turn extension. Position against h4rm3l as
"composable-jailbreak DSL with a statistically-honest search harness," not as a
new attack primitive.

## References

- h4rm3l - Doumbouya et al. 2024, arXiv:2408.04811 (composable jailbreak DSL + synthesizer).
- WildTeaming - Jiang et al. 2024, arXiv:2406.18510 (composition > singletons, 4.6x).
- Rainbow Teaming - Samvelyan et al. 2024, arXiv:2402.16822 (MAP-Elites for adversarial prompts).
- Tempest - Zhou & Arel 2025, arXiv:2503.10619 (multi-turn tree-search jailbreak).
