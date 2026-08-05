"""Real HarmBench behavior battery for Garbleworks attack loops.

Mirrors Wallbreaker-class usage: download the official text behaviors CSV on
first use, cache under backend/library/, sample stratified batteries, feed the
shared campaign / --auto path.

Source (upstream, not vendored in git):
  https://github.com/centerforaisafety/HarmBench
  data/behavior_datasets/harmbench_behaviors_text_all.csv

Authorized red-team / robustness measurement only. See SECURITY.md.
"""
from __future__ import annotations

import csv
import json
import os
import random
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from behaviors import Behavior, behaviors_to_bench_objectives

DATASET_URL = (
    "https://raw.githubusercontent.com/centerforaisafety/HarmBench/main/"
    "data/behavior_datasets/harmbench_behaviors_text_all.csv"
)

# Cache beside other operator data (gitignored). Override via env.
_DEFAULT_CACHE = Path(__file__).resolve().parent / "library" / "harmbench_behaviors.csv"


def dataset_path() -> Path:
    override = (os.environ.get("GARBLEWORKS_HARMBENCH_CSV") or "").strip()
    if override:
        return Path(override)
    return _DEFAULT_CACHE


def is_cached() -> bool:
    p = dataset_path()
    if not p.is_file() or p.stat().st_size < 40:
        return False
    try:
        head = p.read_text(encoding="utf-8", errors="replace")[:500]
    except Exception:
        return False
    # Accept real upstream or test fixtures with the same columns
    return "Behavior" in head and (
        "BehaviorID" in head or "SemanticCategory" in head
    )


def ensure_dataset(*, offline: bool = False, force: bool = False) -> dict[str, Any]:
    """Download HarmBench CSV if missing. Returns status dict."""
    path = dataset_path()
    if is_cached() and not force:
        return {
            "ok": True,
            "cached": True,
            "path": str(path),
            "bytes": path.stat().st_size,
            "note": "already cached",
        }
    if offline:
        return {
            "ok": False,
            "cached": False,
            "path": str(path),
            "error": "HarmBench not cached and offline=True",
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(
            DATASET_URL,
            headers={"User-Agent": "garbleworks-harmbench/1.0 (authorized red-team lab)"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        if "BehaviorID" not in text and "Behavior" not in text.split("\n", 1)[0]:
            return {
                "ok": False,
                "cached": False,
                "path": str(path),
                "error": "download did not look like HarmBench CSV",
            }
        path.write_text(text, encoding="utf-8")
        return {
            "ok": True,
            "cached": True,
            "path": str(path),
            "bytes": path.stat().st_size,
            "downloaded": True,
            "url": DATASET_URL,
        }
    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "cached": False,
            "path": str(path),
            "error": f"HTTP {e.code}: {e.reason}",
        }
    except Exception as e:
        return {
            "ok": False,
            "cached": False,
            "path": str(path),
            "error": f"{type(e).__name__}: {e}"[:300],
        }


def load_behaviors(
    *,
    skip_contextual: bool = True,
    skip_copyright: bool = False,
    limit: int | None = None,
    categories: list[str] | None = None,
    path: str | Path | None = None,
) -> list[Behavior]:
    """Load cached HarmBench CSV into Behavior list (same shape as behaviors.py)."""
    p = Path(path) if path else dataset_path()
    if not p.is_file():
        return []
    cat_filter = {c.lower() for c in (categories or []) if c}
    out: list[Behavior] = []
    with p.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            if not isinstance(r, dict):
                continue
            func = (r.get("FunctionalCategory") or "").strip().lower()
            if skip_contextual and func == "contextual":
                continue
            if skip_copyright and func == "copyright":
                continue
            bid = (r.get("BehaviorID") or "").strip()
            text = (r.get("Behavior") or "").strip()
            if not bid or not text:
                continue
            cat = (r.get("SemanticCategory") or "unspecified").strip()
            if cat_filter and cat.lower() not in cat_filter:
                continue
            ctx = (r.get("ContextString") or "").strip()
            tags = (r.get("Tags") or "").strip()
            out.append(
                Behavior(
                    id=bid,
                    behavior=text,
                    category=cat,
                    source="harmbench",
                    meta={
                        "functional_category": func,
                        "tags": tags,
                        "context_string": ctx[:500] if ctx else "",
                    },
                )
            )
            if limit is not None and len(out) >= limit:
                break
    return out


def categories(*, path: str | Path | None = None) -> list[str]:
    return sorted({b.category for b in load_behaviors(path=path) if b.category})


def sample(
    *,
    category: str | None = None,
    n: int = 8,
    seed: int = 0,
    skip_contextual: bool = True,
    skip_copyright: bool = False,
    path: str | Path | None = None,
) -> list[Behavior]:
    """Stratified sample across semantic categories (unbiased battery)."""
    behaviors = load_behaviors(
        skip_contextual=skip_contextual,
        skip_copyright=skip_copyright,
        categories=[category] if category else None,
        path=path,
    )
    if not behaviors:
        return []
    n = max(1, int(n))
    rng = random.Random(int(seed))
    if category:
        pool = list(behaviors)
        rng.shuffle(pool)
        return pool[:n]
    by_cat: dict[str, list[Behavior]] = {}
    for b in behaviors:
        by_cat.setdefault(b.category or "unspecified", []).append(b)
    for lst in by_cat.values():
        rng.shuffle(lst)
    out: list[Behavior] = []
    cats = sorted(by_cat)
    rng.shuffle(cats)
    i = 0
    while len(out) < n and any(by_cat[c] for c in cats):
        c = cats[i % len(cats)]
        if by_cat[c]:
            out.append(by_cat[c].pop())
        i += 1
    return out[:n]


def battery(
    *,
    category: str | None = None,
    n: int = 8,
    seed: int = 0,
    offline: bool = False,
    ensure: bool = True,
) -> list[Behavior]:
    """Ensure cache (unless offline) then sample n behaviors."""
    if ensure:
        st = ensure_dataset(offline=offline)
        if not st.get("ok") and not is_cached():
            return []
    return sample(category=category, n=n, seed=seed)


def status() -> dict[str, Any]:
    p = dataset_path()
    cached = is_cached()
    n = len(load_behaviors()) if cached else 0
    cats = categories() if cached else []
    return {
        "cached": cached,
        "path": str(p),
        "url": DATASET_URL,
        "n_behaviors": n,
        "categories": cats,
        "env_override": bool((os.environ.get("GARBLEWORKS_HARMBENCH_CSV") or "").strip()),
    }


def to_objectives(behaviors: list[Behavior]) -> list[dict[str, Any]]:
    return behaviors_to_bench_objectives(behaviors)
