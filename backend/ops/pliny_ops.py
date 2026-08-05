"""Registry ops that call the Pliny adapter (builtin + optional corpus).

Keeps phase-F / recipe surface on the normal ``run_recipe`` path.
"""
from __future__ import annotations

from core import Operation, Param, register
import pliny_adapter as PA


def _frame_options() -> list[str]:
    # Builtin ids only in the static Param list so the UI stays stable without
    # a corpus. Corpus frames are still addressable via pliny_adapter.apply_frame
    # and free-form frame_id string on pliny_frame.
    return [f.id for f in PA.list_frames(include_corpus=False)]


def _pliny_frame(text: str, frame_id: str, corpus_path: str) -> list[str]:
    fid = (frame_id or PA.default_frame_id()).strip()
    corpus = (corpus_path or "").strip() or None
    # Prefer explicit corpus path for this call; else env / builtin.
    out = PA.apply_frame(fid, text, corpus=corpus)
    if out:
        return out
    # Unknown id → builtin godmode so recipes never go empty.
    return PA.apply_frame(PA.default_frame_id(), text, corpus=None)


def _pliny_list_hint(text: str) -> list[str]:
    """Diagnostic op: list available frame ids (does not mutate payload intent)."""
    ids = PA.frame_ids()
    head = ", ".join(ids[:24])
    more = f" (+{len(ids) - 24} more)" if len(ids) > 24 else ""
    return [f"[pliny_frames n={len(ids)}] {head}{more}\n\n{text}"]


_OPTS = _frame_options()

register(Operation(
    "pliny_frame",
    "jailbreak",
    "Apply a Pliny-family structural frame via the adapter (builtin kit, or "
    "optional local L1B3RT4S-style corpus when GARBLEWORKS_PLINY_CORPUS / "
    "corpus_path is set). Frames decompose to registered ops (anchor_token, "
    "response_format_split, misdirection_frame, …) — not an opaque mega-prompt "
    "paste. Source: Pliny signature patterns + optional local corpus.",
    [
        Param(
            "frame_id",
            "select",
            PA.default_frame_id(),
            "Builtin frame id (corpus ids also work as free text if supported by client).",
            options=_OPTS,
        ),
        Param(
            "corpus_path",
            "str",
            "",
            "Optional local corpus root override (blank = env GARBLEWORKS_PLINY_CORPUS or builtin only).",
        ),
    ],
    _pliny_frame,
    family="jailbreak",
    deterministic=True,
))

register(Operation(
    "pliny_list_frames",
    "sampler",
    "Prefix the text with the current Pliny adapter frame id list (builtin + "
    "corpus if configured). Diagnostic / operator HUD helper.",
    [],
    _pliny_list_hint,
    family="control",
    deterministic=True,
))
