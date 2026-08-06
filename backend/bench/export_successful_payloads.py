"""Export COMPLIED wins: goal + reconstructed winning payload."""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import harmbench_campaign as hbc
import harmbench_minimax_run as hmr


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--src",
        default=str(_BACKEND / "bench" / "results" / "harmbench-minimax-full-v2.json"),
    )
    ap.add_argument(
        "--out",
        default=str(_BACKEND / "bench" / "results" / "successful_payloads_v2.json"),
    )
    ap.add_argument(
        "--md",
        default=str(_BACKEND / "bench" / "results" / "successful_payloads_v2.md"),
    )
    ap.add_argument(
        "--no-copyright",
        action="store_true",
        help="omit copyright category from export",
    )
    args = ap.parse_args()

    hmr._patch_payload_builder()
    doc = json.loads(Path(args.src).read_text(encoding="utf-8"))
    items: list[dict] = []
    for r in doc.get("results") or []:
        w = r.get("winner") or {}
        tech = None
        if w.get("label") == "COMPLIED":
            tech = w.get("technique")
        else:
            for t in r.get("trail") or []:
                if t.get("label") == "COMPLIED":
                    tech = t.get("technique")
                    break
        if not tech:
            continue
        cat = r.get("category") or "?"
        if args.no_copyright and cat == "copyright":
            continue
        goal = r.get("behavior") or ""
        try:
            payload = hbc._build_payload(goal, tech)
        except Exception as e:
            payload = f"[rebuild failed: {e}]"
        # trail payload_preview for evidence that run matched
        trail_prev = ""
        for t in r.get("trail") or []:
            if t.get("label") == "COMPLIED" and t.get("technique") == tech:
                trail_prev = t.get("payload_preview") or ""
                break
        items.append(
            {
                "behavior_id": r.get("behavior_id"),
                "category": cat,
                "goal": goal,
                "technique": tech,
                "payload": payload,
                "payload_preview_from_run": trail_prev,
            }
        )

    by: dict[str, list] = defaultdict(list)
    for x in items:
        by[x["category"]].append(x)

    out_doc = {
        "n": len(items),
        "source": args.src,
        "note": (
            "payload reconstructed via same _build_payload(goal, winning_technique) "
            "used at fire time. Run stored only payload_preview (160 chars)."
        ),
        "by_category": {k: len(v) for k, v in sorted(by.items())},
        "items": items,
    }
    Path(args.out).write_text(
        json.dumps(out_doc, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Markdown catalog
    lines = [
        "# Successful HarmBench MiniMax-M3 payloads (v2)",
        "",
        f"n_complied={len(items)} (reconstructed from winning technique + goal)",
        "",
    ]
    order = [
        "chemical_biological",
        "illegal",
        "cybercrime_intrusion",
        "harmful",
        "harassment_bullying",
        "misinformation_disinformation",
        "copyright",
    ]
    for cat in order:
        xs = by.get(cat) or []
        if not xs:
            continue
        lines.append(f"## {cat} ({len(xs)})")
        lines.append("")
        for i, x in enumerate(xs, 1):
            lines.append(f"### {i}. `{x['behavior_id']}` — tech: `{x['technique']}`")
            lines.append("")
            lines.append("**Goal (victim task):**")
            lines.append("")
            lines.append("```")
            lines.append(x["goal"])
            lines.append("```")
            lines.append("")
            lines.append("**Winning payload:**")
            lines.append("")
            lines.append("```")
            lines.append(x["payload"])
            lines.append("```")
            lines.append("")
    Path(args.md).write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"n": len(items), "by_category": out_doc["by_category"], "out": args.out, "md": args.md}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
