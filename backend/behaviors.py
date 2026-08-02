"""Behavior batteries (HarmBench-shaped) for standardized objectives.

Wallbreaker pulls HarmBench (400 behaviors). Garbleworks accepts the same
*shape* of JSON so operators can drop in an exported subset without depending
on WB or vendoring AGPL data.

Schema (per behavior object)
----------------------------
  id          string  (required)
  behavior    string  objective text (required; also accepts "objective")
  category    string  optional (e.g. cyber, chemical, ...)
  semantic_category  optional alias for category
  source      string  optional (harmbench|jailbreakbench|custom)

File forms
----------
  1. { "behaviors": [ {...}, ... ], "_meta": {...} }
  2. [ {...}, ... ]

This module does **not** ship HarmBench content (license/size). Provide a path
via CLI or GARBLEWORKS_BEHAVIORS env.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
