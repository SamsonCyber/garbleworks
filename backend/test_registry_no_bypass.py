"""If someone hard-codes a live op list bypassing list_ops, this fails."""
from __future__ import annotations

import ops  # noqa: F401
from core import disable, enable, list_ops, run_recipe


def test_run_recipe_respects_disable_not_hardcoded_registry_only():
    name = list_ops(enabled_only=True)[0]["name"]
    disable(name)
    try:
        _variants, report = run_recipe("x", [{"op": name, "params": {}}])
        assert report[0].get("error") == "disabled"
    finally:
        enable(name)
