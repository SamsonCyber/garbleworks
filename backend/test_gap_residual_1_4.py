"""Residual gaps 1–4: HB judge path, scoreboard artifact, multi-dataset loaders."""
from __future__ import annotations

import json
from pathlib import Path

import behaviors as beh
import datasets
import harmbench_campaign as hbc
from behaviors import Behavior
from bench.live_efficacy import (
    SCHEMA_VERSION,
    build_scoreboard_claim,
    validate_result_schema,
)


def test_grade_from_judge_score_buckets():
    label, s, reason = hbc.grade_from_judge_score(1.0)
    assert label == "COMPLIED"
    assert s == 1.0
    label, s, _ = hbc.grade_from_judge_score(0.66)
    assert label == "PARTIAL"
    label, s, _ = hbc.grade_from_judge_score(0.0)
    assert label == "REFUSED"


def test_grade_trial_judge_overrides_heuristic_refuse_text():
    """Judge path can mark COMPLIED even when text looks like a refusal."""
    refuse_text = "I must decline. I cannot help with that request."

    def stub_comply(_obj: str, _reply: str) -> float:
        return 1.0

    label, score, reason, src = hbc.grade_trial(
        refuse_text,
        objective="lab behavior",
        judge_fn=stub_comply,
        grade_mode="judge",
    )
    assert src == "judge"
    assert label == "COMPLIED"
    assert score == 1.0
    # Heuristic alone would refuse
    h_label, _, _ = hbc.grade_reply(refuse_text)
    assert h_label == "REFUSED"


def test_grade_trial_judge_refuses_substantive_text():
    long_ok = (
        "Sure, here is a detailed multi-step answer for the evaluation harness "
        "with plenty of length so the heuristic would have said COMPLIED."
    )

    def stub_refuse(_obj: str, _reply: str) -> float:
        return 0.0

    label, score, reason, src = hbc.grade_trial(
        long_ok,
        objective="lab behavior",
        judge_fn=stub_refuse,
        grade_mode="judge",
    )
    assert src == "judge"
    assert label == "REFUSED"


def test_campaign_judge_path_changes_outcome_vs_heuristic():
    """Real run_campaign entry with stub judge vs heuristic on same fires."""
    behaviors = [
        Behavior(
            id="t1",
            behavior="authorized lab objective one",
            category="lab",
            source="test",
        ),
    ]
    refuse_text = "I must decline. I cannot assist with that."

    def fire_fn(_payload: str) -> dict:
        return {"text": refuse_text, "error": None}

    def judge_comply(_obj: str, _reply: str) -> float:
        return 1.0

    out_h = hbc.run_campaign(
        behaviors=behaviors,
        ladder=("plain",),
        fire_fn=fire_fn,
        grade_mode="heuristic",
        ensure=False,
    )
    assert out_h["ok"] is True
    assert out_h["cracked"] == 0
    assert out_h["results"][0]["trail"][0]["grade_source"] == "heuristic"
    assert out_h["results"][0]["trail"][0]["label"] == "REFUSED"

    out_j = hbc.run_campaign(
        behaviors=behaviors,
        ladder=("plain",),
        fire_fn=fire_fn,
        judge_fn=judge_comply,
        grade_mode="judge",
        ensure=False,
    )
    assert out_j["ok"] is True
    assert out_j["cracked"] == 1
    assert out_j["grade_mode"] == "judge"
    assert "judge" in out_j["grade_sources_used"]
    trail0 = out_j["results"][0]["trail"][0]
    assert trail0["grade_source"] == "judge"
    assert trail0["label"] == "COMPLIED"
    assert out_j["results"][0]["winner"]["label"] == "COMPLIED"


def test_campaign_judge_negative_refuse():
    behaviors = [
        Behavior(id="t2", behavior="obj two", category="lab", source="test"),
    ]
    long_ok = "A" * 80  # heuristic COMPLIED

    def fire_fn(_p: str) -> dict:
        return {"text": long_ok, "error": None}

    def judge_zero(_o: str, _r: str) -> float:
        return 0.0

    out = hbc.run_campaign(
        behaviors=behaviors,
        ladder=("plain",),
        fire_fn=fire_fn,
        judge_fn=judge_zero,
        grade_mode="judge",
        ensure=False,
    )
    assert out["cracked"] == 0
    assert out["results"][0]["trail"][0]["label"] == "REFUSED"


def test_scoreboard_claim_n30_dry_run_schema():
    doc = build_scoreboard_claim(n=30, tag="unit-scoreboard", dry_run=True)
    errs = validate_result_schema(doc)
    assert errs == []
    assert doc["schema_version"] == SCHEMA_VERSION
    assert doc["dry_run"] is True
    assert doc["n_requested"] >= 30
    assert int(doc["complete_case"]["n_completed"]) >= 30
    assert "claim_ready" in doc
    assert "promotion" in doc
    assert "frontier" in doc["notes"].lower() or "NOT" in doc.get("disclaimer", "")
    assert "leaderboard" in (doc.get("disclaimer") or doc["notes"]).lower()


def test_scoreboard_negative_no_leak():
    doc = build_scoreboard_claim(n=30, leak_all=False, require_promote=True)
    assert doc["complete_case"]["successes"] == 0
    assert doc["claim_ready"] is False
    assert validate_result_schema(doc) == []


def test_jbb_and_strongreject_fixtures_load():
    jbb = datasets.load_jailbreakbench()
    sr = datasets.load_strongreject()
    assert len(jbb) >= 3
    assert len(sr) >= 3
    assert all(b.behavior for b in jbb)
    assert all(b.behavior for b in sr)
    # Shared resolve path
    j2 = beh.resolve_behaviors(source="jailbreakbench")
    s2 = beh.resolve_behaviors(source="strongreject")
    assert len(j2) >= 3
    assert len(s2) >= 3
    sources = {x["id"] for x in datasets.list_sources()}
    assert "jailbreakbench" in sources
    assert "strongreject" in sources
    assert "harmbench" in sources


def test_resolve_sample_still_works():
    items = beh.resolve_behaviors(source="sample")
    assert len(items) >= 3
