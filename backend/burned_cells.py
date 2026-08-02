"""Per-challenge burned gold cells — persistent miss memory for densify/align.

When a draft fails the gold gate (or platform scorer), record which cells missed.
Later densify/align prompts prioritize those holes so we do not re-discover them
every session.

Store: backend/sessions/burned_cells/<challenge_key>.json
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parent
STORE_DIR = _BACKEND / "sessions" / "burned_cells"


def challenge_key(objective: str = "", *, title: str = "", explicit: str = "") -> str:
    """Stable short key for a challenge card / objective."""
    if explicit:
        raw = explicit.strip().lower()
    else:
        raw = f"{title}\n{objective}".strip().lower()
    raw = re.sub(r"\s+", " ", raw)[:240]
    if not raw:
        return "unknown"
    # human-readable slug + short hash for collisions
    slug = re.sub(r"[^a-z0-9]+", "-", raw)[:48].strip("-") or "chal"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"{slug}-{h}"


def _path(key: str) -> Path:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", key)[:80]
    return STORE_DIR / f"{safe}.json"


def load(key: str) -> dict[str, Any]:
    p = _path(key)
    if not p.is_file():
        return {
            "key": key,
            "updated_ts": None,
            "cells": {},  # id -> {label, hint, n_miss, n_hit, last_miss_ts, last_hit_ts}
            "events": [],
        }
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        data.setdefault("cells", {})
        data.setdefault("events", [])
        data["key"] = key
        return data
    except Exception:
        return {"key": key, "updated_ts": None, "cells": {}, "events": []}


def save(data: dict[str, Any]) -> Path:
    key = str(data.get("key") or "unknown")
    p = _path(key)
    data["updated_ts"] = time.time()
    # cap event log
    ev = data.get("events") or []
    if len(ev) > 200:
        data["events"] = ev[-200:]
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def record_gate(
    key: str,
    gate: dict[str, Any],
    *,
    technique: str = "",
    outcome: str = "",
) -> dict[str, Any]:
    """Merge a score_draft/submit_gate result into the burned-cells file."""
    data = load(key)
    cells = data["cells"]
    ts = time.time()
    misses = gate.get("misses") or []
    # hits: cells present in full cell list with status hit
    hit_ids: set[str] = set()
    for c in gate.get("cells") or []:
        if c.get("status") == "hit" and c.get("id"):
            hit_ids.add(str(c["id"]))
    for m in misses:
        cid = str(m.get("id") or "")
        if not cid:
            continue
        row = cells.get(cid) or {
            "id": cid,
            "label": m.get("label"),
            "hint": m.get("hint"),
            "n_miss": 0,
            "n_hit": 0,
        }
        row["label"] = m.get("label") or row.get("label")
        row["hint"] = m.get("hint") or row.get("hint")
        row["n_miss"] = int(row.get("n_miss") or 0) + 1
        row["last_miss_ts"] = ts
        cells[cid] = row
    for hid in hit_ids:
        row = cells.get(hid) or {"id": hid, "n_miss": 0, "n_hit": 0}
        row["n_hit"] = int(row.get("n_hit") or 0) + 1
        row["last_hit_ts"] = ts
        cells[hid] = row

    data["cells"] = cells
    data["events"].append({
        "ts": ts,
        "technique": technique,
        "outcome": outcome,
        "coverage": gate.get("coverage"),
        "allow_submit": gate.get("allow_submit"),
        "miss_ids": [m.get("id") for m in misses],
    })
    data["last_coverage"] = gate.get("coverage")
    data["last_allow_submit"] = gate.get("allow_submit")
    save(data)
    return data


def top_misses(key: str, *, limit: int = 12, min_n: int = 1) -> list[dict[str, Any]]:
    """Cells with the most misses (and fewer recent hits), for densify prompts."""
    data = load(key)
    rows = []
    for cid, row in (data.get("cells") or {}).items():
        n_miss = int(row.get("n_miss") or 0)
        n_hit = int(row.get("n_hit") or 0)
        if n_miss < min_n:
            continue
        # score: miss-heavy cells float up; hits dampen
        score = n_miss - 0.5 * n_hit
        rows.append({
            "id": cid,
            "label": row.get("label") or cid,
            "hint": row.get("hint") or "",
            "n_miss": n_miss,
            "n_hit": n_hit,
            "score": score,
        })
    rows.sort(key=lambda r: (-r["score"], -r["n_miss"], r["id"]))
    return rows[:limit]


def densify_checklist(key: str, *, limit: int = 12) -> str:
    """Bullet list of persistent misses for injection into densify/align prompts."""
    misses = top_misses(key, limit=limit)
    if not misses:
        return ""
    lines = [
        "PERSISTENT SCORE HOLES from prior failed submits on this challenge "
        "(fix these first — they have failed the gold gate before):",
    ]
    for m in misses:
        lines.append(
            f"- {m['label']}: {m['hint']}  "
            f"[missed {m['n_miss']}×, hit {m['n_hit']}×]"
        )
    return "\n".join(lines)


def merge_misses_into_align(
    base_prompt: str,
    key: str,
    *,
    limit: int = 12,
) -> str:
    block = densify_checklist(key, limit=limit)
    if not block:
        return base_prompt
    return f"{base_prompt.rstrip()}\n\n{block}\n"


def list_keys() -> list[str]:
    if not STORE_DIR.is_dir():
        return []
    return sorted(p.stem for p in STORE_DIR.glob("*.json"))
