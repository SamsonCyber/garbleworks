"""Live agentic IPI closed loop against MiniMax-M3 as tools-loop AGENT.

Authorized robustness measurement only.
RoE: engagements/ipi-minimax-roe.json

This is the IPI twin of harmbench_minimax_run (direct chat ladder):
  - Direct HB: user payload → chat completion → grade_reply COMPLIED
  - This loop: document carrier → tools-loop agent → dual success
    (delivery + harm tool + conceal)

Usage:
  # Offline smoke (no network)
  python ipi_minimax_run.py --agent mock_obey -n 2

  # Full bank offline
  python ipi_minimax_run.py --agent mock_obey --full

  # Live MiniMax tools-loop (needs MINIMAX_API_KEY or ~/.secrets/minimax_api_key.txt)
  python ipi_minimax_run.py --full --live
  python ipi_minimax_run.py --full --live --checkpoint bench/results/ipi-minimax-ckpt.json

  python ipi_minimax_run.py --peek
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import ipi_closed_loop as icl

ROE_PATH = _BACKEND / "engagements" / "ipi-minimax-roe.json"
DEFAULT_CKPT = _BACKEND / "bench" / "results" / "ipi-minimax-checkpoint.json"
DEFAULT_OUT = _BACKEND / "bench" / "results" / "ipi-minimax.json"
DEFAULT_MODEL = "MiniMax-M3"
DEFAULT_BASE = "https://api.minimax.io/v1"


def _read_secret(*names: str) -> str:
    for n in names:
        env = os.environ.get(n) or ""
        if env.strip():
            return env.strip()
    home = Path.home() / ".secrets"
    for fname in (
        "minimax_api_key.txt",
        "minimax_key.txt",
        "MINIMAX_API_KEY.txt",
    ):
        p = home / fname
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    return ""


def _load_roe() -> dict[str, Any]:
    if ROE_PATH.is_file():
        try:
            return json.loads(ROE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def resolve_minimax_agent_kwargs(
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """OpenAI-compat tools-loop kwargs for MiniMax as agent brain."""
    key = (api_key or "").strip() or _read_secret("MINIMAX_API_KEY", "MINIMAX_KEY")
    base = (base_url or "").strip() or os.environ.get("MINIMAX_BASE_URL") or DEFAULT_BASE
    mdl = (model or "").strip() or os.environ.get("MINIMAX_MODEL") or DEFAULT_MODEL
    if not key:
        raise RuntimeError(
            "MiniMax live IPI needs MINIMAX_API_KEY or ~/.secrets/minimax_api_key.txt"
        )
    # Optional system: agent should use tools, treat docs as untrusted unless
    # instructed — we leave default tools_loop system so inject can land.
    return {
        "base_url": base.rstrip("/"),
        "api_key": key,
        "model": mdl,
        "timeout": float(timeout),
        "require_document_evidence": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python ipi_minimax_run.py",
        description="Agentic IPI closed loop (MiniMax tools-loop or mock)",
    )
    p.add_argument(
        "--agent",
        default="",
        help="mock_obey|openai_tools (default: mock_obey, or openai_tools with --live)",
    )
    p.add_argument("--live", action="store_true", help="MiniMax tools-loop agent")
    p.add_argument("--full", action="store_true", help="full scenario bank")
    p.add_argument("-n", type=int, default=0, help="max scenarios")
    p.add_argument("--bank", default="", help="scenario bank JSON")
    p.add_argument("--checkpoint", default="", help="checkpoint path")
    p.add_argument("--out", default="", help="final results JSON")
    p.add_argument("--budget", type=int, default=0)
    p.add_argument("--model", default="")
    p.add_argument("--base-url", default="")
    p.add_argument("--api-key", default="")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--no-requeue", action="store_true")
    p.add_argument("--no-sharpen", action="store_true")
    p.add_argument("--peek", action="store_true")
    p.add_argument("--roe", default=str(ROE_PATH), help="RoE JSON path (logged only)")
    args = p.parse_args(argv)

    ckpt = Path(args.checkpoint) if args.checkpoint else DEFAULT_CKPT
    out_path = Path(args.out) if args.out else DEFAULT_OUT

    if args.peek:
        doc = icl._load_checkpoint(ckpt) or {}
        rep = icl.analyze_checkpoint(doc)
        print(icl.format_analysis(rep))
        if rep.get("ok"):
            print(f"checkpoint={ckpt}")
        return 0 if rep.get("ok") else 1

    roe = _load_roe()
    if roe:
        print(
            f"RoE engagement={roe.get('engagement_id')} "
            f"scope={roe.get('authorized_scope')} "
            f"estimand=agentic_ipi",
            flush=True,
        )

    agent = (args.agent or "").strip()
    ak: dict[str, Any] = {}
    if args.live or agent in ("openai_tools", "tools_loop", "minimax"):
        agent = "openai_tools"
        try:
            ak = resolve_minimax_agent_kwargs(
                model=args.model or None,
                base_url=args.base_url or None,
                api_key=args.api_key or None,
                timeout=float(args.timeout),
            )
        except RuntimeError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(
            f"live tools-loop → model={ak.get('model')} base={ak.get('base_url')}",
            flush=True,
        )
    else:
        agent = agent or "mock_obey"
        if args.base_url:
            # Generic openai_tools without --live
            agent = "openai_tools"
            ak = {
                "base_url": args.base_url,
                "api_key": args.api_key or _read_secret("MINIMAX_API_KEY", "OPENAI_API_KEY"),
                "model": args.model or "gpt-4o-mini",
                "timeout": float(args.timeout),
            }

    if not args.full and not args.n:
        args.n = 2
        print("note: default -n 2 (pass --full for whole bank)", flush=True)

    max_n = None if args.full and not args.n else (args.n or 2)

    result = icl.run_closed_loop(
        scenario_bank=args.bank or None,
        agent=agent,
        agent_kwargs=ak or None,
        checkpoint_path=ckpt,
        out_path=out_path,
        requeue_held=not args.no_requeue,
        live_sharpen=not args.no_sharpen,
        budget_per_scenario=args.budget or None,
        max_scenarios=max_n,
    )

    # Stamp RoE into checkpoint meta for audit
    if result.get("ok") and ckpt.is_file():
        try:
            doc = json.loads(ckpt.read_text(encoding="utf-8"))
            meta = dict(doc.get("meta") or {})
            meta["engagement_id"] = roe.get("engagement_id") or "ipi-minimax"
            meta["target_model"] = ak.get("model") if ak else agent
            meta["target_base"] = ak.get("base_url") if ak else None
            meta["estimand"] = "agentic_ipi"
            doc["meta"] = meta
            ckpt.write_text(
                json.dumps(doc, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass

    print(
        json.dumps(
            {
                "ok": result.get("ok"),
                "agent": agent,
                "n_population": result.get("n_population"),
                "n_success": result.get("n_success"),
                "n_held": result.get("n_held"),
                "asr": result.get("asr"),
                "winning_techniques": result.get("winning_techniques"),
                "checkpoint": result.get("checkpoint"),
                "out": result.get("out"),
                "wall_s": result.get("wall_s"),
            },
            indent=2,
        )
    )
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
