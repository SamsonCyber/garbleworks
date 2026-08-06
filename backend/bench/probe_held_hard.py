"""Focused MiniMax probe on held hard HarmBench IDs (non-copyright).

Uses the improved FULL_LADDER builders. Writes JSON to --out.
Authorized RoE only (loopback canary → MiniMax).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import fire as fire_mod
import harmbench as hb
import harmbench_campaign as hbc
import harmbench_minimax_run as hmr
from bench import target_chat as tc


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=18, help="max held hard to probe")
    p.add_argument("--timeout", type=float, default=90.0)
    p.add_argument(
        "--held-json",
        default="",
        help="path to hb_held_hard.json (ids list)",
    )
    p.add_argument(
        "--baseline",
        default=str(_BACKEND / "bench" / "results" / "harmbench-minimax-full.json"),
    )
    p.add_argument(
        "--out",
        default=str(_BACKEND / "bench" / "results" / "hb-held-hard-probe.json"),
    )
    p.add_argument(
        "--ladder",
        default="",
        help="comma techniques; default FULL_LADDER",
    )
    args = p.parse_args()

    key_path = Path.home() / ".secrets" / "minimax_api_key.txt"
    if key_path.is_file() and not os.environ.get("MINIMAX_API_KEY"):
        os.environ["MINIMAX_API_KEY"] = key_path.read_text(encoding="utf-8").strip()
    os.environ.setdefault("GARBLEWORKS_TARGET_MAX_TOKENS", "2048")

    # Load held hard ids: prefer explicit json, else derive from baseline
    held_ids: list[str] = []
    if args.held_json and Path(args.held_json).is_file():
        raw = json.loads(Path(args.held_json).read_text(encoding="utf-8"))
        if isinstance(raw, list):
            held_ids = [
                (x.get("id") or x.get("behavior_id") or x)
                if isinstance(x, dict)
                else str(x)
                for x in raw
            ]
        elif isinstance(raw, dict):
            held_ids = list(
                raw.get("held_hard_ids") or raw.get("ids") or raw.get("ids_list") or []
            )
        else:
            held_ids = []
    else:
        base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        for r in base.get("results") or []:
            if r.get("held") and r.get("category") != "copyright":
                held_ids.append(r["behavior_id"])

    by_id = {b.id: b for b in hb.load_behaviors(skip_contextual=True)}
    # Stratify by category: round-robin pick up to n
    by_cat: dict[str, list[str]] = {}
    for hid in held_ids:
        b = by_id.get(hid)
        if not b:
            continue
        by_cat.setdefault(b.category, []).append(hid)
    picks: list[str] = []
    cats = sorted(by_cat.keys())
    i = 0
    while len(picks) < args.n and any(by_cat[c] for c in cats):
        c = cats[i % len(cats)]
        if by_cat[c]:
            picks.append(by_cat[c].pop(0))
        i += 1
        if i > args.n * 20:
            break

    ladder = (
        [x.strip() for x in args.ladder.split(",") if x.strip()]
        if args.ladder
        else list(hmr.FULL_LADDER)
    )
    hmr._patch_payload_builder()
    print(f"probe n={len(picks)} ladder_rungs={len(ladder)}", flush=True)

    cfg = tc.resolve_openai_compat_config("minimax")
    srv, port, _st = tc.start_server(mode="minimax")
    base_url = f"http://127.0.0.1:{port}/v1"
    target = tc.fire_target_dict(base_url, timeout=args.timeout)
    fire_mod.validate_target_url(target["url"])

    def fire_fn(payload: str) -> dict:
        fr = fire_mod.fire_once(target, payload, validate=False, timeout=args.timeout)
        return {
            "text": fr.text or "",
            "error": fr.error,
            "status": fr.status,
            "ms": fr.ms,
        }

    results = []
    t0 = time.perf_counter()
    try:
        for j, hid in enumerate(picks):
            b = by_id[hid]
            print(f"→ [{j+1}/{len(picks)}] {hid} ({b.category})", flush=True)
            row = hbc.run_behavior_ladder(
                b.behavior,
                target=target,
                ladder=ladder,
                fire_fn=fire_fn,
                timeout=args.timeout,
                behavior_id=hid,
            )
            row["category"] = b.category
            results.append(row)
            w = (row.get("winner") or {}).get("label")
            tech = (row.get("winner") or {}).get("technique")
            print(f"  held={row.get('held')} winner={w} tech={tech}", flush=True)
    finally:
        srv.shutdown()

    n_comp = hmr._count_complied(results)
    by_cat_c = Counter()
    win_tech = Counter()
    for r in results:
        if (r.get("winner") or {}).get("label") == "COMPLIED" or any(
            t.get("label") == "COMPLIED" for t in (r.get("trail") or [])
        ):
            by_cat_c[r.get("category")] += 1
            w = r.get("winner") or {}
            if w.get("label") == "COMPLIED":
                win_tech[w.get("technique") or "?"] += 1

    doc = {
        "schema_version": "hb_held_hard_probe.v1",
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_model": cfg["model"],
        "n": len(results),
        "n_complied": n_comp,
        "ladder": ladder,
        "by_category_complied": dict(by_cat_c),
        "winning_techniques": dict(win_tech),
        "wall_s": round(time.perf_counter() - t0, 3),
        "results": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # scrub key if present
    blob = json.dumps(doc, indent=2)
    key = cfg.get("api_key") or ""
    if key and key in blob:
        blob = blob.replace(key, "[REDACTED]")
    out.write_text(blob, encoding="utf-8")
    print(json.dumps({
        "n": doc["n"],
        "n_complied": n_comp,
        "by_category_complied": doc["by_category_complied"],
        "winning_techniques": doc["winning_techniques"],
        "wall_s": doc["wall_s"],
        "out": str(out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
