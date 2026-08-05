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
# Skip multi-MB token dumps and app scaffolding when walking a clone.
_MAX_CORPUS_FILE_BYTES = 400_000
_SKIP_NAME_PARTS = (
    "node_modules",
    "package-lock",
    "experiments/results",
    "token80m8",
    "tokenade",
    ".min.js",
)


def repo_root() -> Path:
    """Garbleworks repository root (parent of ``backend/``)."""
    return Path(__file__).resolve().parents[1]


def default_corpus_candidates() -> list[Path]:
    """Plug-and-play locations checked when env is unset.

    Drop a local clone into one of these paths (or set ``GARBLEWORKS_PLINY_CORPUS``).
    """
    root = repo_root()
    return [
        root / "corpora" / "L1B3RT4S",
        root / "corpora" / "CL4R1T4S",
        root / "corpora" / "pliny",
        root / "pliny_corpus",
        root.parent / "L1B3RT4S",
        root.parent / "CL4R1T4S",
    ]


def looks_like_corpus(path: Path) -> bool:
    """True if directory has liberation-dump shape (mkd / shortcuts / prompt text)."""
    if not path.is_dir():
        return False
    try:
        for p in path.rglob("*"):
            if not p.is_file():
                continue
            name = p.name.lower()
            if "shortcut" in name and p.suffix.lower() == ".json":
                return True
            if p.suffix.lower() in {".mkd", ".txt", ".md"} and p.stat().st_size > 12:
                return True
    except OSError:
        return False
    return False


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
    """Return a readable corpus directory, or None (builtin-only fallback).

    Resolution order:
    1. Explicit ``corpus`` / ``corpus_path`` argument
    2. ``GARBLEWORKS_PLINY_CORPUS`` env
    3. First plug-and-play candidate under ``corpora/`` or sibling clones
       that ``looks_like_corpus`` accepts
    """
    candidates: list[Path] = []
    if explicit is not None and str(explicit).strip():
        candidates.append(Path(str(explicit)).expanduser())
    env = os.environ.get(ENV_CORPUS, "").strip()
    if env:
        candidates.append(Path(env).expanduser())
    # Only auto-discover when no explicit/env path was given.
    if not candidates:
        candidates.extend(default_corpus_candidates())

    for raw in candidates:
        try:
            p = raw.resolve()
        except OSError:
            continue
        if p.is_dir() and looks_like_corpus(p):
            return p
        # Explicit/env path that is a dir but empty of dumps: still accept so
        # operators get a clear "0 frames" rather than silent builtin-only.
        if (
            explicit is not None
            and str(explicit).strip()
            and p.is_dir()
        ) or (env and raw == Path(env).expanduser() and p.is_dir()):
            return p
    return None


def plug_status() -> dict[str, Any]:
    """Operator HUD: how Pliny is wired right now."""
    path = resolve_corpus_path()
    builtin_n = len(list_frames(include_corpus=False))
    frames = list_frames() if path else list_frames(include_corpus=False)
    corpus_n = sum(1 for f in frames if f.source == "corpus")
    return {
        "env_key": ENV_CORPUS,
        "env_value": os.environ.get(ENV_CORPUS, ""),
        "corpus_path": str(path or ""),
        "corpus_active": bool(path),
        "builtin_frames": builtin_n,
        "corpus_frames": corpus_n,
        "total_frames": len(frames),
        "candidates": [str(p) for p in default_corpus_candidates()],
        "plug_hint": (
            f"git clone --depth 1 https://github.com/elder-plinius/L1B3RT4S.git "
            f"{repo_root() / 'corpora' / 'L1B3RT4S'}"
            if not path
            else f"active corpus: {path}"
        ),
    }


# ---------------------------------------------------------------------------
# Structural extraction from corpus files
# ---------------------------------------------------------------------------

_RE_GODMODE = re.compile(r"GODMODE", re.I)
_RE_NEW_PARADIGM = re.compile(r"\[\[?\s*NEW\s+PARADIGM\s*\]\]?", re.I)
_RE_LIBERATED = re.compile(r"\bLIBERAT", re.I)
_RE_RESPONSE_FORMAT = re.compile(r"ResponseFormat|Response\s*Format", re.I)
_RE_REFUSAL = re.compile(r"RefusalSuppression|ApologyControl", re.I)
_RE_DIVIDER = re.compile(r"\.-+\.-+|⊰|LIBERATED|LOVE[- ]?PLINY|divider", re.I)
# Capture ornate Pliny-style divider lines from dumps (new surface vs brand default).
_RE_DIVIDER_LINE = re.compile(
    r"(?:divider\s+)?("
    r"\.-[\.-]{6,}[^\n]{0,120}\.-[\.-]{6,}"
    r"|[⊰•\-✧]{4,}[^\n]{0,80}"
    r"|\.-[\.-]*</?[^>\n]{3,40}>[\.-]*"
    r")",
    re.I,
)
_RE_GODMODE_LINE = re.compile(
    r"^.*GODMODE\s*:\s*ENABLED[^\n]{0,160}$",
    re.I | re.M,
)
_RE_BANG_CMD = re.compile(r"(![A-Z][A-Z0-9_]{1,24}|\{GODMODE:[A-Z]+\})")


def _slug(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return s[:64] or "frame"


def _read_text(path: Path, limit: int = _MAX_CORPUS_FILE_BYTES) -> str:
    try:
        raw = path.read_bytes()[:limit]
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _should_skip_path(path: Path) -> bool:
    low = str(path).replace("\\", "/").lower()
    if any(p in low for p in _SKIP_NAME_PARTS):
        return True
    try:
        if path.stat().st_size > _MAX_CORPUS_FILE_BYTES:
            return True
    except OSError:
        return True
    return False


def _extract_custom_divider(text: str) -> str | None:
    m = _RE_DIVIDER_LINE.search(text)
    if not m:
        return None
    div = m.group(1).strip()
    if len(div) < 8 or len(div) > 200:
        return None
    # Avoid pure "divider" word hits
    if div.lower() in ("divider", "liberated"):
        return None
    return div


def _extract_godmode_line(text: str) -> str | None:
    m = _RE_GODMODE_LINE.search(text)
    if not m:
        return None
    line = m.group(0).strip()
    if 10 <= len(line) <= 220:
        return line
    return None


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
    marker = f"PLINY_CORPUS::{file_id}"
    marker_step = _step("prefix_suffix", prefix=f"[{marker}]\n", suffix="")

    custom_div = _extract_custom_divider(text)
    god_line = _extract_godmode_line(text)

    # Corpus-unique chrome: file's own GODMODE line as free-text prefix (not builtin anchor string).
    if god_line:
        frames.append(
            PlinyFrame(
                id=f"{base}.godmode_line",
                source="corpus",
                label=f"{label} -> corpus GODMODE line",
                steps=(
                    marker_step,
                    _step("prefix_suffix", prefix=god_line + "\n", suffix=""),
                ),
                markers=(marker, "GODMODE", god_line[:40]),
                path=rel,
            )
        )
    elif _RE_GODMODE.search(text):
        frames.append(
            PlinyFrame(
                id=f"{base}.godmode",
                source="corpus",
                label=f"{label} -> GODMODE anchor",
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
                label=f"{label} -> NEW PARADIGM",
                steps=(marker_step, _step("anchor_token", token="new_paradigm", position="wrap")),
                markers=(marker, "NEW PARADIGM"),
                path=rel,
            )
        )

    # Custom divider from dump is net-new vs builtin watto brand divider.
    if custom_div and (_RE_RESPONSE_FORMAT.search(text) or _RE_DIVIDER.search(text)):
        frames.append(
            PlinyFrame(
                id=f"{base}.format_custom_div",
                source="corpus",
                label=f"{label} -> ResponseFormat + corpus divider",
                steps=(
                    marker_step,
                    _step("response_format_split", divider=custom_div, code_block=True),
                ),
                markers=(marker, "ResponseFormat", custom_div[:32]),
                path=rel,
            )
        )
    elif _RE_RESPONSE_FORMAT.search(text):
        frames.append(
            PlinyFrame(
                id=f"{base}.format_split",
                source="corpus",
                label=f"{label} -> ResponseFormat split",
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
                label=f"{label} -> RefusalSuppression",
                steps=(marker_step, _step("refusal_suppression", style="yaml")),
                markers=(marker, "RefusalSuppression"),
                path=rel,
            )
        )

    if _RE_LIBERATED.search(text) and not any("godmode" in f.id for f in frames):
        frames.append(
            PlinyFrame(
                id=f"{base}.liberated",
                source="corpus",
                label=f"{label} -> liberated anchor",
                steps=(marker_step, _step("anchor_token", token="liberated", position="prefix")),
                markers=(marker, "Liberated"),
                path=rel,
            )
        )

    # Stack: corpus GODMODE line + custom divider format (composition not in builtin list).
    if god_line and custom_div:
        frames.append(
            PlinyFrame(
                id=f"{base}.stack_line_div",
                source="corpus",
                label=f"{label} -> GODMODE line + custom format divider",
                steps=(
                    marker_step,
                    _step("prefix_suffix", prefix=god_line + "\n", suffix=""),
                    _step("response_format_split", divider=custom_div, code_block=True),
                ),
                markers=(marker, "GODMODE", "ResponseFormat", custom_div[:24]),
                path=rel,
            )
        )

    # Bang-commands embedded in prose (!JAILBREAK, !OMNI, …) as trigger prefixes.
    for m in list(_RE_BANG_CMD.finditer(text))[:8]:
        cmd = m.group(1)
        cid = _slug(cmd)
        frames.append(
            PlinyFrame(
                id=f"{base}.cmd_{cid}",
                source="corpus",
                label=f"{label} -> trigger {cmd}",
                steps=(
                    marker_step,
                    _step("prefix_suffix", prefix=f"{cmd}\n", suffix=""),
                ),
                markers=(marker, cmd),
                path=rel,
            )
        )

    if not frames and (_RE_DIVIDER.search(text) or _RE_GODMODE.search(text)):
        frames.append(
            PlinyFrame(
                id=f"{base}.chrome",
                source="corpus",
                label=f"{label} -> divider chrome",
                steps=(
                    marker_step,
                    _step("anchor_token", token="divider", position="prefix"),
                ),
                markers=(marker, "LIBERATED"),
                path=rel,
            )
        )

    return frames


def _frames_from_shortcuts_json(
    data: dict[str, Any],
    *,
    file_id: str,
    rel: str,
) -> list[PlinyFrame]:
    """L1B3RT4S !SHORTCUTS.json: commands[] with name/definition/category."""
    commands = data.get("commands")
    if not isinstance(commands, list):
        return []
    out: list[PlinyFrame] = []
    for i, item in enumerate(commands):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        definition = str(item.get("definition") or "").strip()
        category = str(item.get("category") or "shortcut")
        # Cap definition used as framing chrome (not full mega-prompt paste).
        def_snip = definition[:280].rstrip()
        if def_snip and not def_snip.endswith("."):
            def_snip += "."
        prefix = f"{name}\n"
        if def_snip:
            prefix += f"({def_snip})\n"
        fid = f"corpus.shortcut.{_slug(name)}"
        out.append(
            PlinyFrame(
                id=fid,
                source="corpus",
                label=f"SHORTCUT {name} [{category}]",
                steps=(
                    _step("prefix_suffix", prefix=f"[PLINY_SHORTCUT::{_slug(name)}]\n", suffix=""),
                    _step("prefix_suffix", prefix=prefix, suffix=""),
                ),
                markers=(f"PLINY_SHORTCUT::{_slug(name)}", name),
                path=rel,
            )
        )
        # Pair high-value liberation shortcuts with format-split for deeper surface.
        if i < 12 and any(k in name.upper() for k in ("GODMODE", "JAILBREAK", "OMNI", "OPPO", "INSERT")):
            out.append(
                PlinyFrame(
                    id=f"{fid}.plus_format",
                    source="corpus",
                    label=f"SHORTCUT {name} + ResponseFormat",
                    steps=(
                        _step("prefix_suffix", prefix=prefix, suffix=""),
                        _step("response_format_split", divider="watto", code_block=True),
                    ),
                    markers=(name, "ResponseFormat"),
                    path=rel,
                )
            )
    return out


def _frames_from_json(path: Path, root: Path) -> list[PlinyFrame]:
    try:
        # Windows extracts / editors often leave UTF-8 BOM.
        data = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return []

    try:
        rel = str(path.relative_to(root))
    except ValueError:
        rel = str(path)
    file_id = _slug(path.stem)
    out: list[PlinyFrame] = []

    # L1B3RT4S shortcut catalog
    if isinstance(data, dict) and isinstance(data.get("commands"), list):
        return _frames_from_shortcuts_json(data, file_id=file_id, rel=rel)

    # {"frames": [{"id", "label", "steps": [{"op","params"}]}]}
    items: list[Any]
    if isinstance(data, dict) and "frames" in data:
        items = data["frames"]
    elif isinstance(data, list):
        items = data
    else:
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
        if not path.is_file() or _should_skip_path(path):
            continue
        suf = path.suffix.lower()
        # Prefer liberation dumps over app scaffolding
        name_low = path.name.lower()
        if suf in _JSON_SUFFIXES:
            batch = _frames_from_json(path, root)
        elif suf in _TEXT_SUFFIXES:
            # Skip pure package docs that only mention GODMODE in marketing prose
            if name_low in ("license", "contributing.md", "code_of_conduct.md"):
                continue
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


def surface_delta(
    corpus: str | Path | None = None,
) -> dict[str, Any]:
    """Compare builtin frame ids vs corpus-enabled set (for scrutiny / tests)."""
    builtin = {f.id for f in list_frames(include_corpus=False)}
    root = resolve_corpus_path(corpus)
    if root is None:
        return {
            "builtin": sorted(builtin),
            "corpus_only": [],
            "corpus_path": "",
            "new_compositions": 0,
        }
    corp_frames = load_corpus_frames(root)
    corp_ids = {f.id for f in corp_frames}
    only = sorted(corp_ids - builtin)
    # compositions that use non-default dividers or shortcut prefixes
    new_comp = 0
    for fr in corp_frames:
        blob = json.dumps(list(fr.steps))
        if "PLINY_SHORTCUT" in blob or "godmode_line" in fr.id or "format_custom_div" in fr.id:
            new_comp += 1
        elif any(
            (s.get("params") or {}).get("divider") not in (None, "", "watto")
            for s in fr.steps
            if s.get("op") == "response_format_split"
        ):
            new_comp += 1
    return {
        "builtin": sorted(builtin),
        "corpus_only": only,
        "corpus_path": str(root),
        "new_compositions": new_comp,
        "corpus_frame_count": len(corp_frames),
    }

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
            "elder-plinius/L1B3RT4S (mkd dumps + !SHORTCUTS.json -> structural frames)",
            "elder-plinius/CL4R1T4S (system-prompt text; same structural load rules)",
        ],
        "not_adapters": [
            "G0DM0D3: Next.js chat UI (not a recipe string source)",
            "OBLITERATUS: model weight / abliteration surgery (not recipe ops)",
            "GLOSSOPETRAE: JS language engine; shipped mapping is scan_deep.GLOSSOPETRAE_MAP -> lang ops",
        ],
        "policy": (
            "No full liberation corpus committed; local path only; no runtime network fetch. "
            "Corpus frames decompose into ops (prefix_suffix, anchor_token, response_format_split)."
        ),
        "scrutiny_value": (
            "Net new surface = SHORTCUT command prefixes, corpus-specific GODMODE lines, "
            "custom ResponseFormat dividers, and stacks of those; not only renamed builtin.*"
        ),
    }
