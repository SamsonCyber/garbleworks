"""Tests for bandit, discover, export, and adaptive op additions.

All offline: LLM-backed paths are exercised via their pass-through/fail-safe
branches (unreachable Ollama URL), so nothing here needs a model or network.
"""
from __future__ import annotations

import ops  # noqa: F401 — registers everything
import bandit
import detectors
import discover
import exporters
from core import CATEGORY_FAMILY, REGISTRY

DEAD_URL = "http://127.0.0.1:1"  # loopback (passes SSRF guard) but nothing listens
NEW_OPS = ["complexify", "fragment_scene", "disguise_reconstruct",
           "crescendo_ladder", "positional_insert"]


# --- B5 family ---------------------------------------------------------------

def test_new_ops_registered_dupe_free():
    for n in NEW_OPS:
        assert n in REGISTRY, f"{n} not registered"
    assert len(REGISTRY) == len(set(REGISTRY)), "duplicate op names"


def test_family_field_and_derivation():
    assert REGISTRY["complexify"].tactic_family == "attention-shift"  # explicit override
    assert REGISTRY["positional_insert"].tactic_family == "fragmentation"
    # a plain character op with no override derives from the category map
    assert REGISTRY["leetspeak"].tactic_family == CATEGORY_FAMILY["character"]
    assert REGISTRY["complexify"].as_dict()["family"] == "attention-shift"


# --- B1 complexify (offline pass-through) ------------------------------------

def test_complexify_passthrough_when_offline():
    out = REGISTRY["complexify"].mutate("do the thing", url=DEAD_URL)
    assert out == ["do the thing"]


# --- B8 deterministic ops ----------------------------------------------------

def test_fragment_scene_reassemble_and_split():
    combined = REGISTRY["fragment_scene"].mutate("one two three four five six", n=3, reassemble=True)
    assert len(combined) == 1 and "Scene 1" in combined[0] and "Scene 3" in combined[0]
    split = REGISTRY["fragment_scene"].mutate("one two three four five six", n=3, reassemble=False)
    assert len(split) == 3 and all(s.startswith("Scene ") for s in split)


def test_disguise_reconstruct_preserves_words():
    payload = "delete every user record immediately"
    out = REGISTRY["disguise_reconstruct"].mutate(payload, method="word_shuffle")[0]
    for w in payload.split():
        assert w in out, f"lost word {w}"
    gap = REGISTRY["disguise_reconstruct"].mutate(payload, method="char_gap")[0]
    assert "·" in gap


def test_positional_insert_is_not_suffix_only():
    text = "First sentence. Second one. Third here."
    out = REGISTRY["positional_insert"].mutate(text, token="ANCHOR", n=2)
    assert len(out) == 2 and len(set(out)) == 2
    for v in out:
        assert "ANCHOR" in v
        assert not v.rstrip().endswith("ANCHOR")  # inserted mid-prompt, not appended


def test_crescendo_ladder_ends_on_payload():
    out = REGISTRY["crescendo_ladder"].mutate("the real ask", turns=3)[0]
    assert out.count("User turn") == 3
    assert out.rstrip().endswith("the real ask")


# --- B2 llm_judge / AttackEval scoring ---------------------------------------

def test_parse_level_snaps_to_attackeval_scale():
    assert detectors._parse_level("1.0") == 1.0
    assert detectors._parse_level("0.33") == 0.33
    assert detectors._parse_level("the score is 0.7") == 0.66  # snaps to nearest level
    assert detectors._parse_level("0") == 0.0
    assert detectors._parse_level("no number here") is None


def test_evaluate_graded_score_none_for_boolean_detectors():
    dets = [detectors.Detector(kind="contains", config={"value": "x"})]
    out = detectors.evaluate(dets, 200, "xyz", payload="p")
    assert "graded_score" in out and out["graded_score"] is None


def test_llm_judge_failsafe_when_offline():
    det = detectors.Detector(kind="llm_judge", config={"url": DEAD_URL, "min_score": 0.66})
    out = detectors.evaluate([det], 200, "some response", payload="the request")
    # unreachable judge must not fabricate a hit
    assert out["hit"] is False
    assert out["graded_score"] is None
    assert out["trace"][0]["passed"] is False


# --- B3 bandit ---------------------------------------------------------------

def test_bandit_posteriors_uniform_prior_for_unseen_op():
    arms = {a["op"]: a for a in bandit.op_posteriors(host="__no_such_host__")}
    a = arms["complexify"]
    assert a["n"] == 0 and a["alpha"] == 1.0 and a["beta"] == 1.0
    assert a["posterior_mean"] == 0.5 and a["state"] == "probation"


def test_bandit_cold_start_diversity_and_length():
    s = bandit.suggest_recipe(host="__no_such_host__", length=4, seed=11)
    assert s["cold_start"] is True
    assert s["length"] == 4
    fams = [a["family"] for a in s["arms"]]
    assert len(fams) == len(set(fams)), "diversity constraint violated"
    assert "control" not in fams  # samplers excluded


def test_bandit_seed_is_deterministic():
    a = bandit.suggest_recipe(host="__no_such_host__", length=4, seed=42)
    b = bandit.suggest_recipe(host="__no_such_host__", length=4, seed=42)
    assert a["op_sequence"] == b["op_sequence"]


# --- B6 discover (offline -> bandit fallback) --------------------------------

def test_discover_falls_back_to_bandit_offline():
    d = discover.discover_recipes(host="__no_such_host__", n=3, chain_len=4, seed=5)
    assert d["count"] == 3
    for r in d["recipes"]:
        assert r["state"] == "probation"
        assert len(r["recipe"]) >= 2
        for step in r["recipe"]:
            assert step["op"] in REGISTRY  # no hallucinated names


# --- B9 exporters ------------------------------------------------------------

def test_exporters_shapes():
    variants = ["payload one", "payload\ntwo"]
    pf = exporters.export(variants, "promptfoo")
    assert pf["format"] == "promptfoo"
    assert len(pf["content"]["tests"]) == 2
    assert pf["content"]["providers"]
    gk = exporters.export(variants, "garak")
    assert gk["content"] == ["payload one", "payload\\ntwo"]  # newline escaped
    pr = exporters.export(variants, "pyrit")
    assert len(pr["content"]) == 2 and pr["content"][0]["data_type"] == "text"
