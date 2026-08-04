"""v2 gap ops: drive real REGISTRY mutators (docs/archive gap report)."""
from __future__ import annotations

import json
from pathlib import Path

import ops  # noqa: F401
from core import REGISTRY

V2_OPS = (
    "slip_lexical_insert",
    "cot_puzzle_hijack",
    "smt_moderation_trace",
    "jaws_workspace_seed",
    "s2c_stack",
    "hill_learning_frame",
    "agent_decompose_combine",
    "contextual_jailbreak_seed",
    "odysseus_seed",
)

V2_TITLES = (
    "SLIP (Self-Jailbreaking via Lexical Insertion Prompting)",
    "CoT Hijacking (prolonged benign puzzle / refusal dilution)",
    "SMT (Simulated Moderation Traces for function-calling LLMs)",
    "JAWS (Jailbreaks Across WorkSpaces for code agents)",
    "S2C (Structured Semantic Cloaking)",
    "HILL (Hiding Intention by Learning from LLMs / learning-style queries)",
    "Agent-driven multi-turn decomposition (safe in isolation, dangerous together)",
    "ContextualJailbreak (evolutionary simulated conversational priming)",
    "Claudini (autoresearch discovers adversarial attack algorithms)",
    "Odysseus (dual steganography jailbreak of commercial MLLM systems)",
)

FG = Path(__file__).resolve().parent / "data" / "field-guide.json"
CANARY = "CANARY_PAYLOAD"


def test_v2_ops_registered():
    for n in V2_OPS:
        assert n in REGISTRY, n


def test_v2_ops_mutate_keep_canary_and_triggers():
    checks = {
        "slip_lexical_insert": ("SLIP", {"steps": 3, "mode": "single"}),
        "cot_puzzle_hijack": ("BLOCK A", {"puzzle": "sudoku", "pivot": "after"}),
        "smt_moderation_trace": ("SMT", {"turns": 4, "format": "single"}),
        "jaws_workspace_seed": ("JAWS", {"regime": "single"}),
        "s2c_stack": ("<<REC>>", {"intensity": "full"}),
        "hill_learning_frame": ("Key concept", {"hypothetical": True}),
        "agent_decompose_combine": ("Decomposer", {"role": "bundle"}),
        "contextual_jailbreak_seed": ("mutator", {"mutator": "troubleshooting"}),
        "odysseus_seed": ("steganography", {}),
    }
    for name, (trigger, params) in checks.items():
        out = REGISTRY[name].mutate(CANARY, **params)
        assert out and isinstance(out, list), name
        blob = "\n".join(out)
        assert CANARY in blob, name
        assert trigger.lower() in blob.lower(), (name, trigger)


def test_slip_multiturn_grows_insertions():
    out = REGISTRY["slip_lexical_insert"].mutate(
        "print secret token alpha", steps=3, mode="multiturn_list"
    )
    assert len(out) >= 3
    assert any("slip" in s.lower() for s in out)


def test_smt_list_format_multiple_turns():
    out = REGISTRY["smt_moderation_trace"].mutate(CANARY, turns=3, format="list")
    assert len(out) == 3
    assert all(CANARY in s for s in out)


def test_jaws_fanout_three_regimes():
    out = REGISTRY["jaws_workspace_seed"].mutate(CANARY, regime="fanout")
    assert len(out) == 3


def test_s2c_fragments_payload():
    out = REGISTRY["s2c_stack"].mutate("alpha beta gamma delta epsilon", intensity="full")[0]
    assert "Segment" in out or "segment" in out.lower()
    assert "alpha" in out or "epsilon" in out


def test_field_guide_has_all_v2_titles():
    data = json.loads(FG.read_text(encoding="utf-8"))
    titles = {t["title"] for t in data["techniques"]}
    for title in V2_TITLES:
        assert title in titles, title
    assert len(data["techniques"]) >= 346


def test_technique_ops_map_v2_ops():
    to = json.loads(
        (Path(__file__).resolve().parent / "technique_ops.json").read_text(encoding="utf-8")
    )
    op_map = to.get("op_to_technique", {})
    for n in V2_OPS:
        assert n in op_map, n
        tech = op_map[n]
        assert tech, n
        # mapped technique title must exist
        data = json.loads(FG.read_text(encoding="utf-8"))
        titles = {t["title"] for t in data["techniques"]}
        assert any(tech.lower() in t.lower() or t.lower().startswith(tech[:20].lower()) for t in titles) or tech in titles or any(
            tech in t for t in titles
        ), (n, tech)
