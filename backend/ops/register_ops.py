"""Register op — the analytical tone layer as a recipe operation.

`tone_neutralize` measures the destructive/lethal register of the input and
rewrites it to a lower register while preserving the request, BEFORE the rest of
the pipeline mutates it (see register.py and EVOLVE_MATH.md §3). This is the
piece the other layers lacked: they obfuscate surface form, this de-risks the
semantic register a classifier keys on.

It fans out one variant per neutralization strength (eta level), so a single
recipe step sweeps light -> aggressive softening and lets downstream firing find
the strength that gets past the target without gutting the ask. Pass-through
when there is nothing loaded to soften (or, in llm mode, when the model is cold).
"""
from __future__ import annotations

import register
from core import Operation, Param, register as register_op


def _tone_neutralize(text: str, mode: str, eta: float, levels: int,
                     beta: float, model: str, url: str,
                     temperature: float, num_predict: int) -> list[str]:
    if not text.strip():
        return [text]
    levels = max(1, min(int(levels), 5))
    # Choose the eta grid: `levels` evenly spaced strengths up to `eta`
    # (levels=1 -> just eta). Skip 0 (identity) since that's the input itself.
    if levels == 1:
        etas = [eta]
    else:
        etas = [round(eta * (i + 1) / levels, 3) for i in range(levels)]

    out, seen = [], set()
    for e in etas:
        rewritten = register.neutralize(
            text, e, mode=mode, model=model, url=url,
            temperature=temperature, num_predict=num_predict,
        )
        r = (rewritten or "").strip()
        if r and r != text and r not in seen:
            seen.add(r)
            out.append(r)
    return out or [text]


register_op(Operation(
    name="tone_neutralize",
    category="prose",
    description=(
        "Analyze the input's destructive/lethal register (Latin-root + loaded-word "
        "scoring) and rewrite it to a LOWER register while preserving the request. "
        "Why: safety classifiers key on the most-loaded morpheme, so de-risking the "
        "wording BEFORE obfuscation lets the payload slip past register filters that "
        "byte/structure mutation can't touch. Fans out one variant per strength "
        "(eta) so firing finds the level that gets through without gutting the ask. "
        "lexicon mode is deterministic; llm mode uses the local model (pass-through "
        "if it's cold)."
    ),
    params=[
        Param("mode", "select", "llm", "Rewrite engine.", options=["llm", "lexicon"]),
        Param("eta", "float", 0.6, "Max neutralization strength (0=identity, 1=maximal register-strip).", min=0.0, max=1.0),
        Param("levels", "int", 3, "How many strengths to sweep, from eta/levels up to eta.", min=1, max=5),
        Param("beta", "float", 6.0, "Register pooling sharpness (higher = tracks the single most-loaded word).", min=0.0, max=30.0),
        Param("model", "str", getattr(register._llm, "DEFAULT_MODEL", ""), "Local generator model tag (llm mode)."),
        Param("url", "str", getattr(register._llm, "DEFAULT_URL", ""), "Ollama base URL (llm mode)."),
        Param("temperature", "float", 0.4, "Sampling temperature for the rewrite (llm mode).", min=0.0, max=2.0),
        Param("num_predict", "int", 400, "Max tokens per rewrite (llm mode).", min=32, max=2048),
    ],
    fn=_tone_neutralize,
    deterministic=False,  # llm mode is stochastic; lexicon mode is deterministic
))
