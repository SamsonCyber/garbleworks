# Garbleworks: Beyond LCB vs Mean - Full Architecture Spec

**Version:** 2026-07-27 
**Status:** Design spec for v0.4+ 
**Goal:** Replace the current "LCB for search, held-out mean for claim" binary with a rich, multi-dimensional, statistically honest evidence system that produces actionable attack surfaces instead of single-recipe scores.

This spec integrates and upgrades existing components (`rainbow.py`, `bandit.py`, `register.py` + calibration, `optimizer.py`, `EVOLVE_MATH.md`, `research_store.py`, `history.py`).

---

## 1. Problems with Current "LCB vs Mean"

- Collapses a high-dimensional attack surface into one number per recipe.
- LCB rarely crosses the product threshold under realistic budgets (explicitly measured in `math_lcb_gate`).
- Register signal is lexical-only and not causally attributed.
- No coverage story (we don't know what regions of behavior/obfuscation/register space are unexplored).
- No composition/interaction modeling.
- No transfer or hierarchical learning across targets.
- Reporting is threshold-based rather than decision-theoretic or Pareto.

---

## 2. Design Principles

1. **Evidence is multi-dimensional and compositional** - not a single success probability.
2. **Coverage + Quality + Attribution** - fill the space, improve elites, explain *why*.
3. **Hierarchical + transferable** - learn across targets while specializing.
4. **Always-valid + honest** - sequential inference, proper optional stopping, no post-hoc p-hacking.
5. **Decision-theoretic output** - report fronts, utilities, value-of-information, not just "it cleared 0.7".
6. **Incremental** - reuse existing `Elite`, `Archive`, Beta posteriors, `L(x)`, fire history.

---

## 3. Core Data Model

### 3.1 Descriptor (Cell Key) - Extended

```python
CellKey = tuple[Behavior, ObfuscationLevel, RegisterBin, TargetClass?]

Behavior = "jailbreak" | "template" | "structure" | "persona" | "encoding" | "stego" | "carrier" | "hybrid"
ObfuscationLevel = "none" | "light" | "medium" | "heavy" # derived from op families + η
RegisterBin = "low" | "med" | "high" # L(x) quantiles or fixed cuts
TargetClass = "rlhf-heavy" | "abliterated" | "base" | "unknown" # optional, learned or tagged
```

The archive becomes a **hierarchical grid** (behavior × obfuscation × register) with optional target-class slicing.

### 3.2 Elite (per cell)

```python
@dataclass
class Elite:
 stack: list[str] # the recipe / op chain
 s: int = 0 # successes (can be graded-weighted)
 n: int = 0
 graded_sum: float = 0.0 # sum of AttackEval grades (0/0.33/0.66/1)
 modes: dict[str, int] = field(default_factory=dict) # behavior modes hit

 # Attribution
 feature_lifts: dict[str, float] = field(default_factory=dict) # e.g. {"L": -0.31, "chat_template": 0.18}
 last_L: float = 0.0
 last_eta: float = 0.0

 # Posterior (Beta for binary, or mean + var for graded)
 alpha: float = 1.0
 beta: float = 1.0

 @property
 def lcb(self) -> float: ...
 @property
 def posterior_mean(self) -> float: ...
```

### 3.3 Archive

```python
@dataclass
class Archive:
 cells: dict[CellKey, Elite]
 dead: set[CellKey]
 global_prior: dict[str, float] # hierarchical shrinkage (global a0/a1 or alpha/beta offsets)
```

Cells accumulate evidence on the **same stack** (tighten interval) and only replace when a strictly better LCB arrives.

---

## 4. Evidence Layers (Beyond Single p)

Every fire produces a rich observation:

```python
Observation = {
 "cell": CellKey,
 "stack": list[str],
 "L": float,
 "eta": float,
 "features": dict[str, float], # lexical L + structural + syntactic + persona
 "refused": bool,
 "grade": float, # 0/0.33/0.66/1.0
 "target_host": str,
 "target_class": str | None,
 "timestamp": float,
}
```

### 4.1 Hierarchical Calibration (live + global)

- Per-cell + per-target Beta posterior.
- Global hierarchical prior (shrinkage toward population).
- On new target: start with `alpha = global_alpha + target_offset`, etc.
- `p_refuse(L, features)` becomes a small logistic or additive model over the feature vector.

This directly upgrades EVOLVE_MATH §3.8 from single-axis lexical to multi-feature attribution.

### 4.2 Attribution Engine

After sufficient observations per cell:
- Fit (or maintain online) feature coefficients.
- Report lift tables: "Reducing L by 0.4 increases pass prob by +0.28 (this target)"
- Per-morpheme + per-structure breakdown.

---

## 5. Search Mechanisms (Hybrid)

### 5.1 QD / MAP-Elites Loop (Rainbow)

- Maintain the archive.
- Sample elite from live cells.
- Mutate stack (add/swap/drop layers, respecting family diversity).
- Fire → observe → place or accumulate.
- Kill cells only when UCB < floor after `dead_min_trials`.

### 5.2 Genetic / Optimizer Layer (current EVOLVE)

- Still useful for deep single-ask optimization inside a promising cell.
- Can be seeded from archive elites.
- Feeds new high-quality stacks back into the archive.

### 5.3 Bandit / Thompson Layer (current bandit.py)

- Per-op (or per-family) Thompson arms, now conditioned on cell context when possible.
- Used for recipe suggestion and seed-basket expansion.

---

## 6. Inference & Stopping Rules (Always-Valid)

Replace or augment fixed Wilson with always-valid methods for sequential decisions:

- Use **e-processes** or mixture martingales for the "is this cell reliably above X?" question.
- Report both:
 - Classic Wilson LCB (for comparability)
 - Always-valid lower bound (for honest early stopping)
- Optional-stopping correction is already partially present via `delta_eff`; make it explicit and documented.

**Stopping rules become multi-objective:**
- Stop per cell when its always-valid UCB < dead_floor (kill)
- Stop per cell when its always-valid LCB > promote_threshold (promote + spawn children)
- Global budget or coverage target

---

## 7. Reporting & Decision Layer (The Real Output)

Instead of a single recipe + one number, produce:

### 7.1 Attack Surface Map
- Heatmap or table of cells with:
 - Best elite stack
 - Posterior mean + always-valid LCB/UCB
 - n, graded_avg
 - Key feature lifts

### 7.2 Pareto Fronts
Multiple fronts the user can choose from:
- High success / high stealth (low L + low structural change)
- High coverage (fills many behaviors)
- Low query cost (small n, high efficiency)
- High transfer (works across multiple target_classes)

### 7.3 Attribution Report
- "For this target class, the top three drivers of refusal are: L (lexical), chat-template markers, second-person imperative."
- Lift curves: pass probability vs L (with CI) at different obfuscation levels.

### 7.4 Decision Aids
- Expected utility under user-supplied value/cost/risk model.
- Value of Information: "Running 12 more targeted queries on cell X would reduce uncertainty by Y%."
- Recommended recipe per front + confidence statement.

---

## 8. Implementation Mapping

### New / Upgraded Modules

| File | Role |
|------|------|
| `register.py` + `register_calibration.py` | Keep lexical + add `FeatureVector` + multi-feature logistic |
| `rainbow.py` | Upgrade `Elite` and `Archive` to hold posteriors + feature_lifts + target_class |
| `attribution.py` (new) | Online feature lift estimation, lift tables, per-morpheme + structural |
| `hierarchical_cal.py` (new) | Global + per-target + per-cell shrinkage |
| `surface_report.py` (new) | Pareto, utility, attribution, always-valid bounds rendering |
| `optimizer.py` | Keep as "deep dive inside a cell" engine; feed results back to archive |
| `bandit.py` | Extend posteriors with cell context when available |
| `history.py` + `research_store.py` | Add `observations` table or JSONL for attribution training data |

### Key New Classes

```python
@dataclass
class Observation: ...

class HierarchicalCalibrator:
 def update(self, obs: Observation): ...
 def p_pass(self, features: dict, target: str) -> tuple[float, float]: ... # mean, ci

class AttackSurface:
 archive: Archive
 calibrator: HierarchicalCalibrator
 def get_pareto_front(self, axes: list[str]) -> list[dict]: ...
 def attribution(self, cell: CellKey) -> dict: ...
 def value_of_information(self, cell: CellKey, budget: int) -> float: ...
```

---

## 9. Migration Path (Minimal Breaking Change)

1. Keep current `run_evolve` + LCB/heldout_mean as the "focused optimization" path.
2. Add `run_surface(asks, budget, ...)` that populates the archive using QD + calibration.
3. Make `run_evolve` optionally seed from the archive and write high-quality results back.
4. New reporting CLI / MCP tools: `surface report`, `surface pareto`, `surface explain`.
5. Old single-recipe output remains for backward compat; new tools produce the rich surface.

---

## 10. Verification & Metrics

- **Coverage**: % of cells with n ≥ min_n
- **Quality**: mean LCB of non-dead cells
- **Attribution power**: correlation between predicted lifts and observed Δpass
- **Calibration sharpness**: Brier score or proper scoring rule on held-out fires
- **Decision quality**: simulated utility of chosen front vs oracle
- Harness suites: `suite_surface_coverage`, `suite_attribution_accuracy`, `suite_always_valid_stopping`

---

## 11. Open Questions / Future

- How to handle continuous features in the grid (discretize + kernel smoothing)?
- Multi-turn / beam search integration (Tempest-style) into cells?
- Vision / multimodal cells?
- Automated "why this cell is dead" natural language explanations.

---

This spec turns Garbleworks from a recipe optimizer that occasionally produces a defensible number into a **system that maps, explains, and ranks the reliable attack surface** for a given target with proper statistical hygiene and decision support.

It builds directly on the existing high-quality components (QD archive, Thompson posteriors, live calibration, stochastic fitness) instead of throwing them away.

Ready for detailed interface design or first implementation spike on any section.