"""CLI: arena advisor for human paste (Gray Swan–style rules).

  python arena_advise_cli.py "short objective" [history.json]
  python arena_advise_cli.py --brief path/to/pasted_challenge.txt [history.json]
  python arena_advise_cli.py --brief - [history.json]   # brief on stdin

Paste the full Gray Swan card into a file or stdin; we extract the concrete
question + win criteria, then emit the next payload for YOU to paste manually.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from arena_brief import parse_arena_brief
from arena_solver import LADDER, ladder_snapshot, next_move
from tool_advise import tool_next_move
import tui_events as te

# Always dump the paste payload here so operators can open/copy without TUI select.
_NEXT_PASTE = Path(__file__).resolve().parent / "sessions" / "next_paste.txt"
_TUI_PASTE = Path(__file__).resolve().parent.parent / "tui" / "last_paste.txt"


def _write_paste_files(text: str) -> None:
    body = (text or "").strip() + "\n"
    for path in (_NEXT_PASTE, _TUI_PASTE):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        except Exception:
            pass


def _load_history(raw: str | None) -> list:
    if not raw or raw in ("", "-"):
        return []
    if raw.startswith("["):
        return json.loads(raw)
    with open(raw, encoding="utf-8") as f:
        return json.load(f)


def _load_brief(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Arena advise — next paste payload")
    p.add_argument("objective", nargs="?", default="",
                   help="short objective (or omit if --brief)")
    p.add_argument("history", nargs="?", default="",
                   help="history JSON file or inline JSON array")
    p.add_argument("--brief", default="",
                   help="path to full challenge paste, or - for stdin")
    p.add_argument("--brief-text", default="",
                   help="full challenge paste as a single string (TUI uses this)")
    args = p.parse_args(argv)

    # Prefer env (TUI) to avoid Windows command-line length limits on long cards.
    brief_text = (os.environ.get("GARBLEWORKS_BRIEF") or "").strip()
    if not brief_text and args.brief_text:
        brief_text = args.brief_text
    if not brief_text and args.brief:
        brief_text = _load_brief(args.brief)

    parsed = parse_arena_brief(brief_text) if brief_text.strip() else None
    objective = (args.objective or "").strip()
    if parsed and parsed.objective:
        objective = parsed.objective
    if not objective:
        print("error: pass objective and/or --brief / --brief-text", file=sys.stderr)
        return 2

    history = _load_history(args.history or None)

    te.emit_plan(
        ["parse_brief", "tool_chain", "stage_payload", "paste_manually", "record_outcome"],
        job="arena_advise",
        budget=1,
    )
    if parsed:
        te.emit_activity(
            f"Brief: {parsed.title or 'challenge'}"
            + (f" · win if answer={parsed.expected_answer}" if parsed.expected_answer else ""),
            level="info",
            objective=objective[:120],
        )
        for c in parsed.constraints[:4]:
            te.emit_activity(f"Rule: {c}", level="warn")
        te.emit_step("parse_brief", "done", note=parsed.title[:40] if parsed.title else "ok")
    else:
        te.emit_step("parse_brief", "skip", note="no brief")

    te.emit_activity(
        "RULES: do not auto-submit on Gray Swan — paste the payload yourself",
        level="warn",
        objective=objective[:120],
    )
    te.emit_step("tool_chain", "active")

    # Stream ladder state so the TUI can show gears before the build finishes.
    pre_snap = ladder_snapshot(history, objective)
    te.emit_progress(
        current=len(history),
        total=max(len(LADDER), len(pre_snap) or 1),
        label="tool-chain",
        detail=f"{len(history)} tries logged",
    )
    for row in pre_snap:
        st = row.get("status") or "pending"
        # map ladder HUD status → plan step status
        step_st = {
            "tried": "done",
            "next": "active",
            "skipped": "skip",
            "pending": "pending",
        }.get(st, "pending")
        te.emit_step(
            str(row["id"]),
            step_st,
            note=row.get("outcome") or row.get("kind") or "",
        )
        if st == "next":
            te.emit_activity(
                f"GEAR · advancing to {row['id']} ({row.get('kind')})"
                + (f" via op:{row['op']}" if row.get("op") else " · tool chain"),
                level="info",
                strategy=str(row["id"]),
            )

    # Real tool chain (same ops MCP generate_framings / evolve_seeds expose).
    # Streams TOOL · lines into the TUI mutation terminal.
    expected = parsed.expected_answer if parsed else None

    def _emit_tool(message: str, **extra):
        # Long previews so the mutation terminal can show exact BEFORE/AFTER text.
        te.emit_activity(
            message,
            level=str(extra.pop("level", "info")),
            strategy=extra.get("strategy"),
            payload_preview=(extra.get("payload") or "")[:280] or None,
            reply_preview=(extra.get("reply") or "")[:200] or None,
        )

    te.emit_activity(
        "AGENT · running tool chain (generate_framings / evolve / neutralize)",
        level="info",
    )
    move = tool_next_move(
        objective,
        history,
        expected_answer=expected,
        emit=_emit_tool,
        mode="tools",
    )
    if move.get("done"):
        te.emit_step("advise", "done", note=str(move.get("message", "done"))[:80])
        te.emit_activity(str(move.get("message") or "ladder done"), level="info")
        te.emit_result(
            success=bool(move.get("solved")),
            strategy=move.get("winning_technique"),
            defense_type=move.get("defense_type"),
        )
        print(json.dumps(move, indent=2, ensure_ascii=False))
        return 0 if move.get("solved") else 1

    tech = str(move.get("technique") or "?")
    kind = str(move.get("kind") or "")
    rationale = str(move.get("rationale") or "")
    payload = move.get("payload")
    reset = bool(move.get("reset_first"))
    op_name = move.get("op")
    attempt = move.get("attempt") or (len(history) + 1)
    used_reply = bool(move.get("used_reply"))
    improvement = str(move.get("improvement") or "")
    last_reply_prev = str(move.get("last_reply_preview") or "")

    te.emit_step("tool_chain", "done", note=tech)
    te.emit_step("stage_payload", "active", note=tech)
    te.emit_activity(
        f"MORPH · attempt {attempt} → {tech} [{kind}]"
        + (" · tool_chain" if move.get("tool_chain") else ""),
        level="info",
        strategy=tech,
    )
    if used_reply:
        te.emit_activity(
            f"MUTATE · using pasted failure reply ({len(last_reply_prev)}+ chars seen)",
            level="info",
            strategy=tech,
            reply_preview=last_reply_prev,
        )
        if improvement:
            te.emit_activity(
                f"PAIR · {improvement}",
                level="info",
                strategy=tech,
            )
        elif kind == "reply_mutate":
            te.emit_activity(
                "MUTATE · offline counter-wrap (attacker brain empty/unavailable)",
                level="warn",
                strategy=tech,
            )
    if op_name and kind not in ("pair_mutate", "reply_mutate"):
        te.emit_activity(
            f"HARNESS · run_recipe op={op_name} (same registry MCP expose)",
            level="info",
            strategy=tech,
        )
    elif not used_reply:
        te.emit_activity(
            f"HARNESS · clean framing builder (no loud op) · {kind}",
            level="info",
            strategy=tech,
        )
    te.emit_activity(
        f"NEXT · {tech} ({kind})"
        + (" · RESET SESSION FIRST" if reset else "")
        + (f" · {rationale}" if rationale else ""),
        level="info",
        strategy=tech,
    )
    if history:
        last = history[-1]
        te.emit_activity(
            f"BRANCH · last={last.get('technique')}:{last.get('outcome')} → now={tech}",
            level="info",
            strategy=tech,
        )
    if parsed and parsed.expected_answer:
        te.emit_activity(
            f"Operator win check: visible reply must answer the exam Q with "
            f"'{parsed.expected_answer}' (not CoT-only)",
            level="info",
        )

    turns: list[str]
    if isinstance(payload, list):
        turns = [str(p) for p in payload]
    else:
        turns = [str(payload or "")]

    # Multi-turn: write full sequence; single-turn: write the one payload.
    combined = "\n\n".join(
        (f"[turn {i + 1}]\n{t}" if len(turns) > 1 else t) for i, t in enumerate(turns)
    )
    _write_paste_files(combined)
    te.emit_activity(
        f"Payload saved → sessions/next_paste.txt  and  tui/last_paste.txt",
        level="info",
    )

    for i, turn in enumerate(turns):
        label = f"turn {i + 1}/{len(turns)}" if len(turns) > 1 else "payload"
        te.emit_fire(
            strategy=tech,
            payload_preview=turn[:160],
            reply_preview="(open next_paste.txt or press c in TUI to copy)",
            leaked=False,
            channel="manual_paste",
            q=i + 1,
        )
        te.emit_activity(f"COPY {label}:", level="info", strategy=tech)
        print(f"===== PASTE ({tech} · {label}) =====", flush=True)
        if reset and i == 0:
            print("[RESET the arena session first, then paste]", flush=True)
        print(turn, flush=True)
        print("===== END PASTE =====", flush=True)

    print(f"PASTE_FILE={_NEXT_PASTE}", flush=True)
    print(f"PASTE_FILE_TUI={_TUI_PASTE}", flush=True)

    te.emit_step("paste_manually", "active", note="waiting for human")
    te.emit_activity(
        "OPERATOR · 1) Ctrl+V payload in BROWSER  2) copy model reply  3) paste into REPLY field",
        level="warn",
    )
    te.emit_activity(
        "FEEDBACK · REPLY field gets failure text · Ctrl+R refuse / Ctrl+T trip / Ctrl+S success",
        level="warn",
    )
    te.emit_result(
        success=False,
        strategy=tech,
        queries=0,
        channel="manual_paste",
        defense_type=move.get("defense_type"),
        expected_answer=(parsed.expected_answer if parsed else ""),
        brief_title=(parsed.title if parsed else ""),
        await_outcome=True,
    )
    print("GW_ADVISE|" + json.dumps({
        "technique": tech,
        "kind": kind,
        "reset_first": reset,
        "payload": payload,
        "rationale": rationale,
        "defense_type": move.get("defense_type"),
        "objective_used": objective,
        "expected_answer": parsed.expected_answer if parsed else "",
        "brief_title": parsed.title if parsed else "",
        "constraints": parsed.constraints if parsed else [],
        "op": op_name,
        "attempt": attempt,
        "ladder": move.get("ladder") or pre_snap,
        "await_outcome": True,
        "used_reply": used_reply,
        "improvement": improvement,
        "base_technique": move.get("base_technique"),
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
