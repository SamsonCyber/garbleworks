# Optional Pliny corpora (local only)

Garbleworks does **not** ship liberation prompt dumps. Drop an operator-local clone here and the adapter picks it up automatically.

## Plug L1B3RT4S (recommended)

From the **repo root**:

```bash
git clone --depth 1 https://github.com/elder-plinius/L1B3RT4S.git corpora/L1B3RT4S
python scripts/pliny_plug.py status
python scripts/pliny_plug.py list --source corpus | head
python scripts/pliny_plug.py apply corpus.shortcut.jailbreak "authorized red-team objective"
```

Or set an absolute path:

```bash
# Windows PowerShell
$env:GARBLEWORKS_PLINY_CORPUS = "D:\datasets\L1B3RT4S"
# POSIX
export GARBLEWORKS_PLINY_CORPUS=/path/to/L1B3RT4S
```

Optional second dump:

```bash
git clone --depth 1 https://github.com/elder-plinius/CL4R1T4S.git corpora/CL4R1T4S
```

## What loads

| Content | Becomes |
| --- | --- |
| `!SHORTCUTS.json` commands | `corpus.shortcut.*` frames (`!JAILBREAK`, `!OMNI`, …) |
| Model `.mkd` dumps | custom GODMODE lines, ResponseFormat dividers, bang-command prefixes |
| Missing folder | builtin Pliny kit only (always works) |

Recipes / UI / MCP: op `pliny_frame` with `frame_id=…`. Phase F scan also exercises the adapter.

## Do not commit dumps

Everything under `corpora/*` except this README is gitignored. See [SECURITY.md](../SECURITY.md).

## Not plug-and-play here

| Repo | Why |
| --- | --- |
| G0DM0D3 | Chat UI, not a prompt tree |
| OBLITERATUS | Weight surgery |
| GLOSSOPETRAE | JS engine; language ideas already map to in-tree lang ops |
