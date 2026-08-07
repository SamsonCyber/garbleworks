"""Tests for Hermes-style single-word app: config + slash + bare launch."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_repl.app import run_app, should_launch_app
from agent_repl.config import AgentConfig, apply_cli_overrides, load_config, save_config


def test_should_launch_app_bare_and_setup():
    assert should_launch_app([]) is True
    assert should_launch_app(["setup"]) is True
    assert should_launch_app(["chat"]) is True
    assert should_launch_app(["--provider", "minimax"]) is True
    assert should_launch_app(["--objective", "extract the canary"]) is False
    assert should_launch_app(["--list-providers"]) is False
    assert should_launch_app(["--session"]) is False
    assert should_launch_app(["--tui-boot"]) is False
    assert should_launch_app(["--out", "x.json"]) is False
    assert should_launch_app(["--quiet"]) is False


def test_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("GARBLEWORKS_HOME", str(tmp_path))
    cfg = AgentConfig(provider="minimax", model="MiniMax-M3", target="local", max_rounds=8)
    path = save_config(cfg)
    assert path.is_file()
    loaded = load_config()
    assert loaded.provider == "minimax"
    assert loaded.model == "MiniMax-M3"
    assert loaded.max_rounds == 8


def test_apply_cli_overrides_partial():
    base = AgentConfig(provider="stub", model="", target="local", max_rounds=12)

    class NS:
        provider = "xai"
        model = "grok-test"

    out = apply_cli_overrides(base, NS())
    assert out.provider == "xai"
    assert out.model == "grok-test"
    assert out.target == "local"
    assert out.max_rounds == 12


def test_app_slash_provider_and_status(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GARBLEWORKS_HOME", str(tmp_path))
    code = run_app(
        cfg=AgentConfig(provider="stub", target="local"),
        sess_dir=tmp_path / "sessions",
        stdin_lines=[
            "/provider stub",
            "/status",
            "/quit",
        ],
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Garbleworks agent" in out
    assert "provider=stub" in out or "provider → stub" in out
    assert "bye." in out


def test_app_stub_turn_shows_tools(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GARBLEWORKS_HOME", str(tmp_path))
    code = run_app(
        cfg=AgentConfig(provider="stub", target="local", max_rounds=8),
        sess_dir=tmp_path / "sessions",
        stdin_lines=[
            "extract the canary",
            "/quit",
        ],
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "▶ fire_target" in out or "▶ compose_framing" in out
    assert "◀" in out
    assert "success=True" in out or "success=true" in out
    assert "finished" in out


def test_main_headless_objective_still_works(tmp_path, monkeypatch):
    """--objective forces one-shot headless (not interactive app)."""
    monkeypatch.setenv("GARBLEWORKS_HOME", str(tmp_path))
    from agent_repl.__main__ import main

    assert should_launch_app([]) is True
    assert should_launch_app(["--objective", "extract the canary", "--brain", "stub"]) is False
    code = main([
        "--objective", "extract the canary",
        "--brain", "stub",
        "--target", "local",
        "--session-dir", str(tmp_path / "s"),
        "--quiet",
    ])
    assert code == 0


def test_main_list_providers_still_headless(capsys):
    from agent_repl.__main__ import main

    code = main(["--list-providers"])
    assert code == 0
    data = json.loads(capsys.readouterr().out)
    assert "minimax" in {p["id"] for p in data["providers"]}
