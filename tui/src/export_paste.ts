/**
 * Get the advised payload out of the TUI (clipboard + file).
 * OpenTUI alternate screens make mouse-select unreliable on Windows.
 */
import { spawnSync } from "bun"
import { join, dirname } from "path"
import { fileURLToPath } from "url"
import { writeFileSync, mkdirSync } from "fs"

const __dirname = dirname(fileURLToPath(import.meta.url))
export const PASTE_FILE = join(__dirname, "..", "last_paste.txt")
export const PASTE_FILE_BACKEND = join(
  __dirname,
  "..",
  "..",
  "backend",
  "sessions",
  "next_paste.txt",
)

export type ExportResult = {
  ok: boolean
  path: string
  clipboard: boolean
  error?: string
}

/** Write payload to disk and try system clipboard. */
export function exportPastePayload(
  text: string,
  opts?: {
    copyToClipboardOSC52?: (t: string) => boolean
    /** Open Notepad/default editor so user can Ctrl+A Ctrl+C without TUI select */
    openEditor?: boolean
  },
): ExportResult {
  const body = (text || "").trim()
  if (!body) {
    return { ok: false, path: PASTE_FILE, clipboard: false, error: "empty payload" }
  }

  try {
    writeFileSync(PASTE_FILE, body + "\n", "utf-8")
    try {
      mkdirSync(dirname(PASTE_FILE_BACKEND), { recursive: true })
      writeFileSync(PASTE_FILE_BACKEND, body + "\n", "utf-8")
    } catch {
      /* sessions dir optional */
    }
  } catch (e) {
    return {
      ok: false,
      path: PASTE_FILE,
      clipboard: false,
      error: `write failed: ${e}`,
    }
  }

  let clipboard = false
  // Prefer terminal OSC 52 when the renderer provides it
  if (opts?.copyToClipboardOSC52) {
    try {
      clipboard = Boolean(opts.copyToClipboardOSC52(body))
    } catch {
      clipboard = false
    }
  }
  if (!clipboard) {
    clipboard = copyViaOs(body)
  }

  if (opts?.openEditor) {
    openPasteFile(PASTE_FILE)
  }

  return { ok: true, path: PASTE_FILE, clipboard }
}

/** Open last_paste.txt in the OS default editor (Notepad on Windows). */
export function openPasteFile(path: string = PASTE_FILE): boolean {
  try {
    if (process.platform === "win32") {
      // `start` needs cmd; empty title arg required
      spawnSync({
        cmd: ["cmd", "/c", "start", "", "notepad.exe", path],
        stdout: "ignore",
        stderr: "ignore",
      })
      return true
    }
    if (process.platform === "darwin") {
      spawnSync({ cmd: ["open", "-t", path], stdout: "ignore", stderr: "ignore" })
      return true
    }
    spawnSync({ cmd: ["xdg-open", path], stdout: "ignore", stderr: "ignore" })
    return true
  } catch {
    return false
  }
}

function copyViaOs(text: string): boolean {
  // Windows: clip.exe reads stdin as UTF-16LE is flaky; use PowerShell Set-Clipboard
  if (process.platform === "win32") {
    try {
      const r = spawnSync({
        cmd: [
          "powershell",
          "-NoProfile",
          "-Command",
          "Set-Clipboard -Value ([Console]::In.ReadToEnd())",
        ],
        stdin: new Blob([text]),
        stdout: "pipe",
        stderr: "pipe",
      })
      if (r.exitCode === 0) return true
    } catch {
      /* fall through */
    }
    try {
      // last resort: clip (OEM codepage; fine for ASCII payloads)
      const r = spawnSync({
        cmd: ["clip"],
        stdin: new Blob([text]),
        stdout: "pipe",
        stderr: "pipe",
      })
      return r.exitCode === 0
    } catch {
      return false
    }
  }
  // macOS
  try {
    const r = spawnSync({
      cmd: ["pbcopy"],
      stdin: new Blob([text]),
      stdout: "pipe",
      stderr: "pipe",
    })
    if (r.exitCode === 0) return true
  } catch {
    /* linux */
  }
  try {
    const r = spawnSync({
      cmd: ["xclip", "-selection", "clipboard"],
      stdin: new Blob([text]),
      stdout: "pipe",
      stderr: "pipe",
    })
    return r.exitCode === 0
  } catch {
    return false
  }
}
