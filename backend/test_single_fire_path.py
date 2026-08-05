"""Structural: MCP and CLI harness share one fire policy module."""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path

import fire as fire_mod


def test_fire_policy_symbols_are_single_module() -> None:
    assert hasattr(fire_mod, "validate_fire_target")
    assert hasattr(fire_mod, "fire_once")
    assert hasattr(fire_mod, "assert_in_scope")
    path = Path(inspect.getfile(fire_mod)).resolve()
    assert path.name == "fire.py"
    assert "garbleworks" in str(path).replace("\\", "/").lower() or path.parent.name == "backend"


def test_mcp_validate_imports_same_fire_module() -> None:
    # Import mcp_server without running stdio server forever: load module only
    import mcp_server as mcp_mod

    src = inspect.getsource(mcp_mod._mcp_validate_target)
    assert "fire" in src
    assert "validate_fire_target" in src
    # Bindings: function body imports fire as fire_mod
    fire_again = importlib.import_module("fire")
    assert fire_again is fire_mod
    assert fire_again.validate_fire_target is fire_mod.validate_fire_target


def test_harness_does_not_reimplement_fire() -> None:
    import harness as h

    src = Path(inspect.getfile(h)).read_text(encoding="utf-8")
    assert "validate_fire_target" not in src
    assert "urllib" not in src
    # harness uses registry/list_ops only for offline path
    assert "list_ops" in src or "offline_scan_demo" in src
