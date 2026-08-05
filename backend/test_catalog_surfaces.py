"""All operator-facing catalogs honor soft-disable (HTTP + MCP + harness)."""
from __future__ import annotations

import ops  # noqa: F401
from core import disable, enable, list_modules, list_ops, reset_registry_runtime_state


def setup_function() -> None:
    reset_registry_runtime_state()


def _http_ops_names() -> set[str]:
    # Import app after ops registered; call route function directly (no server boot).
    import app as app_mod

    by_cat = app_mod.list_ops()
    names: set[str] = set()
    for _cat, rows in by_cat.items():
        for row in rows:
            names.add(row["name"])
    return names


def _mcp_technique_names() -> set[str]:
    import mcp_server as mcp_mod

    rows = mcp_mod.list_techniques()
    return {r["name"] for r in rows}


def _harness_names() -> set[str]:
    return {r["name"] for r in list_ops(enabled_only=True)}


def test_all_catalog_surfaces_agree_on_enabled_set() -> None:
    http = _http_ops_names()
    mcp = _mcp_technique_names()
    harness = _harness_names()
    assert http == mcp == harness
    assert len(http) >= 10


def test_disable_op_absent_from_http_mcp_and_harness() -> None:
    name = next(iter(_harness_names()))
    assert disable(name) is True
    try:
        assert name not in _http_ops_names()
        assert name not in _mcp_technique_names()
        assert name not in _harness_names()
        # Surfaces still agree with each other while disabled
        assert _http_ops_names() == _mcp_technique_names() == _harness_names()
    finally:
        enable(name)
    assert name in _http_ops_names()
    assert name in _mcp_technique_names()
    assert name in _harness_names()


def test_disable_module_pack_absent_everywhere() -> None:
    from core import disable_module, enable_module

    mods = list_modules()
    assert mods
    target = next((m for m in mods if "encode" in m["module"]), mods[0])
    mod_name = target["module"]
    op_names = set(target["ops"])
    before = _harness_names()
    n = disable_module(mod_name)
    assert n >= 1
    try:
        http = _http_ops_names()
        mcp = _mcp_technique_names()
        harness = _harness_names()
        assert http == mcp == harness
        assert op_names.isdisjoint(http)
        assert len(harness) < len(before)
    finally:
        enable_module(mod_name)
    assert op_names.issubset(_harness_names())
