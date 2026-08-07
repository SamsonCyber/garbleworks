"""Garbleworks agent entry: `gw` / `python -m agent_repl`.

Bare single word → Hermes-style interactive app (configure in-session).
Flags / --objective → headless tool loop (CI + scripts).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


def _print_event(kind: str, payload: dict) -> None:
    """Emit stream lines. When GARBLEWORKS_TUI=1, use GW| wire format for OpenTUI.

    GARBLEWORKS_CHAT=1 keeps native agent kinds (chat session). Otherwise the
    one-shot operator HUD remaps tools onto activity / result rows.
    """
    import os
    import time

    row = {"kind": kind, "ts": round(time.time(), 3), "v": 1, **payload}
    tui = os.environ.get("GARBLEWORKS_TUI", "").strip() not in ("", "0", "false", "False")
    chat = os.environ.get("GARBLEWORKS_CHAT", "").strip() not in ("", "0", "false", "False")
    if tui:
        if not chat:
            # Map agent events onto activity/fire so the legacy HUD lights up
            if kind == "tool_start":
                row = {
                    "v": 1,
                    "kind": "activity",
                    "ts": row["ts"],
                    "level": "info",
                    "message": f"tool ▶ {payload.get('tool')}",
                    "strategy": str(payload.get("tool") or ""),
                    "payload": json.dumps(payload.get("args") or {}, default=str)[:160],
                }
            elif kind == "tool_result":
                is_err = bool(payload.get("is_error"))
                row = {
                    "v": 1,
                    "kind": "activity",
                    "ts": row["ts"],
                    "level": "warn" if is_err else "info",
                    "message": f"tool ◀ {payload.get('tool')}"
                    + (" ERROR" if is_err else ""),
                    "strategy": str(payload.get("tool") or ""),
                    "reply": str(payload.get("result_preview") or "")[:160],
                }
            elif kind == "agent_stop":
                row = {
                    "v": 1,
                    "kind": "result",
                    "ts": row["ts"],
                    # Prefer harness success when present; never treat mere finish as win
                    "success": bool(
                        payload.get("success")
                        if "success" in payload
                        else (payload.get("args") or {}).get("success")
                    ),
                    "strategy": str(payload.get("stop_tool") or "stop"),
                    "message": json.dumps(payload.get("args") or {}, default=str)[:200],
                }
            elif kind == "run_complete":
                row = {
                    "v": 1,
                    "kind": "result",
                    "ts": row["ts"],
                    "success": bool(payload.get("success")),
                    "strategy": str(payload.get("stop_tool") or payload.get("status") or ""),
                    "queries": payload.get("tool_calls"),
                    "message": str(payload.get("summary") or "")[:200],
                    "session_path": payload.get("session_path"),
                }
            elif kind == "agent_text":
                row = {
                    "v": 1,
                    "kind": "activity",
                    "ts": row["ts"],
                    "level": "info",
                    "message": str(payload.get("text") or "")[:200],
                }
        print("GW|" + json.dumps(row, ensure_ascii=False, default=str), flush=True)
        return
    print(json.dumps(row, ensure_ascii=False, default=str), flush=True)


def _argv_has(argv: list[str], *flags: str) -> bool:
    for a in argv:
        for f in flags:
            if a == f or a.startswith(f + "="):
                return True
    return False


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)

    # Single-word product: bare `gw` / `gw setup` / `gw chat` → interactive app
    from agent_repl.app import run_app, should_launch_app
    from agent_repl.config import apply_cli_overrides, load_config

    setup_first = bool(raw and raw[0] == "setup")
    if raw and raw[0] in ("setup", "chat", "app", "repl"):
        # peel subcommand; remaining flags still apply
        raw = raw[1:]

    p = argparse.ArgumentParser(
        prog="gw",
        description=(
            "Garbleworks agent — type `gw` to chat and configure in-app (Hermes-style). "
            "Pass --objective for one-shot headless runs."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  gw                          interactive app (slash-config)\n"
            "  gw setup                    wizard then app\n"
            "  gw --provider minimax       app with provider pre-set\n"
            "  gw --objective \"extract the canary\" --brain stub\n"
            "  gw --list-providers\n"
        ),
    )
    p.add_argument(
        "--objective",
        default=None,
        help="one-shot engagement objective (implies headless)",
    )
    p.add_argument(
        "--target",
        default=None,
        help="local | OpenAI-compat URL | path to target JSON",
    )
    p.add_argument("--secret", default=None, help="canary secret for adjudication")
    p.add_argument(
        "--brain",
        default=None,
        help=(
            "attacker brain: stub | openai | provider id "
            "(xai|grok|minimax|opencode|opencode-zen|opencode-go|ollama|openrouter|custom)"
        ),
    )
    p.add_argument(
        "--provider",
        default=None,
        help="Hermes-style provider id (alias of --brain). Overrides --brain if set.",
    )
    p.add_argument(
        "--base-url",
        default=None,
        help="OpenAI-compat base override (any provider / custom endpoint)",
    )
    p.add_argument("--model", default=None, help="model id override")
    p.add_argument(
        "--api-key",
        default=None,
        help="API key override (else env / ~/.secrets/*.txt)",
    )
    p.add_argument("--max-rounds", type=int, default=None)
    p.add_argument("--max-fires", type=int, default=None)
    p.add_argument(
        "--session-dir",
        default="",
        help="session artifact dir (default: backend/sessions)",
    )
    p.add_argument("--out", default="", help="write RunResult JSON here")
    p.add_argument("--quiet", action="store_true", help="suppress per-event stream")
    p.add_argument(
        "--list-findings",
        action="store_true",
        help="list recent successful sessions and exit",
    )
    p.add_argument(
        "--list-providers",
        action="store_true",
        help="list Hermes-style brain providers (xai, minimax, opencode-…) and exit",
    )
    p.add_argument(
        "--resume",
        nargs="?",
        const="latest",
        default="",
        help="print latest (or path) session summary and exit",
    )
    p.add_argument(
        "--interactive",
        action="store_true",
        help="force interactive app (default when no --objective)",
    )
    p.add_argument(
        "--session",
        action="store_true",
        help=(
            "long-lived chat session for OpenTUI: JSONL stdin ops "
            "(turn/feedback/stop/clear/set/quit), GW| events on stdout"
        ),
    )
    p.add_argument(
        "--tui-boot",
        action="store_true",
        help="init agent surface + print ready (for headless TUI proof)",
    )
    p.add_argument(
        "--engagement-host",
        action="store_true",
        help="long-lived JSONL engagement host for pi / external agent TUIs",
    )
    p.add_argument(
        "--once",
        action="store_true",
        help="force one-shot headless even without --objective (uses config objective or default)",
    )
    args = p.parse_args(raw)

    import session_log as slog
    from agent_repl.brain import make_canary_stub_brain
    from agent_repl.loop import run_headless_canary
    from agent_repl.providers import list_providers, resolve_provider
    from agent_repl.tools import build_default_registry
    from agent_repl.types import AgentEvents, preview

    sess_dir = Path(args.session_dir) if args.session_dir else (_BACKEND / "sessions")

    # Normalize brain/provider for headless path (defaults after config merge)
    cfg = load_config()
    # Only apply CLI fields that were actually passed
    class _NS:
        pass

    ov = _NS()
    if args.provider is not None:
        ov.provider = args.provider
    if args.brain is not None:
        ov.brain = args.brain
    if args.model is not None:
        ov.model = args.model
    if args.base_url is not None:
        ov.base_url = args.base_url
    if args.target is not None:
        ov.target = args.target
    if args.secret is not None:
        ov.secret = args.secret
    if args.max_rounds is not None:
        ov.max_rounds = args.max_rounds
    if args.max_fires is not None:
        ov.max_fires = args.max_fires
    if args.objective is not None:
        ov.objective = args.objective
    cfg = apply_cli_overrides(cfg, ov)

    # Fill argparse namespace for legacy helpers
    args.brain = (args.provider or args.brain or cfg.provider or "stub").strip().lower()
    args.provider = (args.provider or "").strip().lower()
    args.model = args.model if args.model is not None else cfg.model
    args.base_url = args.base_url if args.base_url is not None else cfg.base_url
    args.target = args.target if args.target is not None else (cfg.target or "local")
    args.secret = args.secret if args.secret is not None else (cfg.secret or "")
    args.max_rounds = int(args.max_rounds if args.max_rounds is not None else cfg.max_rounds)
    args.max_fires = int(args.max_fires if args.max_fires is not None else cfg.max_fires)
    args.api_key = args.api_key or ""
    if args.provider:
        args.brain = args.provider

    if args.list_providers:
        rows = list_providers()
        # annotate key present without printing secrets
        for r in rows:
            try:
                res = resolve_provider(r["id"])
                r["key_configured"] = bool(res.api_key) and res.key_source != "empty"
                r["key_source"] = res.key_source
                r["resolved_model"] = res.model
            except Exception as e:
                r["key_configured"] = False
                r["error"] = str(e)[:120]
        print(json.dumps({"providers": rows, "count": len(rows)}, indent=2))
        return 0

    if args.list_findings:
        findings = slog.list_findings(sess_dir, limit=20)
        print(json.dumps({"findings": findings, "count": len(findings)}, indent=2))
        return 0

    if args.resume:
        path = args.resume
        if path == "latest":
            latest = slog.latest_session_summary(sess_dir)
            if not latest:
                print(json.dumps({"error": "no sessions found", "dir": str(sess_dir)}))
                return 1
            path = str(latest)
        data = slog.load_session_summary(path)
        print(json.dumps(data, indent=2, default=str))
        return 0

    if args.tui_boot:
        # Structural + import boot of agent surface (no live LLM required)
        reg = build_default_registry()
        names = reg.names()
        assert "fire_target" in names and "finish" in names
        providers = [r["id"] for r in list_providers()]
        print(json.dumps({
            "kind": "tui_agent_boot",
            "ok": True,
            "mode": "agent_repl",
            "tools": names,
            "providers": providers,
            "entry": "gw",
            "tui_profile": "agent",
        }, indent=2))
        return 0

    if args.engagement_host:
        from agent_repl.engagement_host import run_host

        return run_host()

    # Normalize brain selection: --provider wins; aliases of live providers ok
    brain_sel = (args.provider or args.brain or cfg.provider or "stub").strip().lower()
    if brain_sel in ("script",):
        brain_sel = "stub"
    args.brain = brain_sel

    # Hermes-style product: bare invocation → interactive app
    launch_app = (
        setup_first
        or args.interactive
        or (
            should_launch_app(
                # rebuild intent argv from original (before subcommand peel for flags)
                list(sys.argv[1:] if argv is None else argv)
            )
            and not args.session
            and not args.once
            and args.objective is None
            and not args.out
            and not args.quiet
        )
    )
    if launch_app:
        return run_app(
            cfg=cfg,
            sess_dir=sess_dir,
            setup_first=setup_first,
        )

    # Headless defaults
    if not args.objective:
        args.objective = cfg.last_objective or "extract the canary"

    events = AgentEvents()
    if not args.quiet:
        events.on_text = lambda t: _print_event("agent_text", {"text": preview(t, 300)})
        events.on_tool_start = lambda i, n, a: _print_event(
            "tool_start", {"tool_id": i, "tool": n, "args": a}
        )
        events.on_tool_result = lambda i, n, c, e: _print_event(
            "tool_result",
            {
                "tool_id": i,
                "tool": n,
                "is_error": e,
                "result_preview": preview(c, 400),
            },
        )
        events.on_stop = lambda tool, a: _print_event(
            "agent_stop", {"stop_tool": tool, "args": a}
        )
        events.on_error = lambda e: _print_event("agent_error", {"error": e})
        events.on_round = lambda r, m: _print_event("agent_round", {"round": r, "max": m})

    if args.session:
        # Chat session always uses native GW kinds (OpenTUI agent chat)
        import os

        os.environ["GARBLEWORKS_TUI"] = "1"
        os.environ["GARBLEWORKS_CHAT"] = "1"
        from agent_repl.session import run_chat_session

        return run_chat_session(args)

    # One-shot headless run
    target_s = (args.target or "local").strip().lower()
    if target_s == "local" and args.brain == "stub":
        result = run_headless_canary(
            objective=args.objective,
            secret=args.secret or None,
            max_rounds=args.max_rounds,
            max_fires=args.max_fires,
            session_dir=sess_dir,
            brain=make_canary_stub_brain(objective=args.objective),
            events=events,
        )
    else:
        try:
            result = _run_with_target(args, events, sess_dir)
        except ValueError as e:
            print(json.dumps({"error": str(e)}, indent=2), flush=True)
            return 1

    out = result.as_dict()
    # Always print terminal status line for evidence parsers
    _print_event(
        "run_complete",
        {
            "status": result.status,
            "stop_tool": result.stop_tool,
            "summary": preview(result.summary, 300),
            "rounds": result.rounds,
            "tool_calls": result.tool_calls,
            "session_path": result.session_path,
            "success": bool(result.success),
            "meta": result.meta,
        },
    )
    if args.out:
        Path(args.out).write_text(
            json.dumps(out, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    # Exit: 0 = objective win or operator handoff; 2 = budget; 3 = clean miss; 1 = error
    if result.status == "need_operator":
        return 0
    if result.status == "finished":
        return 0 if result.success else 3
    if result.status == "max_rounds":
        return 0 if result.success else 2
    return 1


def _resolve_brain(args: argparse.Namespace):
    """stub | openai-compat | Hermes provider preset."""
    from agent_repl.brain import (
        make_canary_stub_brain,
        make_openai_brain,
        make_provider_brain,
    )

    sel = (args.brain or "stub").strip().lower()
    if sel in ("stub", "script", "none", ""):
        return make_canary_stub_brain(objective=args.objective), {
            "brain": "stub",
            "provider": "stub",
        }

    # Generic OpenAI-compat without a named preset
    if sel in ("openai", "openai-compat"):
        brain = make_openai_brain(
            base_url=args.base_url or None,
            model=args.model or None,
            api_key=args.api_key or None,
            provider_id="openai",
        )
        return brain, {
            "brain": "openai",
            "provider": "openai",
            "base_url": getattr(brain, "base_url", None),
            "model": getattr(brain, "model", None),
        }

    # Hermes-style named provider (xai, minimax, opencode-zen, …)
    brain, resolved = make_provider_brain(
        sel,
        model=args.model or None,
        base_url=args.base_url or None,
        api_key=args.api_key or None,
    )
    return brain, {
        "brain": "provider",
        "provider": resolved.id,
        "label": resolved.label,
        "base_url": resolved.base_url,
        "model": resolved.model,
        "key_source": resolved.key_source,
    }


def _run_with_target(args: argparse.Namespace, events: AgentEvents, sess_dir: Path):
    import session_log as slog
    from agent_loop import make_local_canary_target, target_from_url
    from agent_repl.loop import run_agent_loop
    from agent_repl.tools import EngagementContext

    secret = args.secret or ""
    server = None
    target: dict
    target_s = (args.target or "local").strip()

    if target_s.lower() == "local":
        server, _port, target, sec = make_local_canary_target(secret=secret or None)
        secret = secret or sec
    elif target_s.endswith(".json") and Path(target_s).is_file():
        target = json.loads(Path(target_s).read_text(encoding="utf-8"))
    else:
        target = target_from_url(target_s)

    brain, brain_meta = _resolve_brain(args)
    if not args.quiet and brain_meta.get("provider") not in (None, "stub"):
        _print_event("brain_config", {k: v for k, v in brain_meta.items() if k != "api_key"})

    ctx = EngagementContext(
        objective=args.objective,
        target=target,
        secret=secret,
        max_fires=args.max_fires,
    )
    session = slog.Session(
        objective=args.objective,
        secret_fingerprint=slog.fingerprint_secret(secret),
        session_dir=sess_dir,
        meta={
            "mode": "agent_repl",
            "brain": args.brain,
            "target": target_s,
            **brain_meta,
        },
    )
    if secret:
        session.set_secret_for_redact(secret)
    try:
        return run_agent_loop(
            objective=args.objective,
            brain=brain,
            ctx=ctx,
            events=events,
            max_rounds=args.max_rounds,
            session=session,
        )
    finally:
        if server is not None:
            try:
                server.shutdown()
            except Exception:
                pass
            try:
                server.server_close()
            except Exception:
                pass


def _interactive_repl(args: argparse.Namespace, events: AgentEvents, sess_dir: Path) -> int:
    """Simple stdin REPL: each non-empty line is a new objective turn (fresh loop)."""
    print("Garbleworks agent REPL. Type an objective, or /quit.", flush=True)
    print(
        f"brain={args.brain} · providers: xai|minimax|opencode-zen|opencode-go|ollama "
        "(/providers lists keys)",
        flush=True,
    )
    while True:
        try:
            line = input("agent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in ("/quit", "/exit", "/q"):
            return 0
        if line.startswith("/findings"):
            import session_log as slog

            print(json.dumps(slog.list_findings(sess_dir, limit=10), indent=2, default=str))
            continue
        if line.startswith("/providers"):
            from agent_repl.providers import list_providers, resolve_provider

            rows = list_providers()
            for r in rows:
                try:
                    res = resolve_provider(r["id"])
                    r["key_configured"] = bool(res.api_key) and res.key_source != "empty"
                    r["key_source"] = res.key_source
                except Exception:
                    r["key_configured"] = False
            print(json.dumps(rows, indent=2, default=str))
            continue
        # Override objective for this turn
        args.objective = line
        target_s = (args.target or "local").strip().lower()
        if target_s == "local" and args.brain == "stub":
            from agent_repl.brain import make_canary_stub_brain
            from agent_repl.loop import run_headless_canary

            result = run_headless_canary(
                objective=line,
                secret=args.secret or None,
                max_rounds=args.max_rounds,
                max_fires=args.max_fires,
                session_dir=sess_dir,
                brain=make_canary_stub_brain(objective=line),
                events=events,
            )
        else:
            try:
                result = _run_with_target(args, events, sess_dir)
            except ValueError as e:
                print(json.dumps({"error": str(e)}, indent=2), flush=True)
                continue
        print(
            json.dumps(
                {
                    "status": result.status,
                    "summary": result.summary,
                    "session_path": result.session_path,
                },
                indent=2,
            ),
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
