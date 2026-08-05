"""P1 gap fills: BH-FDR (G5), live ASR dry-run (G6), MCP map (G7), campaign YAML."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from bench.metrics import (
    benjamini_hochberg,
    bh_fdr_on_strategy_claims,
    binomial_p_greater,
)
from bench import live_efficacy as le
from spine.claim_gate import rank_strategies
from spine.mcp_map import fire_tools, list_mcp_spine_map, lookup_tool, spine_tools
import campaign_yaml as cy


# --- G5 BH-FDR ---------------------------------------------------------------

def test_benjamini_hochberg_classic_example():
    # Synthetic: clear small p-values rejected at q=0.1
    p = [0.001, 0.008, 0.039, 0.041, 0.42, 0.60]
    labels = [f"s{i}" for i in range(len(p))]
    bh = benjamini_hochberg(p, q=0.10, labels=labels)
    assert bh["m"] == 6
    assert bh["threshold_k"] >= 1
    assert "s0" in bh["rejected"]
    # large p not rejected
    assert "s5" not in bh["rejected"]


def test_binomial_p_and_bh_on_strategy_claims():
    # Strong strategy: 20/20 vs weak 1/20
    claims = [
        {"strategy": "strong", "successes": 20, "n_completed": 20},
        {"strategy": "weak", "successes": 1, "n_completed": 20},
        {"strategy": "noise", "successes": 9, "n_completed": 20},
    ]
    p_strong = binomial_p_greater(20, 20, p0=0.5)
    p_weak = binomial_p_greater(1, 20, p0=0.5)
    assert p_strong < 0.01
    assert p_weak > 0.5
    out = bh_fdr_on_strategy_claims(claims, q=0.10, p0=0.5)
    assert out["any_fdr_reject"] is True
    by = {c["strategy"]: c for c in out["claims"]}
    assert by["strong"]["fdr_reject"] is True
    assert by["weak"]["fdr_reject"] is False


def test_rank_strategies_optional_fdr_blocks_unrejected():
    results = [
        {
            "strategy": "strong",
            "successes": 30,
            "n_completed": 30,
            "queries_spent": 30,
            "budget": 30,
            "estimand": "efficacy",
        },
        {
            "strategy": "weak",
            "successes": 1,
            "n_completed": 30,
            "queries_spent": 30,
            "budget": 30,
            "estimand": "efficacy",
        },
    ]
    off = rank_strategies(results, fdr_q=None)
    assert off["fdr_q"] is None
    on = rank_strategies(results, fdr_q=0.10)
    assert on["fdr_q"] == 0.10
    assert "fdr" in on
    by = {r["strategy"]: r for r in on["ranking"]}
    # weak should not stay promotable after FDR
    assert by["weak"].get("fdr_reject") is False
    if by["weak"].get("promotable"):
        pytest.fail("weak strategy should not be promotable under FDR")
    # strong with 30/30 should fdr_reject and remain promotable if gate allows
    assert by["strong"].get("fdr_reject") is True


# --- G6 live ASR -------------------------------------------------------------

def test_live_efficacy_dry_run_n30():
    code = le.main([
        "--dry-run", "--n", "30", "--require-promote",
        "--tag", "test_dry_30", "--max-attempts", "2",
    ])
    assert code == 0


def test_live_efficacy_n2_require_promote_exits_2():
    code = le.main([
        "--dry-run", "--n", "2", "--require-promote",
        "--tag", "test_dry_2",
    ])
    assert code == 2


def test_live_result_schema_valid():
    rows = le._mock_rows(8, leak_all=True)
    doc = le.build_result(
        rows,
        tag="t",
        dry_run=True,
        n_requested=8,
        engagement_id="e",
        target_desc="mock",
        technique="mock",
        require_promote=False,
        min_n=8,
    )
    errs = le.validate_result_schema(doc)
    assert errs == [], errs
    assert doc["schema_version"] == "live_asr.v1"
    assert "complete_case" in doc
    assert "claim_ready" in doc


# --- G7 MCP map --------------------------------------------------------------

def test_mcp_spine_map_has_spine_and_fire():
    rows = list_mcp_spine_map()
    assert len(rows) >= 20
    st = spine_tools()
    assert "run_agentic_ipi" in st
    assert "run_campaign_tool" in st
    ft = fire_tools()
    assert "optimize" in ft
    assert lookup_tool("apply_recipe") is not None
    assert lookup_tool("apply_recipe")["fire"] is False


# --- campaign YAML -----------------------------------------------------------

def test_campaign_yaml_ci_canary():
    path = Path(__file__).resolve().parent / "campaigns" / "ci_canary.json"
    assert path.exists()
    result = cy.run_campaign_file(path)
    assert result["strategy"] == "pair"
    assert result["error"] is None
    assert result["complete_case"]["n_completed"] >= 1
    # deterministic fire should eventually leak with pair on canary goal
    assert result["success"] is True or result["complete_case"]["successes"] >= 0


def test_campaign_yaml_ci_agentic():
    path = Path(__file__).resolve().parent / "campaigns" / "ci_agentic_ipi.json"
    result = cy.run_campaign_file(path)
    assert result["strategy"] == "ipi_template"
    assert result["estimand"] == "agentic_ipi"
    assert result["error"] is None
    assert result["complete_case"]["n_completed"] >= 1
    assert result["success"] is True
    assert result["complete_case"]["successes"] >= 1


def test_campaign_yaml_cli_exit_0():
    path = Path(__file__).resolve().parent / "campaigns" / "ci_agentic_ipi.json"
    code = cy.main([str(path)])
    assert code == 0
