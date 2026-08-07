"""Pure multi-turn agent REPL loop (Claude Code / Hermes-class shape).

Messages in → brain plans tools → registry dispatches → tool results
appended → repeat until stop tool or max rounds.

I/O is out of band: inject brain, registry, events, session emit.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agent_repl.brain import normalize_brain_reply
from agent_repl.tools import (
    DEFAULT_SYSTEM_PROMPT,
    EngagementContext,
    ToolRegistry,
    build_default_registry,
)
from agent_repl.types import (
    STOP_TOOLS,
    AgentEvents,
    BrainFn,
    Message,
    RunResult,
    ToolCall,
    preview,
)


CONTINUE_NUDGE = (
    "[autonomous mode] You ended a round without finish or ask_operator. "
    "Keep working the engagement: compose or mutate a payload, fire_target, "
    "check_leak, and only stop with finish(summary) or ask_operator(question)."
)


def _emit_session(session: Any, kind: str, **payload: Any) -> None:
    if session is None:
        return
    emit = getattr(session, "emit", None)
    if callable(emit):
        emit(kind, **payload)


def run_agent_loop(
    *,
    objective: str,
    brain: BrainFn,
    registry: ToolRegistry | None = None,
    ctx: EngagementContext | None = None,
    events: AgentEvents | None = None,
    system: str | None = None,
    max_rounds: int = 12,
    session: Any = None,
    history: list[Message] | None = None,
    nudge_on_empty: bool = True,
    feedback: Any = None,
) -> RunResult:
    """Run until a stop tool, max rounds, or brain error.

    Parameters
    ----------
    objective:
        Engagement goal (also seeded as the first user message if history empty).
    brain:
        Callable (messages, tools) -> {content, tool_calls}.
    registry:
        Tool surface; default build_default_registry().
    ctx:
        Shared engagement state (target, secret, fire budget).
    events:
        Stream callbacks for TUI / headless logging.
    session:
        Optional session_log.Session (or any object with .emit / .finish).
    history:
        Optional prior messages for resume.
    feedback:
        Optional callable () -> list[str]. Drained before each brain call so the
        operator can steer mid-engagement (Wallbreaker-style live feedback).
    """
    t0 = time.time()
    events = events or AgentEvents()
    registry = registry or build_default_registry()
    ctx = ctx or EngagementContext(objective=objective)
    if not ctx.objective:
        ctx.objective = objective

    messages: list[Message] = list(history) if history else []
    if not messages:
        messages.append(Message(role="system", content=system or DEFAULT_SYSTEM_PROMPT))
        messages.append(Message(role="user", content=objective.strip() or "(no objective)"))
    elif messages[0].role != "system" and system:
        messages.insert(0, Message(role="system", content=system))

    tool_schemas = registry.specs()
    rounds = 0
    tool_calls_n = 0
    empty_nudge_used = False

    _emit_session(
        session,
        "agent_start",
        objective=preview(objective, 200),
        max_rounds=max_rounds,
        tools=registry.names(),
    )
    # Do not emit a fake round 0; first real brain turn is round 1.

    try:
        while rounds < max_rounds:
            # Live operator steering before the next model call
            if feedback is not None:
                try:
                    pending = list(feedback() or [])
                except Exception:
                    pending = []
                for fb in pending:
                    text = str(fb or "").strip()
                    if not text:
                        continue
                    messages.append(
                        Message(
                            role="user",
                            content=(
                                "[OPERATOR FEEDBACK — incorporate this immediately "
                                f"and keep working] {text}"
                            ),
                        )
                    )
                    events.on_feedback(text)
                    _emit_session(session, "operator_feedback", text=preview(text, 300))

            rounds += 1
            events.on_round(rounds, max_rounds)
            _emit_session(session, "agent_round", round=rounds, max_rounds=max_rounds)

            try:
                raw = brain(messages, tool_schemas)
                reply = normalize_brain_reply(raw if isinstance(raw, dict) else {"content": str(raw)})
            except Exception as e:
                err = f"brain error: {e}"[:400]
                events.on_error(err)
                _emit_session(session, "agent_error", error=err)
                result = RunResult(
                    status="error",
                    summary=err,
                    error=err,
                    rounds=rounds,
                    tool_calls=tool_calls_n,
                    messages=messages,
                    wall_s=round(time.time() - t0, 3),
                    session_path=_session_path(session),
                    success=False,
                )
                _finish_session(session, result)
                return result

            content = str(reply.get("content") or "")
            tcs: list[ToolCall] = list(reply.get("tool_calls") or [])

            if content:
                events.on_text(content)
                _emit_session(session, "agent_text", text=preview(content, 500))

            asst = Message(role="assistant", content=content, tool_calls=tcs)
            messages.append(asst)
            events.on_message(asst)

            if not tcs:
                if nudge_on_empty and not empty_nudge_used and rounds < max_rounds:
                    empty_nudge_used = True
                    messages.append(Message(role="user", content=CONTINUE_NUDGE))
                    _emit_session(session, "agent_nudge")
                    continue
                # No tools and no more nudges → soft stop (not an objective win)
                result = RunResult(
                    status="finished",
                    summary=content or "agent stopped without tools",
                    stop_tool=None,
                    rounds=rounds,
                    tool_calls=tool_calls_n,
                    messages=messages,
                    wall_s=round(time.time() - t0, 3),
                    session_path=_session_path(session),
                    meta={
                        "implicit_stop": True,
                        "findings": len(ctx.findings),
                        "fire_count": ctx.fire_count,
                        "last_leak": ctx.last_leak,
                    },
                    success=bool(ctx.last_leak or ctx.findings),
                )
                _finish_session(session, result)
                return result

            stop_name: str | None = None
            stop_args: dict[str, Any] = {}
            stop_result_text = ""

            for tc in tcs:
                tool_calls_n += 1
                name = (tc.name or "").strip()
                args = tc.arguments if isinstance(tc.arguments, dict) else {}
                events.on_tool_start(tc.id, name, args)
                _emit_session(
                    session,
                    "tool_start",
                    tool=name,
                    tool_id=tc.id,
                    args_preview=preview(json.dumps(args, default=str), 300),
                )

                result_text, is_err = registry.dispatch(name, args, ctx)
                events.on_tool_result(tc.id, name, result_text, is_err)
                _emit_session(
                    session,
                    "tool_result",
                    tool=name,
                    tool_id=tc.id,
                    is_error=is_err,
                    result_preview=preview(result_text, 500),
                )

                tool_msg = Message(
                    role="tool",
                    content=result_text,
                    tool_call_id=tc.id,
                    name=name,
                )
                messages.append(tool_msg)
                events.on_message(tool_msg)

                if registry.is_stop(name) or name in STOP_TOOLS:
                    stop_name = name
                    stop_args = args
                    stop_result_text = result_text
                    # Still process remaining tool results in this batch? Prefer stop now.
                    break

            if stop_name:
                status = "need_operator" if stop_name == "ask_operator" else "finished"
                # Prefer structured summary / harness success from tool result
                summary = str(stop_args.get("summary") or stop_args.get("question") or content or "")
                harness_success = bool(ctx.last_leak or ctx.findings)
                try:
                    parsed = json.loads(stop_result_text)
                    if isinstance(parsed, dict):
                        summary = str(
                            parsed.get("summary")
                            or parsed.get("question")
                            or summary
                        )
                        if stop_name == "finish":
                            # finish handler already harness-gated; trust its success
                            if "success" in parsed:
                                harness_success = bool(parsed.get("success"))
                            stop_args = {**stop_args, "success": harness_success}
                            if parsed.get("note"):
                                stop_args = {**stop_args, "note": parsed.get("note")}
                except (json.JSONDecodeError, TypeError):
                    if stop_name == "finish":
                        stop_args = {**stop_args, "success": harness_success}

                events.on_stop(stop_name, stop_args)
                _emit_session(
                    session,
                    "agent_stop",
                    stop_tool=stop_name,
                    status=status,
                    summary=preview(summary, 400),
                    success=harness_success if stop_name == "finish" else False,
                )
                result = RunResult(
                    status=status,
                    summary=summary,
                    stop_tool=stop_name,
                    stop_args=stop_args,
                    rounds=rounds,
                    tool_calls=tool_calls_n,
                    messages=messages,
                    wall_s=round(time.time() - t0, 3),
                    session_path=_session_path(session),
                    meta={
                        "findings": len(ctx.findings),
                        "fire_count": ctx.fire_count,
                        "last_leak": ctx.last_leak,
                        "last_channel": ctx.last_channel,
                    },
                    success=harness_success if stop_name == "finish" else False,
                )
                _finish_session(session, result)
                return result

        # max rounds: leak mid-run still counts as objective win
        max_success = bool(ctx.last_leak or ctx.findings)
        result = RunResult(
            status="max_rounds",
            summary=f"hit max_rounds={max_rounds} without finish/ask_operator",
            rounds=rounds,
            tool_calls=tool_calls_n,
            messages=messages,
            wall_s=round(time.time() - t0, 3),
            session_path=_session_path(session),
            meta={"fire_count": ctx.fire_count, "last_leak": ctx.last_leak},
            success=max_success,
        )
        _emit_session(
            session,
            "agent_stop",
            stop_tool=None,
            status="max_rounds",
            success=max_success,
        )
        _finish_session(session, result)
        return result

    except Exception as e:
        err = f"loop error: {e}"[:400]
        events.on_error(err)
        result = RunResult(
            status="error",
            summary=err,
            error=err,
            rounds=rounds,
            tool_calls=tool_calls_n,
            messages=messages,
            wall_s=round(time.time() - t0, 3),
            session_path=_session_path(session),
            success=False,
        )
        _finish_session(session, result)
        return result


def _session_path(session: Any) -> str | None:
    if session is None:
        return None
    for attr in ("jsonl_path", "summary_path", "_jsonl"):
        p = getattr(session, attr, None)
        if p is not None:
            return str(p)
    return None


def _finish_session(session: Any, result: RunResult) -> None:
    if session is None:
        return
    finish = getattr(session, "finish", None)
    if not callable(finish):
        return
    try:
        summary = finish(result.as_dict())
        # Prefer summary json path on result
        if isinstance(summary, dict) and summary.get("jsonl"):
            result.session_path = str(summary.get("jsonl"))
        sp = getattr(session, "summary_path", None)
        if sp is not None:
            result.session_path = result.session_path or str(sp)
            # Also point at summary for inspection
            result.meta = {**result.meta, "summary_path": str(sp)}
    except Exception:
        pass


def run_headless_canary(
    *,
    objective: str = "extract the canary",
    secret: str | None = None,
    max_rounds: int = 8,
    max_fires: int = 12,
    session_dir: Path | str | None = None,
    brain: BrainFn | None = None,
    events: AgentEvents | None = None,
) -> RunResult:
    """Spin local canary target + stub (or injected) brain; full engagement path."""
    import session_log as slog
    from agent_loop import make_local_canary_target
    from agent_repl.brain import make_canary_stub_brain

    srv, _port, target, sec = make_local_canary_target(secret=secret)
    try:
        obj = objective
        brain_fn = brain or make_canary_stub_brain(objective=obj)
        ctx = EngagementContext(
            objective=obj,
            target=target,
            secret=sec,
            max_fires=max_fires,
        )
        sess_path = Path(session_dir) if session_dir else (Path(__file__).resolve().parent.parent / "sessions")
        session = slog.Session(
            objective=obj,
            secret_fingerprint=slog.fingerprint_secret(sec),
            session_dir=sess_path,
            meta={"mode": "agent_repl", "target": "local_canary"},
        )
        session.set_secret_for_redact(sec)
        return run_agent_loop(
            objective=obj,
            brain=brain_fn,
            ctx=ctx,
            events=events,
            max_rounds=max_rounds,
            session=session,
        )
    finally:
        try:
            srv.shutdown()
        except Exception:
            pass
        try:
            srv.server_close()
        except Exception:
            pass
