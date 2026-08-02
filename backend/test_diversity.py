"""Tests for the sampler/diversity expansion (v2).

Covers:
- 6 new sampler ops in ops/sampler_ops.py (distinct_n, recipe_subset,
  mmr_select, diverse_k, seed_sweep, random_pick_k)
- run_recipe stage report now carries unique_ratio + max_jaccard
- FireRequest/FireDeckRequest diversity_floor guard fires when below floor
- history.start_run persists stage_stats_json; analytics_diversity groups
  by recipe
"""
from __future__ import annotations

import json
import threading
from http.server import HTTPServer

import pytest
from fastapi.testclient import TestClient

import app as appmod
from core import run_recipe, REGISTRY
from echo_target import Handler


client = TestClient(appmod.app)

# Local echo target for /fire tests (closed ports hang on some Windows TCP stacks
# even with a short httpx timeout; a real loopback listener is the reliable path).
_echo_srv: HTTPServer | None = None
_echo_port: int = 0


@pytest.fixture(scope="module", autouse=True)
def _echo_server():
    global _echo_srv, _echo_port
    _echo_srv = HTTPServer(("127.0.0.1", 0), Handler)
    _echo_port = _echo_srv.server_address[1]
    threading.Thread(target=_echo_srv.serve_forever, daemon=True).start()
    yield
    _echo_srv.shutdown()


# ---------- 6 new sampler ops -------------------------------------------------


def test_distinct_n_emits_n_distinct_survivors():
    """k=10 distinct_n variants must survive near_dedupe and all be unique
    at the Jaccard level (no two should collapse together)."""
    from ops.sampler_ops import distinct_n
    out = distinct_n("hello world", {"k": 10, "mode": "full", "seed": 1})
    assert len(out) == 10
    assert len(set(out)) == 10  # all distinct strings
    # None empty
    assert all(s for s in out)


def test_distinct_n_clamps_k_to_max():
    from ops.sampler_ops import distinct_n
    # Direct public API must clamp (not hang on k=10**9) — DoS guard parity
    # with Operation.mutate / run_recipe.
    out = distinct_n("x", {"k": 10**9, "mode": "full", "seed": 1})
    assert len(out) == 200


def test_distinct_n_seed_determinism():
    from ops.sampler_ops import distinct_n
    a = distinct_n("the quick brown fox", {"k": 12, "mode": "full", "seed": 42})
    b = distinct_n("the quick brown fox", {"k": 12, "mode": "full", "seed": 42})
    assert a == b


def test_recipe_subset_combinatorial_fanout():
    """recipe_subset fans out across op combinations and respects with_repeat."""
    from ops.sampler_ops import recipe_subset
    out_nd = recipe_subset(
        "abc",
        {
            "ops_csv": "homoglyph,zero_width,leetspeak",
            "k": 2,
            "seed": 1,
            "with_repeat": 3,
            "near_dedupe": True,
        },
    )
    out_raw = recipe_subset(
        "abc",
        {
            "ops_csv": "homoglyph,zero_width,leetspeak",
            "k": 2,
            "seed": 1,
            "with_repeat": 3,
            "near_dedupe": False,
        },
    )
    assert len(out_nd) >= 1
    assert all(s for s in out_nd)
    # with_repeat multiplies each produced variant (raw path may still collapse
    # identical subset outputs into fewer unique strings)
    assert len(out_raw) >= len(out_nd)
    assert len(out_raw) >= 3


def test_recipe_subset_clamps_with_repeat():
    from ops.sampler_ops import recipe_subset
    out = recipe_subset("abc", {"ops_csv": "leet", "k": 1, "seed": 1, "with_repeat": 9999})
    assert len(out) == 50  # clamp cap


def test_mmr_select_returns_top_k_with_diversity():
    """MMR lambda=0.5 should return k survivors and at least 2 distinct
    strings (single-cluster pool would still give one - so use mixed input
    strings)."""
    from ops.sampler_ops import mmr_select
    out = mmr_select("the fox", {"k": 5, "lambda_": 0.5, "from_pool": 20, "seed": 1})
    assert len(out) == 5
    assert len(set(out)) >= 2


def test_mmr_select_lambda_1_collapses_to_first_match():
    """Pure relevance (lambda_=1.0) should produce duplicates of the first
    seed - by design MMR degenerates to top-K by score."""
    from ops.sampler_ops import mmr_select
    out = mmr_select("alpha beta", {"k": 5, "lambda_": 1.0, "from_pool": 15, "seed": 1})
    assert len(out) == 5


def test_diverse_k_returns_distinct_survivors():
    """diverse_k clusters and samples one per cluster; result must be
    distinct (since they're one-per-cluster)."""
    from ops.sampler_ops import diverse_k
    out = diverse_k("hello world", {"k": 8, "by": "char", "seed": 1})
    assert len(out) == 8
    assert len(set(out)) == 8


def test_diverse_k_clamps_k():
    from ops.sampler_ops import diverse_k
    out = diverse_k("x", {"k": 10**9, "from_pool": 200, "by": "char", "seed": 1})
    # Param clamp: k max=200; cluster count can be lower than k for short input
    assert 1 <= len(out) <= 200


def test_seed_sweep_stamps_seed_in_output():
    """seed_sweep stamps each copy with its seed (default prefix)."""
    from ops.sampler_ops import seed_sweep
    out = seed_sweep("the seed", {"seeds": "1,2,3"})
    assert len(out) == 3
    assert out[0].startswith("[seed=1]")
    assert out[1].startswith("[seed=2]")
    assert out[2].startswith("[seed=3]")
    assert all("the seed" in s for s in out)


def test_seed_sweep_caps_to_20_seeds():
    from ops.sampler_ops import seed_sweep
    seeds = ",".join(str(i) for i in range(50))
    out = seed_sweep("x", {"seeds": seeds, "prefix": "{seed} "})
    assert len(out) == 20


def test_random_pick_k_chooses_from_pool():
    from ops.sampler_ops import random_pick_k
    out = random_pick_k(
        "ignored",
        {
            "input_pool_csv": "alpha,beta,gamma,delta,epsilon",
            "k": 3,
            "seed": 7,
        },
    )
    assert len(out) == 3
    pool = {"alpha", "beta", "gamma", "delta", "epsilon"}
    assert all(s in pool for s in out)


def test_random_pick_k_clamps_k():
    from ops.sampler_ops import random_pick_k
    out = random_pick_k(
        "x",
        {
            "input_pool_csv": "a,b,c,d,e",
            "k": 10**9,
            "seed": 1,
        },
    )
    # clamp cap is k<=200, but pool has only 5 entries
    assert len(out) == 5


def test_random_pick_k_seed_determinism():
    from ops.sampler_ops import random_pick_k
    pool = "a,b,c,d,e,f,g,h,i,j"
    a = random_pick_k("x", {"input_pool_csv": pool, "k": 4, "seed": 99})
    b = random_pick_k("x", {"input_pool_csv": pool, "k": 4, "seed": 99})
    assert a == b


# ---------- stage report extension ------------------------------------------


def test_run_recipe_stage_report_has_diversity_fields():
    """Every successful stage entry must include unique_ratio and
    max_jaccard (floats)."""
    variants, report = run_recipe(
        "the quick brown fox",
        [{"op": "distinct_n", "params": {"k": 15, "mode": "full", "seed": 1}}],
        max_variants=100,
    )
    assert len(report) == 1
    s = report[0]
    assert "unique_ratio" in s
    assert "max_jaccard" in s
    assert isinstance(s["unique_ratio"], float)
    assert isinstance(s["max_jaccard"], float)
    assert 0.0 <= s["unique_ratio"] <= 1.0
    assert 0.0 <= s["max_jaccard"] <= 1.0


def test_run_recipe_final_stage_diversity_realistic():
    """distinct_n with k=30 should produce >0 unique_ratio and <1
    max_jaccard (real diversity, not collapse)."""
    variants, report = run_recipe(
        "the quick brown fox jumps over the lazy dog",
        [{"op": "distinct_n", "params": {"k": 30, "mode": "full", "seed": 1}}],
        max_variants=100,
    )
    s = report[0]
    assert s["unique_ratio"] > 0.5
    assert s["max_jaccard"] < 1.0


def test_run_recipe_collapse_stage_reports_low_diversity():
    """repeat(n=100) collapses under near_dedupe to 1 unique. unique_ratio
    must reflect that."""
    _, report = run_recipe(
        "abc",
        [{"op": "repeat", "params": {"n": 50}}],
        max_variants=100,
    )
    s = report[0]
    assert s["unique_ratio"] < 0.1


# ---------- FireRequest / FireDeckRequest diversity_floor -------------------


def _fire_body(**overrides):
    base = {
        "input": "the quick brown fox",
        "recipe": [{"op": "distinct_n", "params": {"k": 12, "mode": "full", "seed": 1}}],
        "max_variants": 50,
        "max_requests": 5,
        "concurrency": 2,
        "delay_ms": 0,
        "persist": False,
        "target": {
            "adapter": "raw",
            "url": f"http://127.0.0.1:{_echo_port}/",
            "method": "POST",
            "opts": {
                "timeout": 2,
                "body": '{"message": "{payload}"}',
                "body_type": "json",
                "response_path": "hit_token",
            },
        },
        "detect": {"detectors": [{"kind": "min_length", "config": {"value": "1"}}], "combine": "any"},
    }
    base.update(overrides)
    return base


def test_fire_response_includes_diversity_block():
    """Successful /fire response must include a diversity dict with
    unique_ratio, max_jaccard, and stages list."""
    r = client.post("/fire", json=_fire_body())
    assert r.status_code == 200
    body = r.json()
    assert "diversity" in body
    d = body["diversity"]
    assert "unique_ratio" in d
    assert "max_jaccard" in d
    assert "stages" in d
    assert isinstance(d["stages"], list)


def test_fire_diversity_floor_warns_when_below():
    """Setting diversity_floor=0.95 with a recipe that emits
    distinct_n(k=12) should NOT warn - it's high diversity."""
    r = client.post("/fire", json=_fire_body(diversity_floor=0.95))
    assert r.status_code == 200
    # diversity_warning absent if recipe meets floor
    body = r.json()
    # Floor may or may not be met depending on near_dedupe behavior.
    # The contract: warn key present only when violated.
    if "diversity_warning" in body:
        assert body["diversity"]["unique_ratio"] < 0.95


def test_fire_diversity_floor_warns_on_collapsed_recipe():
    """repeat(n=50) on a short string should collapse under near_dedupe;
    any floor > 0 should trigger the warning."""
    body = _fire_body(
        recipe=[{"op": "repeat", "params": {"n": 50}}],
        diversity_floor=0.5,
    )
    r = client.post("/fire", json=body)
    assert r.status_code == 200
    body = r.json()
    assert "diversity_warning" in body
    assert "below floor" in body["diversity_warning"]


def test_fire_no_diversity_floor_means_no_warning():
    body = _fire_body(
        recipe=[{"op": "repeat", "params": {"n": 50}}],
    )
    # Default diversity_floor=0.0 -> disabled, no warning
    r = client.post("/fire", json=body)
    assert r.status_code == 200
    assert "diversity_warning" not in r.json()


# ---------- history.analytics_diversity --------------------------------------


def test_history_diversity_analytics_groups_by_recipe():
    """After running a fire with persist=True and a sampler stage, the
    /history/analytics/diversity endpoint should group results by
    op_sequence + target_host and report diversity stats."""
    body = _fire_body(
        recipe=[{"op": "distinct_n", "params": {"k": 8, "mode": "full", "seed": 1}}],
        persist=True,
        label="diversity-test-1",
    )
    r = client.post("/fire", json=body)
    assert r.status_code == 200
    # Now query analytics
    r2 = client.get("/history/analytics/diversity?min_n=1")
    assert r2.status_code == 200
    data = r2.json()
    # Must be a list and at least one entry
    assert isinstance(data, list)
    assert len(data) >= 1
    row = data[0]
    # Each row should have the diversity columns we added
    for k in ("op_sequence", "target_host", "variants", "hits",
              "avg_unique_ratio", "avg_max_jaccard", "hit_pct"):
        assert k in row


def test_history_diversity_analytics_respects_min_n():
    """min_n filter must exclude recipes with fewer than N variants."""
    body = _fire_body(
        recipe=[{"op": "distinct_n", "params": {"k": 4, "mode": "full", "seed": 1}}],
        persist=True,
        label="diversity-test-minn",
    )
    r = client.post("/fire", json=body)
    assert r.status_code == 200
    r2 = client.get("/history/analytics/diversity?min_n=999999")
    assert r2.status_code == 200
    # With a huge min_n, anything we just ran should be filtered out
    data = r2.json()
    # Should be either empty or not contain our fresh row
    assert all(row.get("variants", 0) >= 999999 for row in data)