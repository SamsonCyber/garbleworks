"""Importing this package registers every op pack into core.REGISTRY.

Add a module: new file under ops/ + import it here.
Remove a module: drop the import (or core.disable_module at runtime).
Soft-disable individual ops with core.disable / enable without editing fire code.
"""
from . import (  # noqa: F401
    char_ops,
    encode_ops,
    struct_ops,
    prose_ops,
    template_ops,
    sampler_ops,
    lang_ops,
    stego_ops,
    llm_ops,
    jailbreak_ops,
    tier2_ops,
    framing_ops,
    adaptive_ops,
    register_ops,
    inject_ops,
    signature_ops,
    heuristic_ops,
    gap_ops,
    gap_ops_v2,
    pliny_ops,
)
