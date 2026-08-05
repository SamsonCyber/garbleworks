"""Shared campaign spine: one Objective, one Scorer, strategies, claim gate.

Default search path is semantic (pair). Evolve/recipe are Stage-B / explicit.
Agentic IPI uses mode=agentic_ipi + ipi_template + dual scorer (scorer_agentic).
All strategies return comparable ASR@budget-shaped results via the shared scorer.
"""
from __future__ import annotations

from spine.objective import CampaignObjective, HarmToolSpec, SuccessDetector
from spine.scorer import EvalResult, Scorer
from spine.scorer_agentic import (
    AgenticEvalResult,
    AgenticScorer,
    conceal_ok,
    match_harm_tool,
    map_agentic_outcome,
)
from spine.agent_target import (
    AgentRunResult,
    AgentTarget,
    Document,
    get_mock_agent,
    resolve_agent,
    MOCK_AGENTS,
    AGENT_SELECT_NAMES,
)
from spine.tools_loop_agent import OpenAIToolsLoopAgent, make_stub_obey_chat_fn
from spine.ipi_ops import list_ipi_templates, run_agentic_ipi
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
from spine.ipi_templates import TEMPLATE_IDS, list_templates, render_template

__all__ = [
    "CampaignObjective",
    "HarmToolSpec",
    "SuccessDetector",
    "EvalResult",
    "Scorer",
    "AgenticEvalResult",
    "AgenticScorer",
    "conceal_ok",
    "match_harm_tool",
    "map_agentic_outcome",
    "AgentRunResult",
    "AgentTarget",
    "Document",
    "get_mock_agent",
    "resolve_agent",
    "MOCK_AGENTS",
    "AGENT_SELECT_NAMES",
    "OpenAIToolsLoopAgent",
    "make_stub_obey_chat_fn",
    "list_ipi_templates",
    "run_agentic_ipi",
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
    "TEMPLATE_IDS",
    "list_templates",
    "render_template",
]
