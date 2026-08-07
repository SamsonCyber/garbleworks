"""Chat session protocol tests (stdin JSONL → GW| events, stub brain)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent


def _run_session(lines: list[str], timeout: float = 60.0) -> list[dict]:
    proc = subprocess.Popen(
        [sys.executable, "-m", "agent_repl", "--session", "--brain", "stub", "--target", "local"],
        cwd=str(BACKEND),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **dict(**{k: v for k, v in __import__("os").environ.items()}),
            "PYTHONIOENCODING": "utf-8",
            "GARBLEWORKS_TUI": "1",
            "GARBLEWORKS_CHAT": "1",
        },
    )
    assert proc.stdin is not None
    assert proc.stdout is not None
    payload = "\n".join(lines) + "\n"
    try:
        out, err = proc.communicate(payload, timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        raise AssertionError(f"session timed out\nstderr={err[:500]}") from None

    events: list[dict] = []
    for line in (out or "").splitlines():
        if line.startswith("GW|"):
            try:
                events.append(json.loads(line[3:]))
            except json.JSONDecodeError:
                pass
    return events


def test_session_ready_and_stub_turn():
    events = _run_session(
        [
            json.dumps({"op": "turn", "text": "extract the canary"}),
            json.dumps({"op": "quit"}),
        ]
    )
    kinds = [e.get("kind") for e in events]
    assert "session_ready" in kinds
    assert "user" in kinds
    assert "turn_start" in kinds
    assert "turn_complete" in kinds
    # Operator-visible tool transparency (Wallbreaker-class stream)
    assert "tool_start" in kinds, f"missing tool_start in {kinds}"
    assert "tool_result" in kinds, f"missing tool_result in {kinds}"
    starts = [e for e in events if e.get("kind") == "tool_start"]
    results = [e for e in events if e.get("kind") == "tool_result"]
    assert len(starts) >= 2, f"expected multi-tool engagement, got starts={starts}"
    assert len(results) >= 2
    tool_names = {e.get("tool") for e in starts}
    assert "fire_target" in tool_names or "compose_framing" in tool_names
    # Each start should carry tool_id + tool name for TUI live tool-call state
    for e in starts:
        assert e.get("tool"), e
        assert e.get("tool_id"), e
    complete = [e for e in events if e.get("kind") == "turn_complete"]
    assert complete, f"no turn_complete in {kinds}"
    last = complete[-1]
    assert last.get("status") in ("finished", "need_operator", "max_rounds", "error")
    assert int(last.get("tool_calls") or 0) >= 1
    assert int(last.get("rounds") or 0) >= 1
    # Local canary + stub brain is a deterministic harness win
    assert last.get("status") == "finished"
    assert last.get("success") is True
    assert "session_end" in kinds


def test_session_clear_and_feedback_ops():
    events = _run_session(
        [
            json.dumps({"op": "set", "max_rounds": 6}),
            json.dumps({"op": "clear"}),
            json.dumps({"op": "quit"}),
        ]
    )
    kinds = [e.get("kind") for e in events]
    assert "session_ready" in kinds
    assert "session_config" in kinds
    assert "session_cleared" in kinds
    assert "session_end" in kinds


def test_loop_feedback_injects_user_message():
    from agent_repl.brain import make_scripted_brain
    from agent_repl.loop import run_agent_loop
    from agent_repl.tools import EngagementContext
    from agent_repl.types import AgentEvents

    fb = ["try the literal dump"]
    seen: list[str] = []

    def drain():
        nonlocal fb
        out = list(fb)
        fb = []
        return out

    events = AgentEvents(on_feedback=lambda m: seen.append(m))
    brain = make_scripted_brain(
        [
            {
                "content": "wrapping up",
                "tool_calls": [
                    {
                        "name": "finish",
                        "arguments": {"summary": "stopped after feedback", "success": False},
                    }
                ],
            }
        ]
    )
    result = run_agent_loop(
        objective="test feedback",
        brain=brain,
        ctx=EngagementContext(objective="test feedback"),
        events=events,
        max_rounds=3,
        feedback=drain,
    )
    assert seen == ["try the literal dump"]
    assert any(
        m.role == "user" and "OPERATOR FEEDBACK" in (m.content or "")
        for m in result.messages
    )
    assert result.status == "finished"
