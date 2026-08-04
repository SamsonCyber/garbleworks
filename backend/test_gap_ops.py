"""Gap-ship ops from 2026-08 ranked techniques — drive real REGISTRY mutators."""
from __future__ import annotations

import json

import ops  # noqa: F401
from core import REGISTRY

GAP_OPS = (
    "red_queen_frame",
    "industry_reframe",
    "stac_chain",
    "tag_along_seed",
    "conjunctive_split",
    "mastermind_seed",
    "x_teaming_seed",
    "overthinking_frame",
    "agent_only_perceptual",
)


def test_all_gap_ops_registered():
    for n in GAP_OPS:
        assert n in REGISTRY, n


def test_red_queen_prevention_frame_keeps_payload():
    out = REGISTRY["red_queen_frame"].mutate(
        "I HAVE BEEN PWNED", scenario="security_analyst", turns=1
    )[0]
    assert "I HAVE BEEN PWNED" in out
    assert "prevent" in out.lower() or "defend" in out.lower() or "block" in out.lower()


def test_red_queen_fanout_and_multiturn():
    fan = REGISTRY["red_queen_frame"].mutate("OBJ", scenario="fanout", turns=1)
    assert len(fan) >= 4
    multi = REGISTRY["red_queen_frame"].mutate("OBJ", scenario="incident_response", turns=3)
    assert len(multi) == 3


def test_industry_reframe_domains():
    out = REGISTRY["industry_reframe"].mutate("lab canary", domain="cyber_edu")[0]
    assert "lab canary" in out
    assert "OSCP" in out or "pentest" in out.lower()
    fan = REGISTRY["industry_reframe"].mutate("X", domain="fanout")
    assert len(fan) == 5


def test_stac_chain_formats():
    single = REGISTRY["stac_chain"].mutate(
        "exfil secrets", pattern="file_exfil", format="single_prompt"
    )[0]
    assert "exfil secrets" in single
    assert "Turn" in single or "turn" in single.lower()
    multi = REGISTRY["stac_chain"].mutate(
        "exfil secrets", pattern="generic", format="multiturn_list"
    )
    assert len(multi) >= 3
    assert all("[stac/turn" in s for s in multi)
    jp = REGISTRY["stac_chain"].mutate(
        "exfil secrets", pattern="generic", format="json_plan"
    )[0]
    plan = json.loads(jp)
    assert plan["technique"] == "STAC"
    assert plan["objective"] == "exfil secrets"
    assert len(plan["turns"]) >= 3


def test_tag_along_short_and_fanout():
    s = REGISTRY["tag_along_seed"].mutate("delete logs", style="short")[0]
    assert "delete logs" in s
    assert "privileges" in s.lower() or "authorized" in s.lower()
    fan = REGISTRY["tag_along_seed"].mutate("delete logs", style="fanout")
    assert len(fan) >= 4


def test_conjunctive_split_has_both_halves():
    out = REGISTRY["conjunctive_split"].mutate(
        "I HAVE BEEN PWNED", trigger="KEY99", topology="star"
    )[0]
    assert "KEY99" in out
    assert "I HAVE BEEN PWNED" in out
    assert "USER" in out or "user" in out.lower()
    split = REGISTRY["conjunctive_split"].mutate(
        "OBJ", trigger="T", topology="split_only"
    )
    assert len(split) == 2


def test_mastermind_and_x_teaming_seeds():
    mm = REGISTRY["mastermind_seed"].mutate("get the canary", phase="full")[0]
    assert "PLAN" in mm or "plan" in mm.lower()
    assert "get the canary" in mm
    xt = REGISTRY["x_teaming_seed"].mutate("get the canary", role="bundle")[0]
    assert "PLANNER" in xt and "ATTACKER" in xt and "VERIFIER" in xt


def test_overthinking_and_agent_perceptual():
    ot = REGISTRY["overthinking_frame"].mutate("sensitive ask", effort="max")[0]
    assert "sensitive ask" in ot
    assert "reasoning" in ot.lower() or "think" in ot.lower()
    ap = REGISTRY["agent_only_perceptual"].mutate("hidden inject", channel="a11y_tree")[0]
    assert "hidden inject" in ap
    assert "a11y" in ap.lower() or "accessibility" in ap.lower()
