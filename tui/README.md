# Garbleworks Agent Chat TUI

## Primary: pi (high-quality agent TUI)

Chat like Finbot: you talk, the model calls **real Garbleworks tools**, live
latency / ASR graphs sit in the footer. Built on the open-source **pi** TUI
(`@earendil-works/pi-coding-agent`), not a one-off toy shell.

```powershell
# from repo root
.\gw-chat.exe

# or
cd C:\code\garbleworks\tui
bun start
```

Package: `../pi-garbleworks` (tools + red-team skill + graph footer).
Host: `python -m agent_repl.engagement_host` (JSONL, long-lived).

In-session: `/gw` status · `/gw setup local` · `/gw graph` · `/gw mode`

## Legacy OpenTUI shell

```powershell
bun run start:legacy
bun run start:cockpit
```

## Layout

| Strip | Role |
|-------|------|
| **status** | profile → target · phase · fires/wins/misses |
| **trace** | live graphs (`asciichart` + `drawille`) · call table · structured focus |
| **chat** | conversation (you / brain / results) |
| **prompt** | `›` input · Enter send · `/help` |
| **hints** | keys + mode · live tool count |

Keys: **Enter** send · **Esc** stop · **Ctrl+↑↓** profile · **Ctrl+C** quit.
Arena: **Alt+r/t/s** report when that profile is active.

## Chat session (agent profiles)

Agent profiles open a long-lived process:

```text
python -m agent_repl --session --brain <id> --target local
```

stdin JSONL: `turn` / `feedback` / `stop` / `clear` / `set` / `quit`.
stdout: `GW|{json}` with native kinds (`agent_text`, `tool_start`, `turn_complete`, …).

Slash commands: `/help` `/clear` `/stop` `/profile` `/target` `/secret` `/brain` `/auto` `/arena` `/reconnect` `/quit`.

## Profiles

| Profile | Backend path |
|---------|----------------|
| Agent · stub / Grok / MiniMax / OpenCode | `agent_repl --session` |
| Local canary | `agent_loop --auto` one-shot |
| Web arena | `arena_advise_cli.py` (paste + r/t/s) |
| Prefill / Qwen | auto ladder one-shot |

## Develop

```powershell
bun test
bun run typecheck
bun run dev
cd ..\backend; python -m pytest test_agent_session.py -q
```

Event mapping: `src/shell_state.ts`. Live tool deck: `src/shell_tools.tsx`.
Graph engines: `src/charts.ts` (`asciichart` line plots, `drawille` braille canvas).
Session spawn: `src/bridge.ts`. Theme: `src/shell_theme.ts` (transparent by default).

## Bridge contract

Backend processes start with `GARBLEWORKS_TUI=1` so structured lines are
`GW|{json}`. The shell maps those into chat lines and status. Harness
`success` is never inferred from “finished” alone.
