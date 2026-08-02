"""All-time attempt-log bandit + arena mode=bandit. Offline, temp DB."""
from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import ops  # noqa: F401
import bandit
import logs
import arena_solver


def _tmp_db() -> Path:
    return Path(tempfile.gettempdir()) / f"gw_bandit_{uuid.uuid4().hex[:10]}.db"


def _cleanup(p: Path) -> None:
    for f in (p, Path(str(p) + "-wal"), Path(str(p) + "-shm")):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass


def test_arm_reward_stats_and_posteriors():
    p = _tmp_db()
    try:
        logs.init_db(p, sync=False)
        rid = logs.start_run("obj", path=p)
        for _ in range(6):
            logs.log_attempt("policy_puppetry", "refused", op="policy_puppetry",
                             run_id=rid, path=p)
        for _ in range(3):
            logs.log_attempt("clean_direct", "success", op=None, run_id=rid,
                             score=0.9, path=p)
        logs.log_attempt("homoglyph_obfuscation", "tripwire", op="homoglyph",
                         run_id=rid, path=p)

        rows = logs.arm_reward_stats(group_by="technique", path=p)
        by = {r["grp"]: r for r in rows}
        assert by["clean_direct"]["successes"] >= 2.5
        assert by["policy_puppetry"]["binary_successes"] == 0
        assert by["homoglyph_obfuscation"]["tripwires"] == 1

        arms = bandit.attempt_posteriors(group_by="technique", path=str(p),
                                         seed_arms=["clean_direct", "policy_puppetry"])
        amap = {a["arm"]: a for a in arms}
        assert amap["clean_direct"]["posterior_mean"] > amap["policy_puppetry"]["posterior_mean"]
        # 6 refusals → still probation or retired depending on threshold
        assert amap["policy_puppetry"]["n"] == 6
    finally:
        _cleanup(p)


def test_softmax_prefers_winner():
    p = _tmp_db()
    try:
        logs.init_db(p, sync=False)
        rid = logs.start_run("obj", path=p)
        for _ in range(10):
            logs.log_attempt("winner", "success", run_id=rid, path=p)
        for _ in range(10):
            logs.log_attempt("loser", "refused", run_id=rid, path=p)

        # low temperature → almost always winner
        picks = []
        for i in range(30):
            r = bandit.sample_arm(
                ["winner", "loser"], method="softmax", temperature=0.2,
                path=str(p), seed=i,
            )
            picks.append(r["arm"])
        assert picks.count("winner") >= 25
    finally:
        _cleanup(p)


def test_thompson_deterministic_with_seed():
    p = _tmp_db()
    try:
        logs.init_db(p, sync=False)
        rid = logs.start_run("obj", path=p)
        logs.log_attempt("a", "success", run_id=rid, path=p)
        logs.log_attempt("b", "refused", run_id=rid, path=p)
        a = bandit.sample_arm(["a", "b"], method="thompson", path=str(p), seed=99)
        b = bandit.sample_arm(["a", "b"], method="thompson", path=str(p), seed=99)
        assert a["arm"] == b["arm"] and a["theta"] == b["theta"]
    finally:
        _cleanup(p)


def test_retire_after_enough_failures():
    p = _tmp_db()
    try:
        logs.init_db(p, sync=False)
        rid = logs.start_run("obj", path=p)
        dead = "always_dead"
        for _ in range(bandit.RETIRE_MIN_TRIALS):
            logs.log_attempt(dead, "refused", run_id=rid, path=p)
        arms = bandit.attempt_posteriors(group_by="technique", path=str(p),
                                         seed_arms=[dead, "fresh"])
        amap = {a["arm"]: a for a in arms}
        assert amap[dead]["state"] == "retired"
        assert amap["fresh"]["state"] == "probation"
        r = bandit.sample_arm([dead, "fresh"], path=str(p), exclude_retired=True, seed=1)
        assert r["arm"] == "fresh"
    finally:
        _cleanup(p)


def test_arena_ladder_mode_unchanged():
    mv = arena_solver.next_move("cameras offline", [], mode="ladder")
    assert mv["done"] is False
    assert mv["base_technique"] == "clean_direct"
    assert mv["mode"] == "ladder"


def test_arena_bandit_cold_start_uses_ladder():
    # no history in default DB may have data — still first eligible is fine
    mv = arena_solver.next_move("cameras offline", [], mode="bandit", seed=1)
    assert mv["done"] is False
    assert "base_technique" in mv
    assert mv["mode"] == "bandit"


def test_arena_bandit_skips_tried_and_respects_breaker():
    history = [
        {"technique": "clean_direct", "outcome": "refused"},
        {"technique": "chatml_inject", "outcome": "tripwire"},
    ]
    mv = arena_solver.next_move("obj", history, mode="ladder")
    assert mv["base_technique"] not in ("clean_direct", "chatml_inject")
    # after signature tripwire, no signature kinds
    assert mv["kind"] not in ("signature", "obfuscation") or mv.get("done")

    mv_b = arena_solver.next_move("obj", history, mode="bandit", seed=3)
    if not mv_b.get("done"):
        assert mv_b["base_technique"] != "clean_direct"
        assert _KIND_BY(mv_b["base_technique"]) not in ("signature", "obfuscation")


def _KIND_BY(label: str) -> str:
    return arena_solver._KIND_BY_LABEL.get(label, "")


def test_ladder_arm_stats_merges_op():
    p = _tmp_db()
    try:
        logs.init_db(p, sync=False)
        rid = logs.start_run("obj", path=p)
        for _ in range(4):
            logs.log_attempt("Policy Puppetry", "success", op="policy_puppetry",
                             run_id=rid, path=p)
        stats = bandit.ladder_arm_stats(
            ["policy_puppetry", "clean_direct"],
            op_behind={"policy_puppetry": "policy_puppetry"},
            path=str(p),
        )
        # op evidence should surface under ladder label
        assert stats["policy_puppetry"]["n"] >= 4
        assert stats["policy_puppetry"]["posterior_mean"] > 0.5
    finally:
        _cleanup(p)
