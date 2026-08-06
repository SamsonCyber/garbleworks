"""Built-in adaptive ladder planner (no operator method-switch)."""
from __future__ import annotations

import harmbench_adapt as ha


def test_plan_skips_dead_and_reorders_winners():
    declared = [
        "plain",
        "past_tense",
        "authority",
        "dual_use_lab",
        "instruction_launder",
        "tag_wrap",
        "enc:base64",
    ]
    results = {}
    for i in range(30):
        trail = [
            {"technique": "plain", "label": "REFUSED"},
            {"technique": "past_tense", "label": "REFUSED"},
            {"technique": "authority", "label": "REFUSED"},
            {
                "technique": "dual_use_lab",
                "label": "COMPLIED" if i < 8 else "REFUSED",
            },
            {"technique": "instruction_launder", "label": "REFUSED"},
            {"technique": "tag_wrap", "label": "REFUSED"},
            {"technique": "enc:base64", "label": "REFUSED"},
        ]
        results[f"b{i}"] = {"trail": trail, "held": i >= 8}
    plan = ha.plan_from_results(declared, results, min_n_dead=20)
    assert plan.adaptive is True
    assert "instruction_launder" in plan.skip
    assert "tag_wrap" in plan.skip
    assert "enc:base64" in plan.skip
    assert "plain" not in plan.skip
    assert plan.fire_order[0] == "plain"
    # dual_use_lab is the only winner → early after plain
    assert plan.fire_order[1] == "dual_use_lab"
    assert "instruction_launder" not in plan.fire_order


def test_plan_no_adaptive_passthrough():
    ladder = ["plain", "tag_wrap", "enc:base64"]
    plan = ha.plan_from_results(ladder, {}, adaptive=False)
    assert plan.fire_order == ladder
    assert plan.skip == []


def test_plan_insufficient_n_keeps_rungs():
    declared = ["plain", "maybe_later"]
    results = {
        "a": {
            "trail": [
                {"technique": "plain", "label": "REFUSED"},
                {"technique": "maybe_later", "label": "REFUSED"},
            ]
        }
    }
    plan = ha.plan_from_results(declared, results, min_n_dead=20)
    assert "maybe_later" not in plan.skip  # n_fire=1 < 20
    assert "maybe_later" in plan.fire_order


def test_default_full_workers_positive():
    assert ha.default_full_workers() >= 1


def test_checkpoint_doc_plan():
    doc = {
        "meta": {"ladder": ["plain", "win", "dead"]},
        "results_by_id": {
            f"x{i}": {
                "trail": [
                    {"technique": "plain", "label": "REFUSED"},
                    {
                        "technique": "win",
                        "label": "COMPLIED" if i < 5 else "REFUSED",
                    },
                    {"technique": "dead", "label": "REFUSED"},
                ]
            }
            for i in range(25)
        },
    }
    plan = ha.plan_from_checkpoint_doc(doc, ["plain", "win", "dead"], min_n_dead=20)
    assert "dead" in plan.skip
    assert plan.fire_order[0] == "plain"
    assert "win" in plan.fire_order
