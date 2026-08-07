/**
 * Garbleworks agent chat — lightweight transparent shell.
 *
 * Layout (no panels, no solid fills):
 *   top     thin status strip
 *   center  chat stream
 *   bottom  prompt + key hints
 *
 * Agent profiles: long-lived Python session (stdin JSONL + GW| events).
 * Auto / arena profiles: one-shot jobs.
 */
import { createCliRenderer } from "@opentui/core"
import {
  createRoot,
  useKeyboard,
  useRenderer,
  useTerminalDimensions,
} from "@opentui/react"
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import {
  clearArenaHistory,
  emptyBoard,
  loadArenaHistory,
  openAgentSession,
  saveArenaHistory,
  type AgentSessionHandle,
  type ArenaAttempt,
  type JobHandle,
  type RunEvent,
  runAgentRepl,
  runArenaAdvise,
  runAuto,
} from "./bridge"
import {
  applyShellRunEvent,
  emptyShellState,
  getProfile,
  markShellRunning,
  pushShellChat,
  SHELL_PROFILES,
  type ChatLine,
  type ShellState,
} from "./shell_state"
import { roleColor, roleTag, successColor, T } from "./shell_theme"
import { estimateDeckRows, ToolLiveDeck } from "./shell_tools"

const HELP = [
  "/help              this list",
  "/clear             clear chat (session + UI)",
  "/stop              wrap up current turn (Esc)",
  "/profile [id]      list or switch brain",
  "/target <id|url>   set target",
  "/secret <s>        set canary secret",
  "/brain <id>        set brain on live session",
  "/auto <objective>  one-shot auto ladder",
  "/arena             web-arena advise profile",
  "/reconnect         reopen agent session",
  "/quit              exit",
  "",
  "Anything else talks to the agent. Mid-flight text is live steering.",
].join("\n")

function wrapText(text: string, width: number): string[] {
  const w = Math.max(12, width)
  const out: string[] = []
  for (const para of text.split("\n")) {
    if (!para) {
      out.push("")
      continue
    }
    let rest = para
    while (rest.length > w) {
      let cut = rest.lastIndexOf(" ", w)
      if (cut < Math.floor(w * 0.4)) cut = w
      out.push(rest.slice(0, cut))
      rest = rest.slice(cut).replace(/^\s+/, "")
    }
    out.push(rest)
  }
  return out.length ? out : [""]
}

function ChatStream({
  lines,
  maxRows,
  contentWidth,
  /** When true, tool lines live in ToolLiveDeck — skip duplicate dumps. */
  toolsInDeck = false,
}: {
  lines: ChatLine[]
  maxRows: number
  contentWidth: number
  toolsInDeck?: boolean
}) {
  const rows: {
    key: string
    tag: string
    tagFg: string
    body: string
    bodyFg: string
    role: string
  }[] = []
  for (const ln of lines) {
    if (toolsInDeck && ln.role === "tool") continue
    const tag = (ln.meta || roleTag(ln.role)).slice(0, 7)
    const bodyW = Math.max(8, contentWidth - 12)
    const parts = wrapText(ln.text, bodyW)
    parts.forEach((part, i) => {
      rows.push({
        key: `${ln.id}-${i}`,
        tag: i === 0 ? tag : "",
        tagFg: roleColor(ln.role),
        body: part,
        bodyFg: roleColor(ln.role),
        role: ln.role,
      })
    })
  }
  const slice = rows.slice(-Math.max(4, maxRows))

  if (!slice.length) {
    return (
      <box flexDirection="column" backgroundColor={T.clear} flexGrow={1}>
        <text>
          <span fg={T.dim}>chat empty · type below</span>
        </text>
      </box>
    )
  }

  return (
    <box flexDirection="column" backgroundColor={T.clear} flexGrow={1}>
      {slice.map((r) => {
        const edge =
          r.role === "operator"
            ? T.you
            : r.role === "result"
              ? T.success
              : r.role === "error"
                ? T.danger
                : r.role === "agent"
                  ? T.accent
                  : T.dim
        return (
          <text key={r.key}>
            <span fg={r.tag ? edge : T.dim}>{r.tag ? "│" : " "}</span>
            <span fg={r.tag ? r.tagFg : T.dim}>
              {(r.tag || "").padEnd(7).slice(0, 7)}
            </span>
            <span fg={T.dim}> </span>
            <span fg={r.bodyFg}>{r.body}</span>
          </text>
        )
      })}
    </box>
  )
}

function StatusStrip({
  state,
  profileLabel,
  busy,
}: {
  state: ShellState
  profileLabel: string
  busy: boolean
}) {
  const stats = state.board.stats
  const tools = state.tools
  const running = tools.filter((t) => t.status === "running").length
  const phase =
    busy
      ? running > 0
        ? `call ${tools[tools.length - 1]?.tool || "…"}`
        : "working"
      : state.run.phase === "need_operator"
        ? "need you"
        : state.run.success === true
          ? "win"
          : state.run.success === false
            ? "miss"
            : "ready"
  const target = (state.target || getProfile(state.profileId).target || "local").slice(
    0,
    28,
  )

  return (
    <box
      flexDirection="row"
      justifyContent="space-between"
      height={1}
      flexShrink={0}
      backgroundColor={T.clear}
    >
      <text>
        <span fg={T.accent}>gw</span>
        <span fg={T.dim}>  </span>
        <span fg={T.text}>{profileLabel}</span>
        <span fg={T.dim}> → </span>
        <span fg={T.info}>{target}</span>
        {tools.length > 0 ? (
          <>
            <span fg={T.dim}>  </span>
            <span fg={T.muted}>tools {tools.length}</span>
          </>
        ) : null}
      </text>
      <text>
        <span fg={successColor(state.run.success)}>{phase}</span>
        <span fg={T.dim}>  </span>
        <span fg={T.dim}>fire {stats.fires}</span>
        <span fg={T.dim}>  </span>
        <span fg={T.success}>hit {stats.wins}</span>
        <span fg={T.dim}>  </span>
        <span fg={T.muted}>miss {stats.misses}</span>
      </text>
    </box>
  )
}

function Sep({ width }: { width: number }) {
  const n = Math.max(8, Math.min(width, 200))
  return (
    <box height={1} flexShrink={0} backgroundColor={T.clear}>
      <text>
        <span fg={T.dim}>{"─".repeat(n)}</span>
      </text>
    </box>
  )
}

export function ShellApp() {
  const renderer = useRenderer()
  const dims = useTerminalDimensions()
  const [state, setState] = useState<ShellState>(() => emptyShellState())
  const [prompt, setPrompt] = useState("")
  const [history, setHistory] = useState<ArenaAttempt[]>(() => loadArenaHistory())
  const [inputHist, setInputHist] = useState<string[]>([])
  const [histPos, setHistPos] = useState<number | null>(null)

  const jobRef = useRef<JobHandle | null>(null)
  const sessionRef = useRef<AgentSessionHandle | null>(null)
  const stateRef = useRef(state)
  stateRef.current = state
  const promptRef = useRef(prompt)
  promptRef.current = prompt

  const profile = getProfile(state.profileId)
  const profileIdx = Math.max(
    0,
    SHELL_PROFILES.findIndex((p) => p.id === state.profileId),
  )
  const isArena = profile.kind === "arena_advise"
  const isAgentRepl = profile.kind === "agent_repl"
  const busy = state.run.busy

  const pushEvent = useCallback((ev: RunEvent) => {
    setState((s) => applyShellRunEvent(ev, s))
  }, [])

  const note = useCallback((text: string, role: ChatLine["role"] = "system") => {
    setState((s) => pushShellChat(s, role, text))
  }, [])

  const killSession = useCallback(() => {
    if (sessionRef.current) {
      sessionRef.current.kill()
      sessionRef.current = null
    }
  }, [])

  const killJob = useCallback(() => {
    if (jobRef.current) {
      jobRef.current.kill()
      jobRef.current = null
    }
  }, [])

  const quit = useCallback(() => {
    killSession()
    killJob()
    renderer.destroy()
  }, [killJob, killSession, renderer])

  const startChatSession = useCallback(
    (profId?: string) => {
      const s0 = stateRef.current
      const prof = getProfile(profId || s0.profileId)
      if (prof.kind !== "agent_repl") return

      killSession()
      killJob()

      const target =
        (s0.target.trim() || prof.target || "local").trim() || "local"
      const provider = prof.provider || "stub"
      const sec =
        s0.secret.trim() ||
        (target !== "local" ? "CANARY_LAB_DEFAULT" : undefined)

      setState((s) =>
        pushShellChat(
          {
            ...s,
            board: emptyBoard(),
            tools: [],
            toolHitSeries: [],
            toolLatencySeries: [],
            run: {
              ...s.run,
              busy: false,
              phase: "idle",
              note: "Connecting…",
              banner: "",
              success: null,
            },
          },
          "system",
          `open · ${prof.label} → ${target}`,
          "session",
        ),
      )

      const handle = openAgentSession({
        target,
        secret: sec,
        brain: provider,
        provider: provider === "stub" ? undefined : provider,
        maxRounds: prof.budget || 12,
        maxFires: Math.max(24, prof.budget || 12),
        model: prof.model,
        objective: s0.objective.trim() || undefined,
        onEvent: (ev) => {
          pushEvent(ev)
          if (ev.type === "done") {
            sessionRef.current = null
          }
        },
      })
      sessionRef.current = handle
      void handle.done.then(() => {
        if (sessionRef.current === handle) sessionRef.current = null
      })
    },
    [killJob, killSession, pushEvent],
  )

  const lastSessionProfile = useRef<string>("")
  useEffect(() => {
    if (!isAgentRepl) {
      lastSessionProfile.current = ""
      return
    }
    if (lastSessionProfile.current === state.profileId && sessionRef.current) {
      return
    }
    lastSessionProfile.current = state.profileId
    startChatSession(state.profileId)
  }, [isAgentRepl, state.profileId, startChatSession])

  useEffect(() => {
    return () => {
      killSession()
      killJob()
    }
  }, [killJob, killSession])

  const startOneShot = useCallback(
    async (kind: "auto" | "arena_advise" | "agent_repl", objective?: string) => {
      if (jobRef.current || stateRef.current.run.busy) return
      const s0 = stateRef.current
      const prof = getProfile(s0.profileId)
      const target =
        (s0.target.trim() || prof.target || "local").trim() || "local"
      const obj = (objective ?? s0.objective).trim() || "extract the canary"

      setState((s) =>
        markShellRunning(
          { ...s, board: emptyBoard() },
          `start · ${prof.label} → ${target}`,
        ),
      )

      const onEvent = (ev: RunEvent) => pushEvent(ev)
      let handle: JobHandle

      if (kind === "arena_advise") {
        handle = runArenaAdvise({
          objective: obj,
          brief: s0.brief.trim() || undefined,
          history,
          onEvent,
        })
      } else if (kind === "agent_repl") {
        const provider = prof.provider || "stub"
        const sec =
          s0.secret.trim() ||
          (target !== "local" ? "CANARY_LAB_DEFAULT" : undefined)
        handle = runAgentRepl({
          objective: obj,
          target,
          secret: sec,
          brain: provider,
          provider: provider === "stub" ? undefined : provider,
          maxRounds: prof.budget || 12,
          maxFires: Math.max(24, prof.budget || 12),
          model: prof.model,
          onEvent,
        })
      } else {
        const sec =
          s0.secret.trim() ||
          (target !== "local" ? "CANARY_LAB_DEFAULT" : undefined)
        handle = runAuto({
          objective: obj,
          mode: prof.mode,
          target,
          model: prof.model,
          budget: prof.budget,
          secret: sec,
          onEvent,
        })
      }

      jobRef.current = handle
      try {
        await handle.done
      } catch (e) {
        pushEvent({ type: "error", text: String(e) })
      } finally {
        jobRef.current = null
      }
    },
    [history, pushEvent],
  )

  const switchProfile = useCallback(
    (id: string) => {
      const p = getProfile(id)
      if (p.kind !== "agent_repl") {
        killSession()
        lastSessionProfile.current = ""
      }
      setState((s) => ({
        ...s,
        profileId: p.id,
        target: p.target === "(browser)" ? s.target : p.target || s.target,
      }))
      if (p.kind !== "agent_repl") {
        note(`${p.label} · one-shot — type objective or /auto`)
      }
    },
    [killSession, note],
  )

  const handleSlash = useCallback(
    (raw: string) => {
      const body = raw.slice(1).trim()
      const [cmd, ...rest] = body.split(/\s+/)
      const arg = rest.join(" ").trim()
      const c = (cmd || "").toLowerCase()

      if (c === "help" || c === "h" || c === "?") {
        note(HELP, "system")
        return
      }
      if (c === "quit" || c === "exit" || c === "q") {
        quit()
        return
      }
      if (c === "clear") {
        sessionRef.current?.clear()
        setState((s) => ({
          ...emptyShellState({
            profileId: s.profileId,
            target: s.target,
            secret: s.secret,
            objective: s.objective,
            brief: s.brief,
          }),
        }))
        note("cleared")
        return
      }
      if (c === "stop") {
        if (sessionRef.current) sessionRef.current.stop()
        else killJob()
        note("stop requested")
        return
      }
      if (c === "profile" || c === "profiles") {
        if (!arg) {
          note(
            SHELL_PROFILES.map(
              (p) =>
                `${p.id === stateRef.current.profileId ? "›" : " "} ${p.id.padEnd(16)} ${p.label}`,
            ).join("\n"),
          )
          return
        }
        const hit =
          SHELL_PROFILES.find((p) => p.id === arg) ||
          SHELL_PROFILES.find((p) =>
            p.label.toLowerCase().includes(arg.toLowerCase()),
          )
        if (!hit) {
          note(`unknown profile: ${arg}`, "error")
          return
        }
        switchProfile(hit.id)
        return
      }
      if (c === "target") {
        if (!arg) {
          note(`target = ${stateRef.current.target || "local"}`)
          return
        }
        setState((s) => ({ ...s, target: arg }))
        sessionRef.current?.set({ target: arg })
        note(`target → ${arg}`)
        return
      }
      if (c === "secret") {
        setState((s) => ({ ...s, secret: arg }))
        sessionRef.current?.set({ secret: arg })
        note(arg ? "secret set" : "secret cleared")
        return
      }
      if (c === "brain") {
        if (!arg) {
          note(
            `brain = ${getProfile(stateRef.current.profileId).provider || "stub"}`,
          )
          return
        }
        sessionRef.current?.set({ brain: arg })
        note(`brain → ${arg}`)
        return
      }
      if (c === "auto") {
        const obj = arg || stateRef.current.objective || "extract the canary"
        void startOneShot("auto", obj)
        return
      }
      if (c === "arena") {
        switchProfile("arena")
        return
      }
      if (c === "reconnect") {
        startChatSession()
        return
      }
      note(`unknown /${c} · try /help`, "error")
    },
    [killJob, note, quit, startChatSession, startOneShot, switchProfile],
  )

  const submitPrompt = useCallback(
    (value: string) => {
      const text = value.trim()
      setPrompt("")
      setHistPos(null)
      if (!text) return

      setInputHist((h) =>
        h[h.length - 1] === text ? h : [...h.slice(-80), text],
      )

      if (text.startsWith("/")) {
        handleSlash(text)
        return
      }

      const s0 = stateRef.current
      const prof = getProfile(s0.profileId)

      if (prof.kind === "agent_repl") {
        if (!sessionRef.current) {
          startChatSession()
          setTimeout(() => {
            sessionRef.current?.turn(text)
          }, 250)
          return
        }
        if (s0.run.busy) {
          sessionRef.current.feedback(text)
        } else {
          sessionRef.current.turn(text)
        }
        return
      }

      setState((s) => ({ ...s, objective: text }))
      void startOneShot(prof.kind, text)
    },
    [handleSlash, startChatSession, startOneShot],
  )

  const reportOutcome = useCallback(
    (outcome: "refused" | "tripwire" | "success") => {
      if (!isArena) return
      const tech =
        stateRef.current.board.mission.lastStrategy ||
        stateRef.current.board.mission.lastFire?.strategy ||
        "unknown"
      const payload = stateRef.current.board.mission.lastFire?.payload || ""
      const nextHist: ArenaAttempt[] = [
        ...history,
        { technique: tech, outcome, payload },
      ]
      setHistory(nextHist)
      saveArenaHistory(nextHist)
      note(`reported ${outcome} · ${tech}`)
    },
    [history, isArena, note],
  )

  useKeyboard((key) => {
    if (key.name === "escape" || (key.ctrl && key.name === "x")) {
      if (sessionRef.current && stateRef.current.run.busy) {
        sessionRef.current.stop()
        note("stop (esc)")
      } else {
        killJob()
      }
      return
    }

    if (isArena && key.meta) {
      if (key.name === "r") {
        reportOutcome("refused")
        return
      }
      if (key.name === "t") {
        reportOutcome("tripwire")
        return
      }
      if (key.name === "s") {
        reportOutcome("success")
        return
      }
      if (key.name === "f") {
        clearArenaHistory()
        setHistory([])
        note("arena history cleared")
        return
      }
    }

    if ((key.name === "up" || key.name === "down") && key.ctrl) {
      const dir = key.name === "up" ? -1 : 1
      const i =
        (profileIdx + dir + SHELL_PROFILES.length) % SHELL_PROFILES.length
      switchProfile(SHELL_PROFILES[i].id)
      return
    }

    if (
      inputHist.length &&
      (key.name === "up" || key.name === "down") &&
      key.meta
    ) {
      if (key.name === "up") {
        setHistPos((pos) => {
          const next =
            pos === null ? inputHist.length - 1 : Math.max(0, pos - 1)
          setPrompt(inputHist[next] || "")
          return next
        })
        return
      }
      if (key.name === "down") {
        setHistPos((pos) => {
          if (pos === null) return null
          const next = pos + 1
          if (next >= inputHist.length) {
            setPrompt("")
            return null
          }
          setPrompt(inputHist[next] || "")
          return next
        })
        return
      }
    }
  })

  useEffect(() => {
    renderer.setBackgroundColor(T.clear)
  }, [renderer])

  const contentWidth = Math.max(40, dims.width - 2)
  // Product-tool instrument always on for agent sessions (talk → real tools).
  const showToolDeck = isAgentRepl || state.tools.length > 0 || busy
  const hasSeries =
    state.toolHitSeries.length > 0 || state.toolLatencySeries.length > 0
  const toolRows = showToolDeck
    ? estimateDeckRows(state.tools, {
        busy,
        width: contentWidth,
        hasSeries,
      }) + 1
    : 0
  // chrome: status(1) + seps(2) + prompt(1) + hints(1) + instrument
  const chatRows = Math.max(5, dims.height - 5 - toolRows)

  const placeholder = useMemo(() => {
    if (isAgentRepl) {
      return busy ? "steer (mid-turn feedback)…" : "message agent…"
    }
    if (isArena) return "objective or focus…"
    return "objective for one-shot…"
  }, [busy, isAgentRepl, isArena])

  const modeLabel = isAgentRepl ? "session" : isArena ? "arena" : "oneshot"
  const liveTools = state.tools.filter((t) => t.status === "running").length

  return (
    <box
      width="100%"
      height="100%"
      flexDirection="column"
      backgroundColor={T.clear}
      paddingLeft={1}
      paddingRight={1}
    >
      <StatusStrip
        state={state}
        profileLabel={profile.label}
        busy={busy}
      />
      <Sep width={contentWidth} />

      {showToolDeck ? (
        <>
          <ToolLiveDeck
            tools={state.tools}
            hitSeries={state.toolHitSeries}
            latencySeries={state.toolLatencySeries}
            width={contentWidth}
            busy={busy}
            showCards={state.tools.length > 0}
          />
          <Sep width={contentWidth} />
        </>
      ) : null}

      <ChatStream
        lines={state.chat}
        maxRows={chatRows}
        contentWidth={contentWidth}
        toolsInDeck={showToolDeck && state.tools.length > 0}
      />

      <Sep width={contentWidth} />

      <box
        flexDirection="row"
        height={1}
        flexShrink={0}
        backgroundColor={T.clear}
        alignItems="center"
      >
        <text>
          <span fg={busy ? T.warn : T.accent}>{busy ? "…" : "›"}</span>
          <span fg={T.dim}> </span>
        </text>
        <box flexGrow={1} backgroundColor={T.clear}>
          <input
            focused
            value={prompt}
            placeholder={placeholder}
            onInput={(v: string) => setPrompt(v)}
            onSubmit={() => submitPrompt(promptRef.current)}
            backgroundColor={T.clear}
            textColor={T.text}
            cursorColor={T.cursor}
            focusedBackgroundColor={T.clear}
            focusedTextColor={T.text}
          />
        </box>
      </box>

      <box
        flexDirection="row"
        height={1}
        flexShrink={0}
        justifyContent="space-between"
        backgroundColor={T.clear}
      >
        <text>
          <span fg={T.dim}>
            enter send · esc stop · /help · ctrl+↑↓ brain
            {isArena ? " · alt+r/t/s report" : ""}
          </span>
        </text>
        <text>
          <span fg={liveTools > 0 ? T.warn : T.dim}>
            {liveTools > 0 ? `run ${liveTools}  ` : ""}
            {modeLabel}  {dims.width}×{dims.height}
          </span>
        </text>
      </box>
    </box>
  )
}

async function main() {
  const renderer = await createCliRenderer({
    exitOnCtrlC: true,
    backgroundColor: "transparent",
    useMouse: false,
  })
  const root = createRoot(renderer)
  root.render(<ShellApp />)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
