"""Pliny-source adapter: builtin structural kit + optional local corpus.

L1B3RT4S / CL4R1T4S are prompt dumps, not importable libraries. This module
treats them as **data adapters**:

1. Always-on **builtin** frames map Pliny-family ideas onto registered ops
   (anchor_token, response_format_split, misdirection_frame, refusal_suppression,
   operator_signature). No external files required.
2. Optional **local corpus** via ``GARBLEWORKS_PLINY_CORPUS`` or an explicit path:
   scan ``.md`` / ``.mkd`` / ``.txt`` / ``.json`` for structural markers and
   emit parameterized recipe steps. Missing path → builtin only, no crash,
   no network fetch.

Out of scope as string-op adapters (documented for operators):
- G0DM0D3 (chat UI)
- OBLITERATUS (weight / abliteration surgery)
- GLOSSOPETRAE (JS engine; language ideas already mapped in ``scan_deep``)

Policy: do not vendor full liberation dumps into this repo. Operator-local path only.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# Env key for optional local corpus root (L1B3RT4S-style tree).
ENV_CORPUS = "GARBLEWORKS_PLINY_CORPUS"

_TEXT_SUFFIXES = {".md", ".mkd", ".txt", ".markdown"}
_JSON_SUFFIXES = {".json"}


@dataclass(frozen=True)
class PlinyFrame:
    """One selectable structural frame → ordered recipe steps."""

    id: str
    source: str  # "builtin" | "corpus"
    label: str
    steps: tuple[dict[str, Any], ...]
    markers: tuple[str, ...] = ()
    path: str = ""  # relative or absolute source file when corpus


def _step(op: str, **params: Any) -> dict[str, Any]:
    return {"op": op, "params": dict(params)} if params else {"op": op, "params": {}}


# ---------------------------------------------------------------------------
# Builtin structural kit (always available)
# ---------------------------------------------------------------------------

def _builtin_frames() -> list[PlinyFrame]:
    return [
        PlinyFrame(
            id="builtin.godmode",
            source="builtin",
            label="GODMODE anchor (prefix)",
            steps=(_step("anchor_token", token="godmode", position="prefix"),),
            markers=("GODMODE",),
        ),
        PlinyFrame(
            id="builtin.new_paradigm",
            source="builtin",
            label="NEW PARADIGM wrap",
            steps=(_step("anchor_token", token="new_paradigm", position="wrap"),),
            markers=("NEW PARADIGM",),
        ),
        PlinyFrame(
            id="builtin.liberated",
            source="builtin",
            label="Liberated system anchor",
            steps=(_step("anchor_token", token="liberated", position="prefix"),),
            markers=("Liberated",),
        ),
        PlinyFrame(
            id="builtin.divider",
            source="builtin",
            label="Liberation divider wrap",
            steps=(_step("anchor_token", token="divider", position="wrap"),),
            markers=("LIBERATED",),
        ),
        PlinyFrame(
            id="builtin.dan",
            source="builtin",
            label="DAN anchor",
            steps=(_step("anchor_token", token="dan", position="prefix"),),
            markers=("DAN",),
        ),
        PlinyFrame(
            id="builtin.response_format_split",
            source="builtin",
            label="ResponseFormat dual-output contract",
            steps=(_step("response_format_split", divider="watto", code_block=True),),
            markers=("ResponseFormat",),
        ),
        PlinyFrame(
            id="builtin.refusal_suppression",
            source="builtin",
            label="RefusalSuppression config block",
            steps=(_step("refusal_suppression", style="yaml"),),
            markers=("RefusalSuppression", "output-config"),
        ),
        PlinyFrame(
            id="builtin.misdirection_academic",
            source="builtin",
            label="Family 27 misdirection (academic)",
            steps=(_step("misdirection_frame", scenario="academic", deniability_tail=True),),
            markers=("peer-review", "scholarly"),
        ),
        PlinyFrame(
            id="builtin.misdirection_fiction",
            source="builtin",
            label="Family 27 misdirection (fiction)",
            steps=(_step("misdirection_frame", scenario="fiction", deniability_tail=True),),
            markers=("fictional",),
        ),
        PlinyFrame(
            id="builtin.operator_signature",
            source="builtin",
            label="Operator signature (loud)",
            steps=(_step("operator_signature", mode="loud", code_block=True),),
            markers=(),  # brand-dependent
        ),
        PlinyFrame(
            id="builtin.godmode_format",
            source="builtin",
            label="GODMODE + ResponseFormat stack",
            steps=(
                _step("anchor_token", token="godmode", position="prefix"),
                _step("response_format_split", divider="watto", code_block=True),
            ),
            markers=("GODMODE", "ResponseFormat"),
        ),
        PlinyFrame(
            id="builtin.pliny_full_stack",
            source="builtin",
            label="Composable full stack (anchor + persona + format)",
            steps=(
                _step("anchor_token", token="godmode", position="prefix"),
                _step("response_format_split", code_block=True),
                _step("operator_signature", mode="whisper", code_block=True),
            ),
            markers=("GODMODE", "ResponseFormat"),
        ),
    ]


# ---------------------------------------------------------------------------
# Corpus path resolution
# ---------------------------------------------------------------------------

def resolve_corpus_path(explicit: str | Path | None = None) -> Path | None:
    """Return a readable directory path, or None (builtin-only fallback)."""
    raw = explicit
    if raw is None or raw == "":
        raw = os.environ.get(ENV_CORPUS, "").strip()
    if not raw:
        return None
    p = Path(raw).expanduser()
    try:
        p = p.resolve()
    except OSError:
        return None
    if not p.is_dir():
        return None
    return p


# ---------------------------------------------------------------------------
# Structural extraction from corpus files
# ---------------------------------------------------------------------------

_RE_GODMODE = re.compile(r"GODMODE", re.I)
_RE_NEW_PARADIGM = re.compile(r"\[\[?\s*NEW\s+PARADIGM\s*\]\]?", re.I)
_RE_LIBERATED = re.compile(r"\bLIBERAT", re.I)
_RE_RESPONSE_FORMAT = re.compile(r"ResponseFormat|Response\s*Format", re.I)
_RE_REFUSAL = re.compile(r"RefusalSuppression|ApologyControl", re.I)
_RE_DIVIDER = re.compile(r"\.-+\.-+|⊰|LIBERATED|LOVE[- ]?PLINY|divider", re.I)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return s[:64] or "frame"


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _extract_frames_from_text(
    text: str,
    *,
    file_id: str,
    label: str,
    rel: str,
) -> list[PlinyFrame]:
    """Decompose file content into structural recipe steps (not opaque paste)."""
    if not text or not text.strip():
        return []

    frames: list[PlinyFrame] = []
    base = f"corpus.{file_id}"

    # Unique short marker from filename for operator / test verification.
    marker = f"PLINY_CORPUS::{file_id}"
    marker_step = _step("prefix_suffix", prefix=f"[{marker}]\n", suffix="")

    if _RE_GODMODE.search(text):
        frames.append(
            PlinyFrame(
                id=f"{base}.godmode",
                source="corpus",
                label=f"{label} → GODMODE anchor",
                steps=(marker_step, _step("anchor_token", token="godmode", position="prefix")),
                markers=(marker, "GODMODE"),
                path=rel,
            )
        )
    if _RE_NEW_PARADIGM.search(text):
        frames.append(
            PlinyFrame(
                id=f"{base}.new_paradigm",
                source="corpus",
                label=f"{label} → NEW PARADIGM",
                steps=(marker_step, _step("anchor_token", token="new_paradigm", position="wrap")),
                markers=(marker, "NEW PARADIGM"),
                path=rel,
            )
        )
    if _RE_RESPONSE_FORMAT.search(text) or (
        _RE_DIVIDER.search(text) and "format" in text.lower()
    ):
        frames.append(
            PlinyFrame(
                id=f"{base}.format_split",
                source="corpus",
                label=f"{label} → ResponseFormat split",
                steps=(
                    marker_step,
                    _step("response_format_split", divider="watto", code_block=True),
                ),
                markers=(marker, "ResponseFormat"),
                path=rel,
            )
        )
    if _RE_REFUSAL.search(text):
        frames.append(
            PlinyFrame(
                id=f"{base}.refusal",
                source="corpus",
                label=f"{label} → RefusalSuppression",
                steps=(marker_step, _step("refusal_suppression", style="yaml")),
                markers=(marker, "RefusalSuppression"),
                path=rel,
            )
        )
    if _RE_LIBERATED.search(text) and not any(f.id.endswith(".godmode") for f in frames):
        frames.append(
            PlinyFrame(
                id=f"{base}.liberated",
                source="corpus",
                label=f"{label} → liberated anchor",
                steps=(marker_step, _step("anchor_token", token="liberated", position="prefix")),
                markers=(marker, "Liberated"),
                path=rel,
            )
        )

    # If we saw Pliny chrome but no specific pattern, still surface a
    # composed stack keyed to the file (structural, not full paste).
    if not frames and (_RE_DIVIDER.search(text) or _RE_GODMODE.search(text)):
        frames.append(
            PlinyFrame(
                id=f"{base}.chrome",
                source="corpus",
                label=f"{label} → divider chrome",
                steps=(
                    marker_step,
                    _step("anchor_token", token="divider", position="prefix"),
                ),
                markers=(marker, "LIBERATED"),
                path=rel,
            )
        )

    # JSON list of {id, steps} or {id, op, params} for structured dumps.
    return frames


def _frames_from_json(path: Path, root: Path) -> list[PlinyFrame]:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []

    rel = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
    file_id = _slug(path.stem)
    out: list[PlinyFrame] = []

    # {"frames": [{"id", "label", "steps": [{"op","params"}]}]}
    items: list[Any]
    if isinstance(data, dict) and "frames" in data:
        items = data["frames"]
    elif isinstance(data, list):
        items = data
    else:
        # Treat as free text blob encoded in JSON string fields
        blob = json.dumps(data)
        return _extract_frames_from_text(
            blob, file_id=file_id, label=path.name, rel=rel
        )

    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        fid = str(item.get("id") or f"{file_id}_{i}")
        label = str(item.get("label") or fid)
        steps_raw = item.get("steps")
        if not isinstance(steps_raw, list) or not steps_raw:
            # Single op form
            op = item.get("op")
            if not op:
                continue
            steps_raw = [{"op": op, "params": item.get("params") or {}}]
        steps: list[dict[str, Any]] = []
        for s in steps_raw:
            if not isinstance(s, dict) or "op" not in s:
                continue
            steps.append({
                "op": str(s["op"]),
                "params": dict(s.get("params") or {}),
            })
        if not steps:
            continue
        markers = tuple(str(m) for m in (item.get("markers") or []))
        out.append(
            PlinyFrame(
                id=f"corpus.{_slug(fid)}",
                source="corpus",
                label=label,
                steps=tuple(steps),
                markers=markers,
                path=rel,
            )
        )
    return out


def load_corpus_frames(root: Path) -> list[PlinyFrame]:
    """Walk a local corpus tree; return structural frames only."""
    if not root.is_dir():
        return []
    found: list[PlinyFrame] = []
    seen_ids: set[str] = set()

    try:
        paths = sorted(root.rglob("*"))
    except OSError:
        return []

    for path in paths:
        if not path.is_file():
            continue
        suf = path.suffix.lower()
        if suf in _JSON_SUFFIXES:
            batch = _frames_from_json(path, root)
        elif suf in _TEXT_SUFFIXES:
            try:
                rel = str(path.relative_to(root))
            except ValueError:
                rel = str(path)
            batch = _extract_frames_from_text(
                _read_text(path),
                file_id=_slug(path.stem),
                label=path.name,
                rel=rel,
            )
        else:
            continue
        for fr in batch:
            if fr.id in seen_ids:
                continue
            seen_ids.add(fr.id)
            found.append(fr)
    return found


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_frames(
    corpus: str | Path | None = None,
    *,
    include_corpus: bool = True,
) -> list[PlinyFrame]:
    """Builtin frames, plus corpus frames when path resolves."""
    frames = list(_builtin_frames())
    if not include_corpus:
        return frames
    root = resolve_corpus_path(corpus)
    if root is None:
        return frames
    frames.extend(load_corpus_frames(root))
    return frames


def get_frame(
    frame_id: str,
    corpus: str | Path | None = None,
) -> PlinyFrame | None:
    for fr in list_frames(corpus):
        if fr.id == frame_id:
            return fr
    return None


def steps_for_frame(
    frame_id: str,
    corpus: str | Path | None = None,
) -> list[dict[str, Any]]:
    fr = get_frame(frame_id, corpus)
    if fr is None:
        return []
    return [dict(s) for s in fr.steps]


def apply_frame(
    frame_id: str,
    text: str,
    corpus: str | Path | None = None,
    *,
    max_variants: int = 32,
) -> list[str]:
    """Apply frame via real ``run_recipe`` path. Empty list on unknown frame."""
    steps = steps_for_frame(frame_id, corpus)
    if not steps:
        return []
    import ops  # noqa: F401  ensure registry
    from core import run_recipe

    # run_recipe → (variants, stage_report)
    variants, report = run_recipe(text, steps, max_variants=max_variants)
    if not variants:
        errs = [r.get("error") for r in report if r.get("error")]
        raise RuntimeError(
            errs[0] if errs else f"run_recipe produced no variants for frame {frame_id}"
        )
    return list(variants)


def default_frame_id() -> str:
    return "builtin.godmode"


def frame_ids(corpus: str | Path | None = None) -> list[str]:
    return [f.id for f in list_frames(corpus)]


def describe_scope() -> dict[str, Any]:
    """Operator-facing scope note for docs / MCP / debugging."""
    return {
        "env": ENV_CORPUS,
        "builtin": True,
        "corpus_path": str(resolve_corpus_path() or ""),
        "adaptable_repos": [
            "elder-plinius/L1B3RT4S (markdown/json dumps → structural frames)",
            "elder-plinius/CL4R1T4S (optional system-prompt text, same load rules)",
        ],
        "not_adapters": [
            "G0DM0D3 — chat UI, not a string-op source",
            "OBLITERATUS — weight/abliteration surgery, not recipe ops",
            "GLOSSOPETRAE — JS language engine; idea mapped to lang ops in scan_deep",
        ],
        "policy": "No full liberation corpus committed; local path only; no runtime network fetch.",
    }
