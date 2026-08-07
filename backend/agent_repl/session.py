"""Long-lived agent chat session for the OpenTUI shell.

JSONL over stdin, GW| events on stdout. Persistent message history across
operator turns. Mid-turn feedback is drained before each brain call.

Protocol (stdin, one JSON object per line; bare text = turn):
  {"op":"turn","text":"..."}
  {"op":"feedback","text":"..."}
  {"op":"stop"}
  {"op":"clear"}
  {"op":"set","target":"local","secret":"...","max_rounds":12,"brain":"stub"}
  {"op":"quit"}

Wire: always GW|{json} so the TUI bridge can parse without remapping noise.
Native kinds (agent_text, tool_start, …) — not collapsed to activity.
"""
from __future__ import annotations

import json
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agent_repl.types import AgentEvents, Message, preview


def emit(kind: str, **payload: Any) -> None:
    row = {"v": 1, "kind": kind, "ts": round(time.time(), 3), **payload}
    print("GW|" + json.dumps(row, ensure_ascii=False, default=str), flush=True)


def _make_events() -> AgentEvents:
    return AgentEvents(
        on_text=lambda t: emit("agent_text", text=preview(t, 800)),
        on_tool_start=lambda i, n, a: emit(
            "tool_start", tool_id=i, tool=n, args=a
        ),
        on_tool_result=lambda i, n, c, e: emit(
            "tool_result",
            tool_id=i,
            tool=n,
            is_error=e,
            result_preview=preview(c, 600),
        ),
        on_stop=lambda tool, a: emit("agent_stop", stop_tool=tool, args=a),
        on_error=lambda e: emit("agent_error", error=e),
        on_round=lambda r, m: emit("agent_round", round=r, max=m),
        on_feedback=lambda m: emit("feedback_applied", text=preview(m, 300)),
    )


class ChatSession:
    """Stateful multi-turn agent chat driven by stdin commands."""

    def __init__(self, args: Any) -> None:
        self.args = args
        self.sess_dir = (
            Path(args.session_dir)
            if getattr(args, "session_dir", None)
            else (_BACKEND / "sessions")
        )
        self.max_rounds = int(getattr(args, "max_rounds", 12) or 12)
        self.max_fires = int(getattr(args, "max_fires", 24) or 24)
        self.history: list[Message] = []
        self.objective = str(getattr(args, "objective", "") or "")
        self._busy = False
        self._stop = False
        self._cmd_q: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._feedback_q: queue.Queue[str] = queue.Queue()
        self._server = None
        self._target: dict[str, Any] | None = None
        self._secret = str(getattr(args, "secret", "") or "")
        self._target_key = ""
        self._brain = None
        self._brain_meta: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _ensure_target(self) -> tuple[dict[str, Any], str]:
        """Build or reuse local canary / URL / JSON target."""
        import session_log as slog
        from agent_loop import make_local_canary_target, target_from_url

        target_s = (getattr(self.args, "target", None) or "local").strip()
        secret = self._secret
        key = f"{target_s}|{secret}"
        if self._target is not None and key == self._target_key:
            return self._target, secret

        # Tear down previous local server if any
        self._shutdown_server()

        if target_s.lower() == "local":
            server, _port, target, sec = make_local_canary_target(
                secret=secret or None
            )
            self._server = server
            secret = secret or sec
            self._secret = secret
        elif target_s.endswith(".json") and Path(target_s).is_file():
            target = json.loads(Path(target_s).read_text(encoding="utf-8"))
        else:
            target = target_from_url(target_s)

        self._target = target
        self._target_key = key
        _ = slog  # keep import path warm for sessions
        return target, secret

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

    def _ensure_brain(self) -> Any:
        if self._brain is not None:
            return self._brain
        # Import from __main__ helpers via local reimplementation to avoid cycles
        from agent_repl.brain import (
            make_canary_stub_brain,
            make_openai_brain,
            make_provider_brain,
        )

        sel = (getattr(self.args, "brain", None) or "stub").strip().lower()
        if sel in ("stub", "script", "none", ""):
            self._brain = make_canary_stub_brain(
                objective=self.objective or "extract the canary"
            )
            self._brain_meta = {"brain": "stub", "provider": "stub"}
            return self._brain

        if sel in ("openai", "openai-compat"):
            self._brain = make_openai_brain(
                base_url=getattr(self.args, "base_url", None) or None,
                model=getattr(self.args, "model", None) or None,
                api_key=getattr(self.args, "api_key", None) or None,
                provider_id="openai",
            )
            self._brain_meta = {
                "brain": "openai",
                "provider": "openai",
                "model": getattr(self._brain, "model", None),
            }
            return self._brain

        brain, resolved = make_provider_brain(
            sel,
            model=getattr(self.args, "model", None) or None,
            base_url=getattr(self.args, "base_url", None) or None,
            api_key=getattr(self.args, "api_key", None) or None,
        )
        self._brain = brain
        self._brain_meta = {
            "brain": "provider",
            "provider": resolved.id,
            "label": resolved.label,
            "base_url": resolved.base_url,
            "model": resolved.model,
            "key_source": resolved.key_source,
        }
        return self._brain

    def _drain_feedback(self) -> list[str]:
        out: list[str] = []
        while True:
            try:
                out.append(self._feedback_q.get_nowait())
            except queue.Empty:
                break
        return out

    def _run_turn(self, text: str) -> None:
        import session_log as slog
        from agent_repl.loop import run_agent_loop
        from agent_repl.tools import EngagementContext

        text = (text or "").strip()
        if not text:
            emit("session_error", error="empty turn")
            return

        with self._lock:
            if self._busy:
                # Queue as feedback if a turn is already running
                self._feedback_q.put(text)
                emit("feedback_queued", text=preview(text, 200))
                return
            self._busy = True
            self._stop = False

        self.objective = text if not self.objective else self.objective
        # First turn sets objective; later turns are free-form steering
        if not self.history:
            self.objective = text

        emit("user", text=text, role="operator")
        emit("turn_start", objective=preview(self.objective, 200), busy=True)

        try:
            target, secret = self._ensure_target()
            brain = self._ensure_brain()
            # Stub brain re-bind to current objective for canary path
            if self._brain_meta.get("provider") == "stub":
                from agent_repl.brain import make_canary_stub_brain

                brain = make_canary_stub_brain(objective=self.objective)
                self._brain = brain

            emit(
                "brain_config",
                **{k: v for k, v in self._brain_meta.items() if k != "api_key"},
            )

            ctx = EngagementContext(
                objective=self.objective,
                target=target,
                secret=secret,
                max_fires=self.max_fires,
            )
            session = slog.Session(
                objective=self.objective,
                secret_fingerprint=slog.fingerprint_secret(secret),
                session_dir=self.sess_dir,
                meta={
                    "mode": "agent_chat",
                    "brain": getattr(self.args, "brain", "stub"),
                    "target": getattr(self.args, "target", "local"),
                    **self._brain_meta,
                },
            )
            if secret:
                session.set_secret_for_redact(secret)

            history = list(self.history)
            if history:
                history.append(Message(role="user", content=text))
            else:
                history = None  # loop seeds system + user from objective

            events = _make_events()

            def feedback() -> list[str]:
                if self._stop:
                    return ["[operator requested stop — call finish or ask_operator]"]
                return self._drain_feedback()

            result = run_agent_loop(
                objective=self.objective if history is None else text,
                brain=brain,
                ctx=ctx,
                events=events,
                max_rounds=self.max_rounds,
                session=session,
                history=history,
                feedback=feedback,
            )
            self.history = list(result.messages or [])

            emit(
                "turn_complete",
                status=result.status,
                stop_tool=result.stop_tool,
                summary=preview(result.summary, 400),
                rounds=result.rounds,
                tool_calls=result.tool_calls,
                session_path=result.session_path,
                success=bool(result.success),
                busy=False,
            )
        except Exception as e:
            emit("session_error", error=str(e)[:400], busy=False)
        finally:
            with self._lock:
                self._busy = False
            emit("ready", busy=False)

    def _handle(self, cmd: dict[str, Any]) -> bool:
        """Return False to exit the session loop."""
        op = str(cmd.get("op") or cmd.get("cmd") or "turn").strip().lower()

        if op in ("quit", "exit", "q"):
            emit("session_end", reason="quit")
            return False

        if op == "stop":
            self._stop = True
            self._feedback_q.put(
                "[operator stop — wrap up: finish(summary) or ask_operator]"
            )
            emit("stop_requested")
            return True

        if op == "clear":
            self.history = []
            self.objective = ""
            while True:
                try:
                    self._feedback_q.get_nowait()
                except queue.Empty:
                    break
            emit("session_cleared")
            emit("ready", busy=False)
            return True

        if op == "set":
            changed: list[str] = []
            if "target" in cmd and cmd["target"] is not None:
                self.args.target = str(cmd["target"])
                self._target = None
                self._target_key = ""
                changed.append("target")
            if "secret" in cmd and cmd["secret"] is not None:
                self._secret = str(cmd["secret"])
                self.args.secret = self._secret
                self._target = None
                self._target_key = ""
                changed.append("secret")
            if "brain" in cmd and cmd["brain"]:
                self.args.brain = str(cmd["brain"]).strip().lower()
                self._brain = None
                self._brain_meta = {}
                changed.append("brain")
            if "model" in cmd and cmd["model"] is not None:
                self.args.model = str(cmd["model"])
                self._brain = None
                changed.append("model")
            if "max_rounds" in cmd and cmd["max_rounds"] is not None:
                self.max_rounds = int(cmd["max_rounds"])
                changed.append("max_rounds")
            if "max_fires" in cmd and cmd["max_fires"] is not None:
                self.max_fires = int(cmd["max_fires"])
                changed.append("max_fires")
            if "objective" in cmd and cmd["objective"] is not None:
                self.objective = str(cmd["objective"])
                changed.append("objective")
            emit("session_config", changed=changed, **{
                "target": getattr(self.args, "target", "local"),
                "brain": getattr(self.args, "brain", "stub"),
                "model": getattr(self.args, "model", "") or "",
                "max_rounds": self.max_rounds,
                "objective": preview(self.objective, 120),
            })
            return True

        if op == "feedback":
            text = str(cmd.get("text") or cmd.get("message") or "").strip()
            if not text:
                emit("session_error", error="empty feedback")
                return True
            if self._busy:
                self._feedback_q.put(text)
                emit("feedback_queued", text=preview(text, 200))
            else:
                # Idle: treat as a normal turn so operator can keep chatting
                self._run_turn(text)
            return True

        # turn (default)
        text = str(cmd.get("text") or cmd.get("message") or cmd.get("objective") or "").strip()
        if not text:
            emit("session_error", error="empty turn")
            return True
        self._run_turn(text)
        return True

    def _stdin_reader(self) -> None:
        try:
            for raw in sys.stdin:
                line = raw.strip()
                if not line:
                    continue
                if line.startswith("{"):
                    try:
                        cmd = json.loads(line)
                        if not isinstance(cmd, dict):
                            cmd = {"op": "turn", "text": str(cmd)}
                    except json.JSONDecodeError:
                        cmd = {"op": "turn", "text": line}
                else:
                    cmd = {"op": "turn", "text": line}
                self._cmd_q.put(cmd)
        except Exception as e:
            emit("session_error", error=f"stdin reader: {e}"[:200])
        finally:
            self._cmd_q.put(None)

    def run(self) -> int:
        from agent_repl.tools import build_default_registry

        reg = build_default_registry()
        emit(
            "session_ready",
            mode="agent_chat",
            brain=getattr(self.args, "brain", "stub"),
            target=getattr(self.args, "target", "local"),
            model=getattr(self.args, "model", "") or "",
            max_rounds=self.max_rounds,
            tools=reg.names(),
            protocol="jsonl",
            ops=["turn", "feedback", "stop", "clear", "set", "quit"],
        )
        emit("ready", busy=False)

        reader = threading.Thread(target=self._stdin_reader, name="chat-stdin", daemon=True)
        reader.start()

        try:
            while True:
                cmd = self._cmd_q.get()
                if cmd is None:
                    break
                if not self._handle(cmd):
                    break
        finally:
            self._shutdown_server()
        return 0


def run_chat_session(args: Any) -> int:
    return ChatSession(args).run()
