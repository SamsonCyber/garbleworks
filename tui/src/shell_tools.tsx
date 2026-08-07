/**
 * Product tool instrument for the agent chat shell.
 *
 * Live graphs use real engines:
 *   - asciichart → multi-series line plots (latency ms, hit-rate %)
 *   - drawille   → dense braille canvas waveform
 *
 * Below the plots: compact call table + structured focus detail.
 */
import { plotToolTelemetry } from "./charts"
import {
  toolChartStats,
  type ToolCallLive,
} from "./shell_state"
import { T } from "./shell_theme"

const NAME_W = 16
const MS_W = 6
const ST_W = 5

function clip(s: string, n: number): string {
  const t = (s || "").replace(/\s+/g, " ").trim()
  if (t.length <= n) return t
  return t.slice(0, Math.max(1, n - 1)) + "…"
}

function padL(s: string, n: number): string {
  const t = s.slice(0, n)
  return t.length >= n ? t : " ".repeat(n - t.length) + t
}

function padR(s: string, n: number): string {
  const t = s.slice(0, n)
  return t.length >= n ? t : t + " ".repeat(n - t.length)
}

function fmtMs(ms: number | undefined, running: boolean): string {
  if (running) return padL("…", MS_W)
  if (ms == null || !Number.isFinite(ms)) return padL("—", MS_W)
  if (ms < 1000) return padL(`${Math.round(ms)}ms`, MS_W)
  return padL(`${(ms / 1000).toFixed(1)}s`, MS_W)
}

function statusWord(t: ToolCallLive): { word: string; fg: string } {
  if (t.status === "running") return { word: "run", fg: T.warn }
  if (t.status === "error") return { word: "err", fg: T.danger }
  if (t.leaked === true) return { word: "leak", fg: T.success }
  if (t.leaked === false) return { word: "miss", fg: T.muted }
  return { word: "ok", fg: T.dim }
}

function statusEdge(t: ToolCallLive): string {
  if (t.status === "running") return T.warn
  if (t.status === "error") return T.danger
  if (t.leaked === true) return T.success
  return T.dim
}

/** Pull operator-relevant keys out of tool args/result JSON. */
export function extractToolFields(
  raw: string,
  side: "in" | "out",
): { key: string; value: string }[] {
  const text = (raw || "").trim()
  if (!text) return []
  try {
    const obj = JSON.parse(text) as Record<string, unknown>
    if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
      return [{ key: side, value: clip(text, 120) }]
    }
    const prefer =
      side === "in"
        ? [
            "payload",
            "objective",
            "techniques",
            "summary",
            "success",
            "framing",
            "recipe",
            "seed",
            "text",
          ]
        : [
            "leaked",
            "channel",
            "ok",
            "ms",
            "reply_preview",
            "status",
            "error",
            "count",
            "remaining_fires",
            "fire_count",
            "success",
            "summary",
            "stop",
            "findings",
          ]
    const keys = [
      ...prefer.filter((k) => k in obj),
      ...Object.keys(obj).filter((k) => !prefer.includes(k)),
    ].slice(0, 6)

    return keys.map((k) => {
      const v = obj[k]
      let value: string
      if (v == null) value = "null"
      else if (typeof v === "string") value = v
      else if (typeof v === "number" || typeof v === "boolean") value = String(v)
      else value = JSON.stringify(v)
      return { key: k, value: clip(value, 100) }
    })
  } catch {
    return [{ key: side, value: clip(text, 120) }]
  }
}

/** Rows the deck will consume (for shell layout budgeting). */
export function estimateDeckRows(
  tools: ToolCallLive[],
  opts?: { busy?: boolean; width?: number; hasSeries?: boolean },
): number {
  const busy = Boolean(opts?.busy)
  const hasSeries = Boolean(opts?.hasSeries)
  // header(1) + plot block(~12) + sep + table header + up to 6 rows + focus(~4)
  if (!tools.length && !hasSeries) return busy ? 2 : 2
  const gantt = Math.min(tools.length, 6)
  const plot = hasSeries || tools.length > 0 ? 12 : 0
  let detail = 0
  if (tools.length) {
    const focus =
      tools.filter((t) => t.status === "running").slice(-1)[0] ||
      tools[tools.length - 1]
    detail =
      2 +
      Math.min(3, extractToolFields(focus.argsPreview, "in").length) +
      Math.min(3, extractToolFields(focus.resultPreview, "out").length)
  }
  return 2 + plot + 1 + (gantt ? gantt + 1 : 0) + detail
}

function Metric({
  label,
  value,
  valueFg = T.text,
}: {
  label: string
  value: string
  valueFg?: string
}) {
  return (
    <>
      <span fg={T.dim}>{label}</span>
      <span fg={T.dim}> </span>
      <span fg={valueFg}>{value}</span>
    </>
  )
}

function PlotBlock({
  title,
  lines,
  color,
  width,
}: {
  title: string
  lines: string[]
  color: string
  width: number
}) {
  if (!lines.length) return null
  return (
    <box flexDirection="column" flexShrink={0} backgroundColor={T.clear}>
      <text>
        <span fg={T.muted}>{title}</span>
      </text>
      {lines.map((line, i) => (
        <text key={`${title}-${i}`}>
          <span fg={color}>{clip(line, width)}</span>
        </text>
      ))}
    </box>
  )
}

function LiveGraphs({
  latencySeries,
  hitSeries,
  width,
}: {
  latencySeries: number[]
  hitSeries: number[]
  width: number
}) {
  if (!latencySeries.length && !hitSeries.length) return null

  const plots = plotToolTelemetry({
    latencyMs: latencySeries,
    hit01: hitSeries,
    width: Math.max(24, width - 2),
    height: 14,
  })

  return (
    <box flexDirection="column" flexShrink={0} backgroundColor={T.clear}>
      <PlotBlock
        title="latency (asciichart)"
        lines={plots.latencyLines}
        color={T.tool}
        width={width}
      />
      <PlotBlock
        title="hit rate % rolling (asciichart)"
        lines={plots.hitLines}
        color={T.success}
        width={width}
      />
      <PlotBlock
        title="waveform (drawille braille)"
        lines={plots.brailleLines}
        color={T.info}
        width={width}
      />
    </box>
  )
}

function CallTable({
  tools,
  width,
}: {
  tools: ToolCallLive[]
  width: number
}) {
  const rows = tools.slice(-6)
  if (!rows.length) return null
  void width

  return (
    <box flexDirection="column" flexShrink={0} backgroundColor={T.clear}>
      <text>
        <span fg={T.dim}>
          {"  "}
          {padR("#", 2)}{" "}
          {padR("tool", NAME_W)}{" "}
          {padL("time", MS_W)}{" "}
          {padR("st", ST_W)}
          {"  ch"}
        </span>
      </text>
      {rows.map((t, i) => {
        const seq = padL(String(t.seq || i + 1), 2)
        const name = padR(clip(t.tool, NAME_W), NAME_W)
        const st = statusWord(t)
        const edge = statusEdge(t)
        const ch = t.channel ? clip(t.channel, 10) : ""
        return (
          <text key={t.id}>
            <span fg={edge}>│</span>
            <span fg={T.dim}>{seq} </span>
            <span
              fg={
                t.status === "running"
                  ? T.warn
                  : t.leaked === true
                    ? T.success
                    : T.text
              }
            >
              {name}
            </span>
            <span fg={T.dim}> </span>
            <span fg={T.muted}>{fmtMs(t.ms, t.status === "running")}</span>
            <span fg={T.dim}> </span>
            <span fg={st.fg}>{padR(st.word, ST_W)}</span>
            {ch ? (
              <>
                <span fg={T.dim}>  </span>
                <span fg={T.info}>{ch}</span>
              </>
            ) : null}
          </text>
        )
      })}
    </box>
  )
}

function CallDetail({
  tools,
  width,
}: {
  tools: ToolCallLive[]
  width: number
}) {
  if (!tools.length) return null
  const running = tools.filter((t) => t.status === "running")
  const focus = running.length
    ? running[running.length - 1]
    : tools[tools.length - 1]
  const st = statusWord(focus)
  const edge = statusEdge(focus)
  const bodyW = Math.max(20, width - 6)
  const ins = extractToolFields(focus.argsPreview, "in").slice(0, 3)
  const outs = extractToolFields(focus.resultPreview, "out").slice(0, 3)

  return (
    <box flexDirection="column" flexShrink={0} backgroundColor={T.clear}>
      <text>
        <span fg={T.dim}>focus </span>
        <span fg={edge}>│</span>
        <span
          fg={
            focus.status === "running"
              ? T.warn
              : focus.leaked === true
                ? T.success
                : T.text
          }
        >
          {" "}
          {focus.tool}
        </span>
        <span fg={T.dim}>  </span>
        <span fg={st.fg}>{st.word}</span>
        <span fg={T.dim}>  </span>
        <span fg={T.muted}>
          {fmtMs(focus.ms, focus.status === "running").trim()}
        </span>
        {focus.channel ? (
          <>
            <span fg={T.dim}>  </span>
            <span fg={T.info}>ch={focus.channel}</span>
          </>
        ) : null}
      </text>
      {ins.map((f) => (
        <text key={`in-${f.key}`}>
          <span fg={T.dim}>      in   </span>
          <span fg={T.muted}>{padR(f.key, 12)}</span>
          <span fg={T.dim}>  </span>
          <span fg={T.text}>{clip(f.value, bodyW - 16)}</span>
        </text>
      ))}
      {outs.map((f) => {
        const hot =
          f.key === "leaked" && f.value === "true"
            ? T.success
            : f.key === "leaked" && f.value === "false"
              ? T.muted
              : f.key === "error" || (f.key === "ok" && f.value === "false")
                ? T.danger
                : T.muted
        return (
          <text key={`out-${f.key}`}>
            <span fg={T.dim}>      out  </span>
            <span fg={T.muted}>{padR(f.key, 12)}</span>
            <span fg={T.dim}>  </span>
            <span fg={hot}>{clip(f.value, bodyW - 16)}</span>
          </text>
        )
      })}
      {focus.status === "running" && outs.length === 0 ? (
        <text>
          <span fg={T.dim}>      out  </span>
          <span fg={T.warn}>pending</span>
        </text>
      ) : null}
    </box>
  )
}

function EmptyTrace({ busy }: { busy?: boolean }) {
  return (
    <box flexDirection="column" flexShrink={0} backgroundColor={T.clear}>
      <text>
        <span fg={T.muted}>trace</span>
        <span fg={T.dim}>  </span>
        {busy ? (
          <span fg={T.warn}>session busy · waiting on first product call</span>
        ) : (
          <span fg={T.dim}>
            no calls yet · engines idle (asciichart + drawille)
          </span>
        )}
      </text>
    </box>
  )
}

/**
 * Full instrument: engine plots + call table + focus detail.
 */
export function ToolLiveDeck({
  tools,
  hitSeries,
  latencySeries = [],
  width,
  busy,
  showCards = true,
}: {
  tools: ToolCallLive[]
  hitSeries: number[]
  latencySeries?: number[]
  width: number
  busy?: boolean
  showCards?: boolean
}) {
  const w = Math.max(40, width)
  void showCards

  const stats = toolChartStats(tools, hitSeries)
  const lat = latencySeries.length
    ? latencySeries
    : tools
        .filter((t) => t.ms != null)
        .map((t) => t.ms as number)

  if (!tools.length && !lat.length && !hitSeries.length) {
    return <EmptyTrace busy={busy} />
  }

  return (
    <box flexDirection="column" flexShrink={0} backgroundColor={T.clear}>
      <text>
        <span fg={T.muted}>trace</span>
        <span fg={T.dim}>  </span>
        <Metric label="n" value={String(stats.total)} />
        <span fg={T.dim}>  </span>
        <Metric
          label="run"
          value={String(stats.running)}
          valueFg={stats.running > 0 ? T.warn : T.dim}
        />
        <span fg={T.dim}>  </span>
        <Metric label="ok" value={String(stats.ok)} valueFg={T.success} />
        <span fg={T.dim}>  </span>
        <Metric
          label="err"
          value={String(stats.err)}
          valueFg={stats.err > 0 ? T.danger : T.dim}
        />
        {stats.leaks > 0 ? (
          <>
            <span fg={T.dim}>  </span>
            <Metric
              label="leak"
              value={String(stats.leaks)}
              valueFg={T.success}
            />
          </>
        ) : null}
        <span fg={T.dim}>  </span>
        <span fg={T.dim}>asciichart+drawille</span>
      </text>

      <LiveGraphs
        latencySeries={lat}
        hitSeries={hitSeries}
        width={w}
      />

      {tools.length ? (
        <>
          <text>
            <span fg={T.dim}>{"─".repeat(Math.min(w, 96))}</span>
          </text>
          <CallTable tools={tools} width={w} />
          <text>
            <span fg={T.dim}>{"─".repeat(Math.min(w, 96))}</span>
          </text>
          <CallDetail tools={tools} width={w} />
        </>
      ) : null}
    </box>
  )
}

/** Kept for API compat / tests that import chart helpers. */
export function formatHitTape(series: number[], width: number): string {
  const w = Math.max(4, width)
  if (!series.length) return "·".repeat(w)
  const slice = series.slice(-w)
  const pad = w - slice.length
  return "·".repeat(pad) + slice.map((v) => (v > 0 ? "▮" : "▯")).join("")
}

export function latencyBar(
  ms: number | undefined,
  maxMs: number,
  width: number,
  running: boolean,
): string {
  const w = Math.max(4, width)
  if (running) {
    const mid = Math.max(1, Math.floor(w * 0.35))
    return "▓".repeat(mid) + "░".repeat(w - mid)
  }
  if (ms == null || !Number.isFinite(ms) || maxMs <= 0) return "░".repeat(w)
  const r = Math.max(0, Math.min(1, ms / maxMs))
  const filled = Math.max(ms > 0 ? 1 : 0, Math.round(r * w))
  return "█".repeat(filled) + "░".repeat(Math.max(0, w - filled))
}
