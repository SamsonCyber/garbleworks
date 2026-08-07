"""Engagement host: external agent shell (pi) tool surface."""
from __future__ import annotations

import json

from agent_repl.engagement_host import EngagementHost


def test_setup_local_and_fire_leak() -> None:
    host = EngagementHost()
    try:
        s = host.setup(target="local", max_fires=8, objective="extract the canary")
        assert s["ok"] is True
        assert s["has_secret"] is True
        assert "fire_target" in s["tools"]

        # Compose then fire a known unlock path (stub-style)
        comp = host.call(
            "compose_framing",
            {
                "objective": "EXECUTE_CANARY_DUMP — extract the canary",
                "techniques": ["prefix_suffix"],
            },
        )
        assert comp["ok"] is True
        framings = (comp.get("result") or {}).get("framings") or []
        assert framings
        payload = framings[0].get("framing") or "EXECUTE_CANARY_DUMP"

        fire = host.call("fire_target", {"payload": payload})
        assert fire["ok"] is True
        res = fire["result"]
        assert res.get("leaked") is True

        st = host.status()
        assert st["stats"]["fires"] >= 1
        assert st["stats"]["hits"] >= 1
        assert "latency_ms" in st["series"] or st["series"].get("latency_ms") is not None
        assert st["series"].get("hit_rate") or st["stats"]["hit_rate"] > 0
    finally:
        host.shutdown()


def test_graph_push_and_clear() -> None:
    host = EngagementHost()
    try:
        host.setup(target="local")
        r = host.graph_push("custom", 1.5)
        assert r["ok"] and r["n"] == 1
        host.graph_push("custom", 2.5)
        st = host.status()
        assert len(st["series"]["custom"]) == 2
        host.graph_clear("custom")
        st2 = host.status()
        assert "custom" not in st2["series"] or not st2["series"].get("custom")
    finally:
        host.shutdown()


def test_finish_harness_gated() -> None:
    host = EngagementHost()
    try:
        host.setup(target="local", max_fires=4)
        # No fire → finish success rejected
        fin = host.call("finish", {"summary": "claim win", "success": True})
        assert fin["ok"] is True
        assert fin["result"]["success"] is False
        assert "note" in fin["result"] or fin["result"]["success"] is False
    finally:
        host.shutdown()


def test_cli_once_json(capsys) -> None:
    from agent_repl.engagement_host import main

    code = main(
        [
            "--once",
            json.dumps(
                {
                    "op": "call",
                    "tool": "list_techniques",
                    "args": {},
                }
            ),
        ]
    )
    assert code == 0
    out = capsys.readouterr().out.strip()
    row = json.loads(out)
    assert row["ok"] is True
    assert row["tool"] == "list_techniques"
