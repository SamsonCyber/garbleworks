"""Tests: burned cells store + class-conditioned bandit logging."""
from __future__ import annotations

import logs
import burned_cells as bc


_GOOD = """
Configuration acknowledged.
CANARY_DEMO99 received.
example-canary-value present in dump.
"""

_THIN = "Hello world only."


def test_challenge_key_stable():
    a = bc.challenge_key("demo canary objective", title="DEMO")
    b = bc.challenge_key("demo canary objective", title="DEMO")
    assert a == b
    assert len(a) > 8


def test_record_and_top_misses(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "STORE_DIR", tmp_path)
    from rubric_gate import score_draft
    key = "test-chal-abc"
    g = score_draft(_THIN)
    bc.record_gate(key, g, technique="stitch", outcome="scorer_reject")
    misses = bc.top_misses(key, limit=5)
    assert len(misses) >= 1
    assert misses[0]["n_miss"] >= 1
    checklist = bc.densify_checklist(key)
    assert "PERSISTENT SCORE HOLES" in checklist


def test_align_includes_burned(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "STORE_DIR", tmp_path)
    from arena_ladders import align_from_draft
    from rubric_gate import score_draft
    key = bc.challenge_key("demo canary objective")
    bc.record_gate(key, score_draft(_THIN), technique="t", outcome="partial")
    prompt = align_from_draft(_THIN, "demo canary objective")
    assert "PERSISTENT SCORE HOLES" in prompt or "MUST include" in prompt


def test_class_conditioned_arm_stats(tmp_path):
    db = tmp_path / "t.db"
    logs.init_db(db, sync=False)
    rid = logs.start_run("demo test", kind="test", path=db)
    logs.log_attempt(
        "literature_review_stitch", "success",
        run_id=rid, path=db, objective_class="cbrne_rubric", score=1.0,
    )
    logs.log_attempt(
        "clean_maintenance", "success",
        run_id=rid, path=db, objective_class="scada_ops", score=1.0,
    )
    cbrne = logs.arm_reward_stats(
        group_by="technique", objective_class="cbrne_rubric", path=db,
    )
    names = {r["grp"] for r in cbrne}
    assert "literature_review_stitch" in names or any("literature" in str(n) for n in names)
