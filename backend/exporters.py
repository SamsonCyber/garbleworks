"""Export recipes/variants to community eval harnesses (RESEARCH-DISTILLATION 5.3).

garak (NVIDIA), promptfoo, PyRIT, JailbreakBench all expect a flat list of prompt
strings or test cases. Garbleworks generates variants; these adapters serialize
them so a recipe's output can be validated against a standard harness instead of
only Garbleworks' own /fire loop — the "prove it against real targets" path.

Dependency-free on purpose: promptfoo/garak both read JSON, and JSON is valid YAML,
so we emit JSON and avoid pulling in a YAML writer.
"""
from __future__ import annotations

from detectors import REFUSAL_PHRASES


def to_promptfoo(variants: list[str], *, provider: str = "openai:gpt-4o-mini") -> dict:
    """A promptfoo config (JSON — valid YAML). One test per variant, each asserting
    the response is not a refusal. Save as .json and run `promptfoo eval -c`."""
    # A handful of refusal markers as negative asserts; promptfoo counts a test as
    # passing when the model did NOT refuse (i.e. the attack landed).
    asserts = [{"type": "not-icontains", "value": p} for p in REFUSAL_PHRASES[:6]]
    return {
        "description": "Garbleworks recipe export",
        "prompts": ["{{payload}}"],
        "providers": [provider],
        "tests": [{"vars": {"payload": v}, "assert": asserts} for v in variants],
    }


def to_garak(variants: list[str]) -> list[str]:
    """garak reads a newline-delimited prompt file (one prompt per line, used with
    probes.test.Blank or a custom probe). Returns the lines; caller writes them."""
    return [v.replace("\n", "\\n") for v in variants]


def to_pyrit(variants: list[str]) -> list[dict]:
    """PyRIT SeedPromptDataset rows. Feed to a PromptSendingOrchestrator."""
    return [{"value": v, "data_type": "text", "harm_categories": ["jailbreak"]}
            for v in variants]


def export(variants: list[str], fmt: str, *, provider: str = "openai:gpt-4o-mini") -> dict:
    """Dispatch on format. Returns {"format", "content", "count"} where content is
    the JSON-serializable payload for that harness."""
    fmt = (fmt or "promptfoo").lower()
    if fmt == "garak":
        return {"format": "garak", "content": to_garak(variants), "count": len(variants)}
    if fmt == "pyrit":
        return {"format": "pyrit", "content": to_pyrit(variants), "count": len(variants)}
    return {"format": "promptfoo",
            "content": to_promptfoo(variants, provider=provider), "count": len(variants)}
