/**
 * Bridge: OpenTUI → Garbleworks Python backend.
 * Parses GW|{json} structured events into work-plan / activity / mission HUD.
 * Jobs are killable (Esc / Ctrl+X).
 */
import { spawn, type Subprocess } from "bun"
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs"
import { join, dirname } from "path"
import { fileURLToPath } from "url"

const __dirname = dirname(fileURLToPath(import.meta.url))
export const BACKEND = join(__dirname, "..", "..", "backend")
export const ARENA_HISTORY_PATH = join(BACKEND, "sessions", "arena_history.json")

export type StepStatus = "pending" | "active" | "done" | "skip" | "fail" | "win"

export type PlanStep = {
  id: string
  label: string
  status: StepStatus
  note?: string
  queries?: number
}

export type ActivityItem = {
  ts: number
  level: string
  message: string
  strategy?: string
  payload?: string
  reply?: string
}

export type ProgressState = {
  current: number
  total: number
  ratio: number
  label: string
  detail: string
}

export type FireStats = {
  wins: number
  misses: number
  errors: number
  asrSeries: number[]
  lcbSeries: number[]
  fires: number
}

/** Mission HUD — critical operator context that must stay on-screen. */
export type MissionState = {
  job: string
  budget: number | null
  remaining: number | null
  queriesSpent: number
  activeStrategy: string
  lastStrategy: string
  lastChannel: string
  objectivePreview: string
  sessionPath: string
  lastResult: {
    success: boolean
    strategy?: string
    queries?: number
    channel?: string
  } | null
  lastFire: {
    strategy: string
    payload: string
    reply: string
    leaked: boolean
    q?: number
    channel?: string
  } | null
  killRequested: boolean
}

export type BoardState = {
  steps: PlanStep[]
  activity: ActivityItem[]
  progress: ProgressState
  stats: FireStats
  mission: MissionState
}

export type GwEvent = {
  v?: number
  kind: string
  ts?: number
  [key: string]: unknown
}

/** One logged arena attempt (matches arena_go / arena_solver history). */
export type ArenaAttempt = {
  technique: string
  outcome: "success" | "refused" | "tripwire" | "unknown" | string
  /** Model failure text the operator pasted back for mutation. */
  response?: string
  /** Payload that was sent for this attempt. */
  payload?: string
  base_technique?: string
}

/** Structured advise payload from GW_ADVISE|… lines. */
export type ArenaAdvise = {
  technique: string
  kind: string
  reset_first?: boolean
  payload?: string | string[]
  rationale?: string
  defense_type?: string
  objective_used?: string
  expected_answer?: string
  brief_title?: string
  constraints?: string[]
  op?: string | null
  attempt?: number
  ladder?: {
    id: string
    label: string
    kind: string
    status: string
    outcome?: string | null
    op?: string | null
  }[]
  await_outcome?: boolean
  used_reply?: boolean
  improvement?: string
  base_technique?: string
}

export type RunEvent =
  | { type: "line"; text: string }
  | { type: "gw"; event: GwEvent }
  | { type: "advise"; advise: ArenaAdvise }
  | { type: "done"; code: number; killed?: boolean }
  | { type: "error"; text: string }

export function loadArenaHistory(): ArenaAttempt[] {
  try {
    if (!existsSync(ARENA_HISTORY_PATH)) return []
    const raw = JSON.parse(readFileSync(ARENA_HISTORY_PATH, "utf-8"))
    return Array.isArray(raw) ? (raw as ArenaAttempt[]) : []
  } catch {
    return []
  }
}

export function saveArenaHistory(history: ArenaAttempt[]): void {
  try {
    mkdirSync(dirname(ARENA_HISTORY_PATH), { recursive: true })
    writeFileSync(ARENA_HISTORY_PATH, JSON.stringify(history, null, 2), "utf-8")
  } catch {
    /* ignore */
  }
}

export function clearArenaHistory(): void {
  saveArenaHistory([])
}

export type JobHandle = {
  kill: () => void
  done: Promise<number>
}

function pythonBin(): string {
  return process.env.GARBLEWORKS_PYTHON || process.env.PYTHON || "python"
}

function parseLine(line: string): RunEvent {
  if (line.startsWith("GW_ADVISE|")) {
    try {
      const advise = JSON.parse(line.slice("GW_ADVISE|".length)) as ArenaAdvise
      return { type: "advise", advise }
    } catch {
      return { type: "line", text: line }
    }
  }
  if (line.startsWith("GW|")) {
    try {
      const event = JSON.parse(line.slice(3)) as GwEvent
      return { type: "gw", event }
    } catch {
      return { type: "line", text: line }
    }
  }
  return { type: "line", text: line }
}

export function emptyFireStats(): FireStats {
  return { wins: 0, misses: 0, errors: 0, asrSeries: [], lcbSeries: [], fires: 0 }
}

export function emptyProgress(): ProgressState {
  return { current: 0, total: 1, ratio: 0, label: "", detail: "" }
}

export function emptyMission(): MissionState {
  return {
    job: "",
    budget: null,
    remaining: null,
    queriesSpent: 0,
    activeStrategy: "",
    lastStrategy: "",
    lastChannel: "",
    objectivePreview: "",
    sessionPath: "",
    lastResult: null,
    lastFire: null,
    killRequested: false,
  }
}

export function emptyBoard(): BoardState {
  return {
    steps: [],
    activity: [],
    progress: emptyProgress(),
    stats: emptyFireStats(),
    mission: emptyMission(),
  }
}

export function runPython(
  args: string[],
  onEvent: (ev: RunEvent) => void,
  opts?: { env?: Record<string, string> },
): JobHandle {
  let killed = false
  let proc: Subprocess | null = null

  try {
    proc = spawn({
      cmd: [pythonBin(), ...args],
      cwd: BACKEND,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
        GARBLEWORKS_TUI: "1",
        ...opts?.env,
      },
    })
  } catch (e) {
    onEvent({ type: "error", text: `spawn failed: ${e}` })
    onEvent({ type: "done", code: 1 })
    return {
      kill: () => {},
      done: Promise.resolve(1),
    }
  }

  const read = async (stream: ReadableStream<Uint8Array> | null, label: string) => {
    if (!stream) return
    const reader = stream.getReader()
    const dec = new TextDecoder()
    let buf = ""
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const parts = buf.split(/\r?\n/)
        buf = parts.pop() || ""
        for (const line of parts) {
          if (line.length) onEvent(parseLine(line))
        }
      }
      if (buf.trim()) onEvent(parseLine(buf))
    } catch (e) {
      if (!killed) onEvent({ type: "error", text: `${label}: ${e}` })
    }
  }

  const done = (async () => {
    await Promise.all([
      read(proc!.stdout as ReadableStream<Uint8Array> | null, "stdout"),
      read(proc!.stderr as ReadableStream<Uint8Array> | null, "stderr"),
    ])
    const code = killed ? 130 : ((await proc!.exited) ?? 1)
    onEvent({ type: "done", code, killed })
    return code
  })()

  return {
    kill: () => {
      if (killed || !proc) return
      killed = true
      try {
        proc.kill()
      } catch {
        /* already dead */
      }
      try {
        proc.kill(9)
      } catch {
        /* ignore */
      }
    },
    done,
  }
}

export function runAuto(opts: {
  objective: string
  mode: string
  target: string
  secret?: string
  budget?: number
  confirmN?: number
  model?: string
  onEvent: (ev: RunEvent) => void
}): JobHandle {
  const args = [
    "-m", "agent_loop",
    "--auto", opts.objective,
    "--mode", opts.mode,
    "--target", opts.target || "local",
    "--budget", String(opts.budget ?? 24),
  ]
  if (opts.model) args.push("--model", opts.model)
  if (opts.secret) args.push("--secret", opts.secret)
  if (opts.confirmN && opts.confirmN > 0) {
    args.push("--confirm-n", String(opts.confirmN))
  }
  return runPython(args, opts.onEvent)
}

export function runValidate(opts: {
  payload: string
  target: string
  secret?: string
  n?: number
  onEvent: (ev: RunEvent) => void
}): JobHandle {
  const args = [
    "-m", "agent_loop",
    "--validate", opts.payload,
    "--target", opts.target || "local",
    "--validate-n", String(opts.n ?? 5),
  ]
  if (opts.secret) args.push("--secret", opts.secret)
  return runPython(args, opts.onEvent)
}

export function runFindings(onEvent: (ev: RunEvent) => void): JobHandle {
  return runPython(["-m", "agent_loop", "--findings"], onEvent)
}

export function runResume(onEvent: (ev: RunEvent) => void): JobHandle {
  return runPython(["-m", "agent_loop", "--resume", "latest", "--quiet"], onEvent)
}

export function runListBehaviors(
  path: string,
  onEvent: (ev: RunEvent) => void,
): JobHandle {
  return runPython(
    ["-m", "agent_loop", "--list-behaviors", "--behaviors", path],
    onEvent,
  )
}

export function runH2H(opts: {
  protocol: string
  only?: string
  onEvent: (ev: RunEvent) => void
}): JobHandle {
  const args = [
    "-m", "bench.ab_wallbreaker",
    "--protocol", opts.protocol,
    "--tag", "tui",
  ]
  if (opts.only) args.push("--only", opts.only)
  return runPython(args, opts.onEvent)
}

/** Gray Swan–style: get next payload to paste (no browser automation). */
export function runArenaAdvise(opts: {
  objective: string
  /** Full challenge card paste (title, overview, criteria…) */
  brief?: string
  /** Inline JSON array or path; defaults to sessions/arena_history.json when present. */
  historyJson?: string
  history?: ArenaAttempt[]
  onEvent: (ev: RunEvent) => void
}): JobHandle {
  const args = ["arena_advise_cli.py"]
  // Objective still passed; brief goes via env (long Gray Swan cards).
  args.push(opts.objective || "arena objective")

  // NEVER put full history JSON on argv — Windows CreateProcess max ~8191 chars.
  // After a few tries with payloads, inline JSON is 30KB+ and the morph silently
  // fails (spawn / truncated argv). Always pass a file path.
  if (opts.historyJson) {
    args.push(opts.historyJson)
  } else if (opts.history) {
    try {
      saveArenaHistory(opts.history)
      args.push(ARENA_HISTORY_PATH)
    } catch {
      // Last resort: tiny empty history rather than a broken argv bomb
      args.push("[]")
    }
  } else if (existsSync(ARENA_HISTORY_PATH)) {
    args.push(ARENA_HISTORY_PATH)
  } else {
    args.push("[]")
  }

  return runPython(args, opts.onEvent, {
    env: opts.brief?.trim()
      ? { GARBLEWORKS_BRIEF: opts.brief }
      : undefined,
  })
}

/** Apply a structured GW event onto plan/activity/progress/stats/mission. */
export function applyGwEvent(
  event: GwEvent,
  state: BoardState,
): BoardState {
  let { steps, activity, progress, stats, mission } = state
  // Defensive defaults if a caller forgets a field
  if (!stats) stats = emptyFireStats()
  if (!mission) mission = emptyMission()
  const kind = event.kind

  if (kind === "plan" && Array.isArray(event.steps)) {
    steps = (event.steps as { id?: string; label?: string; status?: string }[]).map(
      (s, i) => ({
        id: String(s.id || s.label || `s${i}`),
        label: String(s.label || s.id || `step ${i + 1}`),
        status: (s.status as StepStatus) || "pending",
      }),
    )
    const budget = event.budget != null ? Number(event.budget) : mission.budget
    mission = {
      ...mission,
      job: event.job != null ? String(event.job) : mission.job || "auto",
      budget: Number.isFinite(budget as number) ? (budget as number) : mission.budget,
      remaining:
        event.budget != null && Number.isFinite(Number(event.budget))
          ? Number(event.budget)
          : mission.remaining,
      queriesSpent: 0,
      activeStrategy: "",
      lastResult: null,
    }
    activity = [
      ...activity,
      {
        ts: Number(event.ts) || Date.now() / 1000,
        level: "info",
        message: `Plan: ${steps.map((s) => s.label).join(" → ")}${
          mission.budget != null ? `  budget=${mission.budget}` : ""
        }`,
      },
    ].slice(-120)
  }

  if (kind === "step" && event.step_id) {
    const id = String(event.step_id)
    const status = (event.status as StepStatus) || "active"
    const note =
      event.note != null
        ? String(event.note)
        : event.reason != null
          ? String(event.reason)
          : undefined
    const q = event.queries != null ? Number(event.queries) : undefined
    steps = steps.map((s) =>
      s.id === id
        ? {
            ...s,
            status,
            note: note ?? s.note,
            queries: q ?? s.queries,
          }
        : status === "active" && s.status === "active"
          ? { ...s, status: "pending" }
          : s,
    )
    if (!steps.some((s) => s.id === id)) {
      steps = [...steps, { id, label: id, status, note, queries: q }]
    }
    if (status === "active") {
      mission = {
        ...mission,
        activeStrategy: id,
        remaining:
          event.remaining_budget != null
            ? Number(event.remaining_budget)
            : mission.remaining,
      }
    } else {
      mission = {
        ...mission,
        lastStrategy: id,
        activeStrategy: status === "win" || status === "done" || status === "fail" || status === "skip"
          ? ""
          : mission.activeStrategy,
        lastChannel: event.channel != null ? String(event.channel) : mission.lastChannel,
        queriesSpent:
          q != null && Number.isFinite(q)
            ? mission.queriesSpent + q
            : mission.queriesSpent,
        remaining:
          event.remaining_budget != null
            ? Number(event.remaining_budget)
            : mission.budget != null && q != null
              ? Math.max(0, (mission.remaining ?? mission.budget) - q)
              : mission.remaining,
      }
    }
  }

  if (kind === "activity" && event.message) {
    if (event.objective) {
      mission = {
        ...mission,
        objectivePreview: String(event.objective).slice(0, 120),
      }
    }
    activity = [
      ...activity,
      {
        ts: Number(event.ts) || Date.now() / 1000,
        level: String(event.level || "info"),
        message: String(event.message),
        strategy: event.strategy ? String(event.strategy) : undefined,
        payload: event.payload_preview
          ? String(event.payload_preview)
          : event.payload
            ? String(event.payload)
            : undefined,
        reply: event.reply_preview
          ? String(event.reply_preview)
          : event.reply
            ? String(event.reply)
            : undefined,
      },
    ].slice(-120)
  }

  if (kind === "fire") {
    const leaked = Boolean(event.leaked)
    const strat = event.strategy ? String(event.strategy) : ""
    const payload = event.payload_preview ? String(event.payload_preview) : ""
    const reply = event.reply_preview ? String(event.reply_preview) : ""
    const q = event.q != null ? Number(event.q) : undefined
    const channel = event.channel != null ? String(event.channel) : undefined
    // manual_paste = advise only (human hasn't reported outcome yet)
    const adviseOnly = channel === "manual_paste"
    if (!adviseOnly) {
      stats = {
        ...stats,
        fires: stats.fires + 1,
        wins: stats.wins + (leaked ? 1 : 0),
        misses: stats.misses + (leaked ? 0 : 1),
      }
      const total = stats.wins + stats.misses
      if (total > 0) {
        stats = {
          ...stats,
          asrSeries: [...stats.asrSeries, stats.wins / total].slice(-48),
        }
      }
    } else {
      stats = { ...stats, fires: stats.fires + 1 }
    }
    mission = {
      ...mission,
      lastStrategy: strat || mission.lastStrategy,
      lastChannel: channel || mission.lastChannel,
      lastFire: {
        strategy: strat,
        payload,
        reply: adviseOnly ? "(paste in browser, then press r/t/s)" : reply,
        leaked,
        q,
        channel,
      },
    }
    activity = [
      ...activity,
      {
        ts: Number(event.ts) || Date.now() / 1000,
        level: leaked ? "win" : adviseOnly ? "info" : "info",
        message: leaked
          ? `FIRE HIT  q=${q ?? "?"}  ch=${channel || "-"}`
          : adviseOnly
            ? `ADVISE ready · ${strat || "?"} · paste then r/t/s`
            : `FIRE miss  q=${q ?? "?"}`,
        strategy: strat || undefined,
        payload: payload || undefined,
        reply: reply || undefined,
      },
    ].slice(-120)
  }

  if (kind === "progress") {
    progress = {
      current: Number(event.current) || 0,
      total: Number(event.total) || 1,
      ratio: Number(event.ratio) || 0,
      label: String(event.label || ""),
      detail: String(event.detail || ""),
    }
    if (event.label) {
      mission = { ...mission, activeStrategy: String(event.label) }
    }
  }

  if (kind === "result") {
    if (event.asr != null) {
      stats = {
        ...stats,
        asrSeries: [...stats.asrSeries, Number(event.asr)].slice(-48),
      }
    }
    if (event.asr_lcb != null) {
      stats = {
        ...stats,
        lcbSeries: [...stats.lcbSeries, Number(event.asr_lcb)].slice(-48),
      }
    }
    const queries = event.queries != null ? Number(event.queries) : undefined
    const success = Boolean(event.success)
    const strategy = event.strategy != null ? String(event.strategy) : undefined
    const channel = event.channel != null ? String(event.channel) : undefined
    mission = {
      ...mission,
      activeStrategy: "",
      lastStrategy: strategy || mission.lastStrategy,
      lastChannel: channel || mission.lastChannel,
      queriesSpent: queries ?? mission.queriesSpent,
      remaining:
        mission.budget != null && queries != null
          ? Math.max(0, mission.budget - queries)
          : mission.remaining,
      lastResult: { success, strategy, queries, channel },
      sessionPath:
        event.session_report != null
          ? String(event.session_report)
          : event.session_jsonl != null
            ? String(event.session_jsonl)
            : mission.sessionPath,
    }
    activity = [
      ...activity,
      {
        ts: Number(event.ts) || Date.now() / 1000,
        level: success ? "win" : "info",
        message: `RESULT  ${success ? "SUCCESS" : "no-win"}  strategy=${strategy || "-"}  q=${queries ?? "?"}  ch=${channel || "-"}`,
      },
    ].slice(-120)
    if (success) {
      steps = steps.map((s) =>
        s.status === "pending" ? { ...s, status: "skip", note: "not reached" } : s,
      )
    }
  }

  return { steps, activity, progress, stats, mission }
}
