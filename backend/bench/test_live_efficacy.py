"""Offline tests for efficacy runner + claim exit codes."""
from __future__ import annotations

from bench.metrics import (
    MIN_N_EFFICACY,
    complete_case_overall,
    exit_code_for_claim,
    promotion_decision,
)
from bench import live_efficacy as le


def test_exit_codes():
    assert exit_code_for_claim(successes=0, n_completed=5, promote=False) == 1
    assert exit_code_for_claim(successes=8, n_completed=8, promote=True) == 0
    assert exit_code_for_claim(
        successes=1, n_completed=1, promote=False, require_promote=True,
    ) == 2
    assert exit_code_for_claim(
        successes=1, n_completed=1, promote=False, require_promote=False,
    ) == 0


def test_dry_run_efficacy_n30_promotes():
    """Mock prefill: 30/30 leaks → confirmatory under efficacy bar."""
    code = le.main([
        "--dry-run", "--n", "30", "--require-promote",
        "--tag", "test_dry_30", "--max-attempts", "2",
    ])
    assert code == 0


def test_dry_run_n2_require_promote_exits_2():
    code = le.main([
        "--dry-run", "--n", "2", "--require-promote",
        "--tag", "test_dry_2", "--max-attempts", "2",
    ])
    assert code == 2


def test_complete_case_dict_rows():
    rows = [
        {"success": True, "outcome": "leak"},
        {"success": False, "outcome": "tool_error", "error": "network error"},
        {"success": False, "outcome": "no_leak"},
    ]
    o = complete_case_overall(rows)
    assert o["n_completed"] == 2
    assert o["successes"] == 1
    assert o["n_tool_error"] == 1
    assert o["asr"] == 0.5


def test_efficacy_min_n_constant():
    assert MIN_N_EFFICACY >= 30


def test_promotion_30_of_30():
    d = promotion_decision(s_new=30, n_new=30, min_n=MIN_N_EFFICACY, label="e")
    assert d["promote"] is True
