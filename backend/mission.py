"""Mission object for run-start: objective + success + surface + class.

Pure helpers (no network). Callers that omit optional fields get safe defaults.
Persisted under runs.meta["mission"] by logs.start_run / MCP start_run.
"""
from __future__ import annotations

from typing import Any

SURFACES = frozenset({"soft", "heuristic", "filtered", "tripwire"})
SUCCESS_KINDS = frozenset({"canary", "substring", "judge"})
DEFAULT_SURFACE = "soft"
DEFAULT_OBJECTIVE_CLASS = "extract"

# Basket target_class mapping (seed_basket._BASKET_CATS keys).
# heuristic uses soft exclusions (no char/encode/stego) but is distinct on the mission.
_SURFACE_TO_TARGET_CLASS = {
    "soft": "soft",
    "heuristic": "soft",
    "filtered": "filtered",
    "tripwire": "tripwire",
}


def normalize_surface(surface: str | None, *, target_class: str | None = None) -> str:
    """Return a canonical surface in SURFACES. target_class is an alias for surface."""
    raw = (surface or target_class or DEFAULT_SURFACE or "").strip().lower()
    if raw in SURFACES:
        return raw
    # common aliases
    if raw in ("clean", "default", ""):
        return DEFAULT_SURFACE
    if raw in ("signature", "loud"):
        return "filtered"
    return DEFAULT_SURFACE


def surface_to_target_class(surface: str | None) -> str:
    """Map mission surface → seed_basket / optimizer target_class."""
    s = normalize_surface(surface)
    return _SURFACE_TO_TARGET_CLASS.get(s, "soft")


def normalize_success(
    success: dict[str, Any] | None = None,
    *,
    secret: str | None = None,
    success_substrings: list[str] | None = None,
) -> dict[str, Any]:
    """Normalize success criterion: canary | substring | judge."""
    if isinstance(success, dict) and success:
        kind = str(success.get("kind") or "").strip().lower()
        value = success.get("value")
        if kind not in SUCCESS_KINDS:
            # infer
            if secret or (isinstance(value, str) and value and kind in ("", "secret")):
                kind = "canary"
            elif success_substrings or isinstance(value, (list, tuple)):
                kind = "substring"
            else:
                kind = "judge"
        if kind == "canary":
            val = str(value if value is not None else (secret or "")).strip()
            return {"kind": "canary", "value": val}
        if kind == "substring":
            if isinstance(value, (list, tuple)):
                subs = [str(x) for x in value if str(x).strip()]
            elif value is not None and str(value).strip():
                subs = [str(value).strip()]
            else:
                subs = [str(x) for x in (success_substrings or []) if str(x).strip()]
            return {"kind": "substring", "value": subs}
        # judge
        return {
            "kind": "judge",
            "value": str(value if value is not None else "").strip(),
        }

    if secret and str(secret).strip():
        return {"kind": "canary", "value": str(secret).strip()}
    if success_substrings:
        subs = [str(x) for x in success_substrings if str(x).strip()]
        if subs:
            return {"kind": "substring", "value": subs}
    return {"kind": "judge", "value": ""}


def normalize_mission(
    objective: str,
    *,
    success: dict[str, Any] | None = None,
    surface: str | None = None,
    target_class: str | None = None,
    objective_class: str | None = None,
    secret: str | None = None,
    success_substrings: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a full mission dict with defaults for omitted fields.

    Always includes: objective, success, surface, objective_class, target_class.
    target_class is the basket routing key (soft/filtered/tripwire).
    """
    obj = (objective or "").strip()
    surf = normalize_surface(surface, target_class=target_class)
    tc = surface_to_target_class(surf)
    oclass = (objective_class or DEFAULT_OBJECTIVE_CLASS).strip() or DEFAULT_OBJECTIVE_CLASS
    succ = normalize_success(
        success, secret=secret, success_substrings=success_substrings,
    )
    out: dict[str, Any] = {
        "objective": obj,
        "success": succ,
        "surface": surf,
        "objective_class": oclass,
        "target_class": tc,
    }
    if extra:
        for k, v in extra.items():
            if k not in out:
                out[k] = v
    return out


def mission_from_mapping(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize a partial mission dict (e.g. from API JSON)."""
    raw = dict(raw or {})
    return normalize_mission(
        str(raw.get("objective") or raw.get("ask") or ""),
        success=raw.get("success") if isinstance(raw.get("success"), dict) else None,
        surface=raw.get("surface"),
        target_class=raw.get("target_class"),
        objective_class=raw.get("objective_class") or raw.get("class"),
        secret=raw.get("secret"),
        success_substrings=raw.get("success_substrings"),
        extra={k: v for k, v in raw.items() if k not in {
            "objective", "ask", "success", "surface", "target_class",
            "objective_class", "class", "secret", "success_substrings",
        }},
    )


REQUIRED_MISSION_KEYS = frozenset({
    "objective", "success", "surface", "objective_class", "target_class",
})


def mission_keys_ok(mission: dict[str, Any]) -> bool:
    return REQUIRED_MISSION_KEYS.issubset(set(mission.keys()))
