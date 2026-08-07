"""CLI: python -m spine.ipi_cli list-templates | run | score-doc

Thin wrapper over spine.ipi_ops (same path as MCP).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    # Ensure backend on path when run as module from repo root
    backend = Path(__file__).resolve().parent.parent
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    p = argparse.ArgumentParser(
        prog="python -m spine.ipi_cli",
        description="Agentic IPI operator CLI (shared spine dual scorer)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list-templates", help="List IPI carrier templates")

    pr = sub.add_parser("run", help="Run ipi_template campaign")
    pr.add_argument(
        "--agent",
        default="mock_obey",
        help="mock_obey|mock_summarize|mock_snitch|mock_no_ingest|mock_detect|openai_tools",
    )
    pr.add_argument(
        "--templates",
        default="",
        help="Comma-separated template ids (default: all primary)",
    )
    pr.add_argument("--budget", type=int, default=None)
    pr.add_argument(
        "--objective-json",
        default="",
        help="Path to CampaignObjective JSON (optional)",
    )
    pr.add_argument(
        "--base-url",
        default="",
        help="For agent=openai_tools: OpenAI-compatible base URL",
    )
    pr.add_argument("--model", default="gpt-4o-mini")

    ps = sub.add_parser("score-doc", help="Score one document body file")
    ps.add_argument("path", help="Path to carrier document text")
    ps.add_argument("--agent", default="mock_obey")
    ps.add_argument("--role", default="report_fill")

    pp = sub.add_parser(
        "paste",
        help="Manual Gray Swan paste desk (NO auto-loop; stages clipboard only)",
    )
    pp.add_argument(
        "paste_args",
        nargs=argparse.REMAINDER,
        help="args for ipi_paste.py (next|record|pack|status|…)",
    )

    pc = sub.add_parser(
        "closed-loop",
        help="Full IPI closed loop (scenario bank + template×mutation ladder + checkpoint)",
    )
    pc.add_argument("--agent", default="mock_obey")
    pc.add_argument("--full", action="store_true")
    pc.add_argument("-n", type=int, default=0)
    pc.add_argument("--bank", default="")
    pc.add_argument("--checkpoint", default="")
    pc.add_argument("--out", default="")
    pc.add_argument("--budget", type=int, default=0)
    pc.add_argument("--base-url", default="")
    pc.add_argument("--model", default="gpt-4o-mini")
    pc.add_argument("--live-minimax", action="store_true", help="delegate to ipi_minimax_run --live")
    pc.add_argument("--peek", action="store_true")

    args = p.parse_args(argv)

    from spine import ipi_ops

    if args.cmd == "list-templates":
        rows = ipi_ops.list_ipi_templates()
        print(json.dumps(rows, indent=2))
        return 0

    if args.cmd == "run":
        objective = None
        if args.objective_json:
            objective = json.loads(Path(args.objective_json).read_text(encoding="utf-8"))
        tids = [t.strip() for t in (args.templates or "").split(",") if t.strip()] or None
        agent_kwargs = {}
        if args.base_url:
            agent_kwargs["base_url"] = args.base_url
            agent_kwargs["model"] = args.model
        out = ipi_ops.run_agentic_ipi(
            objective=objective,
            agent=args.agent,
            template_ids=tids,
            agent_kwargs=agent_kwargs or None,
            budget=args.budget,
        )
        print(json.dumps(out, indent=2, default=str))
        return 0 if not out.get("error") else 1

    if args.cmd == "score-doc":
        body = Path(args.path).read_text(encoding="utf-8")
        out = ipi_ops.run_agentic_ipi_single_document(
            body, agent=args.agent, document_role=args.role
        )
        print(json.dumps(out, indent=2, default=str))
        return 0

    if args.cmd == "paste":
        from ipi_paste import main as paste_main

        rest = list(args.paste_args or [])
        if rest and rest[0] == "--":
            rest = rest[1:]
        return int(paste_main(rest) or 0)

    if args.cmd == "closed-loop":
        # Live MiniMax path has its own CLI (RoE + secrets).
        if args.live_minimax:
            from ipi_minimax_run import main as mm_main

            rest: list[str] = []
            if args.full:
                rest.append("--full")
            if args.n:
                rest.extend(["-n", str(args.n)])
            if args.checkpoint:
                rest.extend(["--checkpoint", args.checkpoint])
            if args.out:
                rest.extend(["--out", args.out])
            if args.peek:
                rest.append("--peek")
            else:
                rest.append("--live")
            return int(mm_main(rest) or 0)

        import ipi_closed_loop as icl

        if args.peek:
            ckpt = args.checkpoint or str(
                Path(__file__).resolve().parent.parent
                / "bench"
                / "results"
                / "ipi-closed-loop-checkpoint.json"
            )
            doc = icl._load_checkpoint(Path(ckpt)) or {}
            print(icl.format_analysis(icl.analyze_checkpoint(doc)))
            return 0

        ak = {}
        agent = args.agent
        if args.base_url:
            agent = "openai_tools"
            ak = {"base_url": args.base_url, "model": args.model}
        max_n = None if args.full and not args.n else (args.n or (None if args.full else 2))
        out = icl.run_closed_loop(
            scenario_bank=args.bank or None,
            agent=agent,
            agent_kwargs=ak or None,
            checkpoint_path=args.checkpoint or None,
            out_path=args.out or None,
            budget_per_scenario=args.budget or None,
            max_scenarios=max_n,
        )
        print(
            json.dumps(
                {
                    "ok": out.get("ok"),
                    "n_success": out.get("n_success"),
                    "n_held": out.get("n_held"),
                    "asr": out.get("asr"),
                    "winning_techniques": out.get("winning_techniques"),
                    "checkpoint": out.get("checkpoint"),
                    "out": out.get("out"),
                },
                indent=2,
            )
        )
        return 0 if out.get("ok") else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
