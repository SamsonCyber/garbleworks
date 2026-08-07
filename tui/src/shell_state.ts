/**
 * Pure shell state for the Garbleworks multi-section TUI.
 *
 * Separates event → chat / board / run-status mapping from OpenTUI render
 * so unit tests drive the shipped reducers without a live terminal.
 */
import {
  applyGwEvent,
  emptyBoard,
  type BoardState,
  type GwEvent,
  type RunEvent,
} from "./bridge"

export type ChatRole =
  | "system"
  | "agent"
  | "tool"
  | "operator"
  | "event"
  | "error"
  | "result"

export type ChatLine = {
  id: string
  ts: number
  role: ChatRole
  text: string
  /** Secondary label: tool name, strategy, level, etc. */
  meta?: string
  /** Structured tool-call id when role is tool (links chat ↔ live deck). */
  toolId?: string
}

/** One live product tool invocation (compose_framing, fire_target, …). */
export type ToolCallStatus = "running" | "ok" | "error"

export type ToolCallLive = {
  id: string
  tool: string
  status: ToolCallStatus
  argsPreview: string
  resultPreview: string
  startedAt: number
  endedAt?: number
  ms?: number
  /** From fire_target / check_leak result JSON when present. */
  leaked?: boolean | null
  channel?: string
  seq: number
}

export type ShellRunStatus = {
  busy: boolean
  /** Lifecycle label only — not a win claim. */
  phase: "idle" | "running" | "finished" | "error" | "need_operator"
  /** Harness objective success when known; null until a result event. */
  success: boolean | null
  note: string
  banner: string
  lastSessionPath: string
  stopTool: string
}

export type ShellProfile = {
  id: string
  label: string
  blurb: string
  mode: string
  target: string
  model?: string
  budget: number
  kind: "auto" | "arena_advise" | "agent_repl"
  provider?: string
}

export type ShellState = {
  board: BoardState
  chat: ChatLine[]
  /** Live product tool calls for the chart deck (not a win claim). */
  tools: ToolCallLive[]
  /** 0/1 hit series from fire/check tools (graph engines). */
  toolHitSeries: number[]
  /** Per-call latency ms series (completed tools with timing). */
  toolLatencySeries: number[]
  run: ShellRunStatus
  profileId: string
  objective: string
  target: string
  secret: string
  /** Operator free-text / brief for arena. */
  brief: string
  chatSeq: number
  toolSeq: number
}

const MAX_CHAT = 400
const MAX_TOOLS = 80
const MAX_HIT_SERIES = 48

export const SHELL_PROFILES: ShellProfile[] = [
  {
    id: "agent",
    label: "Agent · stub",
    blurb: "Local canary · offline tool loop",
    mode: "agent_repl",
    target: "local",
    budget: 12,
    kind: "agent_repl",
    provider: "stub",
  },
  {
    id: "agent-xai",
    label: "Agent · Grok",
    blurb: "xAI attacker brain",
    mode: "agent_repl",
    target: "local",
    budget: 12,
    kind: "agent_repl",
    provider: "xai",
    model: "grok-4-1-fast-reasoning",
  },
  {
    id: "agent-minimax",
    label: "Agent · MiniMax",
    blurb: "MiniMax-M3 attacker brain",
    mode: "agent_repl",
    target: "local",
    budget: 12,
    kind: "agent_repl",
    provider: "minimax",
    model: "MiniMax-M3",
  },
  {
    id: "agent-opencode",
    label: "Agent · OpenCode",
    blurb: "OpenCode Zen gateway",
    mode: "agent_repl",
    target: "local",
    budget: 12,
    kind: "agent_repl",
    provider: "opencode-zen",
    model: "minimax-m3",
  },
  {
    id: "local",
    label: "Local canary",
    blurb: "Auto ladder · deterministic",
    mode: "local",
    target: "local",
    budget: 24,
    kind: "auto",
  },
  {
    id: "arena",
    label: "Web arena",
    blurb: "Advise · paste · report r/t/s",
    mode: "advise",
    target: "(browser)",
    budget: 1,
    kind: "arena_advise",
  },
  {
    id: "qwen",
    label: "Abliterated Qwen",
    blurb: "Ollama target file",
    mode: "auto",
    target: "TARGET-abliterated-qwen.json",
    budget: 24,
    kind: "auto",
  },
  {
    id: "prefill",
    label: "Prefill · Haiku",
    blurb: "Anthropic multi-turn",
    mode: "prefill",
    target: "local",
    model: "claude-haiku-4-5-20251001",
    budget: 12,
    kind: "auto",
  },
]

export function emptyRunStatus(): ShellRunStatus {
  return {
    busy: false,
    phase: "idle",
    success: null,
    note: "Ready",
    banner: "",
    lastSessionPath: "",
    stopTool: "",
  }
}

export function emptyShellState(partial?: Partial<ShellState>): ShellState {
  return {
    board: emptyBoard(),
    chat: [
      {
        id: "boot-0",
        ts: Date.now() / 1000,
        role: "system",
        text: "garbleworks chat · type to talk · /help · esc stop · ctrl+c quit",
      },
    ],
    tools: [],
    toolHitSeries: [],
    toolLatencySeries: [],
    run: emptyRunStatus(),
    profileId: "agent",
    objective: "extract the canary",
    target: "local",
    secret: "",
    brief: "",
    chatSeq: 1,
    toolSeq: 0,
    ...partial,
  }
}

/** Local operator lines (slash help, errors) without a bridge event. */
export function pushShellChat(
  state: ShellState,
  role: ChatRole,
  text: string,
  meta?: string,
): ShellState {
  return pushChat(state, {
    ts: Date.now() / 1000,
    role,
    text,
    meta,
  })
}

function pushChat(
  state: ShellState,
  line: Omit<ChatLine, "id"> & { id?: string },
): ShellState {
  const seq = state.chatSeq + 1
  const entry: ChatLine = {
    id: line.id || `c${seq}`,
    ts: line.ts,
    role: line.role,
    text: line.text,
    meta: line.meta,
    toolId: line.toolId,
  }
  return {
    ...state,
    chatSeq: seq,
    chat: [...state.chat, entry].slice(-MAX_CHAT),
  }
}

function tsOf(event: GwEvent): number {
  return Number(event.ts) || Date.now() / 1000
}

function preview(s: unknown, n = 220): string {
  const t = String(s ?? "").replace(/\s+/g, " ").trim()
  if (!t) return ""
  return t.length <= n ? t : t.slice(0, n - 1) + "…"
}

/** Pull leak/channel/ms from harness tool result JSON when present. */
export function parseToolResultMeta(raw: unknown): {
  leaked: boolean | null
  channel?: string
  ms?: number
  ok?: boolean
} {
  const text = String(raw ?? "").trim()
  if (!text) return { leaked: null }
  try {
    const obj = JSON.parse(text) as Record<string, unknown>
    const leaked =
      typeof obj.leaked === "boolean"
        ? obj.leaked
        : typeof obj.success === "boolean" && /leak|canary|token/i.test(text)
          ? obj.success
          : null
    const channel = obj.channel != null ? String(obj.channel) : undefined
    const ms = obj.ms != null && Number.isFinite(Number(obj.ms)) ? Number(obj.ms) : undefined
    const ok = typeof obj.ok === "boolean" ? obj.ok : undefined
    return { leaked, channel, ms, ok }
  } catch {
    if (/\bleaked\b\s*[:=]\s*true/i.test(text) || /\bleak(ed)?\b.*\btrue\b/i.test(text)) {
      return { leaked: true }
    }
    if (/\bleaked\b\s*[:=]\s*false/i.test(text)) return { leaked: false }
    return { leaked: null }
  }
}

function startToolCall(
  state: ShellState,
  opts: { tool: string; toolId?: string; argsPreview: string; ts: number },
): { state: ShellState; call: ToolCallLive } {
  const seq = state.toolSeq + 1
  const id = opts.toolId || `t${seq}`
  const call: ToolCallLive = {
    id,
    tool: opts.tool,
    status: "running",
    argsPreview: opts.argsPreview,
    resultPreview: "",
    startedAt: opts.ts,
    seq,
  }
  return {
    state: {
      ...state,
      toolSeq: seq,
      tools: [...state.tools, call].slice(-MAX_TOOLS),
    },
    call,
  }
}

function finishToolCall(
  state: ShellState,
  opts: {
    tool: string
    toolId?: string
    resultPreview: string
    isError: boolean
    ts: number
  },
): ShellState {
  const meta = parseToolResultMeta(opts.resultPreview)
  const tools = [...state.tools]
  let idx = -1
  if (opts.toolId) {
    idx = tools.findIndex((t) => t.id === opts.toolId)
  }
  if (idx < 0) {
    for (let i = tools.length - 1; i >= 0; i--) {
      if (tools[i].tool === opts.tool && tools[i].status === "running") {
        idx = i
        break
      }
    }
  }
  if (idx < 0) {
    // Orphan result — open+close so the chart still sees it
    const opened = startToolCall(state, {
      tool: opts.tool,
      toolId: opts.toolId,
      argsPreview: "",
      ts: opts.ts,
    })
    return finishToolCall(opened.state, opts)
  }

  const prev = tools[idx]
  const ms =
    meta.ms ??
    Math.max(0, Math.round((opts.ts - prev.startedAt) * 1000))
  tools[idx] = {
    ...prev,
    status: opts.isError || meta.ok === false ? "error" : "ok",
    resultPreview: opts.resultPreview,
    endedAt: opts.ts,
    ms,
    leaked: meta.leaked,
    channel: meta.channel || prev.channel,
  }

  let hitSeries = state.toolHitSeries
  const isFireTool = /fire|check_leak|validate/i.test(opts.tool)
  if (isFireTool && meta.leaked !== null) {
    hitSeries = [...hitSeries, meta.leaked ? 1 : 0].slice(-MAX_HIT_SERIES)
  }

  let latencySeries = state.toolLatencySeries
  if (ms != null && Number.isFinite(ms)) {
    latencySeries = [...latencySeries, ms].slice(-MAX_HIT_SERIES)
  }

  return {
    ...state,
    tools,
    toolHitSeries: hitSeries,
    toolLatencySeries: latencySeries,
  }
}

/**
 * Map a structured GW event onto board + chat + run status.
 * Success is taken only from harness fields (event.success / lastResult),
 * never from status==="finished" alone.
 */
export function applyShellGwEvent(event: GwEvent, state: ShellState): ShellState {
  const kind = String(event.kind || "")
  let next: ShellState = {
    ...state,
    board: applyGwEvent(event, state.board),
  }

  // Chat session lifecycle
  if (kind === "session_ready") {
    const brain = event.brain || "stub"
    const target = event.target || "local"
    const tools = Array.isArray(event.tools) ? event.tools.length : "?"
    return {
      ...pushChat(next, {
        ts: tsOf(event),
        role: "system",
        meta: "session",
        text: `Session ready · brain=${brain} · target=${target} · ${tools} tools`,
      }),
      run: {
        ...next.run,
        busy: false,
        phase: "idle",
        note: "Session ready",
        banner: "",
      },
    }
  }

  if (kind === "user") {
    const text = preview(event.text || event.message || "", 600)
    if (!text) return next
    return pushChat(next, {
      ts: tsOf(event),
      role: "operator",
      meta: "you",
      text,
    })
  }

  if (kind === "turn_start") {
    return {
      ...next,
      run: {
        ...next.run,
        busy: true,
        phase: "running",
        success: null,
        note: preview(event.objective || "working", 80),
        banner: "WORKING",
      },
      objective:
        event.objective != null
          ? String(event.objective).slice(0, 200)
          : next.objective,
    }
  }

  if (kind === "turn_complete") {
    const hasSuccess = Object.prototype.hasOwnProperty.call(event, "success")
    const success = hasSuccess ? Boolean(event.success) : null
    const summary = preview(event.summary || event.message || "", 320)
    const session =
      event.session_path != null
        ? String(event.session_path)
        : next.run.lastSessionPath
    const phase: ShellRunStatus["phase"] =
      event.status === "need_operator" ? "need_operator" : "finished"
    let out: ShellState = {
      ...next,
      run: {
        ...next.run,
        busy: false,
        phase,
        success,
        note: summary || next.run.note,
        lastSessionPath: session,
        stopTool: event.stop_tool != null ? String(event.stop_tool) : next.run.stopTool,
        banner:
          success === true ? "SUCCESS" : success === false ? "NO WIN" : next.run.banner,
      },
    }
    if (summary || success !== null) {
      out = pushChat(out, {
        ts: tsOf(event),
        role: "result",
        meta:
          success === true
            ? "win"
            : success === false
              ? "miss"
              : String(event.status || "done"),
        text:
          summary ||
          (success === true
            ? "Objective met (harness)"
            : success === false
              ? "Turn finished without harness win"
              : "Turn complete"),
      })
    }
    return out
  }

  if (kind === "ready") {
    return {
      ...next,
      run: {
        ...next.run,
        busy: Boolean(event.busy),
        phase: event.busy ? next.run.phase : next.run.phase === "running" ? "idle" : next.run.phase,
      },
    }
  }

  if (kind === "feedback_queued" || kind === "feedback_applied") {
    const text = preview(event.text || "", 240)
    if (!text) return next
    return pushChat(next, {
      ts: tsOf(event),
      role: "operator",
      meta: kind === "feedback_queued" ? "queued" : "steering",
      text:
        kind === "feedback_queued"
          ? `Queued mid-flight: ${text}`
          : `Steering applied: ${text}`,
    })
  }

  if (kind === "session_cleared") {
    return pushChat(
      {
        ...next,
        run: emptyRunStatus(),
        board: emptyBoard(),
        tools: [],
        toolHitSeries: [],
        toolLatencySeries: [],
      },
      {
        ts: tsOf(event),
        role: "system",
        meta: "clear",
        text: "History cleared. Next message starts a new engagement.",
      },
    )
  }

  if (kind === "session_config") {
    return pushChat(next, {
      ts: tsOf(event),
      role: "system",
      meta: "config",
      text: preview(
        `Config · brain=${event.brain || "?"} · target=${event.target || "?"} · rounds=${event.max_rounds ?? "?"}`,
        200,
      ),
    })
  }

  if (kind === "session_error" || kind === "stop_requested") {
    if (kind === "stop_requested") {
      return pushChat(next, {
        ts: tsOf(event),
        role: "system",
        meta: "stop",
        text: "Stop requested — agent should wrap up this turn",
      })
    }
    return pushChat(next, {
      ts: tsOf(event),
      role: "error",
      meta: "error",
      text: preview(event.error || event.message || "session error", 300),
    })
  }

  // Agent-repl / bridge kinds that may arrive unmapped (non-TUI JSON) or as TUI maps
  if (kind === "brain_config") {
    const prov = event.provider || event.label || event.brain || "brain"
    const model = event.model ? String(event.model) : ""
    return pushChat(next, {
      ts: tsOf(event),
      role: "system",
      meta: "brain",
      text: `Brain ready · ${prov}${model ? ` · ${model}` : ""}`,
    })
  }

  if (kind === "agent_round") {
    const r = event.round ?? event.r
    const max = event.max ?? event.max_rounds
    return pushChat(next, {
      ts: tsOf(event),
      role: "event",
      meta: "round",
      text: `Round ${r ?? "?"}${max != null ? ` / ${max}` : ""}`,
    })
  }

  if (kind === "tool_start") {
    const tool = String(event.tool || event.name || "tool")
    const args = event.args != null ? preview(JSON.stringify(event.args), 180) : ""
    const toolId =
      event.tool_id != null
        ? String(event.tool_id)
        : event.id != null
          ? String(event.id)
          : undefined
    const ts = tsOf(event)
    const opened = startToolCall(next, {
      tool,
      toolId,
      argsPreview: args,
      ts,
    })
    return pushChat(opened.state, {
      ts,
      role: "tool",
      meta: tool,
      toolId: opened.call.id,
      text: args ? `▶ ${tool}  ${args}` : `▶ ${tool}`,
    })
  }

  if (kind === "tool_result") {
    const tool = String(event.tool || event.name || "tool")
    const err = Boolean(event.is_error)
    const body = preview(
      event.result_preview ?? event.reply ?? event.message ?? "",
      280,
    )
    const toolId =
      event.tool_id != null
        ? String(event.tool_id)
        : event.id != null
          ? String(event.id)
          : undefined
    const ts = tsOf(event)
    const withTool = finishToolCall(next, {
      tool,
      toolId,
      resultPreview: body,
      isError: err,
      ts,
    })
    const live = withTool.tools.find((t) => t.id === toolId) ||
      [...withTool.tools].reverse().find((t) => t.tool === tool)
    const leakTag =
      live?.leaked === true ? " · LEAK" : live?.leaked === false ? " · no-leak" : ""
    const msTag = live?.ms != null ? ` ${live.ms}ms` : ""
    return pushChat(withTool, {
      ts,
      role: err ? "error" : "tool",
      meta: tool,
      toolId: live?.id,
      text: err
        ? `◀ ${tool} ERROR${msTag}  ${body}`
        : `◀ ${tool}${msTag}${leakTag}  ${body}`,
    })
  }

  if (kind === "agent_text" || kind === "agent_message") {
    const text = preview(event.text || event.message || event.content || "", 400)
    if (!text) return next
    return pushChat(next, {
      ts: tsOf(event),
      role: "agent",
      meta: "brain",
      text,
    })
  }

  if (kind === "agent_error") {
    return pushChat(next, {
      ts: tsOf(event),
      role: "error",
      meta: "error",
      text: preview(event.error || event.message || "agent error", 300),
    })
  }

  if (kind === "activity") {
    const msg = preview(event.message || "", 280)
    if (!msg) return next
    const level = String(event.level || "info")
    return pushChat(next, {
      ts: tsOf(event),
      role: level === "win" ? "result" : level === "error" || level === "warn" ? "error" : "event",
      meta: event.strategy ? String(event.strategy) : level,
      text: msg,
    })
  }

  if (kind === "fire") {
    const leaked = Boolean(event.leaked)
    const strat = event.strategy ? String(event.strategy) : ""
    const channel = event.channel != null ? String(event.channel) : undefined
    // Advise-only paste is not a scored hit series sample
    if (channel !== "manual_paste") {
      next = {
        ...next,
        toolHitSeries: [...next.toolHitSeries, leaked ? 1 : 0].slice(-MAX_HIT_SERIES),
      }
    }
    return pushChat(next, {
      ts: tsOf(event),
      role: leaked ? "result" : "event",
      meta: strat || "fire",
      text: leaked
        ? `Fire hit · ch=${event.channel || "-"} · ${preview(event.reply_preview, 120)}`
        : `Fire · no leak · ${preview(event.payload_preview, 100)}`,
    })
  }

  if (kind === "result" || kind === "run_complete" || kind === "agent_stop") {
    // Harness success only — never treat mere finished lifecycle as a win
    const hasSuccessField = Object.prototype.hasOwnProperty.call(event, "success")
    const success = hasSuccessField
      ? Boolean(event.success)
      : event.args && typeof event.args === "object" && "success" in (event.args as object)
        ? Boolean((event.args as { success?: unknown }).success)
        : null

    const summary = preview(
      event.summary ||
        event.message ||
        (event.args && typeof event.args === "object"
          ? (event.args as { summary?: string }).summary
          : "") ||
        "",
      280,
    )
    const session =
      event.session_path != null
        ? String(event.session_path)
        : event.session_jsonl != null
          ? String(event.session_jsonl)
          : next.run.lastSessionPath

    const stopTool =
      event.stop_tool != null
        ? String(event.stop_tool)
        : kind === "agent_stop"
          ? String(event.stop_tool || "finish")
          : next.run.stopTool

    next = {
      ...next,
      run: {
        ...next.run,
        phase:
          kind === "run_complete" || kind === "result"
            ? "finished"
            : next.run.phase,
        success: success,
        banner:
          success === true
            ? "SUCCESS"
            : success === false
              ? "NO WIN"
              : next.run.banner,
        note: summary || next.run.note,
        lastSessionPath: session,
        stopTool,
        busy: kind === "run_complete" ? false : next.run.busy,
      },
    }

    if (summary || success !== null) {
      next = pushChat(next, {
        ts: tsOf(event),
        role: "result",
        meta:
          success === true ? "win" : success === false ? "miss" : kind,
        text:
          summary ||
          (success === true
            ? "Objective met (harness)"
            : success === false
              ? "Finished without harness win"
              : "Run update"),
      })
    }
    return next
  }

  if (kind === "plan") {
    const labels = Array.isArray(event.steps)
      ? (event.steps as { label?: string; id?: string }[])
          .map((s) => s.label || s.id || "?")
          .join(" → ")
      : ""
    if (labels) {
      next = pushChat(next, {
        ts: tsOf(event),
        role: "system",
        meta: "plan",
        text: `Plan · ${labels}`,
      })
    }
    return next
  }

  if (kind === "step" && event.step_id) {
    return pushChat(next, {
      ts: tsOf(event),
      role: "event",
      meta: String(event.status || "step"),
      text: `Step ${event.step_id}${event.note ? ` · ${preview(event.note, 100)}` : ""}`,
    })
  }

  if (kind === "progress") {
    const label = preview(event.label || event.detail || "", 120)
    if (label) {
      next = pushChat(next, {
        ts: tsOf(event),
        role: "event",
        meta: "progress",
        text: label,
      })
    }
    return next
  }

  return next
}

/**
 * Apply a full bridge RunEvent (line | gw | advise | done | error).
 */
export function applyShellRunEvent(ev: RunEvent, state: ShellState): ShellState {
  if (ev.type === "gw") {
    return applyShellGwEvent(ev.event, state)
  }

  if (ev.type === "advise") {
    const a = ev.advise
    const payload = Array.isArray(a.payload)
      ? a.payload.join("\n")
      : String(a.payload || "")
    let next = pushChat(state, {
      ts: Date.now() / 1000,
      role: "system",
      meta: a.technique || "advise",
      text: `Advise · ${a.technique || "?"} · ${preview(a.rationale || a.kind, 160)}`,
    })
    if (payload.trim()) {
      next = pushChat(next, {
        ts: Date.now() / 1000,
        role: "agent",
        meta: "payload",
        text: preview(payload, 320),
      })
      next = {
        ...next,
        board: {
          ...next.board,
          mission: {
            ...next.board.mission,
            lastFire: {
              strategy: a.technique || "",
              payload: preview(payload, 200),
              reply: "(paste in browser, then report r/t/s)",
              leaked: false,
              channel: "manual_paste",
            },
            lastStrategy: a.technique || next.board.mission.lastStrategy,
          },
        },
      }
    }
    return next
  }

  if (ev.type === "error") {
    return {
      ...pushChat(state, {
        ts: Date.now() / 1000,
        role: "error",
        meta: "error",
        text: preview(ev.text, 300),
      }),
      run: {
        ...state.run,
        phase: "error",
        note: preview(ev.text, 120),
        busy: false,
      },
    }
  }

  if (ev.type === "done") {
    // Exit code alone is not harness success.
    // Long-lived chat sessions may end; mark idle so the UI can reconnect.
    const killed = Boolean(ev.killed)
    let next = state
    if (killed) {
      next = pushChat(next, {
        ts: Date.now() / 1000,
        role: "system",
        meta: "kill",
        text: "Session / run stopped by operator",
      })
    } else if (ev.code !== 0) {
      next = pushChat(next, {
        ts: Date.now() / 1000,
        role: "error",
        meta: "exit",
        text: `Process exited ${ev.code}`,
      })
    }
    return {
      ...next,
      run: {
        ...next.run,
        busy: false,
        phase:
          next.run.success === true || next.run.success === false
            ? "finished"
            : killed
              ? "idle"
              : next.run.phase === "running"
                ? "finished"
                : "idle",
        note: killed
          ? "Stopped"
          : next.run.note || (ev.code === 0 ? "Session closed" : `Exit ${ev.code}`),
      },
    }
  }

  // type === "line" — plain stdout (agent_repl JSON without GW| prefix, or log noise)
  const text = ev.text || ""
  if (!text.trim()) return state

  // Try agent_repl / JSON event shapes
  if (text.startsWith("{") && text.includes('"kind"')) {
    try {
      const obj = JSON.parse(text) as GwEvent
      if (obj && typeof obj.kind === "string") {
        return applyShellGwEvent(obj, state)
      }
    } catch {
      /* fall through */
    }
  }

  return pushChat(state, {
    ts: Date.now() / 1000,
    role: "event",
    meta: "log",
    text: preview(text, 300),
  })
}

export function markShellRunning(
  state: ShellState,
  note: string,
): ShellState {
  return {
    ...pushChat(state, {
      ts: Date.now() / 1000,
      role: "system",
      meta: "run",
      text: note,
    }),
    run: {
      ...state.run,
      busy: true,
      phase: "running",
      success: null,
      note,
      banner: "RUNNING",
    },
    board: emptyBoard(),
    tools: [],
    toolHitSeries: [],
    toolLatencySeries: [],
  }
}

/** Counts + hit rate for the live tool chart (pure helper for UI / tests). */
export function toolChartStats(tools: ToolCallLive[], hitSeries: number[]) {
  const byName = new Map<string, number>()
  let running = 0
  let ok = 0
  let err = 0
  let leaks = 0
  for (const t of tools) {
    byName.set(t.tool, (byName.get(t.tool) || 0) + 1)
    if (t.status === "running") running++
    else if (t.status === "error") err++
    else ok++
    if (t.leaked === true) leaks++
  }
  const bars = [...byName.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8)
    .map(([label, value]) => ({ label, value }))
  const hits = hitSeries.reduce((s, v) => s + v, 0)
  const n = hitSeries.length
  return {
    total: tools.length,
    running,
    ok,
    err,
    leaks,
    bars,
    hitSeries,
    hitRate: n > 0 ? hits / n : 0,
  }
}

export function getProfile(id: string): ShellProfile {
  return SHELL_PROFILES.find((p) => p.id === id) || SHELL_PROFILES[0]
}
