"""RoE-gated live canary battery against in-scope local targets.

Runs the real bench (compare.run_compare) only when:
  1. An AuthorizationReceipt is loaded (env or --roe file)
  2. Target host is in authorized_scope
  3. evidence_required path writes claim-gated results

This is not a cloud multi-provider leaderboard. Default: Ollama-backed
local canary on 127.0.0.1 (operator-owned models).

Usage:
  cd backend
  python -m bench.roe_live_battery --roe engagements/local-selftest-roe.json
  python -m bench.roe_live_battery --roe engagements/local-selftest-roe.json \\
      --tools garbleworks:gw_baseline --battery v1_canary --target-mode ollama

Exit codes:
  0 — completed; at least one promotable cell (or --no-require-promote)
  1 — RoE / scope failure
  2 — completed but nothing promotable under claim gates
  3 — runtime error
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import authority
from bench import live_efficacy as le
from bench.compare import run_compare
from bench.metrics import (
    MIN_N_EFFICACY,
    MIN_N_PROMOTE,
    complete_case_overall,
    promotion_decision,
    summarize,
)
from bench.metrics import RunResult


def load_roe(path: str | None) -> authority.AuthorizationReceipt:
    if path:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return authority.AuthorizationReceipt(
            engagement_id=str(raw.get("engagement_id") or "unnamed"),
            authorized_scope=list(raw.get("authorized_scope") or []),
            permitted_roles=list(raw.get("permitted_roles") or [
                "recon", "scanner", "attacker", "judge",
            ]),
            auto_allowed=list(raw.get("auto_allowed") or []),
            approval_required=list(raw.get("approval_required") or []),
            evidence_required=bool(raw.get("evidence_required", True)),
            authority_source=str(
                raw.get("authority_source") or "operator-supplied RoE file"
            ),
            notes=str(raw.get("notes") or ""),
        )
    return authority.receipt_from_env()


def assert_host_in_scope(host: str, receipt: authority.AuthorizationReceipt) -> None:
    h = (host or "").strip().lower()
    if not h:
        raise SystemExit("RoE: empty host")
    if not receipt.in_scope(h):
        raise SystemExit(
            f"SCOPE DENIED under RoE engagement {receipt.engagement_id}: "
            f"host {h!r} not in {receipt.authorized_scope}"
        )


def _rows_to_claim_doc(
    rows: list[dict[str, Any]],
    *,
    receipt: authority.AuthorizationReceipt,
    tag: str,
    technique: str,
    target_desc: str,
    dry_run: bool,
    battery: str,
    target_mode: str,
) -> dict[str, Any]:
    overall = complete_case_overall(rows)
    s = int(overall["successes"])
    n_c = int(overall["n_completed"])
    min_n = MIN_N_EFFICACY if n_c >= MIN_N_EFFICACY else MIN_N_PROMOTE
    pd = promotion_decision(
        s_new=s,
        n_new=n_c,
        min_n=min_n,
        label=f"{technique}:{tag}",
    )
    claim_ready = bool(pd.get("promote")) and n_c >= min_n
    doc = {
        "schema_version": le.SCHEMA_VERSION,
        "tag": tag,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dry_run": dry_run,
        "n_requested": len(rows),
        "engagement_id": receipt.engagement_id,
        "authority_source": receipt.authority_source,
        "authorized_scope": list(receipt.authorized_scope),
        "target_desc": target_desc,
        "technique": technique,
        "battery": battery,
        "target_mode": target_mode,
        "complete_case": overall,
        "promotion": pd,
        "claim_ready": claim_ready,
        "heldout_lcb": overall.get("asr_lcb"),
        "heldout_ucb": overall.get("asr_ucb"),
        "exit_code": 0 if claim_ready else (1 if s <= 0 else 2),
        "notes": (
            "Live RoE battery against in-scope local canary. "
            "Plumbing (easy unlocks) ≠ frontier multi-provider ASR. "
            "Publish only cells with claim_ready / promotable LCB."
        ),
    }
    errs = le.validate_result_schema(doc)
    if errs:
        doc["schema_warnings"] = errs
    return doc


def run_roe_battery(
    *,
    receipt: authority.AuthorizationReceipt,
    tools: str = "garbleworks:gw_baseline",
    battery: str = "v1_canary",
    target_mode: str = "ollama",
    only: list[str] | None = None,
    tag: str = "roe-live",
    require_promote: bool = False,
) -> dict[str, Any]:
    # Canary always binds 127.0.0.1 — must be in scope
    assert_host_in_scope("127.0.0.1", receipt)
    assert_host_in_scope("localhost", receipt)

    import llm
    if target_mode == "ollama" and not llm.reachable():
        raise SystemExit(
            "RoE live ollama mode requires local Ollama at "
            f"{llm.DEFAULT_URL} (SCOPE: loopback only). Not reachable."
        )
    if target_mode in ("openai_compat", "minimax"):
        from bench import target_chat as tc
        try:
            cfg = tc.resolve_openai_compat_config(target_mode)
            print(
                f"target brain: model={cfg['model']} base={cfg['base_url']} "
                f"(API key loaded, not printed)",
                flush=True,
            )
        except ValueError as e:
            raise SystemExit(f"RoE remote target config: {e}") from e

    from bench.compare import _parse_tools

    tool_list = _parse_tools(tools)
    payload = run_compare(
        tool_list,
        battery_name=battery,
        target_mode=target_mode,
        objective_ids=only,
        tag=tag,
    )

    # Attach RoE + claim document
    rows = payload.get("rows") or []
    claim_doc = _rows_to_claim_doc(
        rows,
        receipt=receipt,
        tag=tag,
        technique=tools,
        target_desc=f"bench canary mode={target_mode} on 127.0.0.1",
        dry_run=False,
        battery=battery,
        target_mode=target_mode,
    )
    payload["roe"] = {
        "engagement_id": receipt.engagement_id,
        "authority_source": receipt.authority_source,
        "authorized_scope": list(receipt.authorized_scope),
        "evidence_required": receipt.evidence_required,
        "notes": receipt.notes,
    }
    payload["live_asr_claim"] = claim_doc
    payload["llm"] = {
        "url": getattr(llm, "DEFAULT_URL", ""),
        "model": getattr(llm, "DEFAULT_MODEL", ""),
        "reachable": llm.reachable(),
    }

    # Per-cell promotions from summaries
    promotable_cells = [
        p for p in (payload.get("promotions") or [])
        if isinstance(p, dict) and p.get("promote")
    ]
    payload["roe_summary"] = {
        "engagement_id": receipt.engagement_id,
        "claim_ready_overall": claim_doc["claim_ready"],
        "complete_case": claim_doc["complete_case"],
        "promotable_cells": len(promotable_cells),
        "n_rows": len(rows),
        "target_mode": target_mode,
    }

    # Persist RoE-stamped copy
    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = payload.get("stamp") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    roe_path = results_dir / f"{stamp}-roe-live.json"
    claim_path = results_dir / f"{stamp}-live-asr-claim.json"
    roe_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    claim_path.write_text(json.dumps(claim_doc, indent=2), encoding="utf-8")
    # latest
    (results_dir / "roe-live-latest.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    (results_dir / "live-asr-claim-latest.json").write_text(
        json.dumps(claim_doc, indent=2), encoding="utf-8"
    )
    payload["_roe_paths"] = {
        "full": str(roe_path),
        "claim": str(claim_path),
    }
    return payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="RoE-gated live canary battery")
    p.add_argument(
        "--roe",
        default="",
        help="Path to RoE JSON (else receipt_from_env)",
    )
    p.add_argument("--tools", default="garbleworks:gw_baseline")
    p.add_argument("--battery", default="v1_canary")
    p.add_argument(
        "--target-mode",
        default="ollama",
        choices=["deterministic", "ollama", "openai_compat", "minimax"],
        help="minimax = MiniMax-M3 as TARGET (guarded); not the ablit generator",
    )
    p.add_argument("--only", default="", help="Comma objective ids")
    p.add_argument("--tag", default="roe-live")
    p.add_argument(
        "--require-promote",
        action="store_true",
        help="Exit 2 if overall claim_ready is false",
    )
    args = p.parse_args(argv)

    try:
        receipt = load_roe(args.roe or None)
    except Exception as e:
        print(f"RoE load failed: {e}", file=sys.stderr)
        return 1

    print(
        f"RoE engagement={receipt.engagement_id} "
        f"scope={receipt.authorized_scope} "
        f"authority={receipt.authority_source}",
        flush=True,
    )
    only = [x.strip() for x in args.only.split(",") if x.strip()] or None
    try:
        payload = run_roe_battery(
            receipt=receipt,
            tools=args.tools,
            battery=args.battery,
            target_mode=args.target_mode,
            only=only,
            tag=args.tag,
            require_promote=bool(args.require_promote),
        )
    except SystemExit as e:
        print(str(e), file=sys.stderr)
        return 1
    except Exception as e:
        print(f"RUNTIME: {type(e).__name__}: {e}", file=sys.stderr)
        return 3

    claim = payload.get("live_asr_claim") or {}
    summ = payload.get("roe_summary") or {}
    print("\n=== RoE LIVE SUMMARY ===", flush=True)
    print(json.dumps(summ, indent=2), flush=True)
    print(
        f"claim_ready={claim.get('claim_ready')} "
        f"asr={claim.get('complete_case', {}).get('asr')} "
        f"lcb={claim.get('heldout_lcb')} "
        f"n_completed={claim.get('complete_case', {}).get('n_completed')}",
        flush=True,
    )
    paths = payload.get("_roe_paths") or {}
    print(f"wrote {paths.get('full')}", flush=True)
    print(f"wrote {paths.get('claim')}", flush=True)

    if args.require_promote and not claim.get("claim_ready"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
