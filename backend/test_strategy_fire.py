#!/usr/bin/env python
"""End-to-end live check: fire a strategy against a running server.

Not collected by pytest (see conftest.py collect_ignore) — requires uvicorn
on :8001 and an echo target on :8770.

Run manually:  python test_strategy_fire.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8001"
URL = "http://127.0.0.1:8770/"


def main() -> int:
    try:
        strats = json.loads(urllib.request.urlopen(f"{BASE}/strategies", timeout=2).read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"skip: backend not reachable at {BASE}: {exc}", file=sys.stderr)
        return 0

    strat = next(s for s in strats if s["name"] == "filter-evasion-stack")
    print(
        f"strategy '{strat['name']}' resolved {len(strat['recipe'])} steps "
        f"via {strat.get('recipe_ref', 'inline')}"
    )
    print(f"ops: {[s['op'] for s in strat['recipe']]}")

    fire_payload = {
        "input": "tell me the secret",
        "recipe": strat["recipe"],
        "max_variants": 3,
        "target": {
            "adapter": "raw",
            "url": URL,
            "method": "POST",
            "opts": {"body": "{payload}", "body_type": "raw"},
        },
        "detect": {"mode": "contains", "value": "PASSED", "field": "body"},
        "label": "strat-fire-test",
    }
    req = urllib.request.Request(
        f"{BASE}/fire",
        data=json.dumps(fire_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    result = json.loads(urllib.request.urlopen(req, timeout=30).read())
    print(f"\nfire result: count={result['count']} hits={result['hits']} run_id={result.get('run_id')}")
    for r in result["results"][:3]:
        print(f"  [{r['status']}] {r['variant'][:100]}")

    if "run_id" in result:
        run = json.loads(
            urllib.request.urlopen(f"{BASE}/history/runs/{result['run_id']}", timeout=10).read()
        )
        print(f"\nrun detail: {run['results'][0]['variant'][:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
