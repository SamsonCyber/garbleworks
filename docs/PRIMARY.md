# Primary tree - one elegant harness

**Home:** `C:\Code\garbleworks`  
**Code:** `backend/`  
**Operator entry (offline install/demo):**

```bash
cd C:\Code\garbleworks\backend
python harness_cli.py scan
# same entry:
python garbleworks.py scan
python -m garbleworks scan   # when backend is on PYTHONPATH
```

| Command | Role |
|---------|------|
| `scan` | Primary offline compose demo (enabled ops only) |
| `modules` | List add/remove packs |
| `toggle` | Self-check enable/disable |
| `auto` | Advanced: multi-strategy agent loop |
| `serve` | Advanced: HTTP API |
| `mcp` | Print single-tree MCP launch config |

Full offline suite: `python scripts/repro.py` -> `REPRO_OK ...`

## Modules

Ops packs live in `backend/ops/*.py`. Importing `ops` registers them.

```python
from core import list_ops, list_modules, disable, enable, disable_module, enable_module, enabled_ops

list_ops(enabled_only=True)   # catalogs + compose pools
disable("base64")             # gone from HTTP/MCP/harness/compose
enable("base64")
```

Add a pack: new file under `ops/` + import in `ops/__init__.py`.  
Remove a pack: drop the import or `disable_module("ops.encode_ops")`.

## Fire

One module: `backend/fire.py`. MCP and HTTP use it. No dual SSRF stack.

## MCP (sessions)

```text
args: PYTHONPATH=C:\Code\garbleworks\backend
      python C:\Code\garbleworks\backend\mcp_server.py
```

`payload-mutator/backend/mcp_server.py` is a thin shim only. Do not dual PYTHONPATH.

## Non-primary scripts (advanced / internal)

These are **not** peer products. Prefer `harness_cli.py` for day-to-day.

| Script | Use |
|--------|-----|
| `agent_loop.py` | multi-strategy auto (also `harness_cli.py auto`) |
| `scan_campaign.py` | coverage map campaigns |
| `campaign_runner.py` | thin seed->fire->score helper |
| `arena_go.py` / `arena_advise_cli.py` | human-paste arena helpers |
| `grok_driver.py` / `console.py` | operator fleet UIs |
| `app.py` | FastAPI (also `harness_cli.py serve`) |
| `mcp_server.py` | MCP stdio (also `harness_cli.py mcp`) |
