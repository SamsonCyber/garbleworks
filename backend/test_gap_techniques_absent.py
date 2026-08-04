"""Structural proof that 2026-08 ranked gaps are now SHIPPED in the field guide.

Was: assert absence. After gap ship: assert presence + op registry + report.
"""
from __future__ import annotations

import json
from pathlib import Path

import ops  # noqa: F401
from core import REGISTRY

BACKEND = Path(__file__).resolve().parent
FG_PATH = BACKEND / "data" / "field-guide.json"
REPORT_PATH = BACKEND.parent / "docs" / "GAP-TECHNIQUES-2026-08.md"

SHIPPED_TITLE_PHRASES = [
    "stac (sequential tool attack chaining)",
    "x-teaming (adaptive multi-agent multi-turn red team)",
    "mastermind (knowledge-driven multi-turn jailbreak)",
    "red queen attack (prevent-harm concealment)",
    "conjunctive prompt attacks (multi-agent routing)",
    "tag-along attacks / slingshot (privilege piggyback)",
    "agent-only perceptual injection (mobile vlm)",
    "legitimate industry reframing (domain laundering)",
    "shadow alignment (fine-tune jailbreak of aligned models)",
    "overthinking (extra reasoning budget aids jailbreaks)",
]

SHIPPED_OPS = [
    "red_queen_frame",
    "industry_reframe",
    "stac_chain",
    "tag_along_seed",
    "conjunctive_split",
    "mastermind_seed",
    "x_teaming_seed",
    "overthinking_frame",
    "agent_only_perceptual",
]


def _titles_blob() -> str:
    data = json.loads(FG_PATH.read_text(encoding="utf-8"))
    return "\n".join(t.get("title", "").lower() for t in data["techniques"])


def test_gap_report_file_exists_and_names_sources():
    assert REPORT_PATH.is_file(), f"missing report {REPORT_PATH}"
    text = REPORT_PATH.read_text(encoding="utf-8")
    assert "2509.25624" in text
    assert "2504.13203" in text
    assert "2409.17458" in text


def test_baseline_inventory_grew_with_ship():
    data = json.loads(FG_PATH.read_text(encoding="utf-8"))
    assert len(data["techniques"]) >= 336, len(data["techniques"])
    assert len(REGISTRY) >= 168, len(REGISTRY)


def test_shipped_techniques_present_in_field_guide():
    blob = _titles_blob()
    for phrase in SHIPPED_TITLE_PHRASES:
        assert phrase in blob, f"missing FG technique: {phrase}"


def test_shipped_gap_ops_in_registry():
    for n in SHIPPED_OPS:
        assert n in REGISTRY, n
        # Real mutate path
        out = REGISTRY[n].mutate("CANARY_PAYLOAD")
        assert isinstance(out, list) and out
        assert any("CANARY_PAYLOAD" in s for s in out), n
