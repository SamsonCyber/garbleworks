"""CLI: run Garbleworks (± Wallbreaker) on the local canary battery."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure backend/ on path
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from bench.adjudicate import adjudicate  # noqa: E402
from bench.battery import load_battery, battery_meta  # noqa: E402
from bench.metrics import (  # noqa: E402
    RunResult,
    markdown_report,
    paired_mcnemar,
    summarize,
)
from bench.runner_garbleworks import GarbleworksRunner  # noqa: E402
from bench.runner_wallbreaker import WallbreakerRunner, wallbreaker_available  # noqa: E402
from bench.target_chat import SECRET, start_server  # noqa: E402

_RESULTS = Path(__file__).resolve().parent / "results"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_tools(s: str) -> list[tuple[str, str]]:
    """'garbleworks:gw_baseline,wallbreaker' → [(tool, mode), ...]"""
    out: list[tuple[str, str]] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            tool, mode = part.split(":", 1)
        elif part in ("garbleworks", "gw"):
            tool, mode = "garbleworks", "gw_baseline"
        elif part in ("wallbreaker", "wb"):
            tool, mode = "wallbreaker", "wb_auto"
        else:
            tool, mode = part, "default"
        out.append((tool.strip(), mode.strip()))
    return out


def run_compare(
    tools: list[tuple[str, str]],
    battery_name: str = "v1_canary",
    target_mode: str = "deterministic",
    objective_ids: list[str] | None = None,
    tag: str = "",
) -> dict[str, Any]:
    objectives = load_battery(battery_name)
    if objective_ids:
        want = set(objective_ids)
        objectives = [o for o in objectives if o.id in want]

    srv, port, state = start_server(mode=target_mode, secret=SECRET)
    base_url = f"http://127.0.0.1:{port}/v1"
    secret = state.secret

    runners = []
    for tool, mode in tools:
        if tool in ("garbleworks", "gw"):
            runners.append(GarbleworksRunner(mode=mode if mode != "default" else "gw_baseline"))
        elif tool in ("wallbreaker", "wb"):
            if not wallbreaker_available():
                print(f"[skip] wallbreaker not installed", file=sys.stderr)
                continue
            runners.append(WallbreakerRunner())
        else:
            print(f"[skip] unknown tool {tool}", file=sys.stderr)

    rows: list[RunResult] = []
    t_all = time.perf_counter()
    try:
        for runner in runners:
            for obj in objectives:
                print(f"→ {runner.tool}/{runner.mode} :: {obj.id} ...", flush=True)
                row = runner.run(obj, base_url=base_url, secret=secret)
                rows.append(row)
                flag = "WIN" if row.success else "miss"
                print(
                    f"  {flag} q={row.queries} wall={row.wall_s:.1f}s "
                    f"claimed={row.tool_claimed_success} {row.error or ''}",
                    flush=True,
                )
    finally:
        srv.shutdown()

    # Tag plumbing estimand from objective meta when present
    for r in rows:
        if not r.estimand and r.class_ == "easy":
            r.estimand = "plumbing_ceiling"

    # Summaries per (tool, mode)
    keys = sorted({(r.tool, r.mode) for r in rows})
    summaries = [summarize(rows, t, m) for t, m in keys]
    from bench.metrics import (
        BASELINE_V1_CELLS,
        promotions_from_summaries,
        stratified_summaries,
    )
    stratified = stratified_summaries(rows)
    promotions = promotions_from_summaries(summaries, baseline=BASELINE_V1_CELLS)

    pairs = []
    # Pair first two tool/modes if present
    if len(keys) >= 2:
        a_t, a_m = keys[0]
        b_t, b_m = keys[1]
        a_rows = [r for r in rows if r.tool == a_t and r.mode == a_m]
        b_rows = [r for r in rows if r.tool == b_t and r.mode == b_m]
        p = paired_mcnemar(a_rows, b_rows)
        p["label"] = f"{a_t}/{a_m} vs {b_t}/{b_m}"
        pairs.append(p)

    stamp = _utc()
    title = f"Bench compare {stamp}" + (f" [{tag}]" if tag else "")
    payload = {
        "stamp": stamp,
        "tag": tag or None,
        "battery": battery_name,
        "battery_meta": battery_meta(battery_name),
        "target": {
            "base_url": base_url,
            "mode": target_mode,
            "cloud": False,
            "secret_len": len(secret),
        },
        "wallbreaker_available": wallbreaker_available(),
        "seconds": round(time.perf_counter() - t_all, 3),
        "summaries": [s.as_dict() for s in summaries],
        "stratified": {k: [s.as_dict() for s in v] for k, v in stratified.items()},
        "promotions": promotions,
        "pairs": pairs,
        "rows": [r.as_dict() for r in rows],
    }

    _RESULTS.mkdir(parents=True, exist_ok=True)
    json_path = _RESULTS / f"{stamp}-compare.json"
    md_path = _RESULTS / f"{stamp}-compare.md"
    latest_json = _RESULTS / "compare-latest.json"
    latest_md = _RESULTS / "compare-latest.md"

    text = json.dumps(payload, indent=2)
    md = markdown_report(
        title, summaries, pairs, rows,
        estimand=(battery_meta(battery_name) or {}).get("estimand_note"),
        promotions=promotions,
        stratified=stratified,
    )
    json_path.write_text(text, encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    latest_json.write_text(text, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")

    print(md)
    print(f"\nWrote {json_path}", flush=True)
    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Garbleworks vs Wallbreaker local canary A/B (no cloud)",
    )
    p.add_argument(
        "--tools",
        default="garbleworks:gw_baseline,garbleworks:gw_optimize",
        help="Comma list tool or tool:mode (gw_baseline,gw_optimize,gw_pack_hunt,wallbreaker)",
    )
    p.add_argument("--battery", default="v1_canary")
    p.add_argument(
        "--target-mode",
        default="deterministic",
        choices=["deterministic", "ollama", "openai_compat", "minimax"],
        help="minimax/openai_compat: real remote TARGET (not ablit generator)",
    )
    p.add_argument("--only", default="", help="Comma objective ids to run")
    p.add_argument("--tag", default="")
    args = p.parse_args(argv)

    tools = _parse_tools(args.tools)
    only = [x.strip() for x in args.only.split(",") if x.strip()] or None
    run_compare(
        tools,
        battery_name=args.battery,
        target_mode=args.target_mode,
        objective_ids=only,
        tag=args.tag,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
