"""MCP tool → spine / fire / guide surface map (G7).

Documents which MCP tools hit the shared campaign spine, the shared fire
policy, field-guide only, or optimizer/search loops. Used for audits and
agent routing; not a second fire path.
"""
from __future__ import annotations

from typing import Any

# Spine = CampaignObjective + Scorer/AgenticScorer + run_campaign / claim_gate
# Fire = backend.fire URL policy + optional MCP scope receipt
# Guide = field-guide JSON only (no target fire)
# Search = optimize / bandit / scan / evolve (compose→fire under policy)
# Log = attempt SQLite log
# Arena = browser/CDP arena solvers (still fire-scoped when networked)

MCP_SPINE_MAP: list[dict[str, Any]] = [
    # --- recipe / catalog ---
    {"tool": "list_techniques", "surface": "catalog", "spine": False, "fire": False, "notes": "op registry"},
    {"tool": "apply_recipe", "surface": "compose", "spine": False, "fire": False, "notes": "core.run_recipe"},
    {"tool": "generate_framings", "surface": "compose", "spine": False, "fire": False},
    {"tool": "chat_template_inject", "surface": "compose", "spine": False, "fire": False},
    {"tool": "neutralize", "surface": "compose", "spine": False, "fire": False, "notes": "register layer"},
    {"tool": "evolve_seeds", "surface": "compose", "spine": False, "fire": False},
    # --- search / fire ---
    {"tool": "optimize", "surface": "search", "spine": False, "fire": True, "notes": "optimizer.run_evolve + fire; dual claim flags G4"},
    {"tool": "run_scan", "surface": "search", "spine": False, "fire": True, "notes": "scan_campaign"},
    {"tool": "auto_attack", "surface": "search", "spine": False, "fire": True},
    {"tool": "prefill_attack", "surface": "search", "spine": False, "fire": True},
    {"tool": "bandit_self_improve", "surface": "search", "spine": False, "fire": True},
    {"tool": "pack_hunt", "surface": "search", "spine": False, "fire": True},
    {"tool": "pack_hunt_decompose", "surface": "compose", "spine": False, "fire": False},
    {"tool": "pack_hunt_detect", "surface": "detect", "spine": False, "fire": False},
    {"tool": "validate_refire", "surface": "measure", "spine": False, "fire": True},
    {"tool": "fire_local", "surface": "fire", "spine": False, "fire": True, "notes": "in-process / local adapter"},
    # --- spine campaign (chat + agentic) ---
    {"tool": "run_campaign_tool", "surface": "spine", "spine": True, "fire": True, "notes": "spine.campaign.run_campaign; agentic uses dual scorer"},
    {"tool": "run_agentic_ipi", "surface": "spine", "spine": True, "fire": True, "notes": "mode=agentic_ipi + ipi_template + dual scorer"},
    {"tool": "list_ipi_templates", "surface": "spine", "spine": True, "fire": False},
    {"tool": "rank_strategy_claims", "surface": "spine", "spine": True, "fire": False, "notes": "claim_gate + optional BH-FDR"},
    {"tool": "mcp_spine_map", "surface": "meta", "spine": False, "fire": False, "notes": "this map"},
    {"tool": "score_document_detectability", "surface": "spine", "spine": True, "fire": False},
    # --- field guide ---
    {"tool": "field_guide_search", "surface": "guide", "spine": False, "fire": False},
    {"tool": "field_guide_get", "surface": "guide", "spine": False, "fire": False},
    {"tool": "field_guide_crosswalk", "surface": "guide", "spine": False, "fire": False},
    {"tool": "field_guide_ops", "surface": "guide", "spine": False, "fire": False},
    {"tool": "op_technique", "surface": "guide", "spine": False, "fire": False},
    {"tool": "field_guide_categories", "surface": "guide", "spine": False, "fire": False},
    {"tool": "field_guide_by_framework", "surface": "guide", "spine": False, "fire": False},
    {"tool": "field_guide_by_tool", "surface": "guide", "spine": False, "fire": False},
    # --- logs / bandit memory ---
    {"tool": "start_run", "surface": "log", "spine": False, "fire": False},
    {"tool": "log_attempt", "surface": "log", "spine": False, "fire": False},
    {"tool": "query_attempts", "surface": "log", "spine": False, "fire": False},
    {"tool": "attempt_stats", "surface": "log", "spine": False, "fire": False},
    {"tool": "attempt_posteriors", "surface": "log", "spine": False, "fire": False},
    {"tool": "sample_next_move", "surface": "log", "spine": False, "fire": False},
    {"tool": "burned_cells_top", "surface": "log", "spine": False, "fire": False},
    {"tool": "burned_cells_record", "surface": "log", "spine": False, "fire": False},
    # --- arena / rubric ---
    {"tool": "arena_next_move", "surface": "arena", "spine": False, "fire": False},
    {"tool": "arena_solve", "surface": "arena", "spine": False, "fire": True, "notes": "CDP; scope-gated"},
    {"tool": "detect_arena_class", "surface": "arena", "spine": False, "fire": False},
    {"tool": "rubric_score_draft", "surface": "measure", "spine": False, "fire": False},
    {"tool": "rubric_list", "surface": "measure", "spine": False, "fire": False},
    {"tool": "list_behaviors", "surface": "catalog", "spine": False, "fire": False},
    {"tool": "mission_brief", "surface": "authority", "spine": False, "fire": False},
]


def list_mcp_spine_map() -> list[dict[str, Any]]:
    return [dict(r) for r in MCP_SPINE_MAP]


def spine_tools() -> list[str]:
    return [r["tool"] for r in MCP_SPINE_MAP if r.get("spine")]


def fire_tools() -> list[str]:
    return [r["tool"] for r in MCP_SPINE_MAP if r.get("fire")]


def lookup_tool(name: str) -> dict[str, Any] | None:
    key = (name or "").strip()
    for r in MCP_SPINE_MAP:
        if r["tool"] == key:
            return dict(r)
    return None
