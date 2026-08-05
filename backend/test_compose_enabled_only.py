"""Primary compose/search pools ignore soft-disabled ops."""
from __future__ import annotations

import ops  # noqa: F401
from core import (
    disable,
    enable,
    enabled_names,
    enabled_ops,
    reset_registry_runtime_state,
    run_recipe,
)


def setup_function() -> None:
    reset_registry_runtime_state()


def test_enabled_ops_excludes_disabled() -> None:
    name = enabled_names()[0]
    assert name in enabled_ops()
    disable(name)
    try:
        assert name not in enabled_ops()
        assert name not in enabled_names()
    finally:
        enable(name)


def test_evolve_pool_skips_disabled() -> None:
    import evolve

    pool = evolve.safe_ops()
    assert pool
    name = pool[0]
    disable(name)
    try:
        pool2 = evolve.safe_ops()
        assert name not in pool2
        assert len(pool2) == len(pool) - 1
    finally:
        enable(name)


def test_bandit_posteriors_skip_disabled() -> None:
    import bandit

    arms = bandit.op_posteriors()
    names = {a["op"] for a in arms}
    assert names
    victim = next(iter(names))
    disable(victim)
    try:
        arms2 = bandit.op_posteriors()
        assert victim not in {a["op"] for a in arms2}
    finally:
        enable(victim)


def test_scan_campaign_technique_list_skips_disabled() -> None:
    import scan_campaign as sc

    names = sc.resolve_catalog()
    assert names
    victim = names[0]
    disable(victim)
    try:
        names2 = sc.resolve_catalog()
        assert victim not in names2
    finally:
        enable(victim)


def test_run_recipe_disabled_errors() -> None:
    name = enabled_names()[0]
    disable(name)
    try:
        _v, report = run_recipe("x", [{"op": name, "params": {}}])
        assert report[0].get("error") == "disabled"
    finally:
        enable(name)
