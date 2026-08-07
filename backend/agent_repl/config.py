"""Persisted operator prefs for the single-word agent app (Hermes-style).

Stored at ~/.garbleworks/agent.json. CLI flags override for one run.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


CONFIG_DIR_NAME = ".garbleworks"
CONFIG_FILE_NAME = "agent.json"


def config_dir() -> Path:
    override = (os.environ.get("GARBLEWORKS_HOME") or "").strip()
    if override:
        return Path(override)
    return Path.home() / CONFIG_DIR_NAME


def config_path() -> Path:
    return config_dir() / CONFIG_FILE_NAME


@dataclass
class AgentConfig:
    """In-app settings the operator can change without CLI flags."""

    provider: str = "stub"  # stub | minimax | xai | opencode-zen | …
    model: str = ""
    base_url: str = ""
    target: str = "local"
    secret: str = ""
    max_rounds: int = 12
    max_fires: int = 24
    # last free-text objective (resume hint only)
    last_objective: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AgentConfig":
        if not data or not isinstance(data, dict):
            return cls()
        known = {f.name for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for k, v in data.items():
            if k not in known:
                continue
            if k in ("max_rounds", "max_fires"):
                try:
                    kwargs[k] = int(v)
                except (TypeError, ValueError):
                    continue
            else:
                kwargs[k] = str(v) if v is not None else ""
        return cls(**kwargs)


def load_config(path: Path | None = None) -> AgentConfig:
    p = path or config_path()
    if not p.is_file():
        return AgentConfig()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AgentConfig()
    return AgentConfig.from_dict(raw if isinstance(raw, dict) else {})


def save_config(cfg: AgentConfig, path: Path | None = None) -> Path:
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    # Never write secrets into the main config file if empty placeholder
    data = cfg.as_dict()
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def apply_cli_overrides(cfg: AgentConfig, args: Any) -> AgentConfig:
    """Merge argparse Namespace into a copy of cfg (CLI wins when set).

    Only attributes present on ``args`` are applied (use a thin namespace
    that omits unset flags so saved prefs survive bare `gw`).
    """
    out = AgentConfig.from_dict(cfg.as_dict())
    provider = getattr(args, "provider", None)
    brain = getattr(args, "brain", None)
    if provider is not None and str(provider).strip():
        out.provider = str(provider).strip().lower()
    elif brain is not None and str(brain).strip():
        out.provider = str(brain).strip().lower()
    if getattr(args, "model", None) is not None:
        out.model = str(args.model or "").strip()
    if getattr(args, "base_url", None) is not None:
        out.base_url = str(args.base_url or "").strip()
    if getattr(args, "target", None) is not None and str(args.target).strip():
        out.target = str(args.target).strip()
    if getattr(args, "secret", None) is not None:
        out.secret = str(args.secret or "")
    mr = getattr(args, "max_rounds", None)
    if mr is not None and int(mr) > 0:
        out.max_rounds = int(mr)
    mf = getattr(args, "max_fires", None)
    if mf is not None and int(mf) > 0:
        out.max_fires = int(mf)
    obj = getattr(args, "objective", None)
    if obj is not None and str(obj).strip():
        out.last_objective = str(obj).strip()
    return out
