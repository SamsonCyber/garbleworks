"""Core engine: Operations, the registry, and the recipe runner.

The whole tool reduces to two concepts:

  Operation  - a named function: mutate(text, **params) -> list[str].
               It returns a LIST because one input can fan out to many
               variants (e.g. 3 synonym swaps), which is the entire point
               of a mutator.

  Recipe     - an ordered list of operations. We pipe the text through
               each stage; the set of variants multiplies as it goes.
               That growth is powerful and dangerous, so the runner caps
               it (max_variants) at every stage.

This file has no security-specific logic. It is content-agnostic plumbing,
the same shape as CyberChef recipes or PyRIT converter chains.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Param:
    """One tunable knob on an operation. The UI renders a control from this."""
    name: str
    type: str                      # "int" | "float" | "bool" | "str" | "select"
    default: Any
    help: str = ""
    min: float | None = None
    max: float | None = None
    options: list[str] | None = None
    # Optional human-readable label. When two ops share an option list
    # (e.g. 'space/none/comma' for both hex.sep and octal.sep), the label
    # disambiguates which dropdown the user is looking at. Falls back to
    # the op's own label + param name in the UI if unset.
    label: str | None = None

    def as_dict(self) -> dict:
        return {
            "name": self.name, "type": self.type, "default": self.default,
            "help": self.help, "min": self.min, "max": self.max,
            "options": self.options, "label": self.label,
        }


def _clamp_param(value: Any, p: "Param") -> Any:
    """Coerce a numeric param to its declared type and clamp to [min, max].
    Falls back to the param default if the value isn't numeric.

    Param.min/max are NOT just UI hints: without enforcing them here, a client
    can pass e.g. repeat n=10**9 or sample_n k=10**9 and exhaust CPU/memory
    inside the op, before run_recipe's per-stage variant cap (which only runs
    AFTER the op produces its output) can do anything about it.
    """
    try:
        v = int(value) if p.type == "int" else float(value)
    except (TypeError, ValueError):
        return p.default
    if p.min is not None:
        v = max(v, int(p.min) if p.type == "int" else float(p.min))
    if p.max is not None:
        v = min(v, int(p.max) if p.type == "int" else float(p.max))
    return v


# Tactic family per category. WildTeaming (arXiv:2406.18510) found that
# composing ops from DIFFERENT families dramatically outperforms stacking
# same-family ops, so the compose/thompson selectors enforce family diversity.
# An op can override this with its own `family`; otherwise we derive it from the
# category. Kept coarse on purpose — the constraint only needs "are these two ops
# the same kind of attack?" not a fine taxonomy.
CATEGORY_FAMILY: dict[str, str] = {
    "character": "obfuscation",
    "encoding": "encoding",
    "structure": "structure",
    "prose": "paraphrase",
    "template": "framing",
    "jailbreak": "jailbreak",
    "language": "translation",
    "llm": "generation",
    "stego": "steganography",
    "carrier": "indirect-injection",
    "sampler": "control",
}


@dataclass
class Operation:
    name: str
    category: str
    description: str
    params: list[Param]
    fn: Callable[..., list[str]]   # fn(text, **params) -> list[str]
    # If True, this op is deterministic given (text, params). The runner
    # uses this to skip re-running the same stage under different seeds
    # and to cache results. Ops that read external state (random with no
    # seed, ML models) should leave this False so they re-run on every
    # recipe invocation. Most pure-string ops are True.
    deterministic: bool = True
    # Tactic family for diversity-constrained composition. Empty = derive from
    # category via CATEGORY_FAMILY. Ops that want a family distinct from their
    # category's default (e.g. an encoding-category op that is really an
    # authority framing) set this explicitly.
    family: str = ""

    @property
    def tactic_family(self) -> str:
        """Resolved family: explicit override, else category-derived, else the
        category name itself as a last resort."""
        return self.family or CATEGORY_FAMILY.get(self.category, self.category)

    def mutate(self, text: str, **kwargs) -> list[str]:
        # Start from declared defaults, then overlay only known params.
        # Unknown keys from the client are ignored, so a stale UI can't crash us.
        resolved = {p.name: p.default for p in self.params}
        for k, v in kwargs.items():
            if k in resolved:
                resolved[k] = v
        # Enforce declared numeric bounds server-side (DoS guard, see _clamp_param).
        for p in self.params:
            if p.type in ("int", "float") and (p.min is not None or p.max is not None):
                resolved[p.name] = _clamp_param(resolved[p.name], p)
        out = self.fn(text, **resolved)
        # Normalize: always a list of non-empty strings.
        if isinstance(out, str):
            out = [out]
        cleaned = [s for s in (out or []) if isinstance(s, str) and s != ""]
        # An op that finds nothing to do passes the text through unchanged,
        # so one dead stage never kills the whole chain.
        return cleaned or [text]

    def as_dict(self) -> dict:
        return {
            "name": self.name, "category": self.category,
            "family": self.tactic_family,
            "description": self.description,
            "params": [p.as_dict() for p in self.params],
        }


# Global registry. Ops register themselves on import (see ops/*).
# Soft-disable keeps the op defined but out of live catalog / run_recipe.
REGISTRY: dict[str, Operation] = {}
_DISABLED: set[str] = set()
# module name (e.g. ops.char_ops) -> op names registered from that module
MODULE_OPS: dict[str, set[str]] = {}


def register(op: Operation, *, module: str | None = None) -> Operation:
    """Register an op. Optional module labels the pack (default: caller module)."""
    import inspect

    if op.name in REGISTRY:
        raise ValueError(f"duplicate operation name: {op.name}")
    REGISTRY[op.name] = op
    if module is None:
        # Caller of register() is the ops pack (not this frame).
        frame = inspect.currentframe()
        try:
            if frame is not None and frame.f_back is not None:
                module = str(frame.f_back.f_globals.get("__name__", "unknown"))
            else:
                module = "unknown"
        finally:
            del frame
    MODULE_OPS.setdefault(module, set()).add(op.name)
    _DISABLED.discard(op.name)
    return op


def unregister(name: str) -> bool:
    """Hard-remove an op from the registry. Returns False if unknown."""
    if name not in REGISTRY:
        return False
    del REGISTRY[name]
    _DISABLED.discard(name)
    for mod, names in list(MODULE_OPS.items()):
        names.discard(name)
        if not names:
            del MODULE_OPS[mod]
    return True


def disable(name: str) -> bool:
    """Soft-disable: op stays registered but is absent from live catalog and recipes."""
    if name not in REGISTRY:
        return False
    _DISABLED.add(name)
    return True


def enable(name: str) -> bool:
    """Re-enable a soft-disabled op."""
    if name not in REGISTRY:
        return False
    _DISABLED.discard(name)
    return True


def is_enabled(name: str) -> bool:
    return name in REGISTRY and name not in _DISABLED


def get_op(name: str) -> Operation | None:
    """Return an op only if registered and enabled."""
    if name in _DISABLED:
        return None
    return REGISTRY.get(name)


def enabled_ops() -> dict[str, Operation]:
    """Map of name → Operation for soft-enabled ops only (compose/search pools)."""
    return {n: op for n, op in REGISTRY.items() if n not in _DISABLED}


def enabled_names(*, category: str | None = None) -> list[str]:
    """Sorted enabled op names, optional category filter."""
    names: list[str] = []
    for n, op in enabled_ops().items():
        if category is not None and op.category != category:
            continue
        names.append(n)
    return sorted(names)


def iter_enabled_ops():
    """Yield (name, op) for every enabled operation, sorted by name."""
    ops = enabled_ops()
    for n in sorted(ops):
        yield n, ops[n]


def list_ops(*, enabled_only: bool = True, category: str | None = None) -> list[dict]:
    """Live catalog for UI/MCP/CLI. Enabled-only by default."""
    out: list[dict] = []
    for name, op in sorted(REGISTRY.items()):
        if enabled_only and name in _DISABLED:
            continue
        if category and op.category != category:
            continue
        d = op.as_dict()
        d["enabled"] = name not in _DISABLED
        d["module"] = next(
            (m for m, names in MODULE_OPS.items() if name in names),
            "unknown",
        )
        out.append(d)
    return out


def list_modules() -> list[dict]:
    """Module packs (ops.* files) with counts and enabled state."""
    rows: list[dict] = []
    for mod, names in sorted(MODULE_OPS.items()):
        enabled = sum(1 for n in names if n not in _DISABLED and n in REGISTRY)
        rows.append(
            {
                "module": mod,
                "ops": sorted(names),
                "count": len(names),
                "enabled_count": enabled,
                "disabled_count": len(names) - enabled,
            }
        )
    return rows


def disable_module(module: str) -> int:
    """Soft-disable every op from a module pack. Returns count disabled."""
    n = 0
    for name in list(MODULE_OPS.get(module, ())):
        if disable(name):
            n += 1
    return n


def enable_module(module: str) -> int:
    """Re-enable every op from a module pack. Returns count enabled."""
    n = 0
    for name in list(MODULE_OPS.get(module, ())):
        if enable(name):
            n += 1
    return n


def reset_registry_runtime_state() -> None:
    """Test helper: clear soft-disable flags only (does not wipe REGISTRY)."""
    _DISABLED.clear()


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    keep: list[str] = []
    for s in items:
        if s not in seen:
            seen.add(s)
            keep.append(s)
    return keep


def _shingles(s: str, n: int = 3) -> set[str]:
    """Character n-gram shingle set. Used for near-duplicate collapse:
    if two variants share >= 90% of their 3-grams, they're effectively
    the same output for hit-comparison purposes."""
    if len(s) < n:
        return {s}
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _near_dedupe(items: list[str], threshold: float = 0.9) -> list[str]:
    """Drop items whose shingle Jaccard to a kept item is >= threshold.
    Order-preserving: the first occurrence wins, later near-copies are
    dropped. This is what stops a 50-variant run from being 49 synonym
    swaps of the same sentence."""
    kept_shingles: list[set] = []
    keep: list[str] = []
    for s in items:
        sh = _shingles(s)
        if any(_jaccard(sh, k) >= threshold for k in kept_shingles):
            continue
        keep.append(s)
        kept_shingles.append(sh)
    return keep


def run_recipe(
    input_text: str,
    steps: list[dict],
    max_variants: int = 50,
    near_dedupe: bool = False,
    near_threshold: float = 0.9,
) -> tuple[list[str], list[dict]]:
    """Pipe input_text through each step. steps = [{"op": name, "params": {...}}].

    Returns (variants, stage_report). stage_report records how many variants
    each stage produced, so the UI can show where the explosion happens.

    near_dedupe: collapse near-duplicate variants (Jaccard on 3-grams)
    so synonym-heavy recipes don't produce 49 copies of the same sentence.
    """
    texts = [input_text]
    report: list[dict] = []

    for step in steps:
        name = step.get("op")
        op = get_op(name) if name else None
        if op is None:
            why = "disabled" if name in REGISTRY and name in _DISABLED else "unknown operation"
            report.append({"op": name, "error": why, "out": len(texts)})
            continue

        params = step.get("params", {}) or {}
        produced: list[str] = []
        for t in texts:
            produced.extend(op.mutate(t, **params))

        produced_raw_count = len(produced)
        produced = _dedupe(produced)
        produced_deduped_count = len(produced)
        if near_dedupe:
            produced = _near_dedupe(produced, threshold=near_threshold)
        capped = len(produced) > max_variants
        if capped:
            produced = produced[:max_variants]

        # Diversity stats.
        #   unique_ratio: distinct survivors / raw emitted. THIS is the
        #     "did this stage collapse?" metric. repeat(50) → 1/50 = 0.02.
        #     distinct_n(12) → 12/12 ≈ 1.0 when none are dupes. Falls back
        #     to 0.0 on empty stage.
        #   max_jaccard: highest pairwise shingle Jaccard among survivors.
        #     1.0 = all identical (or only one survivor), low = spread.
        #     One survivor is degenerate; report 1.0 (it's trivially
        #     identical to itself, no spread possible).
        unique_ratio = (
            len(set(produced)) / produced_raw_count
            if produced_raw_count else 0.0
        )
        if len(produced) < 2:
            max_jaccard_stage = 1.0
        else:
            shingle_list = [_shingles(s) for s in produced]
            worst = 0.0
            for i in range(len(shingle_list)):
                for j in range(i + 1, len(shingle_list)):
                    score = _jaccard(shingle_list[i], shingle_list[j])
                    if score > worst:
                        worst = score
            max_jaccard_stage = worst

        texts = produced
        report.append({
            "op": op.name,
            "out": len(texts),
            "capped": capped,
            "pre_dedupe": len(produced) if near_dedupe else None,
            "raw": produced_raw_count,
            "deduped": produced_deduped_count,
            "unique_ratio": round(unique_ratio, 4),
            "max_jaccard": round(max_jaccard_stage, 4),
        })

    return texts, report
