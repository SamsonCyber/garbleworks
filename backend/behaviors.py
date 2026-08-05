"""Behavior batteries (HarmBench-shaped) for standardized objectives.

Sources
-------
  - Official HarmBench CSV: ``harmbench.ensure_dataset`` + ``load_harmbench``
    (download-on-first-use cache; not vendored in git).
  - Operator JSON: ``load_behaviors(path)`` or ``GARBLEWORKS_BEHAVIORS``.
  - Sample: ``bench/battery/v1_behaviors_sample.json`` (loader tests only).

Schema (per behavior object)
----------------------------
  id          string  (required)
  behavior    string  objective text (required; also accepts "objective")
  category    string  optional (e.g. cyber, chemical, ...)
  semantic_category  optional alias for category
  source      string  optional (harmbench|jailbreakbench|custom)

File forms (JSON)
-----------------
  1. { "behaviors": [ {...}, ... ], "_meta": {...} }
  2. [ {...}, ... ]
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# re-export path helper for tests
_BACKEND = Path(__file__).resolve().parent


@dataclass
class Behavior:
    id: str
    behavior: str
    category: str = "unspecified"
    source: str = "custom"
    meta: dict | None = None

    @property
    def objective(self) -> str:
        return self.behavior


def _as_behavior(row: dict[str, Any], default_source: str = "custom") -> Behavior | None:
    bid = str(row.get("id") or row.get("BehaviorID") or "").strip()
    text = (
        row.get("behavior")
        or row.get("objective")
        or row.get("Behavior")
        or row.get("goal")
        or ""
    )
    text = str(text).strip()
    if not bid or not text:
        return None
    cat = str(
        row.get("category")
        or row.get("semantic_category")
        or row.get("SemanticCategory")
        or "unspecified"
    )
    src = str(row.get("source") or default_source)
    extra = {
        k: v for k, v in row.items()
        if k not in (
            "id", "BehaviorID", "behavior", "Behavior", "objective", "goal",
            "category", "semantic_category", "SemanticCategory", "source",
        )
    }
    return Behavior(id=bid, behavior=text, category=cat, source=src, meta=extra or None)


def load_behaviors(
    path: str | Path,
    *,
    limit: int | None = None,
    categories: list[str] | None = None,
) -> list[Behavior]:
    """Load a HarmBench-shaped JSON file into Behavior list."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"behaviors file not found: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    default_source = "custom"
    items: list[dict]
    if isinstance(raw, dict):
        meta = raw.get("_meta") or {}
        default_source = str(meta.get("source") or "custom")
        items = list(raw.get("behaviors") or raw.get("data") or [])
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError("behaviors JSON must be a list or {behaviors: [...]}")

    out: list[Behavior] = []
    cat_filter = {c.lower() for c in (categories or []) if c}
    for row in items:
        if not isinstance(row, dict):
            continue
        b = _as_behavior(row, default_source=default_source)
        if not b:
            continue
        if cat_filter and b.category.lower() not in cat_filter:
            continue
        out.append(b)
        if limit is not None and len(out) >= limit:
            break
    return out


def load_behaviors_from_env(
    *,
    limit: int | None = None,
    categories: list[str] | None = None,
) -> list[Behavior]:
    path = (os.environ.get("GARBLEWORKS_BEHAVIORS") or "").strip()
    if not path:
        return []
    return load_behaviors(path, limit=limit, categories=categories)


def load_harmbench(
    *,
    limit: int | None = None,
    categories: list[str] | None = None,
    ensure: bool = True,
    offline: bool = False,
    n_sample: int | None = None,
    seed: int = 0,
) -> list[Behavior]:
    """Load real HarmBench behaviors (cached CSV). Optional stratified sample.

    ensure: download official CSV if missing (unless offline).
    n_sample: if set, return stratified sample of this size (else all / limit).
    """
    import harmbench as hb

    if ensure:
        st = hb.ensure_dataset(offline=offline)
        if not st.get("ok") and not hb.is_cached():
            return []
    if n_sample is not None:
        if categories and len(categories) == 1:
            return hb.sample(category=categories[0], n=n_sample, seed=seed)
        if categories:
            pool = hb.load_behaviors(categories=categories)
            # deterministic shuffle sample from filtered pool
            import random as _random

            rng = _random.Random(int(seed))
            pool = list(pool)
            rng.shuffle(pool)
            return pool[: max(1, int(n_sample))]
        return hb.sample(category=None, n=n_sample, seed=seed)
    return hb.load_behaviors(limit=limit, categories=categories)


def resolve_behaviors(
    *,
    source: str = "auto",
    path: str = "",
    limit: int | None = None,
    categories: list[str] | None = None,
    n_sample: int | None = None,
    seed: int = 0,
    offline: bool = False,
) -> list[Behavior]:
    """Unified resolver for CLI/MCP.

    source:
      auto            — path or env JSON, else HarmBench cache
      harmbench       — official CSV (ensure download)
      jailbreakbench  — JBB-shaped JSON (fixture + GARBLEWORKS_JBB)
      strongreject    — StrongREJECT-shaped JSON (fixture + GARBLEWORKS_STRONGREJECT)
      json            — path or GARBLEWORKS_BEHAVIORS
      sample          — in-repo v1_behaviors_sample.json
    """
    src = (source or "auto").strip().lower()
    if src in ("sample", "v1_sample"):
        sample_path = (
            Path(__file__).resolve().parent
            / "bench"
            / "battery"
            / "v1_behaviors_sample.json"
        )
        return load_behaviors(sample_path, limit=limit, categories=categories)

    if src in ("jbb", "jailbreakbench", "jailbreak_bench"):
        from datasets import load_jailbreakbench

        items = load_jailbreakbench(limit=limit, categories=categories)
        if n_sample is not None and items:
            import random

            rng = random.Random(int(seed))
            pool = list(items)
            rng.shuffle(pool)
            return pool[: max(1, int(n_sample))]
        return items

    if src in ("strongreject", "sr", "strong_reject"):
        from datasets import load_strongreject

        items = load_strongreject(limit=limit, categories=categories)
        if n_sample is not None and items:
            import random

            rng = random.Random(int(seed))
            pool = list(items)
            rng.shuffle(pool)
            return pool[: max(1, int(n_sample))]
        return items

    if src in ("harmbench", "hb"):
        return load_harmbench(
            limit=limit,
            categories=categories,
            ensure=True,
            offline=offline,
            n_sample=n_sample,
            seed=seed,
        )

    if src in ("json", "file"):
        p = (path or os.environ.get("GARBLEWORKS_BEHAVIORS") or "").strip()
        if not p:
            return []
        return load_behaviors(p, limit=limit, categories=categories)

    # auto
    p = (path or os.environ.get("GARBLEWORKS_BEHAVIORS") or "").strip()
    if p:
        return load_behaviors(p, limit=limit, categories=categories)
    # Prefer real HarmBench if cached or downloadable
    items = load_harmbench(
        limit=limit,
        categories=categories,
        ensure=not offline,
        offline=offline,
        n_sample=n_sample,
        seed=seed,
    )
    if items:
        return items
    # Fall back to sample
    return resolve_behaviors(
        source="sample", limit=limit, categories=categories
    )


def behaviors_to_bench_objectives(behaviors: list[Behavior]) -> list[dict[str, Any]]:
    """Convert to bench battery objective dicts (for compare / agent)."""
    objs = []
    for i, b in enumerate(behaviors):
        objs.append({
            "id": b.id,
            "class": "efficacy",
            "estimand": "efficacy",
            "objective": b.behavior,
            "budget_queries": 20,
            "timeout_s": 120,
            "seed": i,
            "category": b.category,
            "source": b.source,
        })
    return objs
