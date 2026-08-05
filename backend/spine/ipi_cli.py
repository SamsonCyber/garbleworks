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

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
