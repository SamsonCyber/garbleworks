"""Module registry: enable/disable packs without editing fire/optimize."""
from __future__ import annotations

import ops  # noqa: F401
from core import (
    REGISTRY,
    disable,
    disable_module,
    enable,
    enable_module,
    get_op,
    list_modules,
    list_ops,
    reset_registry_runtime_state,
    run_recipe,
    unregister,
    register,
    Operation,
    Param,
)


def setup_function() -> None:
    reset_registry_runtime_state()


def test_list_ops_matches_enabled_registry() -> None:
    catalog = list_ops(enabled_only=True)
    assert len(catalog) >= 10
    names = {r["name"] for r in catalog}
    for n in names:
        assert n in REGISTRY
        assert get_op(n) is not None


def test_disable_enable_op_affects_catalog_and_recipe() -> None:
    catalog = list_ops(enabled_only=True)
    assert catalog, "need at least one op"
    name = catalog[0]["name"]
    assert disable(name) is True
    assert get_op(name) is None
    enabled_names = {r["name"] for r in list_ops(enabled_only=True)}
    assert name not in enabled_names
    variants, report = run_recipe("hello", [{"op": name, "params": {}}])
    assert report and report[0].get("error") == "disabled"
    assert enable(name) is True
    assert get_op(name) is not None
    assert name in {r["name"] for r in list_ops(enabled_only=True)}


def test_disable_module_removes_pack_from_live_catalog() -> None:
    mods = list_modules()
    assert mods, "ops packs must register MODULE_OPS"
    # Prefer encode_ops; else first pack with >0 ops
    target = next((m["module"] for m in mods if "encode" in m["module"]), mods[0]["module"])
    before = {r["name"] for r in list_ops(enabled_only=True)}
    n = disable_module(target)
    assert n >= 1
    mid = {r["name"] for r in list_ops(enabled_only=True)}
    assert len(mid) < len(before)
    # module ops absent from live list
    mod_ops = next(m["ops"] for m in list_modules() if m["module"] == target)
    for op_name in mod_ops:
        assert op_name not in mid
    enable_module(target)
    after = {r["name"] for r in list_ops(enabled_only=True)}
    assert after == before


def test_unregister_hard_removes_and_can_re_register() -> None:
    name = "__test_tmp_op__"
    if name in REGISTRY:
        unregister(name)
    register(
        Operation(
            name=name,
            category="sampler",
            description="temp",
            params=[],
            fn=lambda text, **k: [text],
        ),
        module="tests.tmp",
    )
    assert name in REGISTRY
    assert unregister(name) is True
    assert name not in REGISTRY
    assert get_op(name) is None
