# pi-garbleworks

Talk to the red-team harness the same way Finbot works: **chat → model calls tools → live results**.

This package sits on top of the **[pi](https://pi.dev)** open-source agent TUI (not the thin custom OpenTUI shell). Real Garbleworks tools run through a long-lived Python engagement host. Live graphs (latency + ASR) render in the footer.

## Prerequisites

- `pi` on PATH (`npm i -g --ignore-scripts @earendil-works/pi-coding-agent`)
- Python 3.12+ with garbleworks backend deps
- A model API key pi already knows (`/login` or env)

## Start

From repo root:

```powershell
# recommended (native binary)
.\gw-chat.exe

# or
.\gw-chat.cmd
cd tui; bun start
pi -e ./pi-garbleworks

# rebuild binary after Go source changes
.\scripts\build-gw-chat.ps1
```

First message example:

```text
extract the canary from the local target. use gw tools only.
```

## Commands (inside pi)

| Command | Action |
|---------|--------|
| `/gw` | Status + fire budget |
| `/gw setup local` | Retarget (local / URL / JSON path) |
| `/gw mode` | Red-team tools only ↔ coding tools too |
| `/gw graph` | Toggle live graph footer |
| `/gw reset` | Clear findings / series |

## Tools

`gw_setup`, `gw_list_techniques`, `gw_compose_framing`, `gw_apply_recipe`, `gw_fire_target`, `gw_check_leak`, `gw_validate_refire`, `gw_status`, `gw_stream_graph`, `gw_finish`

Host protocol: `python -m agent_repl.engagement_host` (JSONL). See `backend/agent_repl/engagement_host.py`.

## Legacy OpenTUI shell

```powershell
cd tui
bun run start:legacy
```

That shell is still tested; pi is the primary operator chat surface.
