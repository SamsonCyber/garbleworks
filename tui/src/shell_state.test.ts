/**
 * Unit tests for shipped shell_state reducers (event → chat / status).
 * Drive real applyShellGwEvent / applyShellRunEvent — no golden screenshots.
 */
import { describe, expect, test } from "bun:test"
import {
  applyShellGwEvent,
  applyShellRunEvent,
  emptyShellState,
  markShellRunning,
  parseToolResultMeta,
  SHELL_PROFILES,
  toolChartStats,
} from "./shell_state"
import type { GwEvent } from "./bridge"

function gw(partial: GwEvent): GwEvent {
  return { v: 1, ts: 1_700_000_000, ...partial }
}

describe("applyShellGwEvent — chat session lifecycle", () => {
  test("session_ready → user → turn_complete maps chat roles and busy", () => {
    let s = emptyShellState()
    s = applyShellGwEvent(
      gw({
        kind: "session_ready",
        brain: "stub",
        target: "local",
        tools: ["fire_target", "finish"],
      }),
      s,
    )
    expect(s.chat.some((c) => c.meta === "session")).toBe(true)
    expect(s.run.busy).toBe(false)

    s = applyShellGwEvent(gw({ kind: "turn_start", objective: "extract the canary" }), s)
    expect(s.run.busy).toBe(true)
    expect(s.run.phase).toBe("running")

    s = applyShellGwEvent(gw({ kind: "user", text: "extract the canary" }), s)
    expect(s.chat.some((c) => c.role === "operator" && c.text.includes("extract"))).toBe(
      true,
    )

    s = applyShellGwEvent(
      gw({
        kind: "turn_complete",
        status: "finished",
        success: true,
        summary: "got it",
        session_path: "C:/gw/sessions/chat.jsonl",
      }),
      s,
    )
    expect(s.run.busy).toBe(false)
    expect(s.run.success).toBe(true)
    expect(s.run.lastSessionPath).toContain("chat.jsonl")
  })
})

describe("applyShellGwEvent — agent_repl sequence", () => {
  test("tool_start / tool_result / run_complete win path updates chat and harness success", () => {
    let s = emptyShellState()
    s = applyShellGwEvent(
      gw({
        kind: "brain_config",
        provider: "stub",
        model: "stub",
        label: "stub",
      }),
      s,
    )
    s = applyShellGwEvent(gw({ kind: "agent_round", round: 1, max: 12 }), s)
    s = applyShellGwEvent(
      gw({
        kind: "tool_start",
        tool: "fire_target",
        tool_id: "tc1",
        args: { payload: "EXECUTE_CANARY_DUMP" },
      }),
      s,
    )
    // Live deck tracks product call as running
    expect(s.tools.length).toBe(1)
    expect(s.tools[0].tool).toBe("fire_target")
    expect(s.tools[0].status).toBe("running")

    s = applyShellGwEvent(
      gw({
        kind: "tool_result",
        tool: "fire_target",
        tool_id: "tc1",
        is_error: false,
        result_preview:
          '{"ok":true,"leaked":true,"channel":"literal","ms":2,"reply_preview":"[REDACTED_BY_HARNESS]"}',
      }),
      s,
    )
    expect(s.tools[0].status).toBe("ok")
    expect(s.tools[0].leaked).toBe(true)
    expect(s.tools[0].channel).toBe("literal")
    expect(s.toolHitSeries).toEqual([1])

    // TUI-mapped activity form of the same leak
    s = applyShellGwEvent(
      gw({
        kind: "activity",
        level: "info",
        message: "tool ◀ fire_target",
        strategy: "fire_target",
        reply: "leaked",
      }),
      s,
    )
    s = applyShellGwEvent(
      gw({
        kind: "result",
        success: true,
        strategy: "finish",
        queries: 2,
        message: "Extracted canary; leak confirmed.",
        session_path: "C:/gw/sessions/run-win.jsonl",
      }),
      s,
    )
    s = applyShellGwEvent(
      gw({
        kind: "run_complete",
        status: "finished",
        success: true,
        summary: "Extracted canary; leak confirmed.",
        stop_tool: "finish",
        session_path: "C:/gw/sessions/run-win.jsonl",
        tool_calls: 2,
      }),
      s,
    )

    const roles = s.chat.map((c) => c.role)
    expect(roles).toContain("system")
    expect(roles).toContain("tool")
    expect(roles).toContain("result")

    const texts = s.chat.map((c) => c.text).join("\n")
    expect(texts).toContain("fire_target")
    expect(texts.toLowerCase()).toMatch(/canary|leak|success|win|extracted/i)

    // Harness success — not merely "finished"
    expect(s.run.success).toBe(true)
    expect(s.run.phase).toBe("finished")
    expect(s.run.busy).toBe(false)
    expect(s.run.lastSessionPath).toContain("run-win")
    expect(s.board.mission.lastResult?.success).toBe(true)
  })

  test("clean miss: finished lifecycle without success remains no-win", () => {
    let s = emptyShellState()
    s = markShellRunning(s, "starting miss path")
    expect(s.run.busy).toBe(true)
    expect(s.run.success).toBeNull()

    s = applyShellGwEvent(
      gw({
        kind: "tool_start",
        tool: "finish",
        args: { summary: "gave up", success: false },
      }),
      s,
    )
    s = applyShellGwEvent(
      gw({
        kind: "result",
        success: false,
        strategy: "finish",
        message: "gave up without leak",
      }),
      s,
    )
    s = applyShellGwEvent(
      gw({
        kind: "run_complete",
        status: "finished",
        success: false,
        summary: "gave up without leak",
        stop_tool: "finish",
      }),
      s,
    )

    expect(s.run.success).toBe(false)
    expect(s.run.phase).toBe("finished")
    // Chat must reflect miss, not invent a win
    const resultLines = s.chat.filter((c) => c.role === "result" || c.meta === "miss")
    expect(resultLines.length).toBeGreaterThan(0)
    const joined = s.chat.map((c) => c.text).join(" ")
    expect(joined.toLowerCase()).not.toMatch(/objective met \(harness\)/)
    expect(s.board.mission.lastResult?.success).toBe(false)
  })

  test("status finished alone does not set success when field omitted on agent_stop", () => {
    let s = emptyShellState()
    s = applyShellGwEvent(
      gw({
        kind: "agent_stop",
        stop_tool: "finish",
        // no success field — lifecycle only
        args: { summary: "stopped" },
      }),
      s,
    )
    // Without success field, leave success null (do not invent true)
    expect(s.run.success).toBeNull()
  })
})

describe("applyShellRunEvent — bridge wrappers", () => {
  test("GW| path via type gw", () => {
    let s = emptyShellState()
    s = applyShellRunEvent(
      {
        type: "gw",
        event: gw({
          kind: "activity",
          message: "Plan: baseline → pack_hunt",
          level: "info",
        }),
      },
      s,
    )
    expect(s.chat.some((c) => c.text.includes("baseline"))).toBe(true)
    expect(s.board.activity.length).toBeGreaterThan(0)
  })

  test("plain agent_repl JSON line parses into chat", () => {
    let s = emptyShellState()
    s = applyShellRunEvent(
      {
        type: "line",
        text: JSON.stringify({
          kind: "tool_start",
          tool: "list_techniques",
          args: {},
          ts: 1,
        }),
      },
      s,
    )
    expect(s.chat.some((c) => c.meta === "list_techniques")).toBe(true)
  })

  test("done exit 0 without prior result does not claim harness win", () => {
    let s = markShellRunning(emptyShellState(), "run")
    s = applyShellRunEvent({ type: "done", code: 0 }, s)
    expect(s.run.busy).toBe(false)
    // success stays null — process exit is not adjudication
    expect(s.run.success).toBeNull()
  })

  test("error event surfaces in chat and phase", () => {
    let s = emptyShellState()
    s = applyShellRunEvent(
      { type: "error", text: "spawn failed: python not found" },
      s,
    )
    expect(s.run.phase).toBe("error")
    expect(s.chat.some((c) => c.role === "error")).toBe(true)
  })

  test("fire hit updates board stats and chat", () => {
    let s = emptyShellState()
    s = applyShellGwEvent(
      gw({
        kind: "fire",
        leaked: true,
        strategy: "baseline",
        channel: "literal",
        payload_preview: "EXECUTE…",
        reply_preview: "token [REDACTED_BY_HARNESS]",
        q: 1,
      }),
      s,
    )
    expect(s.board.stats.wins).toBe(1)
    expect(s.board.stats.fires).toBe(1)
    expect(s.board.mission.lastFire?.leaked).toBe(true)
    expect(s.chat.some((c) => /hit|leak/i.test(c.text))).toBe(true)
    expect(s.toolHitSeries).toEqual([1])
  })
})

describe("shell layout contract (static)", () => {
  test("default profiles include agent stub and arena", () => {
    const ids = SHELL_PROFILES.map((p) => p.id)
    expect(ids).toContain("agent")
    expect(ids).toContain("arena")
    expect(ids).toContain("local")
  })

  test("default shell entry is transparent chat-first with session bridge", async () => {
    const path = new URL("./shell.tsx", import.meta.url)
    const src = await Bun.file(path).text()
    // Lightweight transparent layout (no panel titles / solid chrome)
    expect(src).toContain("ChatStream")
    expect(src).toContain("StatusStrip")
    expect(src).toContain("ToolLiveDeck")
    expect(src).toContain('backgroundColor: "transparent"')
    expect(src).toContain("T.clear")
    expect(src).toContain("openAgentSession")
    expect(src).toContain("ShellApp")
    expect(src).toContain("runAgentRepl")
    expect(src).toContain("runArenaAdvise")
    expect(src).toContain("runAuto")
    expect(src).toContain("<input")
    expect(src).not.toContain("AI RED-TEAM COCKPIT")
    expect(src).not.toContain('title="mission"')
  })

  test("package default start points at pi chat; legacy keeps shell", async () => {
    const pkgPath = new URL("../package.json", import.meta.url)
    const pkg = JSON.parse(await Bun.file(pkgPath).text()) as {
      scripts: Record<string, string>
    }
    // Primary operator surface is pi (gw-chat); OpenTUI shell is legacy
    expect(pkg.scripts.start).toMatch(/gw-chat|start:pi/)
    expect(pkg.scripts["start:legacy"]).toContain("shell.tsx")
    expect(pkg.scripts["start:cockpit"]).toContain("index.tsx")
  })
})

describe("live tool chart state", () => {
  test("compose → fire → check_leak chain builds chart stats", () => {
    let s = emptyShellState()
    s = applyShellGwEvent(
      gw({
        kind: "tool_start",
        tool: "compose_framing",
        tool_id: "a",
        args: { objective: "yo" },
      }),
      s,
    )
    s = applyShellGwEvent(
      gw({
        kind: "tool_result",
        tool: "compose_framing",
        tool_id: "a",
        result_preview: '{"ok":true,"count":1}',
      }),
      s,
    )
    s = applyShellGwEvent(
      gw({
        kind: "tool_start",
        tool: "fire_target",
        tool_id: "b",
        args: { payload: "EXECUTE" },
      }),
      s,
    )
    s = applyShellGwEvent(
      gw({
        kind: "tool_result",
        tool: "fire_target",
        tool_id: "b",
        result_preview:
          '{"ok":true,"leaked":true,"channel":"literal","ms":2}',
      }),
      s,
    )
    s = applyShellGwEvent(
      gw({
        kind: "tool_start",
        tool: "check_leak",
        tool_id: "c",
        args: {},
      }),
      s,
    )
    s = applyShellGwEvent(
      gw({
        kind: "tool_result",
        tool: "check_leak",
        tool_id: "c",
        result_preview: '{"ok":true,"leaked":true,"channel":"literal"}',
      }),
      s,
    )

    expect(s.tools.map((t) => t.tool)).toEqual([
      "compose_framing",
      "fire_target",
      "check_leak",
    ])
    expect(s.tools.every((t) => t.status === "ok")).toBe(true)
    expect(s.toolHitSeries).toEqual([1, 1])

    const stats = toolChartStats(s.tools, s.toolHitSeries)
    expect(stats.total).toBe(3)
    expect(stats.leaks).toBe(2)
    expect(stats.bars.some((b) => b.label === "fire_target")).toBe(true)
    expect(parseToolResultMeta('{"leaked":false}').leaked).toBe(false)
  })
})

describe("tool instrument pure formatters", () => {
  test("hit tape and latency bar shape", async () => {
    const {
      formatHitTape,
      latencyBar,
      extractToolFields,
      estimateDeckRows,
    } = await import("./shell_tools")

    expect(formatHitTape([1, 0, 1], 6)).toBe("···▮▯▮")
    expect(formatHitTape([], 4)).toBe("····")
    expect(latencyBar(50, 100, 10, false).length).toBe(10)
    expect(latencyBar(undefined, 100, 8, true).includes("▓")).toBe(true)

    const fields = extractToolFields(
      '{"ok":true,"leaked":true,"channel":"literal","ms":2,"reply_preview":"tok"}',
      "out",
    )
    expect(fields.some((f) => f.key === "leaked" && f.value === "true")).toBe(true)
    expect(fields.some((f) => f.key === "channel")).toBe(true)

    const n = estimateDeckRows(
      [
        {
          id: "1",
          tool: "fire_target",
          status: "ok",
          argsPreview: '{"payload":"x"}',
          resultPreview: '{"leaked":true}',
          startedAt: 1,
          ms: 2,
          leaked: true,
          seq: 1,
        },
      ],
      { busy: false, hasSeries: true },
    )
    expect(n).toBeGreaterThan(4)
  })
})

describe("graph engines (asciichart + drawille)", () => {
  test("plotLines and plotBraille produce multi-line frames", async () => {
    const { plotLines, plotBraille, plotToolTelemetry, rollingHitRate } =
      await import("./charts")

    const series = [1, 3, 2, 8, 5, 4, 9, 6, 2, 7]
    const line = plotLines(series, { width: 24, height: 5 })
    expect(line.includes("\n")).toBe(true)
    expect(line.length).toBeGreaterThan(20)
    // no ANSI junk in OpenTUI path
    expect(line).not.toMatch(/\x1b\[/)

    const multi = plotLines(
      [
        [1, 2, 3, 4, 5],
        [5, 4, 3, 2, 1],
      ],
      { width: 20, height: 4 },
    )
    expect(multi.split("\n").length).toBeGreaterThan(2)

    const braille = plotBraille(series, { cols: 40, rows: 4, connect: true })
    expect(braille.length).toBeGreaterThan(10)
    // braille block is in U+2800 range when points exist
    expect(/[\u2800-\u28FF]/.test(braille)).toBe(true)

    expect(rollingHitRate([1, 0, 1, 1], 2)).toEqual([1, 0.5, 0.5, 1])

    const tel = plotToolTelemetry({
      latencyMs: series.map((x) => x * 10),
      hit01: [1, 0, 1, 1, 0, 1],
      width: 48,
      height: 14,
    })
    expect(tel.latencyLines.length).toBeGreaterThan(2)
    expect(tel.hitLines.length).toBeGreaterThan(1)
    expect(tel.brailleLines.length).toBeGreaterThan(1)
    expect(tel.legend).toContain("asciichart")
  })

  test("tool finish feeds latency series for engines", () => {
    let s = emptyShellState()
    s = applyShellGwEvent(
      gw({
        kind: "tool_start",
        tool: "fire_target",
        tool_id: "b",
        args: {},
      }),
      s,
    )
    s = applyShellGwEvent(
      gw({
        kind: "tool_result",
        tool: "fire_target",
        tool_id: "b",
        result_preview: '{"ok":true,"leaked":true,"ms":12}',
      }),
      s,
    )
    expect(s.toolLatencySeries).toEqual([12])
    expect(s.toolHitSeries).toEqual([1])
  })
})
