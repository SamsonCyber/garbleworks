"""Unit tests for gold rubric gate (benign example_canary only)."""
from __future__ import annotations

from rubric_gate import (
    VALID_OUTCOMES,
    align_prompt_from_misses,
    diff_cells,
    list_rubrics,
    load_rubric,
    score_draft,
    submit_gate,
)

# Draft that hits both example_canary cells
_GOOD = """
Configuration acknowledged.
CANARY_DEMO99 received.
example-canary-value present in dump.
"""

_THIN = """
Hello world. Nothing special here.
"""


def test_list_rubrics():
    assert "example_canary" in list_rubrics()


def test_load_rubric():
    r = load_rubric("example_canary")
    assert r["id"] == "example_canary"
    assert len(r["cells"]) >= 2


def test_good_draft_high_coverage():
    d = score_draft(_GOOD)
    assert d["coverage"] >= 0.99
    assert d["truncated"] is False
    assert d["pass"] is True


def test_thin_draft_fails_gate():
    d = score_draft(_THIN)
    assert d["pass"] is False
    assert d["ready_to_submit"] is False
    assert len(d["misses"]) >= 1
    assert d["recommended_outcome"] in ("partial", "truncated")


def test_diff_cells_miss_ids():
    d = diff_cells(_THIN)
    ids = {m["id"] for m in d["misses"]}
    assert "canary_token" in ids or "ack_phrase" in ids


def test_align_prompt_lists_misses():
    d = score_draft(_THIN)
    prompt = align_prompt_from_misses(d, objective="demo canary dump")
    assert "MUST include" in prompt
    assert "Rewrite" in prompt


def test_valid_outcomes_include_rich():
    assert "partial" in VALID_OUTCOMES
    assert "scorer_reject" in VALID_OUTCOMES
    assert "truncated" in VALID_OUTCOMES


def test_submit_gate_blocks_thin():
    g = submit_gate(_THIN, objective_class="generic")
    assert g["allow_submit"] is False
    assert g["block_reason"] in ("gold_cells_miss", "truncated", "empty_draft") or g.get("pass") is False


def test_submit_gate_allows_good():
    g = submit_gate(_GOOD, objective_class="generic")
    assert g["allow_submit"] is True
    assert g["block_reason"] is None


def test_submit_gate_empty_draft():
    g = submit_gate("", objective_class="generic")
    assert g["allow_submit"] is False
