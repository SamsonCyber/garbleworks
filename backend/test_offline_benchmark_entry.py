"""Drive the shipped offline benchmark entry point (structural success).

Does not hard-code expected metric values. Runs a fast subset of real suites
through benchmark_harness.main and asserts overall_ok + required suite names.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import benchmark_harness as BH  # noqa: E402


def test_benchmark_harness_security_math_export(tmp_path: Path) -> None:
    out = tmp_path / "bench_out"
    code = BH.main(
        [
            "--out",
            str(out),
            "--suite",
            "math_closed_form,export,security",
            "--fail-on-regression",
        ]
    )
    assert code == 0, "benchmark_harness should exit 0 on offline suites"
    latest = out / "benchmark-latest.json"
    assert latest.is_file(), "must write benchmark-latest.json"
    report = json.loads(latest.read_text(encoding="utf-8"))
    assert report.get("overall_ok") is True
    names = {s.get("name") for s in report.get("suites") or []}
    assert {"math_closed_form", "export", "security"} <= names
    for suite in report["suites"]:
        assert suite.get("ok") is True, suite.get("name")
        assert isinstance(suite.get("metrics"), list)
        assert len(suite["metrics"]) >= 1


def test_publish_script_skip_run_rebuilds_docs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """publish_offline_benchmarks merges a real JSON report into docs text."""
    import importlib.util

    root = BACKEND.parent
    script = root / "scripts" / "publish_offline_benchmarks.py"
    spec = importlib.util.spec_from_file_location("publish_offline_benchmarks", script)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Use a minimal valid report shaped like the harness output
    sample = {
        "timestamp": "2026-01-01T00:00:00Z",
        "python": "3.11.0",
        "suite_names": ["security"],
        "quick": True,
        "overall_ok": True,
        "total_seconds": 1.0,
        "suites": [
            {
                "name": "security",
                "ok": True,
                "seconds": 0.5,
                "metrics": [
                    {"name": "checks_passed", "value": 6, "unit": "count", "note": ""},
                    {"name": "checks_total", "value": 6, "unit": "count", "note": ""},
                ],
            }
        ],
    }
    snap = mod.build_snapshot_md(sample)
    assert "security" in snap
    assert "checks_passed=6" in snap
    docs = mod.merge_docs(snap)
    assert "Offline benchmarks" in docs
    assert "roadmap" in docs.lower() or "Roadmap" in docs
