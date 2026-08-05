"""Garbleworks — one operator CLI (primary offline + thin advanced wrappers).

Primary install/demo:
  python harness_cli.py scan
  python harness_cli.py modules
  python harness_cli.py toggle

Also: python -m garbleworks  (same entry via garbleworks.py)

Advanced subcommands call existing modules; they are not peer product roots.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="garbleworks",
        description="Garbleworks single harness CLI (modular ops, one fire policy).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "primary:\n"
            "  garbleworks scan                 offline compose demo (no HTTP)\n"
            "  garbleworks modules              list module packs\n"
            "  garbleworks toggle               disable/enable one pack (self-check)\n"
            "\n"
            "advanced (same core, not separate products):\n"
            "  garbleworks auto …               multi-strategy agent_loop\n"
            "  garbleworks harmbench …          real HarmBench battery (ensure/sample/campaign)\n"
            "  garbleworks serve                uvicorn HTTP API (app:app)\n"
            "  garbleworks mcp                  print MCP stdio launch hint\n"
            "\n"
            "full offline suite:  python ../scripts/repro.py\n"
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="Offline compose demo over enabled ops")
    s.add_argument("--text", default="authorized research objective")
    s.add_argument("--max-ops", type=int, default=5)

    sub.add_parser("modules", help="List module packs and enable counts")
    sub.add_parser("toggle", help="Disable then re-enable one module pack")

    a = sub.add_parser("auto", help="Advanced: agent_loop multi-strategy --auto")
    a.add_argument("auto_args", nargs=argparse.REMAINDER, help="args passed to agent_loop")

    hb = sub.add_parser(
        "harmbench",
        help="Real HarmBench: ensure / status / list / sample / campaign",
    )
    hb.add_argument(
        "hb_args",
        nargs=argparse.REMAINDER,
        help="args for harmbench CLI (status|ensure|list|sample|campaign …)",
    )

    sub.add_parser("serve", help="Advanced: run FastAPI app (uvicorn)")
    sub.add_parser("mcp", help="Print how to run MCP stdio server")

    args = p.parse_args(argv)

    if args.cmd == "scan":
        from harness import offline_scan_demo

        report = offline_scan_demo(text=args.text, max_ops=args.max_ops)
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok") else 1

    if args.cmd == "modules":
        from harness import list_modules

        print(json.dumps(list_modules(), indent=2))
        return 0

    if args.cmd == "toggle":
        from harness import module_toggle_demo

        report = module_toggle_demo()
        print(json.dumps(report, indent=2))
        return 0 if report.get("ok") and report.get("restored") else 1

    if args.cmd == "auto":
        from agent_loop import main as agent_main

        # agent_loop.main reads sys.argv; rebuild for it
        rest = list(args.auto_args or [])
        if rest and rest[0] == "--":
            rest = rest[1:]
        old = sys.argv
        try:
            sys.argv = ["agent_loop", *rest]
            return int(agent_main() or 0)
        finally:
            sys.argv = old

    if args.cmd == "harmbench":
        from harmbench_campaign import main as hb_main

        rest = list(args.hb_args or [])
        if rest and rest[0] == "--":
            rest = rest[1:]
        if not rest:
            rest = ["status"]
        return int(hb_main(rest) or 0)

    if args.cmd == "serve":
        import uvicorn

        print("serving primary FastAPI app (garbleworks.backend.app)", file=sys.stderr)
        uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
        return 0

    if args.cmd == "mcp":
        print(
            json.dumps(
                {
                    "command": sys.executable,
                    "args": [str(_BACKEND / "mcp_server.py")],
                    "env": {"PYTHONPATH": str(_BACKEND)},
                    "note": "single primary tree; do not dual-stack payload-mutator",
                },
                indent=2,
            )
        )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
