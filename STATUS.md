# Status and reproducibility

| Axis | State |
|------|--------|
| Implemented | Yes. HTTP API, recipe DSL, fire path, MCP server, TUI, exporters. |
| Independently validated | Yes. `test_security.py` (SSRF/scope) + offline `benchmark_harness.py --fail-on-regression`. Full backend pytest in CI. |
| Maintained | Yes. Public under [SamsonCyber/garbleworks](https://github.com/SamsonCyber/garbleworks). Apache-2.0. |

## Independent validation (clean machine)

No live model required:

```bash
python scripts/repro.py
```

Runs:

1. `pytest -q test_security.py` (URL policy, scope, fire safety)
2. `python benchmark_harness.py --fail-on-regression` (stats/plumbing audit, echo/mocks)

Success line: `REPRO_OK garbleworks security + math audit`

Publish refreshed offline numbers into docs:

```bash
python scripts/publish_offline_benchmarks.py
```

See [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md) and [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

Note: `backend/research_store.py` provides Wilson LCB used by the harness and search modules.

CI (`.github/workflows/ci.yml`) runs the full backend pytest suite plus the same math audit on every push/PR to main.

## What full CI covers vs local repro

| Check | Local `scripts/repro.*` | GitHub CI |
|-------|-------------------------|-----------|
| Security / SSRF / scope | yes | yes (via full pytest) |
| Full unit suite | optional: `cd backend && pytest -q` | yes |
| Math regression audit | yes | yes |
| Live multi-model ASR battery | no (roadmap) | no |

## Honest gaps

- HarmBench / JailbreakBench leaderboard-style multi-model battery is roadmap, not shipped.
- Enforce that claims cite Wilson/re-fire, not single lucky hits (see docs/GAPS.md).
