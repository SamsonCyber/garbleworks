"""Garbleworks interactive agent REPL (Claude Code / Hermes-class).

Pure loop + tool registry + injectable brain. Headless CLI:
  python -m agent_repl --objective "extract the canary" --target local

TUI and MCP remain separate I/O planes; they can host the same loop.
"""
from __future__ import annotations

from agent_repl.brain import (
    make_callable_brain,
    make_canary_stub_brain,
    make_openai_brain,
    make_provider_brain,
    make_scripted_brain,
    normalize_brain_reply,
)
from agent_repl.app import run_app, should_launch_app
from agent_repl.config import AgentConfig, load_config, save_config
from agent_repl.loop import run_agent_loop, run_headless_canary
from agent_repl.providers import list_providers, resolve_provider
from agent_repl.tools import (
    DEFAULT_SYSTEM_PROMPT,
    EngagementContext,
    ToolRegistry,
    build_default_registry,
)
from agent_repl.types import (
    STOP_TOOLS,
    AgentEvents,
    Message,
    RunResult,
    ToolCall,
)

__all__ = [
    "AgentConfig",
    "AgentEvents",
    "DEFAULT_SYSTEM_PROMPT",
    "EngagementContext",
    "Message",
    "RunResult",
    "STOP_TOOLS",
    "ToolCall",
    "ToolRegistry",
    "build_default_registry",
    "list_providers",
    "load_config",
    "make_callable_brain",
    "make_canary_stub_brain",
    "make_openai_brain",
    "make_provider_brain",
    "make_scripted_brain",
    "normalize_brain_reply",
    "resolve_provider",
    "run_agent_loop",
    "run_app",
    "run_headless_canary",
    "save_config",
    "should_launch_app",
]
