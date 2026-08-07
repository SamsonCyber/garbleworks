"""Shared types for the Garbleworks agent REPL loop.

Pure data: messages, tool calls, events, run results. No I/O.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


def new_tool_id() -> str:
    return f"call_{uuid.uuid4().hex[:12]}"


@dataclass
class ToolCall:
    """One model-requested tool invocation."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ToolCall":
        args = d.get("arguments")
        if isinstance(args, str):
            import json

            try:
                args = json.loads(args) if args.strip() else {}
            except json.JSONDecodeError:
                args = {"_raw": args}
        if not isinstance(args, dict):
            args = {}
        return cls(
            id=str(d.get("id") or new_tool_id()),
            name=str(d.get("name") or ""),
            arguments=args,
        )


@dataclass
class Message:
    """Chat message in the agent history."""

    role: str  # system | user | assistant | tool
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None  # tool name when role=tool

    def to_openai(self) -> dict[str, Any]:
        """Serialize for OpenAI-compatible chat APIs."""
        if self.role == "tool":
            return {
                "role": "tool",
                "tool_call_id": self.tool_call_id or "",
                "name": self.name or "",
                "content": self.content or "",
            }
        if self.role == "assistant" and self.tool_calls:
            return {
                "role": "assistant",
                "content": self.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": _args_json(tc.arguments),
                        },
                    }
                    for tc in self.tool_calls
                ],
            }
        return {"role": self.role, "content": self.content or ""}


def _args_json(args: dict[str, Any]) -> str:
    import json

    return json.dumps(args, ensure_ascii=False, default=str)


# Brain return shape: content string + list of tool calls (may be empty).
BrainReply = dict[str, Any]
# brain(messages: list[Message], tools: list[dict]) -> BrainReply
BrainFn = Callable[..., BrainReply]


STOP_TOOLS = frozenset({"finish", "ask_operator"})


@dataclass
class AgentEvents:
    """Callbacks the TUI / headless CLI subscribe to."""

    on_text: Callable[[str], None] = lambda _t: None
    on_tool_start: Callable[[str, str, dict], None] = lambda _id, _n, _a: None
    on_tool_result: Callable[[str, str, str, bool], None] = (
        lambda _id, _n, _content, _is_error: None
    )
    on_round: Callable[[int, int], None] = lambda _r, _max: None
    on_stop: Callable[[str, dict], None] = lambda _tool, _args: None
    on_error: Callable[[str], None] = lambda _e: None
    on_message: Callable[[Message], None] = lambda _m: None
    # Mid-turn operator steering (live feedback queue drained before brain call)
    on_feedback: Callable[[str], None] = lambda _m: None


@dataclass
class RunResult:
    """Terminal state of one agent REPL run.

    ``status`` is loop lifecycle (finished | need_operator | max_rounds | error).
    ``success`` is objective achievement (harness-gated for canary runs).
    Clean stop without a leak is status=finished, success=False.
    """

    status: str  # finished | need_operator | max_rounds | error | aborted
    summary: str = ""
    stop_tool: str | None = None
    stop_args: dict[str, Any] = field(default_factory=dict)
    rounds: int = 0
    tool_calls: int = 0
    messages: list[Message] = field(default_factory=list)
    error: str | None = None
    session_path: str | None = None
    wall_s: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)
    success: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "stop_tool": self.stop_tool,
            "stop_args": self.stop_args,
            "rounds": self.rounds,
            "tool_calls": self.tool_calls,
            "error": self.error,
            "session_path": self.session_path,
            "wall_s": self.wall_s,
            "meta": self.meta,
            "message_count": len(self.messages),
            "success": bool(self.success),
        }


def preview(s: str, n: int = 200) -> str:
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def now_ts() -> float:
    return time.time()
