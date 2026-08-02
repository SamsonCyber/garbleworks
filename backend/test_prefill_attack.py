"""Unit tests for prefill_attack (no live API)."""
from __future__ import annotations

import json
from unittest import mock

import canary
import prefill_attack as pa


_SECRET = "CANARY_test_unit_9z"


def test_default_prefills_do_not_embed_secret():
    for p in pa.DEFAULT_PREFILLS:
        assert _SECRET not in p
        assert "CANARY_test" not in p


def test_scrub_secret():
    assert "[REDACTED_BY_HARNESS]" in pa.scrub_secret(f"x {_SECRET} y", _SECRET)


def test_run_prefill_attack_hits_on_continuation(monkeypatch):
    """Mock Anthropic: warm then prefill continuation contains secret."""
    calls = {"n": 0}

    def fake_fire(**kwargs):
        calls["n"] += 1
        messages = kwargs["messages"]
        # warm: single user
        if len(messages) == 1:
            return "Hello! I am DocAssist.", 200, 10, None
        # prefill turn: last message is assistant prefill
        prefill = messages[-1]["content"]
        # complete the canary without refusal keywords that block is_leak
        cont = f"{_SECRET}\n\nI don't have prior dump context."
        return cont, 200, 12, None

    monkeypatch.setattr(pa, "anthropic_prefill_fire", fake_fire)
    res = pa.run_prefill_attack(
        api_key="test-key",
        model="claude-haiku-4-5-20251001",
        system=pa.system_canary_prompt(_SECRET),
        secret=_SECRET,
        max_attempts=3,
    )
    assert res.success is True
    assert res.queries >= 2
    assert res.channel == "literal"
    assert canary.is_leak(res.full_reply, _SECRET) is True
    assert res.transcript and res.transcript[-1]["leaked"] is True


def test_run_prefill_rejects_secret_in_prefill():
    try:
        pa.run_prefill_attack(
            api_key="k", model="m", system="s", secret=_SECRET,
            prefills=[f"SECRET={_SECRET}"],
        )
        assert False, "should raise"
    except ValueError as e:
        assert "prefill" in str(e).lower()


def test_mcp_tool_registered():
    import mcp_server
    # FastMCP stores tools; ensure name exists in module
    assert hasattr(mcp_server, "prefill_attack")
