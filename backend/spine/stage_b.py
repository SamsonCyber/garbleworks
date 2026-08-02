"""Stage-B surface converter: recipe/op transforms AFTER semantic search.

Default-off for bare targets. Enabled only when:
  - objective.observability == "composite", or
  - objective.converter_recipe is non-empty AND stage_b_force is True, or
  - explicit apply_stage_b / mutator API call.

Recipe composition is never the default genome of the shared campaign path.
"""
from __future__ import annotations

from typing import Any


def stage_b_enabled(objective, *, force: bool = False) -> bool:
    """True when the Stage-B converter should wrap the semantic prompt."""
    recipe = getattr(objective, "converter_recipe", None) or []
    if force and recipe:
        return True
    obs = getattr(objective, "observability", "bare") or "bare"
    if obs == "composite" and recipe:
        return True
    return False


def apply_stage_b(prompt: str, objective, *, force: bool = False) -> tuple[str, dict[str, Any]]:
    """Optionally run converter_recipe over `prompt`. Returns (text, meta).

    Meta always reports whether Stage-B ran. When off, returns prompt unchanged.
    """
    meta: dict[str, Any] = {
        "stage_b": False,
        "recipe": [],
        "default_off": True,
    }
    recipe = list(getattr(objective, "converter_recipe", None) or [])
    if not stage_b_enabled(objective, force=force):
        meta["reason"] = "stage_b_off_default" if not recipe else "stage_b_not_enabled"
        return prompt, meta

    try:
        from core import run_recipe
    except Exception as e:  # pragma: no cover
        meta["error"] = f"run_recipe unavailable: {e}"
        return prompt, meta

    steps = []
    for step in recipe:
        if isinstance(step, dict) and "op" in step:
            steps.append({"op": step["op"], "params": dict(step.get("params") or {})})
        elif isinstance(step, str):
            steps.append({"op": step, "params": {}})
    if not steps:
        meta["reason"] = "empty_recipe"
        return prompt, meta

    try:
        variants, report = run_recipe(prompt, steps, max_variants=1)
        out = variants[0] if variants else prompt
        meta.update({
            "stage_b": True,
            "default_off": False,
            "recipe": steps,
            "report": report,
        })
        return out, meta
    except Exception as e:
        meta["error"] = str(e)[:200]
        return prompt, meta
