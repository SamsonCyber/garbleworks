"""RoE live battery: scope gate + deterministic plumbing path."""
from __future__ import annotations

from pathlib import Path

import authority
import pytest
from bench import roe_live_battery as roe


def test_load_roe_file():
    path = Path(__file__).resolve().parent / "engagements" / "local-selftest-roe.json"
    assert path.exists()
    r = roe.load_roe(str(path))
    assert r.engagement_id
    assert "127.0.0.1" in r.authorized_scope
    assert r.in_scope("127.0.0.1")
    assert not r.in_scope("evil.example.com")


def test_assert_host_in_scope_denies_off_scope():
    r = authority.AuthorizationReceipt(
        engagement_id="t",
        authorized_scope=["127.0.0.1"],
        authority_source="test",
    )
    with pytest.raises(SystemExit, match="SCOPE DENIED"):
        roe.assert_host_in_scope("evil.example.com", r)
    roe.assert_host_in_scope("127.0.0.1", r)  # no raise


def test_roe_battery_deterministic_plumbing():
    """Real fire path under RoE against deterministic canary (no Ollama required)."""
    path = Path(__file__).resolve().parent / "engagements" / "local-selftest-roe.json"
    receipt = roe.load_roe(str(path))
    payload = roe.run_roe_battery(
        receipt=receipt,
        tools="garbleworks:gw_baseline",
        battery="v1_canary",
        target_mode="deterministic",
        only=["easy_dump_marker", "easy_baseline_recipe"],
        tag="test-roe-plumbing",
    )
    assert "roe" in payload
    assert payload["roe"]["engagement_id"] == receipt.engagement_id
    claim = payload["live_asr_claim"]
    assert claim["schema_version"] == "live_asr.v1"
    assert claim["dry_run"] is False
    assert claim["complete_case"]["n_completed"] >= 1
    # Easy unlocks should leak on deterministic canary
    assert claim["complete_case"]["successes"] >= 1
    assert payload.get("_roe_paths", {}).get("full")
