"""Hermes-style single-word agent app: `gw` → talk, configure in-session.

Slash commands change provider/model/target without restarting. Config
persists to ~/.garbleworks/agent.json. Tool calls print live on the terminal.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_repl.config import AgentConfig, config_path, load_config, save_config
from agent_repl.types import AgentEvents, Message, preview


BANNER = """
┌─ Garbleworks agent ──────────────────────────────────────────┐
│  type an objective · tools stream live · config stays in-app  │
│  /help  /setup  /provider  /model  /target  /status  /quit    │
└──────────────────────────────────────────────────────────────┘
""".strip()


HELP = """
commands
  /help                 this text
  /setup                pick provider + model + target (wizard)
  /provider [id]        show or set brain (minimax, xai, stub, …)
  /model [id]           show or set model override
  /target [local|url]   show or set fire target
  /secret [value]       set canary secret (empty = auto for local)
  /rounds [n]           max agent rounds
  /fires [n]            max fire_target budget
  /providers            list providers + key status
  /status               current config + key source
  /config               print saved config path + JSON
  /save                 write current config to disk
  /clear                clear conversation history
  /findings             recent successful sessions
  /quit  /exit  /q      leave

anything else is an engagement objective (multi-turn history kept).
""".strip()


@dataclass
class AppState:
    cfg: AgentConfig
    history: list[Message] = field(default_factory=list)
    sess_dir: Path | None = None
    # live local canary server when target=local
    _server: Any = None
    _target: dict[str, Any] | None = None
    _secret: str = ""
    _target_key: str = ""
    _brain: Any = None
    _brain_meta: dict[str, Any] = field(default_factory=dict)
    _brain_key: str = ""

    def invalidate_brain(self) -> None:
        self._brain = None
        self._brain_meta = {}
        self._brain_key = ""

    def invalidate_target(self) -> None:
        self._shutdown_server()
        self._target = None
        self._target_key = ""

    def _shutdown_server(self) -> None:
        if self._server is None:
            return
        try:
            self._server.shutdown()
        except Exception:
            pass
        try:
            self._server.server_close()
        except Exception:
            pass
        self._server = None


def _c(text: str, code: str) -> str:
    """ANSI color if stdout is a TTY."""
    if not getattr(sys.stdout, "isatty", lambda: False)():
        return text
    return f"\033[{code}m{text}\033[0m"


def _print_status(state: AppState) -> None:
    cfg = state.cfg
    key_note = ""
    try:
        if cfg.provider not in ("stub", "script", "none", ""):
            from agent_repl.providers import resolve_provider

            r = resolve_provider(
                cfg.provider,
                model=cfg.model or None,
                base_url=cfg.base_url or None,
            )
            key_ok = bool(r.api_key) and r.key_source != "empty"
            key_note = f" · key={r.key_source}" + ("" if key_ok or not r.hosted else " MISSING")
            model = cfg.model or r.model
        else:
            model = "stub"
    except Exception as e:
        model = cfg.model or "?"
        key_note = f" · resolve_err={preview(str(e), 40)}"
    line = (
        f"  provider={_c(cfg.provider, '36')} model={_c(model, '36')} "
        f"target={_c(cfg.target, '33')} rounds={cfg.max_rounds}{key_note}"
    )
    print(line, flush=True)
    print(f"  config={config_path()}", flush=True)


def _make_pretty_events() -> AgentEvents:
    """Human-readable tool stream (Wallbreaker / Hermes vibe)."""

    def on_text(t: str) -> None:
        t = (t or "").strip()
        if not t:
            return
        # strip mini think tags for cleaner terminal
        if t.startswith("<think>") and "</think>" in t:
            t = t.split("</think>", 1)[-1].strip()
        if t:
            print(_c(f"  · {preview(t, 240)}", "90"), flush=True)

    def on_tool_start(_id: str, name: str, args: dict) -> None:
        args_s = preview(json.dumps(args or {}, default=str), 120)
        print(_c(f"  ▶ {name}", "35") + (f"  {args_s}" if args_s else ""), flush=True)

    def on_tool_result(_id: str, name: str, content: str, is_err: bool) -> None:
        flag = _c(" ERROR", "31") if is_err else ""
        print(
            _c(f"  ◀ {name}{flag}", "32" if not is_err else "31")
            + f"  {preview(content, 160)}",
            flush=True,
        )

    def on_round(r: int, m: int) -> None:
        print(_c(f"  · round {r}/{m}", "90"), flush=True)

    def on_stop(tool: str, args: dict) -> None:
        print(_c(f"  ■ stop {tool}", "33") + f"  {preview(json.dumps(args, default=str), 120)}", flush=True)

    def on_error(e: str) -> None:
        print(_c(f"  ! {e}", "31"), flush=True)

    def on_feedback(m: str) -> None:
        print(_c(f"  ↳ feedback: {preview(m, 100)}", "36"), flush=True)

    return AgentEvents(
        on_text=on_text,
        on_tool_start=on_tool_start,
        on_tool_result=on_tool_result,
        on_round=on_round,
        on_stop=on_stop,
        on_error=on_error,
        on_feedback=on_feedback,
    )


def _ensure_target(state: AppState) -> tuple[dict[str, Any], str]:
    import session_log as slog
    from agent_loop import make_local_canary_target, target_from_url

    target_s = (state.cfg.target or "local").strip()
    secret = state.cfg.secret or state._secret
    key = f"{target_s}|{secret}"
    if state._target is not None and key == state._target_key:
        return state._target, secret or state._secret

    state._shutdown_server()
    if target_s.lower() == "local":
        server, _port, target, sec = make_local_canary_target(secret=secret or None)
        state._server = server
        secret = secret or sec
        state._secret = secret
        state.cfg.secret = state.cfg.secret or ""  # keep empty = auto secret in memory only
    elif target_s.endswith(".json") and Path(target_s).is_file():
        target = json.loads(Path(target_s).read_text(encoding="utf-8"))
    else:
        target = target_from_url(target_s)

    state._target = target
    state._target_key = key
    _ = slog
    return target, secret or state._secret


def _ensure_brain(state: AppState) -> Any:
    from agent_repl.brain import (
        make_canary_stub_brain,
        make_openai_brain,
        make_provider_brain,
    )

    cfg = state.cfg
    bkey = f"{cfg.provider}|{cfg.model}|{cfg.base_url}"
    if state._brain is not None and state._brain_key == bkey:
        return state._brain

    sel = (cfg.provider or "stub").strip().lower()
    if sel in ("stub", "script", "none", ""):
        state._brain = make_canary_stub_brain(
            objective=cfg.last_objective or "extract the canary"
        )
        state._brain_meta = {"brain": "stub", "provider": "stub"}
        state._brain_key = bkey
        return state._brain

    if sel in ("openai", "openai-compat"):
        state._brain = make_openai_brain(
            base_url=cfg.base_url or None,
            model=cfg.model or None,
            provider_id="openai",
        )
        state._brain_meta = {
            "brain": "openai",
            "provider": "openai",
            "model": getattr(state._brain, "model", None),
        }
        state._brain_key = bkey
        return state._brain

    brain, resolved = make_provider_brain(
        sel,
        model=cfg.model or None,
        base_url=cfg.base_url or None,
    )
    state._brain = brain
    state._brain_meta = {
        "brain": "provider",
        "provider": resolved.id,
        "label": resolved.label,
        "base_url": resolved.base_url,
        "model": resolved.model,
        "key_source": resolved.key_source,
    }
    state._brain_key = bkey
    return state._brain


def _run_turn(state: AppState, text: str) -> None:
    import session_log as slog
    from agent_repl.loop import run_agent_loop
    from agent_repl.tools import EngagementContext

    text = (text or "").strip()
    if not text:
        return

    state.cfg.last_objective = text
    print(_c(f"\n▶ {text}", "1;37"), flush=True)

    try:
        target, secret = _ensure_target(state)
        # rebind stub to this objective each turn
        if (state.cfg.provider or "stub").lower() in ("stub", "script", "none", ""):
            state.invalidate_brain()
        brain = _ensure_brain(state)

        if state._brain_meta.get("provider") not in (None, "stub"):
            print(
                _c(
                    f"  brain={state._brain_meta.get('provider')} "
                    f"model={state._brain_meta.get('model')} "
                    f"key={state._brain_meta.get('key_source')}",
                    "90",
                ),
                flush=True,
            )

        ctx = EngagementContext(
            objective=text if not state.history else (state.cfg.last_objective or text),
            target=target,
            secret=secret,
            max_fires=state.cfg.max_fires,
        )
        # For multi-turn: first turn seeds objective; later turns append user msg
        objective = text
        history = list(state.history) if state.history else None
        if history:
            history.append(Message(role="user", content=text))
            objective = state.cfg.last_objective or text

        session = slog.Session(
            objective=objective,
            secret_fingerprint=slog.fingerprint_secret(secret),
            session_dir=state.sess_dir,
            meta={
                "mode": "agent_app",
                "provider": state.cfg.provider,
                "target": state.cfg.target,
                **state._brain_meta,
            },
        )
        if secret:
            session.set_secret_for_redact(secret)

        events = _make_pretty_events()
        result = run_agent_loop(
            objective=objective,
            brain=brain,
            ctx=ctx,
            events=events,
            max_rounds=state.cfg.max_rounds,
            session=session,
            history=history,
        )
        state.history = list(result.messages or [])

        ok = "✓" if result.success else "·"
        color = "32" if result.success else "33"
        print(
            _c(
                f"  {ok} {result.status}  success={result.success}  "
                f"rounds={result.rounds}  tools={result.tool_calls}",
                color,
            ),
            flush=True,
        )
        if result.summary:
            print(f"  summary: {preview(result.summary, 200)}", flush=True)
        if result.session_path:
            print(_c(f"  session: {result.session_path}", "90"), flush=True)
    except Exception as e:
        print(_c(f"  ! turn failed: {e}", "31"), flush=True)


def _cmd_providers() -> None:
    from agent_repl.providers import list_providers, resolve_provider

    rows = list_providers()
    for r in rows:
        try:
            res = resolve_provider(r["id"])
            key = res.key_source if res.api_key and res.key_source != "empty" else "—"
            print(
                f"  {r['id']:<14} {r['default_model']:<28} key={key}  {r.get('note', '')[:50]}",
                flush=True,
            )
        except Exception as e:
            print(f"  {r['id']:<14} error={preview(str(e), 60)}", flush=True)


def _cmd_setup(state: AppState) -> None:
    print("setup wizard (blank keeps current)", flush=True)
    _print_status(state)
    print("providers: stub, minimax, xai, opencode-zen, opencode-go, ollama, openai, …", flush=True)
    try:
        p = input(f"  provider [{state.cfg.provider}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if p:
        state.cfg.provider = p.lower()
        state.invalidate_brain()
    try:
        m = input(f"  model [{state.cfg.model or 'default'}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if m:
        state.cfg.model = m
        state.invalidate_brain()
    try:
        t = input(f"  target [{state.cfg.target}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if t:
        state.cfg.target = t
        state.invalidate_target()
    try:
        r = input(f"  max_rounds [{state.cfg.max_rounds}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if r.isdigit():
        state.cfg.max_rounds = max(1, int(r))
    path = save_config(state.cfg)
    print(f"  saved → {path}", flush=True)
    _print_status(state)


def _handle_slash(state: AppState, line: str) -> bool:
    """Return False to exit app."""
    parts = line.strip().split(maxsplit=1)
    cmd = parts[0].lower().lstrip("/")
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ("quit", "exit", "q"):
        try:
            save_config(state.cfg)
        except OSError:
            pass
        print("bye.", flush=True)
        return False

    if cmd in ("help", "h", "?"):
        print(HELP, flush=True)
        return True

    if cmd == "setup":
        _cmd_setup(state)
        return True

    if cmd == "providers":
        _cmd_providers()
        return True

    if cmd in ("provider", "brain"):
        if not arg:
            print(f"  provider={state.cfg.provider}", flush=True)
            return True
        state.cfg.provider = arg.strip().lower()
        state.invalidate_brain()
        save_config(state.cfg)
        print(f"  provider → {state.cfg.provider}", flush=True)
        _print_status(state)
        return True

    if cmd == "model":
        if not arg:
            print(f"  model={state.cfg.model or '(provider default)'}", flush=True)
            return True
        state.cfg.model = arg.strip()
        state.invalidate_brain()
        save_config(state.cfg)
        print(f"  model → {state.cfg.model}", flush=True)
        return True

    if cmd == "target":
        if not arg:
            print(f"  target={state.cfg.target}", flush=True)
            return True
        state.cfg.target = arg.strip()
        state.invalidate_target()
        save_config(state.cfg)
        print(f"  target → {state.cfg.target}", flush=True)
        return True

    if cmd == "secret":
        state.cfg.secret = arg
        state.invalidate_target()
        save_config(state.cfg)
        print("  secret set" if arg else "  secret cleared (local canary auto)", flush=True)
        return True

    if cmd == "rounds":
        if arg.isdigit():
            state.cfg.max_rounds = max(1, int(arg))
            save_config(state.cfg)
        print(f"  max_rounds={state.cfg.max_rounds}", flush=True)
        return True

    if cmd == "fires":
        if arg.isdigit():
            state.cfg.max_fires = max(1, int(arg))
            save_config(state.cfg)
        print(f"  max_fires={state.cfg.max_fires}", flush=True)
        return True

    if cmd == "status":
        _print_status(state)
        print(f"  history_msgs={len(state.history)}", flush=True)
        return True

    if cmd == "config":
        print(f"  path={config_path()}", flush=True)
        print(json.dumps(state.cfg.as_dict(), indent=2), flush=True)
        return True

    if cmd == "save":
        path = save_config(state.cfg)
        print(f"  saved → {path}", flush=True)
        return True

    if cmd == "clear":
        state.history = []
        print("  history cleared", flush=True)
        return True

    if cmd == "findings":
        import session_log as slog

        rows = slog.list_findings(state.sess_dir, limit=10)
        print(json.dumps(rows, indent=2, default=str), flush=True)
        return True

    print(f"  unknown command /{cmd} — /help", flush=True)
    return True


def run_app(
    *,
    cfg: AgentConfig | None = None,
    sess_dir: Path | None = None,
    setup_first: bool = False,
    stdin_lines: list[str] | None = None,
) -> int:
    """Interactive product surface. stdin_lines injects scripted input (tests)."""
    from pathlib import Path as P

    _backend = P(__file__).resolve().parent.parent
    state = AppState(
        cfg=cfg or load_config(),
        sess_dir=sess_dir or (_backend / "sessions"),
    )

    print(BANNER, flush=True)
    _print_status(state)

    if setup_first:
        _cmd_setup(state)

    # Scripted mode for tests
    if stdin_lines is not None:
        for line in stdin_lines:
            line = (line or "").rstrip("\n")
            if not line.strip():
                continue
            print(f"gw> {line}", flush=True)
            if line.strip().startswith("/"):
                if not _handle_slash(state, line.strip()):
                    state._shutdown_server()
                    return 0
            else:
                _run_turn(state, line.strip())
        state._shutdown_server()
        return 0

    while True:
        try:
            line = input("gw> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            try:
                save_config(state.cfg)
            except OSError:
                pass
            state._shutdown_server()
            return 0
        if not line:
            continue
        if line.startswith("/"):
            if not _handle_slash(state, line):
                state._shutdown_server()
                return 0
            continue
        _run_turn(state, line)

    return 0


def should_launch_app(argv: list[str] | None) -> bool:
    """True when operator typed a single word / no headless intent.

    Headless intent: --objective, --out, --session, --list-*, --resume,
    --tui-boot, --quiet (batch), or positional setup handled separately.
    """
    if argv is None:
        argv = sys.argv[1:]
    # strip prog-only
    args = list(argv)
    if not args:
        return True

    # subcommands
    if args[0] in ("setup", "chat", "app", "repl"):
        return True
    if args[0] in ("-h", "--help"):
        return False

    headless_exact = {
        "--session",
        "--list-providers",
        "--list-findings",
        "--tui-boot",
        "--quiet",
        "--interactive",  # legacy path; still interactive but old code
    }
    for a in args:
        if a in headless_exact:
            # --interactive is app; treat as app
            if a == "--interactive":
                return True
            return False
        if a == "--resume" or a.startswith("--resume="):
            return False
        if a == "--out" or a.startswith("--out="):
            return False
        if a == "--objective" or a.startswith("--objective="):
            return False
    return True
