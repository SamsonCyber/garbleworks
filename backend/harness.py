"""Single offline harness entry: compose → list → (optional) fire policy check.

CLI, MCP wrappers, and tests call this module for the catalog/scan happy path.
Live model fire stays in fire.py (one policy). No second compose loop here.
"""
from __future__ import annotations

from typing import Any

import ops  # noqa: F401  load module packs into core.REGISTRY
from core import (
    disable,
    disable_module,
    enable,
    enable_module,
    list_modules,
    list_ops,
    run_recipe,
)


def offline_scan_demo(
    text: str = "authorized research objective",
    *,
    max_ops: int = 5,
    max_variants: int = 3,
) -> dict[str, Any]:
    """Safe offline demo: enumerate enabled ops and run first N as one-op recipes.

    No HTTP. No model. Returns a non-empty report for install verification.
    """
    catalog = list_ops(enabled_only=True)
    modules = list_modules()
    samples: list[dict[str, Any]] = []
    for row in catalog[: max(0, max_ops)]:
        name = row["name"]
        variants, stage = run_recipe(
            text,
            [{"op": name, "params": {}}],
            max_variants=max_variants,
        )
        samples.append(
            {
                "op": name,
                "category": row.get("category"),
                "module": row.get("module"),
                "n_variants": len(variants),
                "preview": (variants[0][:120] if variants else ""),
                "stage": stage,
            }
        )
    return {
        "ok": True,
        "primary": "garbleworks",
        "ops_enabled": len(catalog),
        "modules": len(modules),
        "samples": samples,
    }


def module_toggle_demo(module_substr: str = "ops.encode_ops") -> dict[str, Any]:
    """Exercise real registry enable/disable for verification (restores state)."""
    mods = list_modules()
    target = next((m["module"] for m in mods if module_substr in m["module"]), None)
    if not target:
        # fall back to any module with >=1 op
        target = mods[0]["module"] if mods else None
    if not target:
        return {"ok": False, "error": "no modules registered"}

    before = {r["name"] for r in list_ops(enabled_only=True)}
    n_off = disable_module(target)
    mid = {r["name"] for r in list_ops(enabled_only=True)}
    n_on = enable_module(target)
    after = {r["name"] for r in list_ops(enabled_only=True)}
    return {
        "ok": True,
        "module": target,
        "disabled_count": n_off,
        "enabled_count": n_on,
        "before": len(before),
        "mid": len(mid),
        "after": len(after),
        "mid_smaller": len(mid) < len(before),
        "restored": after == before,
    }


# re-export for harness consumers
__all__ = [
    "offline_scan_demo",
    "module_toggle_demo",
    "list_ops",
    "list_modules",
    "disable",
    "enable",
    "disable_module",
    "enable_module",
    "run_recipe",
]
