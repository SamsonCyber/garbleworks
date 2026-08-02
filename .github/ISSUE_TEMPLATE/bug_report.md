---
name: Bug report
about: Something in the harness is broken (not a security issue)
title: "[bug] "
labels: bug
---

> ⚠️ **Security issues:** do not file them here. A scope-enforcement escape, SSRF
> bypass, or fan-out/cap bypass is a private report - see [`SECURITY.md`](../../SECURITY.md).

**What happened**
A clear description of the bug.

**Expected**
What you expected instead.

**Repro**
1. …
2. …
Include the recipe / op(s), the target adapter, and the `detect` block if firing.

**Environment**
- OS + Python version:
- Commit / version:
- Running via HTTP (`uvicorn`) or MCP (`mcp_server.py`)?
- Local model (Ollama) reachable, or pass-through?

**Logs / output**
Paste the relevant server log, `benchmark_harness.py` output, or `/history` row.
Redact any target details or payload content that shouldn't be public.
