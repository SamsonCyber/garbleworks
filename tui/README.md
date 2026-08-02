# Garbleworks Operator TUI

AI red-team cockpit. Default mode is **Agent seat**: an external model (Grok)
drives the Garbleworks MCP tools; this TUI is the on-screen instruments.

```powershell
cd C:\code\garbleworks\tui
bun start
```

## Web arena (default)

One mode: local tool-chain morphs on F5 / Ctrl+R·T·S, and Grok can override via the seat hub.

```
BRIEF → F5 / Ctrl+R → tool-chain (generate_framings / MUTATE live)
 → payload bay updates (history via file, not argv)
 → YOU Ctrl+V in Gray Swan · report r/t/s
 → Grok may POST a better payload to hub anytime
```

**Grok seat (optional override, always on in Web arena):**

| Path | Role |
|------|------|
| `fs.watch` on `tui/agent/` | when Grok writes `agent_seat.json` |
| `http://127.0.0.1:8765/seat` | push hub POST |
| `operator_state.json` | brief / reply / history / request_id for Grok |

```powershell
cd C:\code\garbleworks\backend
.\.venv\Scripts\python.exe agent_seat.py status
.\.venv\Scripts\python.exe agent_seat.py dump-operator
.\.venv\Scripts\python.exe agent_seat.py stage --payload-file ..\tui\last_paste.txt --technique policy_puppetry --op policy_puppetry
```

### Where things show up

| Region | What you see |
|--------|----------------|
| **YOUR MOVE** panel | After advise: paste instructions + **r/t/s** |
| **ladder · gears** (right, wide terminal) | Rungs light as you report: pending → next → tried |
| **activity** | `GEAR` / `MORPH` / `HARNESS` / `BRANCH` lines as the solver advances |
| **history** (under profiles) | Logged tries this session |
| **status · payload** | Clipboard preview of the next prompt |

Widen the terminal (≥88 cols) for the ops rail. After advise, focus moves to **profiles** so `r`/`t`/`s` are not typed into BRIEF. If you are still in BRIEF, press **Tab** first.

### Harness ops

Clean rungs (`clean_direct`, …) are hand-built framings (no loud op). 
Signature rungs call the same op registry the MCP exposes (`chat_template_inject`, `homoglyph`, …). Activity shows:

```
HARNESS · run_recipe op=chat_template_inject (same registry MCP expose)
MORPH · attempt 2 → clean_maintenance [clean]
BRANCH · last=clean_direct:refused → now=clean_maintenance
```

History file: `backend/sessions/arena_history.json` (shared with `arena_go.py`).

## Keys

Confirm actions with **Enter** wherever you can; Ctrl combos are only needed
inside the multi-line text areas (BRIEF / REPLY), where Enter must insert a newline.

| Key | Action |
|-----|--------|
| ↑↓ / j k | Profile (when profiles focused) |
| Tab | Cycle fields - now includes **payload bay** and (when armed) the **outcome** bank |
| **Enter** (on profiles) | Advise / run |
| F5 / Ctrl+Enter | Advise / run (works from anywhere, incl. BRIEF) |
| **Enter / c** (on payload bay) | Copy payload to clipboard |
| **←/→ then Enter** (on outcome bank) | Pick + confirm refused / tripwire / success |
| **r / t / s** | Report outcome (fast path, when not typing) |
| Ctrl+R / Ctrl+T / Ctrl+S | Report outcome from inside the REPLY field |
| **n** | Re-copy current payload |
| **f** | Fresh ladder (clear history) |
| **✕ clear** button / Ctrl+L | Empty the BRIEF field |
| c / Ctrl+Y | Copy payload |
| o | Open `last_paste.txt` |
| Esc | Kill job |
| Ctrl+C | Quit |

The BRIEF panel has a red **✕ clear** button on its right edge - click it to
empty the field, or press **Ctrl+L** (a modifier is required since a bare key
would type into the card).

The **payload bay** auto-copies on advise. Tab to it to see the full payload
(it expands) and press **Enter** to re-copy; its title flips to
`SAVED TO FILE (o)` if the clipboard grab failed, so you always know whether
Ctrl+V will work or you need to open the file.

## Profiles

- **Web arena** (default) - advise loop + r/t/s
- **Local canary** - auto ladder against built-in echo (live fires stream in activity)
- **Abliterated Qwen / Prefill / Custom** - API targets

## CLI-only

```powershell
bun run start:cli
python ../backend/arena_go.py --fresh
```
