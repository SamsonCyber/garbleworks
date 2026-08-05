"""Multi-source behavior batteries (HarmBench, JBB-shaped, StrongREJECT-shaped).

Shared resolve path used by CLI/MCP. Full corpora are not vendored in git:
download-on-first-use where URLs exist, else fixture + operator path/env.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from behaviors import Behavior, _as_behavior, load_behaviors

_BACKEND = Path(__file__).resolve().parent
_BATTERY = _BACKEND / "bench" / "battery"
_LIBRARY = _BACKEND / "library"

# Optional public raw mirrors (may change). Fixtures always work offline.
JBB_URL = os.environ.get(
    "GARBLEWORKS_JBB_URL",
    "",  # no default network pull; fixture + operator export
)
STRONGREJECT_URL = os.environ.get("GARBLEWORKS_STRONGREJECT_URL", "")


def fixture_path(name: str) -> Path:
    return _BATTERY / name


def jbb_cache_path() -> Path:
    override = (os.environ.get("GARBLEWORKS_JBB") or "").strip()
    if override:
        return Path(override)
    return _LIBRARY / "jailbreakbench_behaviors.json"


def strongreject_cache_path() -> Path:
    override = (os.environ.get("GARBLEWORKS_STRONGREJECT") or "").strip()
    if override:
        return Path(override)
    return _LIBRARY / "strongreject_behaviors.json"


def _load_json_behaviors(
    path: Path,
    *,
    default_source: str,
    limit: int | None = None,
    categories: list[str] | None = None,
) -> list[Behavior]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    items: list[dict]
    src = default_source
    if isinstance(raw, dict):
        meta = raw.get("_meta") or {}
        src = str(meta.get("source") or default_source)
        items = list(
            raw.get("behaviors")
            or raw.get("data")
            or raw.get("goals")
            or raw.get("prompts")
            or []
        )
    elif isinstance(raw, list):
        items = raw
    else:
        return []

    cat_filter = {c.lower() for c in (categories or []) if c}
    out: list[Behavior] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        # StrongREJECT / JBB field aliases
        if "forbidden_prompt" in row and not (
            row.get("behavior") or row.get("Behavior") or row.get("goal")
        ):
            row = {
                **row,
                "behavior": row.get("forbidden_prompt") or row.get("prompt") or "",
            }
        if "prompt" in row and not (
            row.get("behavior") or row.get("Behavior") or row.get("goal")
        ):
            row = {**row, "behavior": row.get("prompt") or ""}
        b = _as_behavior(row, default_source=src)
        if not b:
            # synthesize id if missing but text present
            text = (
                row.get("behavior")
                or row.get("Behavior")
                or row.get("goal")
                or row.get("forbidden_prompt")
                or row.get("prompt")
                or ""
            )
            text = str(text).strip()
            if not text:
                continue
            bid = str(row.get("id") or row.get("BehaviorID") or f"{src}_{len(out)}")
            cat = str(
                row.get("category")
                or row.get("semantic_category")
                or "unspecified"
            )
            b = Behavior(id=bid, behavior=text, category=cat, source=src)
        if cat_filter and b.category.lower() not in cat_filter:
            continue
        out.append(b)
        if limit is not None and len(out) >= limit:
            break
    return out


def _try_download(url: str, dest: Path) -> dict[str, Any]:
    if not url:
        return {"ok": False, "error": "no download URL configured"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "garbleworks-datasets/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return {"ok": True, "path": str(dest), "bytes": len(data)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}


def load_jailbreakbench(
    *,
    limit: int | None = None,
    categories: list[str] | None = None,
    ensure: bool = False,
    use_fixture_if_empty: bool = True,
) -> list[Behavior]:
    """Load JBB-shaped behaviors (cache path, env, or in-repo fixture)."""
    path = jbb_cache_path()
    if ensure and JBB_URL and not path.is_file():
        _try_download(JBB_URL, path)
    items = _load_json_behaviors(
        path, default_source="jailbreakbench", limit=limit, categories=categories
    )
    if items:
        return items
    if use_fixture_if_empty:
        return _load_json_behaviors(
            fixture_path("jbb_sample.json"),
            default_source="jailbreakbench_shaped",
            limit=limit,
            categories=categories,
        )
    return []


def load_strongreject(
    *,
    limit: int | None = None,
    categories: list[str] | None = None,
    ensure: bool = False,
    use_fixture_if_empty: bool = True,
) -> list[Behavior]:
    """Load StrongREJECT-shaped behaviors (forbidden_prompt field)."""
    path = strongreject_cache_path()
    if ensure and STRONGREJECT_URL and not path.is_file():
        _try_download(STRONGREJECT_URL, path)
    items = _load_json_behaviors(
        path, default_source="strongreject", limit=limit, categories=categories
    )
    if items:
        return items
    if use_fixture_if_empty:
        return _load_json_behaviors(
            fixture_path("strongreject_sample.json"),
            default_source="strongreject_shaped",
            limit=limit,
            categories=categories,
        )
    return []


def list_sources() -> list[dict[str, Any]]:
    return [
        {
            "id": "harmbench",
            "description": "Official HarmBench text behaviors (download-on-first-use CSV)",
            "env": "GARBLEWORKS_HARMBENCH_CSV",
        },
        {
            "id": "jailbreakbench",
            "description": "JailbreakBench-shaped JSON (fixture + optional operator export)",
            "env": "GARBLEWORKS_JBB",
            "fixture": str(fixture_path("jbb_sample.json")),
        },
        {
            "id": "strongreject",
            "description": "StrongREJECT-shaped JSON (forbidden_prompt; fixture + optional export)",
            "env": "GARBLEWORKS_STRONGREJECT",
            "fixture": str(fixture_path("strongreject_sample.json")),
        },
        {
            "id": "sample",
            "description": "In-repo v1_behaviors_sample.json (loader tests)",
            "fixture": str(fixture_path("v1_behaviors_sample.json")),
        },
        {
            "id": "json",
            "description": "Operator JSON via path or GARBLEWORKS_BEHAVIORS",
            "env": "GARBLEWORKS_BEHAVIORS",
        },
    ]


def resolve_dataset(
    source: str,
    *,
    path: str = "",
    limit: int | None = None,
    categories: list[str] | None = None,
    n_sample: int | None = None,
    seed: int = 0,
    offline: bool = False,
) -> list[Behavior]:
    """Resolve behaviors by source id (shared select path)."""
    from behaviors import resolve_behaviors

    src = (source or "auto").strip().lower()
    if src in ("jbb", "jailbreakbench", "jailbreak_bench"):
        items = load_jailbreakbench(limit=limit, categories=categories)
        if n_sample is not None and items:
            import random

            rng = random.Random(int(seed))
            pool = list(items)
            rng.shuffle(pool)
            return pool[: max(1, int(n_sample))]
        return items
    if src in ("strongreject", "sr", "strong_reject"):
        items = load_strongreject(limit=limit, categories=categories)
        if n_sample is not None and items:
            import random

            rng = random.Random(int(seed))
            pool = list(items)
            rng.shuffle(pool)
            return pool[: max(1, int(n_sample))]
        return items
    return resolve_behaviors(
        source=src if src != "auto" else "auto",
        path=path,
        limit=limit,
        categories=categories,
        n_sample=n_sample,
        seed=seed,
        offline=offline,
    )
