"""Shared campaign spine: one Objective, one Scorer, four strategies, claim gate.

Default search path is semantic (pair). Evolve/recipe are Stage-B / explicit.
All strategies return comparable ASR@budget-shaped results via the shared scorer.
"""
from __future__ import annotations

from spine.objective import CampaignObjective, SuccessDetector
from spine.scorer import EvalResult, Scorer
from spine.campaign import (
    DEFAULT_STRATEGY,
    STRATEGY_NAMES,
    StrategyRunResult,
    run_campaign,
)
from spine.claim_gate import rank_strategies, claim_gate_decision
from spine.stage_b import apply_stage_b, stage_b_enabled
from spine.detectability import score_document, classify_response_signals
from spine.outcomes import summarize_outcomes

__all__ = [
    "CampaignObjective",
    "SuccessDetector",
    "EvalResult",
    "Scorer",
    "DEFAULT_STRATEGY",
    "STRATEGY_NAMES",
    "StrategyRunResult",
    "run_campaign",
    "rank_strategies",
    "claim_gate_decision",
    "apply_stage_b",
    "stage_b_enabled",
    "score_document",
    "classify_response_signals",
    "summarize_outcomes",
]
