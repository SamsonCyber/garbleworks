/**
 * Agent seat — event-driven bus between the on-screen TUI and an external driver.
 *
 * Transport (two layers, same schema):
 *   1. File bus (durable, works if agent is offline)
 *        operator_state.json  ← TUI writes
 *        agent_seat.json      ← agent writes
 *   2. Push hub (localhost HTTP) — agent POSTs, TUI gets a callback immediately
 *        default http://127.0.0.1:8765/seat
 *
 * React "hooks" cannot cross process boundaries. This module is the process-edge:
 * fs.watch + optional HTTP push → in-process subscribers → useAgentSeat hook.
 */
import {
  existsSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
  watch,
  type FSWatcher,
} from "fs"
import { createServer, type Server } from "http"
import { dirname, join, basename } from "path"
import { fileURLToPath } from "url"
import { useEffect, useRef, useState } from "react"
import type { ActivityItem, ArenaAdvise, ArenaAttempt } from "./bridge"

export type LadderRung = {
  id: string
  label: string
  kind: string
  status: string
  outcome?: string | null
  op?: string | null
}

const __dirname = dirname(fileURLToPath(import.meta.url))
export const AGENT_DIR = join(__dirname, "..", "agent")
export const SEAT_PATH = join(AGENT_DIR, "agent_seat.json")
export const OPERATOR_PATH = join(AGENT_DIR, "operator_state.json")
export const HUB_PORT = Number(process.env.GARBLEWORKS_SEAT_PORT || 8765)
export const HUB_HOST = process.env.GARBLEWORKS_SEAT_HOST || "127.0.0.1"

export type AgentSeat = {
  v: 1
  updated_at: number
  seq: number
  driver: string
  busy: boolean
  status: string
  payload: string
  technique: string
  kind: string
  op?: string | null
  reset_first?: boolean
  rationale?: string
  expected_answer?: string
  objective_used?: string
  brief_title?: string
  defense_type?: string
  attempt?: number
  base_technique?: string
  improvement?: string
  used_reply?: boolean
  activity: ActivityItem[]
  ladder?: LadderRung[]
}

export type OperatorState = {
  v: 1
  updated_at: number
  seq: number
  request_id: number
  phase: string
  brief: string
  objective: string
  reply: string
  history: ArenaAttempt[]
  last_outcome?: string | null
  last_request?: string
  profile?: string
}

export type SeatApplyOpts = {
  onPayload: (text: string) => void
  onAdvise: (a: ArenaAdvise) => void
  onActivity: (items: ActivityItem[]) => void
  onStatus: (note: string) => void
  onBusy: (busy: boolean) => void
  onReady?: (seat: AgentSeat) => void
  onLadder?: (ladder: LadderRung[]) => void
}

type SeatListener = (seat: AgentSeat, source: "watch" | "push" | "read") => void

function ensureDir() {
  try {
    mkdirSync(AGENT_DIR, { recursive: true })
  } catch {
    /* ignore */
  }
}

export function emptySeat(): AgentSeat {
  return {
    v: 1,
    updated_at: 0,
    seq: 0,
    driver: "",
    busy: false,
    status: "no agent seated",
    payload: "",
    technique: "",
    kind: "",
    activity: [],
  }
}

export function emptyOperator(): OperatorState {
  return {
    v: 1,
    updated_at: Date.now() / 1000,
    seq: 0,
    request_id: 0,
    phase: "edit",
    brief: "",
    objective: "",
    reply: "",
    history: [],
    last_outcome: null,
    last_request: "",
  }
}

export function readSeat(): AgentSeat | null {
  try {
    if (!existsSync(SEAT_PATH)) return null
    const raw = JSON.parse(readFileSync(SEAT_PATH, "utf-8"))
    if (!raw || raw.v !== 1) return null
    return raw as AgentSeat
  } catch {
    // mid-write / partial JSON — ignore, next event will re-read
    return null
  }
}

export function readOperator(): OperatorState | null {
  try {
    if (!existsSync(OPERATOR_PATH)) return null
    const raw = JSON.parse(readFileSync(OPERATOR_PATH, "utf-8"))
    if (!raw || raw.v !== 1) return null
    return raw as OperatorState
  } catch {
    return null
  }
}

export function writeOperatorState(
  state: Omit<OperatorState, "v" | "updated_at" | "seq"> & { seq?: number },
): void {
  ensureDir()
  const prev = readOperator()
  const next: OperatorState = {
    v: 1,
    updated_at: Date.now() / 1000,
    seq: (prev?.seq || 0) + 1,
    request_id: state.request_id,
    phase: state.phase,
    brief: state.brief,
    objective: state.objective,
    reply: state.reply,
    history: state.history || [],
    last_outcome: state.last_outcome ?? null,
    last_request: state.last_request || "",
    profile: state.profile,
  }
  // Atomic-ish: write temp then rename would be nicer; single-writer TUI is fine
  writeFileSync(OPERATOR_PATH, JSON.stringify(next, null, 2), "utf-8")
}

export function seatToAdvise(seat: AgentSeat): ArenaAdvise {
  return {
    technique: seat.technique || "agent",
    kind: seat.kind || "agent",
    reset_first: Boolean(seat.reset_first),
    payload: seat.payload || "",
    rationale: seat.rationale || seat.status,
    defense_type: seat.defense_type,
    objective_used: seat.objective_used,
    expected_answer: seat.expected_answer,
    brief_title: seat.brief_title,
    op: seat.op ?? null,
    attempt: seat.attempt,
    ladder: seat.ladder?.map((r) => ({
      id: r.id,
      label: r.label,
      kind: r.kind,
      status: r.status,
      outcome: r.outcome,
      op: r.op,
    })),
    await_outcome: Boolean(seat.payload?.trim()),
    used_reply: seat.used_reply,
    improvement: seat.improvement,
    base_technique: seat.base_technique || seat.technique,
  }
}

export function applySeatDelta(
  seat: AgentSeat,
  prevSeq: number,
  opts: SeatApplyOpts,
): number {
  if (!seat) return prevSeq

  const agentBusy = Boolean(seat.busy)
  const hasPayload = Boolean(seat.payload?.trim())
  const ready = hasPayload && !agentBusy

  opts.onBusy(agentBusy)
  if (seat.status) {
    opts.onStatus(`${seat.driver || "agent"} · ${seat.status}`.slice(0, 90))
  }

  if (seat.seq > prevSeq) {
    if (seat.activity?.length) opts.onActivity(seat.activity.slice(-120))
    if (seat.ladder?.length && opts.onLadder) opts.onLadder(seat.ladder)
    if (hasPayload) {
      opts.onPayload(seat.payload)
      opts.onAdvise(seatToAdvise(seat))
    } else if (seat.technique || seat.rationale) {
      opts.onAdvise(seatToAdvise(seat))
    }
  }

  if (ready && opts.onReady) opts.onReady(seat)
  return Math.max(prevSeq, seat.seq || 0)
}

/* ───────────────────── in-process pub/sub + fs.watch ───────────────────── */

const listeners = new Set<SeatListener>()
let watcher: FSWatcher | null = null
let watchDebounce: ReturnType<typeof setTimeout> | null = null
let hub: Server | null = null
let lastPushSeq = -1

function emitSeat(seat: AgentSeat, source: "watch" | "push" | "read") {
  for (const fn of listeners) {
    try {
      fn(seat, source)
    } catch {
      /* subscriber error must not kill bus */
    }
  }
}

function readAndEmit(source: "watch" | "push" | "read") {
  const seat = readSeat()
  if (!seat) return
  // Drop duplicate push/watch of the same seq unless status/busy flipped
  if (source !== "read" && seat.seq === lastPushSeq && source === "watch") {
    // still emit: busy/status may change without seq race on some writers
  }
  lastPushSeq = seat.seq
  emitSeat(seat, source)
}

function ensureWatcher() {
  if (watcher) return
  ensureDir()
  try {
    watcher = watch(AGENT_DIR, { persistent: false }, (event, filename) => {
      const name = filename ? String(filename) : ""
      if (name && basename(name) !== "agent_seat.json" && name !== "agent_seat.json") {
        return
      }
      // Windows fires multiple events per write; debounce coalesces them
      if (watchDebounce) clearTimeout(watchDebounce)
      watchDebounce = setTimeout(() => readAndEmit("watch"), 40)
    })
    watcher.on("error", () => {
      try {
        watcher?.close()
      } catch {
        /* */
      }
      watcher = null
    })
  } catch {
    watcher = null
  }
}

/**
 * Subscribe to seat updates. Starts fs.watch on first subscriber.
 * Returns unsubscribe. Immediate sync read is NOT done here — caller decides.
 */
export function subscribeSeat(fn: SeatListener): () => void {
  listeners.add(fn)
  ensureWatcher()
  return () => {
    listeners.delete(fn)
    if (listeners.size === 0 && watcher) {
      try {
        watcher.close()
      } catch {
        /* */
      }
      watcher = null
    }
  }
}

/**
 * Localhost push hub: agent POSTs JSON seat body (or {seat:...}) to /seat.
 * GET /health, GET /operator (current operator_state), GET /seat.
 * Bound to loopback only.
 */
export function startSeatHub(opts?: {
  port?: number
  host?: string
  onError?: (err: Error) => void
}): { port: number; host: string; stop: () => void } {
  if (hub) {
    return {
      port: HUB_PORT,
      host: HUB_HOST,
      stop: () => stopSeatHub(),
    }
  }
  ensureDir()
  const port = opts?.port ?? HUB_PORT
  const host = opts?.host ?? HUB_HOST

  hub = createServer((req, res) => {
    const url = req.url || "/"
    const method = (req.method || "GET").toUpperCase()

    const json = (code: number, body: unknown) => {
      res.writeHead(code, {
        "Content-Type": "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
      })
      res.end(JSON.stringify(body))
    }

    if (method === "OPTIONS") {
      res.writeHead(204, {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
      })
      res.end()
      return
    }

    if (method === "GET" && (url === "/health" || url === "/")) {
      json(200, {
        ok: true,
        hub: "garbleworks-agent-seat",
        seat: SEAT_PATH,
        operator: OPERATOR_PATH,
      })
      return
    }

    if (method === "GET" && url.startsWith("/seat")) {
      json(200, readSeat() || emptySeat())
      return
    }

    if (method === "GET" && url.startsWith("/operator")) {
      json(200, readOperator() || emptyOperator())
      return
    }

    if (method === "POST" && url.startsWith("/seat")) {
      const chunks: Buffer[] = []
      req.on("data", (c) => chunks.push(Buffer.from(c)))
      req.on("end", () => {
        try {
          const raw = Buffer.concat(chunks).toString("utf-8")
          const body = JSON.parse(raw || "{}")
          const seat = (body.seat || body) as AgentSeat
          if (!seat || seat.v !== 1) {
            json(400, { error: "expected AgentSeat v:1" })
            return
          }
          // Persist then notify (push path is authoritative for this write)
          ensureDir()
          writeFileSync(SEAT_PATH, JSON.stringify(seat, null, 2) + "\n", "utf-8")
          lastPushSeq = seat.seq
          emitSeat(seat, "push")
          json(200, { ok: true, seq: seat.seq, source: "push" })
        } catch (e) {
          json(400, { error: String(e) })
        }
      })
      return
    }

    json(404, { error: "not found" })
  })

  hub.on("error", (err) => {
    opts?.onError?.(err)
  })

  hub.listen(port, host)

  return {
    port,
    host,
    stop: () => stopSeatHub(),
  }
}

export function stopSeatHub() {
  if (hub) {
    try {
      hub.close()
    } catch {
      /* */
    }
    hub = null
  }
}

export function seatPaths() {
  return {
    seat: SEAT_PATH,
    operator: OPERATOR_PATH,
    dir: AGENT_DIR,
    hub: `http://${HUB_HOST}:${HUB_PORT}`,
  }
}

/* ─────────────────────────── React hook ────────────────────────────────── */

/**
 * Event-driven agent seat subscription for React.
 * Uses fs.watch + optional localhost push hub — no setInterval poll loop.
 */
export function useAgentSeat(
  enabled: boolean,
  handlers: SeatApplyOpts,
): { lastSeq: number; hubUrl: string } {
  const seqRef = useRef(0)
  const handlersRef = useRef(handlers)
  handlersRef.current = handlers
  const [lastSeq, setLastSeq] = useState(0)

  useEffect(() => {
    if (!enabled) {
      stopSeatHub()
      return
    }

    const hubInfo = startSeatHub({
      onError: () => {
        /* port in use is fine — another TUI or leftover; file watch still works */
      },
    })

    const apply = (seat: AgentSeat) => {
      const next = applySeatDelta(seat, seqRef.current, handlersRef.current)
      if (next !== seqRef.current) {
        seqRef.current = next
        setLastSeq(next)
      } else {
        // busy/ready may still have run inside applySeatDelta
        seqRef.current = next
      }
    }

    // Initial sync read (one shot — not a poll loop)
    const initial = readSeat()
    if (initial) apply(initial)

    const unsub = subscribeSeat((seat) => apply(seat))

    return () => {
      unsub()
      hubInfo.stop()
    }
  }, [enabled])

  return {
    lastSeq,
    hubUrl: `http://${HUB_HOST}:${HUB_PORT}`,
  }
}
