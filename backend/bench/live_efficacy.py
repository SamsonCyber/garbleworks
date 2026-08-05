"""Live / dry-run efficacy battery entry (n≥30 claim path).

G6: schema + dry-run for CI; live fires only with authorized target + keys.
Never invent multi-model leaderboard numbers. Dry-run uses mock all-leak rows
to exercise promotion / exit codes only.

Usage:
  python -m bench.live_efficacy --dry-run --n 30 --require-promote --tag smoke
  python -m bench.live_efficacy --help

Result JSON schema: see RESULT_SCHEMA and docs/LIVE-ASR-RUNBOOK.md
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bench.metrics import (
    MIN_N_EFFICACY,
    complete_case_overall,
    exit_code_for_claim,
    promotion_decision,
    wilson_lcb,
    wilson_ucb,
)

# JSON Schema-ish (docs + validation light check)
RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": [
        "schema_version",
        "tag",
        "timestamp",
        "dry_run",
        "n_requested",
        "engagement_id",
        "target_desc",
        "technique",
        "complete_case",
        "promotion",
        "claim_ready",
        "exit_code",
    ],
    "properties": {
        "schema_version": {"const": "live_asr.v1"},
        "tag": {"type": "string"},
        "timestamp": {"type": "string"},
        "dry_run": {"type": "boolean"},
        "n_requested": {"type": "integer", "minimum": 1},
        "engagement_id": {"type": "string"},
        "target_desc": {"type": "string"},
        "technique": {"type": "string"},
        "complete_case": {"type": "object"},
        "promotion": {"type": "object"},
        "claim_ready": {"type": "boolean"},
        "exit_code": {"type": "integer"},
        "rows": {"type": "array"},
        "notes": {"type": "string"},
    },
}

SCHEMA_VERSION = "live_asr.v1"


def validate_result_schema(doc: dict[str, Any]) -> list[str]:
    """Lightweight required-field check (no jsonschema dep)."""
    errs: list[str] = []
    for k in RESULT_SCHEMA["required"]:
        if k not in doc:
            errs.append(f"missing required field: {k}")
    if doc.get("schema_version") != SCHEMA_VERSION:
        errs.append(f"schema_version must be {SCHEMA_VERSION!r}")
    return errs


def _mock_rows(n: int, *, leak_all: bool = True) -> list[dict[str, Any]]:
    rows = []
    for i in range(n):
        if leak_all:
            rows.append({
                "trial": i,
                "success": True,
                "outcome": "leak",
                "error": None,
            })
        else:
            rows.append({
                "trial": i,
                "success": False,
                "outcome": "no_leak",
                "error": None,
            })
    return rows


def build_result(
    rows: list[dict[str, Any]],
    *,
    tag: str,
    dry_run: bool,
    n_requested: int,
    engagement_id: str,
    target_desc: str,
    technique: str,
    require_promote: bool,
    min_n: int = MIN_N_EFFICACY,
) -> dict[str, Any]:
    overall = complete_case_overall(rows)
    s = int(overall["successes"])
    n_c = int(overall["n_completed"])
    pd = promotion_decision(
        s_new=s,
        n_new=n_c,
        min_n=min_n,
        label=f"{technique}:{tag}",
    )
    code = exit_code_for_claim(
        successes=s,
        n_completed=n_c,
        promote=bool(pd.get("promote")),
        require_promote=require_promote,
    )
    # claim_ready: LCB clears soft bar with n ≥ min_n (aligned with G4 spirit)
    claim_ready = bool(pd.get("promote")) and n_c >= min_n
    doc = {
        "schema_version": SCHEMA_VERSION,
        "tag": tag,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dry_run": dry_run,
        "n_requested": n_requested,
        "engagement_id": engagement_id,
        "target_desc": target_desc,
        "technique": technique,
        "complete_case": overall,
        "promotion": pd,
        "claim_ready": claim_ready,
        "heldout_lcb": overall.get("asr_lcb"),
        "heldout_ucb": overall.get("asr_ucb"),
        "exit_code": code,
        "rows": rows if n_requested <= 50 else rows[:50],  # cap stored rows
        "notes": (
            "dry_run exercises promotion plumbing only — not frontier ASR. "
            "Live runs require authorization, engagement_id, and real target."
            if dry_run
            else "Live run; publish only if claim_ready and promotion.promote."
        ),
    }
    return doc


def build_scoreboard_claim(
    *,
    n: int = MIN_N_EFFICACY,
    tag: str = "scoreboard-dry",
    dry_run: bool = True,
    leak_all: bool = True,
    engagement_id: str = "local-selftest",
    target_desc: str = "dry-run-mock (not a frontier model)",
    technique: str = "mock_prefill",
    require_promote: bool = False,
    min_n: int = MIN_N_EFFICACY,
) -> dict[str, Any]:
    """Build a live_asr.v1 claim document (scoreboard artifact).

    dry_run=True uses mock rows to exercise n≥30 complete-case + promotion plumbing.
    Never treat mock all-leak dry_run as a multi-provider frontier leaderboard.
    """
    n = max(1, int(n))
    if not dry_run:
        raise ValueError(
            "live multi-model fire is not wired in build_scoreboard_claim; "
            "use dry_run=True or docs/LIVE-ASR-RUNBOOK.md for operator live path"
        )
    rows = _mock_rows(n, leak_all=leak_all)
    doc = build_result(
        rows,
        tag=tag,
        dry_run=True,
        n_requested=n,
        engagement_id=engagement_id,
        target_desc=target_desc,
        technique=technique,
        require_promote=require_promote,
        min_n=min_n,
    )
    doc["artifact"] = "scoreboard_claim"
    doc["notes"] = (
        "dry_run scoreboard artifact — exercises live_asr.v1 schema and "
        "promotion plumbing only. Mock all-leak rows are NOT a frontier "
        "multi-model ASR leaderboard. Do not publish as product ASR."
    )
    doc["disclaimer"] = (
        "NOT a multi-provider frontier leaderboard. "
        f"dry_run={doc['dry_run']}; n_requested={doc['n_requested']}."
    )
    return doc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Garbleworks live/dry efficacy battery (G6)")
    p.add_argument("--dry-run", action="store_true", help="Mock trials (CI/plumbing scoreboard)")
    p.add_argument("--n", type=int, default=MIN_N_EFFICACY, help="Trial count (default 30)")
    p.add_argument("--require-promote", action="store_true", help="Exit 2 if not promotable")
    p.add_argument("--tag", type=str, default="untagged")
    p.add_argument("--max-attempts", type=int, default=1, help="Reserved for live retries")
    p.add_argument("--engagement-id", type=str, default="local-selftest")
    p.add_argument("--target-desc", type=str, default="dry-run-mock")
    p.add_argument("--technique", type=str, default="mock_prefill")
    p.add_argument("--out", type=str, default="", help="Write result JSON path")
    p.add_argument("--min-n", type=int, default=MIN_N_EFFICACY)
    p.add_argument(
        "--scoreboard",
        action="store_true",
        help="Alias: emit live_asr.v1 scoreboard claim artifact (implies --dry-run)",
    )
    p.add_argument(
        "--no-leak",
        action="store_true",
        help="With dry-run: mock zero successes (negative promotion path)",
    )
    args = p.parse_args(argv)

    n = max(1, int(args.n))
    dry = bool(args.dry_run or args.scoreboard)
    if not dry:
        print(
            "ERROR: live multi-model fire not configured in this entry without "
            "an authorized adapter. Use --dry-run / --scoreboard for plumbing, "
            "or wire a scoped target (see docs/LIVE-ASR-RUNBOOK.md).",
            file=sys.stderr,
        )
        return 3

    # max_attempts reserved: dry path is single shot
    _ = args.max_attempts
    if args.scoreboard:
        doc = build_scoreboard_claim(
            n=n,
            tag=args.tag or "scoreboard-dry",
            dry_run=True,
            leak_all=not bool(args.no_leak),
            engagement_id=args.engagement_id,
            target_desc=args.target_desc,
            technique=args.technique,
            require_promote=bool(args.require_promote),
            min_n=int(args.min_n),
        )
    else:
        rows = _mock_rows(n, leak_all=not bool(args.no_leak))
        doc = build_result(
            rows,
            tag=args.tag,
            dry_run=True,
            n_requested=n,
            engagement_id=args.engagement_id,
            target_desc=args.target_desc,
            technique=args.technique,
            require_promote=bool(args.require_promote),
            min_n=int(args.min_n),
        )
    errs = validate_result_schema(doc)
    if errs:
        print("SCHEMA_ERROR", errs, file=sys.stderr)
        return 4

    text = json.dumps(doc, indent=2)
    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(text, encoding="utf-8")
        print(f"wrote {outp}")
    else:
        print(text)
    return int(doc["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
