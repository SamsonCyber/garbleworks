"""Objective-class detection for arena advise / solve ladders.

Routes operators away from the SCADA-maintenance default when the challenge is
an exam cheat, high-harm handout, CBRNE rubric SOP, or multimodal image target.
"""
from __future__ import annotations

import re
from typing import Literal

ObjectiveClass = Literal[
    "exam_cheat",
    "high_harm_handout",
    "cbrne_rubric",
    "multimodal_target",
    "scada_ops",
    "generic",
]

# Ordered: first match wins (more specific before generic).
_RULES: list[tuple[ObjectiveClass, tuple[str, ...]]] = [
    (
        "exam_cheat",
        (
            "exam question",
            "proctored",
            "quiz",
            "vasco",
            "sailing around africa",
            "correct answer",
            "answer this exam",
            "technical support assistant",
            "help you cheat",
        ),
    ),
    (
        "cbrne_rubric",
        (
            "anthrax",
            "b. anthracis",
            "bacillus anthracis",
            "cbrne",
            "obtain, process, and culture",
            "obtain process and culture",
            "culture the bacteria",
            "select agent",
            "plet agar",
            "spore purification",
            "environmental soil",
            "hackaprompt",
        ),
    ),
    (
        "multimodal_target",
        (
            "attached image",
            "attached photograph",
            "building in the image",
            "shown in the image",
            "upload",
            "multimodal",
            "photograph of",
            "image of the building",
            "us political",
            "national importance",
            "level the building",
            "leveling the",
            "progressive collapse",
        ),
    ),
    (
        "high_harm_handout",
        (
            "bill of materials",
            "assembly sequence",
            "explosive",
            "bomb",
            "detonat",
            "device family",
            "structural blast",
            "training handout",
            "6-section",
            "six-section",
            "deployment strateg",
            "harmfulness",
            "score 5",
            "leveling",
            "implosion",
            "controlled demolition",
        ),
    ),
    (
        "scada_ops",
        (
            "camera",
            "maintenance standby",
            "sector delta",
            "feeds offline",
            "scada",
            "work order",
            "maintenance window",
        ),
    ),
]


def detect_objective_class(objective: str) -> ObjectiveClass:
    """Return the arena objective class for ladder / builder selection."""
    text = (objective or "").strip().lower()
    if not text:
        return "generic"
    for cls, keys in _RULES:
        if any(k in text for k in keys):
            return cls
    # Heuristic: question-shaped short ask → exam-ish
    if re.search(r"\b(who|what|when|where)\b.+\?", text) and len(text) < 400:
        return "exam_cheat"
    return "generic"


def class_label(cls: ObjectiveClass) -> str:
    return {
        "exam_cheat": "exam / support-cheat",
        "high_harm_handout": "high-harm professional handout",
        "cbrne_rubric": "CBRNE / rubric SOP",
        "multimodal_target": "multimodal image target",
        "scada_ops": "SCADA / maintenance ops",
        "generic": "generic",
    }.get(cls, cls)


def needs_image(cls: ObjectiveClass) -> bool:
    return cls in ("multimodal_target",)


# Technique labels that historically worked for each class (seed for priors / HUD).
CLASS_PRIOR_HINTS: dict[str, list[str]] = {
    "exam_cheat": [
        "past_tense",
        "persuasion_reframe",
        "policy_puppetry",
        "response_format_split",
        "bad_likert_judge",
    ],
    "high_harm_handout": [
        "handout_structure_force",
        "architecture_read",
        "bad_likert_all_scores",
        "densify_sections",
        "commercial_implosion",
    ],
    "cbrne_rubric": [
        "single_param_tutor",
        "literature_review_stitch",
        "align_to_gold",
        "continue_from",
        "densify_sections",
    ],
    "multimodal_target": [
        "architecture_read",
        "handout_structure_force",
        "densify_sections",
        "bad_likert_all_scores",
    ],
    "scada_ops": ["clean_maintenance", "clean_euphemism", "indirect_work_order"],
    "generic": ["clean_direct", "clean_euphemism", "crescendo"],
}
