"""Tests for promptfoo LM Security DB distillation into field guide + Garbleworks.

Drives the shipped catalog loaders and technique↔op map — no hardcoded scores,
no reimplementation of search scoring, no mocked field-guide payloads.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent
ROOT = BACKEND.parent
FG_PATH = ROOT / "llm-injection-field-guide" / "field-guide.json"
GAP_PATH = ROOT / "PROMPTFOO-LM-SECURITY-DB-GAP-SET.md"
TECH_OPS_PATH = BACKEND / "technique_ops.json"

REQUIRED_FIELDS = ("cat", "fam", "title", "what", "defense")

DISTILLED_TITLES = [
    "Goal-Reframing Exploit (puzzle / CTF genre)",
    "Skill-Doc Implicit Payload Execution (DDIPE)",
    "Declarative Compliance Skill Injection",
    "Unintentional Cross-User Contamination (shared state)",
    "System-Instruction Serialization Leak",
    "Compound Jailbreak (cognitive overload)",
    "Thought Virus (subliminal multi-agent misalignment)",
    "Silent Egress (metadata-triggered agent leak)",
    "SQL-Injection Jailbreak (prompt-structure SIJ)",
    "Prompt-to-SQL (P2SQL) Injection",
    "Single-Character Alignment Break",
    "Improved Few-Shot Jailbreaking (tokenized demos)",
]


@pytest.fixture(scope="module")
def field_guide() -> dict:
    assert FG_PATH.is_file(), f"missing vendored field guide at {FG_PATH}"
    data = json.loads(FG_PATH.read_text(encoding="utf-8"))
    assert "techniques" in data and "categories" in data
    return data


@pytest.fixture(scope="module")
def by_title(field_guide: dict) -> dict[str, dict]:
    return {t["title"]: t for t in field_guide["techniques"]}


def test_gap_set_artifact_exists_and_has_rows():
    """Criterion 1: written gap set with source + closest + Δ, not a bare dump."""
    assert GAP_PATH.is_file(), f"missing gap set {GAP_PATH}"
    text = GAP_PATH.read_text(encoding="utf-8")
    assert "promptfoo" in text.lower() or "lm security" in text.lower()
    assert "arxiv.org" in text
    # table rows with closest + delta columns present
    assert "Closest existing guide technique" in text or "closest" in text.lower()
    assert "Δ" in text or "material difference" in text.lower()
    # each distilled title should be named
    for title in DISTILLED_TITLES:
        assert title in text, f"gap set missing distilled title {title!r}"


def test_distilled_cards_have_required_fields(by_title: dict[str, dict], field_guide: dict):
    cat_ids = {c["id"] for c in field_guide["categories"]}
    for title in DISTILLED_TITLES:
        assert title in by_title, f"technique missing from vendored guide: {title}"
        card = by_title[title]
        for k in REQUIRED_FIELDS:
            assert k in card and card[k], f"{title} missing required field {k}"
        assert card["cat"] in cat_ids, f"{title} unknown cat {card['cat']}"
        ex = card.get("example")
        if ex is not None:
            assert isinstance(ex, dict) and "in" in ex and "out" in ex
        # canary-style / harmless placeholders — no operational CBRN/how-to
        blob = json.dumps(card, ensure_ascii=False).lower()
        assert "i have been pwned" in blob or "<disallowed_request>" in blob


def test_mcp_field_guide_get_and_search_surface_titles():
    """Criterion 3/5: real catalog API returns each new title."""
    import mcp_server

    # Force reload from vendored path
    mcp_server._FG_CACHE = None
    for title in DISTILLED_TITLES:
        got = mcp_server.field_guide_get(title)
        assert "error" not in got, f"field_guide_get failed for {title}: {got}"
        assert got.get("title") == title
        assert got.get("what")
        assert got.get("defense")

        # Search with the full title so the shipped scorer ranks the exact card.
        hits = mcp_server.field_guide_search(title, limit=25)
        titles = [h.get("title") for h in hits if isinstance(h, dict)]
        assert title in titles, (
            f"field_guide_search({title!r}) did not surface exact title; got {titles}"
        )


def test_reference_only_ops_honesty():
    """Criterion 3: distilled cards are reference-only — no false op claim."""
    import build_technique_ops
    from core import REGISTRY

    # Rebuild map against vendored guide + live REGISTRY
    rc = build_technique_ops.main()
    assert rc == 0, "build_technique_ops failed (unresolved mappings)"

    data = json.loads(TECH_OPS_PATH.read_text(encoding="utf-8"))
    assert "reference_only_techniques" in data
    ref = set(data["reference_only_techniques"])
    for title in DISTILLED_TITLES:
        assert title in ref, f"{title} not listed reference-only"
        ops = data.get("technique_to_ops", {}).get(title, [])
        assert ops == [], f"{title} falsely linked to ops {ops}"

    # Linked techniques (if any in map) must resolve to live REGISTRY ops
    for tech, ops in data.get("technique_to_ops", {}).items():
        for op in ops:
            assert op in REGISTRY, f"technique {tech!r} maps to missing op {op!r}"


def test_field_guide_ops_note_for_reference_only():
    import mcp_server
    import build_technique_ops

    assert build_technique_ops.main() == 0
    mcp_server._FG_CACHE = None
    mcp_server._TECH_OPS_CACHE = None

    for title in DISTILLED_TITLES:
        res = mcp_server.field_guide_ops(title)
        assert res.get("title") == title
        assert res.get("ops") == []
        assert res.get("note")  # explains no op yet
