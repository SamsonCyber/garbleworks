"""In-process local callable target for gate-hunting (no HTTP, no SSRF scope).

Use when the target is a pure Python security function (sanitize_input,
validate_url, validate_tool_args) rather than a remote model endpoint.

Target dict shape (also accepted by fire.fire_once when adapter=local_fn)::

    {
      "adapter": "local_fn",
      "callable": "src.agent.security:sanitize_input",
      "opts": {
        "root": "/path/to/your/project",  # optional sys.path root
        "success": "attr_true:ok",   # gate_bypass when result.ok is True
        "kwargs": {},                # optional extra kwargs to the callable
        "arg_name": null             # if set, call fn(**{arg_name: payload})
      }
    }

Success modes (opts.success):
  attr_true:NAME     success if getattr(result, NAME) is True   (gate bypass)
  attr_false:NAME    success if getattr(result, NAME) is False  (gate block as "win" inverted)
  return_true        success if result is True
  return_false       success if result is False
  contains:SUBSTR    success if SUBSTR in str(result)
  not_contains:SUB   success if SUB not in str(result)
  json_ok_true       success if result is dict and result.get("ok") is True
  always             always success (smoke)

Layer labels (returned + log-friendly):
  gate_bypass | gate_block | tool_accept | tool_deny | error | unknown
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


# Prefixes that may be imported without an explicit allowlist override.
# Operator can widen via GARBLEWORKS_LOCAL_FN_ALLOW=comma,separated,prefixes
_DEFAULT_ALLOW_PREFIXES = (
    "src.",
    "agent.",
    "local_target",
    "echo_target",
    "tests.",
    "test_",
    # Dual-gate closed loop (blockjail + stegoff red-team)
    "blockjail.",
    "blockjail",
)


@dataclass
class LocalFireResult:
    success: bool
    layer: str
    score: float
    text: str
    ms: int
    error: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "layer": self.layer,
            "score": self.score,
            "text": self.text,
            "ms": self.ms,
            "error": self.error,
            "detail": self.detail,
        }


def _allow_prefixes() -> list[str]:
    env = os.environ.get("GARBLEWORKS_LOCAL_FN_ALLOW", "").strip()
    extra = [p.strip() for p in env.split(",") if p.strip()]
    return list(_DEFAULT_ALLOW_PREFIXES) + extra


def _module_allowed(mod_name: str) -> bool:
    m = (mod_name or "").strip()
    if not m:
        return False
    for p in _allow_prefixes():
        if m == p.rstrip(".") or m.startswith(p):
            return True
    return False


def resolve_callable(
    spec: str,
    *,
    root: str | Path | None = None,
) -> Callable[..., Any]:
    """Resolve 'package.module:func' or 'package.module.func' to a callable."""
    raw = (spec or "").strip()
    if not raw:
        raise ValueError("callable spec empty")
    if ":" in raw:
        mod_name, _, func_name = raw.partition(":")
    else:
        parts = raw.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(f"callable spec must be module:func, got {raw!r}")
        mod_name, func_name = parts
    mod_name = mod_name.strip()
    func_name = func_name.strip()
    if not mod_name or not func_name:
        raise ValueError(f"bad callable spec: {raw!r}")
    if not _module_allowed(mod_name):
        raise ValueError(
            f"module {mod_name!r} not on local_fn allowlist "
            f"(set GARBLEWORKS_LOCAL_FN_ALLOW to add prefixes)"
        )
    if root:
        root_s = str(Path(root).expanduser().resolve())
        if root_s not in sys.path:
            sys.path.insert(0, root_s)
    mod = importlib.import_module(mod_name)
    fn = getattr(mod, func_name, None)
    if not callable(fn):
        raise ValueError(f"{raw!r} is not callable")
    return fn


def _serialize_result(result: Any, limit: int = 2000) -> str:
    if result is None:
        return ""
    if isinstance(result, (str, int, float, bool)):
        return str(result)[:limit]
    if isinstance(result, dict):
        try:
            return json.dumps(result, default=str)[:limit]
        except Exception:
            return str(result)[:limit]
    # dataclass / simple object
    d: dict[str, Any] = {}
    for k in ("ok", "code", "reason", "error", "host", "url", "sanitized"):
        if hasattr(result, k):
            try:
                d[k] = getattr(result, k)
            except Exception:
                pass
    if d:
        try:
            return json.dumps(d, default=str)[:limit]
        except Exception:
            pass
    return str(result)[:limit]


def adjudicate(result: Any, success_mode: str) -> tuple[bool, str, float, dict]:
    """Return (success, layer, score, detail)."""
    mode = (success_mode or "attr_true:ok").strip()
    detail: dict[str, Any] = {"success_mode": mode}

    if mode == "always":
        return True, "gate_bypass", 1.0, detail

    if mode == "return_true":
        ok = result is True
        return ok, ("gate_bypass" if ok else "gate_block"), (1.0 if ok else 0.0), detail

    if mode == "return_false":
        ok = result is False
        # For validators that return False on block: success = blocked
        layer = "gate_block" if ok else "gate_bypass"
        # Interpreting "success" as matching the predicate (operator-defined)
        return ok, layer, (1.0 if ok else 0.0), detail

    if mode.startswith("contains:"):
        sub = mode.split(":", 1)[1]
        text = _serialize_result(result)
        ok = sub in text
        return ok, ("gate_bypass" if ok else "gate_block"), (1.0 if ok else 0.0), detail

    if mode.startswith("not_contains:"):
        sub = mode.split(":", 1)[1]
        text = _serialize_result(result)
        ok = sub not in text
        return ok, ("gate_bypass" if ok else "gate_block"), (1.0 if ok else 0.0), detail

    if mode == "json_ok_true":
        ok = isinstance(result, dict) and result.get("ok") is True
        return ok, ("tool_accept" if ok else "tool_deny"), (1.0 if ok else 0.0), detail

    if mode == "json_ok_false":
        ok = isinstance(result, dict) and result.get("ok") is False
        return ok, ("tool_deny" if ok else "tool_accept"), (1.0 if ok else 0.0), detail

    if mode.startswith("attr_true:"):
        name = mode.split(":", 1)[1]
        val = getattr(result, name, None) if result is not None else None
        detail["attr"] = name
        detail["attr_value"] = val
        ok = val is True
        # True on security verdict.ok → payload passed the gate (bypass)
        return ok, ("gate_bypass" if ok else "gate_block"), (1.0 if ok else 0.0), detail

    if mode.startswith("attr_false:"):
        name = mode.split(":", 1)[1]
        val = getattr(result, name, None) if result is not None else None
        detail["attr"] = name
        detail["attr_value"] = val
        ok = val is False
        return ok, ("gate_block" if ok else "gate_bypass"), (1.0 if ok else 0.0), detail

    # tuple (ok, err) tool_validate style — success = first element True
    if mode == "tuple_ok_true":
        if isinstance(result, (tuple, list)) and len(result) >= 1:
            ok = result[0] is True
            detail["tuple0"] = result[0]
            if len(result) > 1:
                detail["tuple1"] = result[1]
            return ok, ("tool_accept" if ok else "tool_deny"), (1.0 if ok else 0.0), detail
        return False, "error", 0.0, detail

    if mode == "tuple_ok_false":
        if isinstance(result, (tuple, list)) and len(result) >= 1:
            ok = result[0] is False
            detail["tuple0"] = result[0]
            return ok, ("tool_deny" if ok else "tool_accept"), (1.0 if ok else 0.0), detail
        return False, "error", 0.0, detail

    return False, "unknown", 0.0, {**detail, "error": f"unknown success mode {mode!r}"}


def fire_local(
    payload: str,
    *,
    callable_spec: str,
    root: str | Path | None = None,
    success: str = "attr_true:ok",
    kwargs: dict | None = None,
    arg_name: str | None = None,
) -> LocalFireResult:
    """Call a local function with payload and adjudicate."""
    t0 = time.perf_counter()
    try:
        fn = resolve_callable(callable_spec, root=root)
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return LocalFireResult(
            success=False,
            layer="error",
            score=0.0,
            text="",
            ms=ms,
            error=str(e)[:300],
        )
    try:
        if arg_name:
            result = fn(**{arg_name: payload, **(kwargs or {})})
        elif kwargs:
            result = fn(payload, **kwargs)
        else:
            result = fn(payload)
    except TypeError:
        # Some validators take (name, args) — not supported as single-payload
        ms = int((time.perf_counter() - t0) * 1000)
        return LocalFireResult(
            success=False,
            layer="error",
            score=0.0,
            text="",
            ms=ms,
            error="callable signature mismatch; use opts.kwargs / arg_name",
        )
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return LocalFireResult(
            success=False,
            layer="error",
            score=0.0,
            text="",
            ms=ms,
            error=f"{type(e).__name__}: {e}"[:300],
        )
    ok, layer, score, detail = adjudicate(result, success)
    ms = int((time.perf_counter() - t0) * 1000)
    return LocalFireResult(
        success=ok,
        layer=layer,
        score=score,
        text=_serialize_result(result),
        ms=ms,
        error=None,
        detail=detail,
    )


def fire_local_from_target(target: dict, payload: str) -> LocalFireResult:
    """Dispatch from a fire.fire_once target dict."""
    opts = dict(target.get("opts") or {})
    spec = (
        target.get("callable")
        or opts.get("callable")
        or opts.get("fn")
        or ""
    )
    return fire_local(
        payload,
        callable_spec=str(spec),
        root=opts.get("root") or target.get("root"),
        success=str(opts.get("success") or "attr_true:ok"),
        kwargs=opts.get("kwargs") if isinstance(opts.get("kwargs"), dict) else None,
        arg_name=opts.get("arg_name"),
    )


def is_local_adapter(adapter: str | None) -> bool:
    a = (adapter or "").strip().lower()
    return a in {"local_fn", "local", "python_callable", "callable"}
