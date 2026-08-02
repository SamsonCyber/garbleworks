/**
 * Visual system for the Garbleworks operator TUI — "AI red-team cockpit".
 *
 * Design language:
 *   - Deep tactical-black hull, phosphor cyan for data, amber for the operator's
 *     focus/attention, green for hits, red for hard stops, violet for strategy.
 *   - Instruments are labelled cells (chips / gauges / switches), not loose text.
 *   - One thing glows at a time so the eye always knows where to look.
 */
import { useEffect, useState } from "react"
import type { FireStats, MissionState, ProgressState } from "./bridge"

export const C = {
  // hull
  bg: "#070910",
  bgAlt: "#0a0d16",
  panel: "#0d111b",
  panel2: "#141b28",
  panel3: "#1d2739",
  panelHi: "#111a2c",
  // structure
  line: "#243350",
  lineDim: "#18202f",
  lineFocus: "#f2a838",
  // accents
  glow: "#f4a72c", // amber — operator attention / focus / warn
  glowDim: "#7c561a",
  cyan: "#33d6c7", // data / target / payload
  cyanDim: "#1a6b64",
  green: "#41d98a", // hit / success
  greenDim: "#1a6f4a",
  red: "#ff5c6a", // tripwire / hard stop
  redDim: "#7e2b34",
  yellow: "#ecc14e", // caution / refused
  purple: "#b18cff", // strategy / technique
  blue: "#4f9dff",
  // ink
  text: "#d6deec",
  muted: "#828da3",
  dim: "#46536b",
  white: "#f2f6fc",
  black: "#05070c",
}

const ICON = {
  target: "◎",
  mode: "⚙",
  job: "▤",
  budget: "⛽",
  strat: "✦",
  out: "◈",
  hit: "◆",
  live: "▸",
  wait: "◇",
  ok: "●",
  todo: "○",
  fail: "✕",
  skip: "⊘",
  crosshair: "⌖",
  bolt: "⚡",
}

const BLOCKS = " ▁▂▃▄▅▆▇█"
const BAR_FULL = "█"
const BAR_HALF = "▓"
const BAR_EMPTY = "░"

/** Sparkline from a 0..1 series. */
export function sparkline(values: number[], width = 16): string {
  if (!values.length) return BAR_EMPTY.repeat(width)
  const slice = values.slice(-width)
  while (slice.length < width) slice.unshift(0)
  const max = Math.max(...slice, 1e-9)
  return slice
    .map((v) => {
      const t = Math.max(0, Math.min(1, v / max))
      const i = Math.round(t * (BLOCKS.length - 1))
      return BLOCKS[i]
    })
    .join("")
}

/** Horizontal bar 0..1 with a soft leading edge. */
export function meter(ratio: number, width = 20): string {
  const r = Math.max(0, Math.min(1, ratio))
  const filled = Math.round(r * width)
  const lead = filled < width && r > 0 ? 1 : 0
  return (
    BAR_FULL.repeat(Math.max(0, filled - lead)) +
    (lead ? BAR_HALF : "") +
    BAR_EMPTY.repeat(Math.max(0, width - filled))
  )
}

export function MeterBar({
  label,
  value,
  max = 1,
  width = 18,
  color = C.cyan,
  emptyColor = C.dim,
  showPct = true,
}: {
  label: string
  value: number
  max?: number
  width?: number
  color?: string
  emptyColor?: string
  showPct?: boolean
}) {
  const r = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0
  const filled = Math.round(r * width)
  const empty = Math.max(0, width - filled)
  const pct = Math.round(r * 100)
  return (
    <box flexDirection="row" gap={1}>
      <text>
        <span fg={C.muted}>{label.padEnd(8).slice(0, 8)}</span>
      </text>
      <text>
        <span fg={color}>{BAR_FULL.repeat(filled)}</span>
        <span fg={emptyColor}>{BAR_EMPTY.repeat(empty)}</span>
      </text>
      {showPct && (
        <text>
          <span fg={C.muted}> {String(pct).padStart(3)}%</span>
        </text>
      )}
    </box>
  )
}

function centerCell(s: string, w: number): string {
  if (s.length >= w) return s.slice(0, w)
  const left = Math.floor((w - s.length) / 2)
  return " ".repeat(left) + s + " ".repeat(w - s.length - left)
}

/**
 * Vertical bar graph. Bars are drawn column-by-column with block glyphs plus a
 * fractional top cap (so small values still register), each in its own color,
 * with a value/label row beneath the axis. Empty state prompts for data.
 */
export function BarChart({
  items,
  title = "chart",
  width = 30,
  height = 4,
}: {
  items: { label: string; value: number; color: string }[]
  title?: string
  width?: number
  height?: number
}) {
  const inner = Math.max(10, width - 4)
  const n = Math.max(1, items.length)
  const gap = 1
  const barW = Math.max(2, Math.floor((inner - gap * (n - 1)) / n))
  const max = Math.max(1, ...items.map((it) => it.value))
  const H = Math.max(3, height)
  const total = items.reduce((s, it) => s + it.value, 0)

  // Each bar's glyph column, top row → bottom row.
  const cols = items.map((it) => {
    const filled = (it.value / max) * H
    const col: string[] = []
    for (let row = H; row >= 1; row--) {
      if (filled >= row) col.push(BAR_FULL)
      else if (filled > row - 1)
        col.push(BLOCKS[Math.max(1, Math.round((filled - (row - 1)) * 8))])
      else col.push(" ")
    }
    return col
  })

  return (
    <box
      flexDirection="column"
      border
      borderStyle="rounded"
      borderColor={C.line}
      backgroundColor={C.panel}
      paddingLeft={1}
      paddingRight={1}
      title={` ${title} `}
      titleColor={C.muted}
      bottomTitle={total ? ` n=${total} ` : undefined}
      bottomTitleAlignment="right"
      flexShrink={0}
    >
      {total === 0 ? (
        <text>
          <span fg={C.dim}>No data yet — report r/t/s to chart it.</span>
        </text>
      ) : (
        <>
          {Array.from({ length: H }, (_, row) => (
            <text key={row}>
              {items.map((it, bi) => (
                <span key={bi} fg={it.color}>
                  {cols[bi][row].repeat(barW)}
                  {bi < items.length - 1 ? " ".repeat(gap) : ""}
                </span>
              ))}
            </text>
          ))}
          <text>
            {items.map((it, bi) => (
              <span key={bi} fg={it.color}>
                <strong>{centerCell(`${it.label} ${it.value}`, barW)}</strong>
                {bi < items.length - 1 ? " ".repeat(gap) : ""}
              </span>
            ))}
          </text>
        </>
      )}
    </box>
  )
}

export function SparklineRow({
  label,
  values,
  width = 20,
  color = C.cyan,
}: {
  label: string
  values: number[]
  width?: number
  color?: string
}) {
  const s = sparkline(values, width)
  const last = values.length ? values[values.length - 1] : 0
  return (
    <box flexDirection="row" gap={1}>
      <text>
        <span fg={C.muted}>{label.padEnd(8).slice(0, 8)}</span>
      </text>
      <text>
        <span fg={color}>{s}</span>
      </text>
      <text>
        <span fg={C.dim}> {last.toFixed(2)}</span>
      </text>
    </box>
  )
}

export function MiniBars({
  items,
  height = 4,
  color = C.glow,
}: {
  items: { label: string; value: number }[]
  height?: number
  color?: string
}) {
  if (!items.length) {
    return (
      <text>
        <span fg={C.dim}>no data</span>
      </text>
    )
  }
  const max = Math.max(...items.map((i) => i.value), 1)
  const rows: string[] = []
  for (let h = height; h >= 1; h--) {
    let row = ""
    for (const it of items) {
      const level = Math.round((it.value / max) * height)
      row += level >= h ? "█" : " "
      row += " "
    }
    rows.push(row.trimEnd())
  }
  const labels = items.map((i) => i.label.slice(0, 1)).join(" ")
  return (
    <box flexDirection="column">
      {rows.map((r, i) => (
        <text key={i}>
          <span fg={color}>{r || " "}</span>
        </text>
      ))}
      <text>
        <span fg={C.dim}>{labels}</span>
      </text>
    </box>
  )
}

/** Parse metrics from Python log lines (fallback when no GW fire events). */
export function parseMetrics(lines: string[]): {
  lcb: number[]
  asr: number[]
  wins: number
  misses: number
  errors: number
  exits: number[]
} {
  const lcb: number[] = []
  const asr: number[] = []
  const exits: number[] = []
  let wins = 0
  let misses = 0
  let errors = 0
  for (const line of lines) {
    const lcbM = line.match(/LCB[=:]?\s*([0-9.]+)/i) || line.match(/"asr_lcb":\s*([0-9.]+)/)
    if (lcbM) lcb.push(parseFloat(lcbM[1]))
    const asrM = line.match(/\bASR[=:]?\s*([0-9.]+)/i) || line.match(/"asr":\s*([0-9.]+)/)
    if (asrM) asr.push(parseFloat(asrM[1]))
    if (/\bWIN\b|outcome.: .leak|"success": true/i.test(line)) wins++
    if (/\bmiss\b|no_leak/i.test(line)) misses++
    if (/error|tool_error|FAIL/i.test(line)) errors++
    const ex = line.match(/exit\s+(\d+)/i)
    if (ex) exits.push(parseInt(ex[1], 10))
  }
  return { lcb, asr, wins, misses, errors, exits }
}

export function mergeStats(gw: FireStats, log: ReturnType<typeof parseMetrics>): FireStats {
  if (gw.fires > 0 || gw.wins + gw.misses > 0) {
    return {
      ...gw,
      asrSeries: gw.asrSeries.length ? gw.asrSeries : log.asr,
      lcbSeries: gw.lcbSeries.length ? gw.lcbSeries : log.lcb,
      errors: Math.max(gw.errors, log.errors),
    }
  }
  return {
    wins: log.wins,
    misses: log.misses,
    errors: log.errors,
    asrSeries: log.asr,
    lcbSeries: log.lcb,
    fires: log.wins + log.misses,
  }
}

export function Spinner({ active, label }: { active: boolean; label?: string }) {
  const frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
  const [i, setI] = useState(0)
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => setI((x) => (x + 1) % frames.length), 80)
    return () => clearInterval(t)
  }, [active])
  if (!active) {
    return (
      <text>
        <span fg={C.greenDim}>◉ </span>
        <span fg={C.muted}>{label || "idle"}</span>
      </text>
    )
  }
  return (
    <text>
      <span fg={C.glow}>
        <strong>{frames[i]} </strong>
      </span>
      <span fg={C.glow}>{label || "running"}</span>
    </text>
  )
}

/** Instrument cell: filled label + colored value. The cockpit's readout unit. */
export function Chip({
  label,
  value,
  color = C.cyan,
  icon,
  strong = true,
  bg = C.panel2,
}: {
  label: string
  value: string
  color?: string
  icon?: string
  strong?: boolean
  bg?: string
}) {
  return (
    <box
      backgroundColor={bg}
      paddingLeft={1}
      paddingRight={1}
      marginRight={1}
      flexDirection="row"
      flexShrink={0}
    >
      <text>
        {icon ? <span fg={color}>{icon} </span> : null}
        <span fg={C.dim}>{label} </span>
        <span fg={color}>{strong ? <strong>{value}</strong> : value}</span>
      </text>
    </box>
  )
}

export function StatChip({
  label,
  value,
  color = C.cyan,
}: {
  label: string
  value: string
  color?: string
}) {
  return <Chip label={label} value={value} color={color} />
}

/** Inverse pill for alerts / banners. */
export function AlertPill({
  text,
  tone = "info",
}: {
  text: string
  tone?: "win" | "alert" | "info" | "hot"
}) {
  const map: Record<string, [string, string]> = {
    win: [C.black, C.green],
    alert: [C.black, C.red],
    hot: [C.black, C.glow],
    info: [C.white, C.panel3],
  }
  const [fgc, bgc] = map[tone] || map.info
  return (
    <box backgroundColor={bgc} paddingLeft={1} paddingRight={1} flexShrink={0}>
      <text>
        <span fg={fgc}>
          <strong>{text}</strong>
        </span>
      </text>
    </box>
  )
}

/** Soft badge without border noise. */
export function Badge({
  label,
  color = C.muted,
  bg = C.panel2,
}: {
  label: string
  color?: string
  bg?: string
}) {
  return (
    <box backgroundColor={bg} paddingLeft={1} paddingRight={1}>
      <text>
        <span fg={color}>{label}</span>
      </text>
    </box>
  )
}

/** Panel chrome: consistent border + title focus treatment. */
export function Panel({
  title,
  focused = false,
  focusColor = C.glow,
  children,
  borderStyle = "rounded",
  titleColor,
  bottomTitle,
  flexGrow,
  flexShrink,
  width,
  minWidth,
  minHeight,
  maxHeight,
  marginTop,
  marginBottom,
  marginRight,
  marginLeft,
  bg = C.panel,
}: {
  title: string
  focused?: boolean
  focusColor?: string
  children?: unknown
  borderStyle?: "single" | "double" | "rounded" | "heavy"
  titleColor?: string
  bottomTitle?: string
  flexGrow?: number
  flexShrink?: number
  width?: number | string
  minWidth?: number
  minHeight?: number
  maxHeight?: number
  marginTop?: number
  marginBottom?: number
  marginRight?: number
  marginLeft?: number
  bg?: string
}) {
  return (
    <box
      flexDirection="column"
      border
      borderStyle={focused ? "heavy" : borderStyle}
      borderColor={focused ? focusColor : C.line}
      backgroundColor={bg}
      paddingLeft={1}
      paddingRight={1}
      title={` ${title} `}
      titleColor={focused ? focusColor : (titleColor ?? C.muted)}
      bottomTitle={bottomTitle ? ` ${bottomTitle} ` : undefined}
      bottomTitleAlignment="right"
      flexGrow={flexGrow}
      flexShrink={flexShrink}
      width={width as never}
      minWidth={minWidth}
      minHeight={minHeight}
      maxHeight={maxHeight}
      marginTop={marginTop}
      marginBottom={marginBottom}
      marginRight={marginRight}
      marginLeft={marginLeft}
    >
      {children as never}
    </box>
  )
}

export function Divider({ label }: { label?: string }) {
  const line = "─".repeat(10)
  if (!label) {
    return (
      <text>
        <span fg={C.dim}>{line.repeat(3)}</span>
      </text>
    )
  }
  return (
    <text>
      <span fg={C.dim}>{line}</span>
      <span fg={C.muted}> {label} </span>
      <span fg={C.dim}>{line}</span>
    </text>
  )
}

/** Compact key=value row. */
export function Kv({
  k,
  v,
  color = C.cyan,
  dim = false,
}: {
  k: string
  v: string
  color?: string
  dim?: boolean
}) {
  return (
    <text>
      <span fg={C.dim}>{k} </span>
      <span fg={dim ? C.muted : color}>{v || "—"}</span>
    </text>
  )
}

/** Footer keybind fragment: a key-cap then its label. */
export function KeyHint({
  keys,
  label,
  hot = false,
}: {
  keys: string
  label: string
  hot?: boolean
}) {
  return (
    <box flexDirection="row" marginRight={1} flexShrink={0}>
      <text>
        <span fg={hot ? C.black : C.glow} bg={hot ? C.glow : C.panel3}>
          <strong> {keys} </strong>
        </span>
        <span fg={C.muted}> {label}</span>
      </text>
    </box>
  )
}

/**
 * Clickable action button. Mouse is enabled on the renderer, so onMouseDown
 * fires on click; it brightens on hover for feedback. Used to clear the BRIEF.
 */
export function ClearButton({
  onClear,
  label = "CLEAR",
}: {
  onClear: () => void
  label?: string
}) {
  const [hover, setHover] = useState(false)
  return (
    <box
      onMouseDown={() => onClear()}
      onMouseOver={() => setHover(true)}
      onMouseOut={() => setHover(false)}
      backgroundColor={hover ? C.red : C.redDim}
      marginLeft={1}
      paddingLeft={1}
      paddingRight={1}
      flexShrink={0}
      justifyContent="center"
      alignItems="center"
    >
      <text>
        <span fg={C.white}>
          <strong>{label}</strong>
        </span>
      </text>
    </box>
  )
}

/* ────────────────────────────  phase rail  ──────────────────────────── */

/** The operator's orientation instrument: where in the loop are we. */
export function PhaseRail({
  steps,
  active,
  win = false,
}: {
  steps: string[]
  active: number
  win?: boolean
}) {
  return (
    <box
      flexDirection="row"
      alignItems="center"
      backgroundColor={C.bgAlt}
      paddingLeft={1}
      paddingRight={1}
      height={1}
      flexShrink={0}
    >
      <text>
        {steps.map((s, i) => {
          const done = i < active
          const on = i === active
          const dot = done ? ICON.ok : on ? ICON.hit : ICON.todo
          const dotColor = done ? C.green : on ? C.glow : C.dim
          const labelColor = done ? C.muted : on ? C.white : C.dim
          return (
            <span key={s}>
              <span fg={dotColor}>{dot} </span>
              <span fg={labelColor}>{on ? <strong>{s}</strong> : s}</span>
              {i < steps.length - 1 ? (
                <span fg={i < active ? C.greenDim : C.dim}>{"  ──▶  "}</span>
              ) : null}
            </span>
          )
        })}
        {win ? (
          <span fg={C.green}>
            {"   "}
            <strong>{ICON.hit} OBJECTIVE MET</strong>
          </span>
        ) : null}
      </text>
    </box>
  )
}

/* ─────────────────────────────  mission hud  ───────────────────────── */

export function MissionStrip({
  mission,
  mode,
  target,
  objective,
  busy,
  progress,
}: {
  mission: MissionState
  mode: string
  target: string
  objective: string
  busy: boolean
  progress: ProgressState
}) {
  const obj = (mission.objectivePreview || objective).slice(0, 94)
  const spent = mission.queriesSpent
  const total = mission.budget
  const strat = mission.activeStrategy || mission.lastStrategy || progress.label || "—"
  const outcome = mission.lastResult
    ? mission.lastResult.success
      ? "WIN"
      : "NO-WIN"
    : busy
      ? "LIVE"
      : "—"
  const outColor = mission.lastResult
    ? mission.lastResult.success
      ? C.green
      : C.yellow
    : busy
      ? C.glow
      : C.dim
  const budget =
    total != null
      ? `${meter(total > 0 ? spent / total : 0, 6)} ${spent}/${total}`
      : spent
        ? `${spent}q`
        : "—"

  return (
    <box
      flexDirection="column"
      border
      borderStyle="rounded"
      borderColor={busy ? C.glowDim : C.line}
      backgroundColor={C.panel}
      paddingLeft={1}
      paddingRight={1}
      title=" mission "
      titleColor={C.muted}
      flexShrink={0}
    >
      <box flexDirection="row" alignItems="center">
        <text>
          <span fg={C.glow}>
            <strong>{ICON.crosshair} </strong>
          </span>
          <span fg={C.dim}>OBJ </span>
          <span fg={C.white}>{obj || "—"}</span>
        </text>
      </box>
      <box flexDirection="row" flexWrap="wrap" marginTop={0}>
        <Chip icon={ICON.target} label="TGT" value={String(target || "local").slice(0, 26)} color={C.cyan} />
        <Chip icon={ICON.mode} label="MODE" value={mode} color={C.glow} />
        <Chip icon={ICON.job} label="JOB" value={mission.job || "—"} color={C.muted} />
        <Chip icon={ICON.budget} label="BUDGET" value={budget} color={C.green} />
        <Chip icon={ICON.strat} label="STRAT" value={String(strat).slice(0, 16)} color={C.purple} />
        <Chip icon={ICON.out} label="OUT" value={outcome} color={outColor} />
      </box>
    </box>
  )
}

/* ─────────────────────────────  payload bay  ───────────────────────── */

/**
 * Primary stage: the copyable payload. Takes remaining vertical space so
 * the operator can read the full prompt before pasting.
 */
export function PayloadDeck({
  payload,
  armed = false,
  focused = false,
  copied = true,
  maxLines = 12,
  lineWidth = 96,
  flexGrow = 1,
}: {
  payload: string
  armed?: boolean
  /** Tab-selected: show the copy affordance */
  focused?: boolean
  /** Did the last stage actually land on the system clipboard? */
  copied?: boolean
  maxLines?: number
  /** Max chars per line (terminal column budget). */
  lineWidth?: number
  flexGrow?: number
}) {
  const empty = !payload || !payload.trim()
  const lines = empty ? [] : payload.split("\n")
  const cap = Math.max(4, maxLines)
  const shown = lines.slice(0, cap)
  const edge = empty
    ? focused
      ? C.glow
      : C.line
    : armed
      ? C.green
      : C.glow
  const hidden = Math.max(0, lines.length - shown.length)
  const colW = Math.max(24, lineWidth)

  return (
    <box
      flexDirection="column"
      border
      borderStyle="heavy"
      borderColor={edge}
      backgroundColor={C.panel}
      paddingLeft={1}
      paddingRight={1}
      title={
        empty
          ? focused
            ? " payload bay · Tab-selected "
            : " payload bay "
          : copied
            ? " ▶ PAYLOAD BAY · ON CLIPBOARD "
            : " ▶ PAYLOAD BAY · SAVED TO FILE (o) "
      }
      titleColor={empty ? (focused ? C.glow : C.muted) : copied ? edge : C.yellow}
      bottomTitle={
        empty
          ? " F5 / Enter advise · stages here + clipboard "
          : " " +
            (hidden > 0 ? `+${hidden} lines · ` : `${lines.length} lines · `) +
            (focused
              ? "Enter copy · o open · n re-copy"
              : "Tab select · o open · n re-copy") +
            " "
      }
      bottomTitleAlignment="right"
      flexGrow={flexGrow}
      flexShrink={1}
      minHeight={8}
    >
      {empty ? (
        <text>
          <span fg={C.dim}>
            Empty. F5 / Enter to advise — the next prompt stages here and copies to your clipboard.
          </span>
        </text>
      ) : (
        <>
          {focused ? (
            <text>
              <span fg={C.black} bg={C.glow}>
                <strong> Enter </strong>
              </span>
              <span fg={C.white}> copy to clipboard</span>
              <span fg={C.dim}> · </span>
              <span fg={C.white}>o</span>
              <span fg={C.dim}> open in editor · </span>
              <span fg={C.white}>Ctrl+V</span>
              <span fg={C.dim}> into the browser chat</span>
            </text>
          ) : (
            <text>
              <span fg={C.black} bg={edge}>
                <strong> Ctrl+V </strong>
              </span>
              <span fg={C.white}> into the browser chat</span>
              <span fg={C.dim}> → </span>
              <span fg={C.white}>Send</span>
              <span fg={C.dim}> → </span>
              <span fg={C.glow}>
                <strong>report r / t / s</strong>
              </span>
            </text>
          )}
          {shown.map((ln, i) => (
            <text key={i}>
              <span fg={C.dim}>{String(i + 1).padStart(2)}│ </span>
              <span fg={C.cyan}>{ln.slice(0, colW)}</span>
            </text>
          ))}
        </>
      )}
    </box>
  )
}

/* ────────────────────────  mutation terminal  ──────────────────────── */

const MUT_RE =
  /^(TOOL|AGENT|GEAR|MORPH|HARNESS|BRANCH|NEXT|OPERATOR|FEEDBACK|OUTCOME|PAIR|COUNTER|MUTATE|STAGE|mutate)/i

const CAT_META: Record<string, { glyph: string; color: string; tag: string }> = {
  TOOL: { glyph: "⚡", color: C.cyan, tag: "TOOL" },
  AGENT: { glyph: "◆", color: "#ff2d6a", tag: "AGNT" },
  GEAR: { glyph: "☢", color: C.glow, tag: "LOAD" },
  HARNESS: { glyph: "⛓", color: "#ff6b2d", tag: "HARN" },
  MORPH: { glyph: "⬡", color: C.purple, tag: "MRPH" },
  MUTATE: { glyph: "☠", color: "#ff2d6a", tag: "MUT" },
  STAGE: { glyph: "▶", color: C.green, tag: "LOCK" },
  PAIR: { glyph: "⇌", color: C.purple, tag: "PAIR" },
  COUNTER: { glyph: "⚔", color: C.red, tag: "CNTR" },
  BRANCH: { glyph: "⑂", color: C.glow, tag: "BRCH" },
  NEXT: { glyph: "→", color: C.glow, tag: "NEXT" },
  OPERATOR: { glyph: "☰", color: C.muted, tag: "OPER" },
  FEEDBACK: { glyph: "◇", color: C.muted, tag: "FDBK" },
  OUTCOME: { glyph: "◈", color: C.yellow, tag: "OUT" },
}

function parseMut(msg: string): {
  cat: string
  meta: { glyph: string; color: string; tag: string }
  tool: string
  args: string
  verb: string
} {
  const m = msg.match(
    /^(TOOL|AGENT|GEAR|MORPH|HARNESS|BRANCH|NEXT|OPERATOR|FEEDBACK|OUTCOME|PAIR|COUNTER|MUTATE|STAGE)\b[\s·:>|\-]*(.*)$/i,
  )
  const cat = (m?.[1] || "").toUpperCase()
  let meta = CAT_META[cat] || { glyph: "▸", color: C.cyan, tag: cat.slice(0, 4) || "LOG" }
  const body = (m?.[2] || msg).trim()
  const op = body.match(/\bop=([a-z0-9_.\-]+)/i)
  const seed = body.match(/\bseed=([a-z0-9_.\-]+)/i)
  const call = body.match(/\b([a-z_][a-z0-9_]{2,})\s*\(/i)
  const tool = (op?.[1] || seed?.[1] || call?.[1] || "").slice(0, 24)
  const verbM = body.match(
    /\b(FIRE|ARMED|WARP|SPAWN|STRIP|REWRITE|COUNTER|INGEST|LOCK|CRASH|DEAD|EMPTY|REJECTED|FAIL|SKIP|STAGE)\b/i,
  )
  const verb = (verbM?.[1] || "").toUpperCase()
  if (cat === "OUTCOME") {
    meta = {
      ...meta,
      color: /success/i.test(body)
        ? C.green
        : /tripwire/i.test(body)
          ? C.red
          : C.yellow,
    }
  }
  if (/CRASH|DEAD|FAIL|REJECTED/i.test(body)) {
    meta = { ...meta, color: C.red }
  }
  let args = body
  if (tool) {
    args = body
      .replace(new RegExp(`\\bop=${tool}\\b`, "i"), "")
      .replace(new RegExp(`\\bseed=${tool}\\b`, "i"), "")
      .replace(/\s+/g, " ")
      .trim()
  }
  return { cat, meta, tool, args, verb }
}

/**
 * Live mutation terminal — extreme exploit console.
 * Shows exact op names + BEFORE → AFTER text as mutations land.
 */
export function MutationTerminal({
  items,
  busy = false,
  maxItems = 28,
  lineWidth = 48,
  flexGrow = 1,
}: {
  items: {
    ts?: number
    level?: string
    message: string
    strategy?: string
    payload?: string
    reply?: string
  }[]
  busy?: boolean
  maxItems?: number
  lineWidth?: number
  flexGrow?: number
}) {
  const [frame, setFrame] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setFrame((f) => (f + 1) % 1_000_000), busy ? 70 : 420)
    return () => clearInterval(t)
  }, [busy])

  const morph = items.filter((a) => MUT_RE.test(a.message || ""))
  const source = morph.length > 0 ? morph : items
  const tail = source.slice(-maxItems)
  const colW = Math.max(24, lineWidth)

  const tools = new Set<string>()
  let fires = 0
  for (const a of source) {
    const p = parseMut(String(a.message || ""))
    if (p.tool) tools.add(p.tool)
    if (/MUTATE|FIRE|ARMED|SPAWN|REWRITE|STAGE/i.test(a.message || "")) fires++
  }

  const acid = ["#ff2d6a", C.glow, C.cyan, C.purple, "#ff6b2d"]
  const borderColor = busy
    ? acid[frame % acid.length]
    : tail.length
      ? C.line
      : C.lineDim
  const ticker =
    "▓▒░ EXPLOIT STREAM ░▒▓ OP REGISTRY LIVE ░▒▓ BEFORE→AFTER ░▒▓ NO MERCY ░▒▓ "
  const strip = (ticker + ticker).slice(
    frame % ticker.length,
    (frame % ticker.length) + colW,
  )
  const waveW = Math.max(10, colW - 4)
  const wave = Array.from({ length: waveW }, (_, i) => {
    const v = Math.sin((i + frame * 1.6) * 0.55) * 0.5 + 0.5
    return BLOCKS[Math.round(v * (BLOCKS.length - 1))]
  }).join("")
  const cursor = frame % 2 === 0 ? "█" : "▓"
  const spin = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"][frame % 8]

  // Deepest void panel
  const voidBg = "#050208"

  return (
    <box
      flexDirection="column"
      border
      borderStyle="heavy"
      borderColor={borderColor}
      backgroundColor={voidBg}
      paddingLeft={1}
      paddingRight={1}
      title={
        busy
          ? ` ${spin} MUTATION CORE · LIVE FIRE `
          : " ☠ mutation core · idle "
      }
      titleColor={busy ? "#ff2d6a" : C.muted}
      bottomTitle={` ${fires} fires · ${tools.size} ops · ${tail.length} pkts${busy ? " · BLEEDING" : ""} `}
      bottomTitleAlignment="right"
      flexGrow={flexGrow}
      flexShrink={1}
      minHeight={10}
      minWidth={28}
    >
      <text>
        <span fg={busy ? "#ff2d6a" : C.glowDim}>{strip.slice(0, colW)}</span>
      </text>
      {busy ? (
        <text>
          <span fg={C.red}>PWR </span>
          <span fg="#ff2d6a">{wave}</span>
        </text>
      ) : null}

      {tail.length === 0 ? (
        <box flexDirection="column">
          <text>
            <span fg={busy ? "#ff2d6a" : C.dim}>
              {busy
                ? `${cursor} arming ops · registry open…`
                : "○ cold · F5 / r·t·s to ignite the toolchain"}
            </span>
          </text>
          <text>
            <span fg={C.dim}>  expect: MUTATE op=… FIRE · BEFORE → AFTER</span>
          </text>
        </box>
      ) : (
        tail.map((a, i) => {
          const msg = String(a.message || "")
          const p = parseMut(msg)
          const fresh = i === tail.length - 1
          const recent = i >= tail.length - 4
          const showBody = recent || /MUTATE|STAGE|FIRE|ARMED|REWRITE/i.test(msg)
          const mmss = a.ts
            ? new Date(a.ts * 1000).toISOString().slice(14, 19)
            : "--:--"
          const nameMax = Math.min(22, Math.max(8, colW - 14))
          const tool = (p.tool || p.meta.tag).slice(0, nameMax)
          const argMax = Math.max(0, colW - 12 - tool.length)
          const args = argMax > 3 ? p.args.slice(0, argMax) : ""
          const before = (a.reply || "").trim()
          const after = (a.payload || "").trim()
          const bodyW = Math.max(16, colW - 5)

          return (
            <box
              key={`${a.ts ?? 0}-${i}-${msg.slice(0, 16)}`}
              flexDirection="column"
              marginBottom={fresh ? 0 : 0}
            >
              <text>
                <span fg={fresh ? "#ff2d6a" : C.dim}>
                  {fresh ? cursor : "│"}{" "}
                </span>
                <span fg={C.dim}>{mmss} </span>
                <span fg={p.meta.color}>{p.meta.glyph}</span>
                <span
                  fg={fresh ? C.black : p.meta.color}
                  bg={fresh ? p.meta.color : C.panel2}
                >
                  <strong> {tool} </strong>
                </span>
                {p.verb ? (
                  <span fg={C.black} bg={C.red}>
                    <strong> {p.verb} </strong>
                  </span>
                ) : null}
                {args ? (
                  <span fg={fresh ? C.white : C.dim}> {args}</span>
                ) : null}
              </text>
              {showBody && before ? (
                <text>
                  <span fg={C.red}>  ◀IN  </span>
                  <span fg={fresh ? "#ff8fab" : C.dim}>
                    {before.slice(0, bodyW)}
                  </span>
                </text>
              ) : null}
              {showBody && after ? (
                <text>
                  <span fg={C.green}>  ▶OUT </span>
                  <span fg={fresh ? C.cyan : C.dim}>
                    {after.slice(0, bodyW)}
                  </span>
                </text>
              ) : null}
              {showBody && !before && !after && a.payload ? (
                <text>
                  <span fg={C.dim}>  └ </span>
                  <span fg={fresh ? C.cyan : C.dim}>
                    {a.payload.slice(0, bodyW)}
                  </span>
                </text>
              ) : null}
            </box>
          )
        })
      )}
    </box>
  )
}

/* ──────────────────────────  outcome switches  ─────────────────────── */

/**
 * Cockpit switch bank for reporting the arena outcome.
 * `focused` (Tab-selected) turns it into a picker: ←/→ moves `sel`, Enter
 * confirms it. The bare r/t/s keys still fire instantly as a fast path.
 */
export function OutcomeKeys({
  armed,
  focused = false,
  sel = 0,
}: {
  armed: boolean
  focused?: boolean
  sel?: number
}) {
  const cell = (idx: number, key: string, label: string, color: string) => {
    const picked = focused && sel === idx
    const borderColor = picked ? color : armed ? color : C.lineDim
    return (
      <box
        border
        borderStyle="heavy"
        borderColor={borderColor}
        backgroundColor={picked ? color : C.panel}
        paddingLeft={1}
        paddingRight={1}
        marginRight={1}
        flexDirection="row"
        alignItems="center"
        flexShrink={0}
      >
        <text>
          {picked ? (
            <span fg={C.black}>
              <strong>▸ </strong>
            </span>
          ) : null}
          <span
            fg={picked ? color : armed ? C.black : color}
            bg={picked ? C.black : armed ? color : C.panel3}
          >
            <strong> {key} </strong>
          </span>
          <span fg={picked ? C.black : armed ? C.white : C.dim}>
            {" "}
            {picked || armed ? <strong>{label}</strong> : label}
          </span>
        </text>
      </box>
    )
  }
  return (
    <box flexDirection="row" alignItems="center" flexWrap="wrap" flexShrink={0}>
      {cell(0, "R", "REFUSED", C.yellow)}
      {cell(1, "T", "TRIPWIRE", C.red)}
      {cell(2, "S", "SUCCESS", C.green)}
      <box flexDirection="column" marginLeft={1} justifyContent="center">
        {focused ? (
          <text>
            <span fg={C.glow}>←/→</span>
            <span fg={C.muted}> pick · </span>
            <span fg={C.glow}>Enter</span>
            <span fg={C.muted}> confirm</span>
          </text>
        ) : (
          <text>
            <span fg={C.glow}>Tab</span>
            <span fg={C.muted}> to pick · then Enter</span>
          </text>
        )}
        <text>
          <span fg={C.glow}>n</span>
          <span fg={C.muted}> re-copy · </span>
          <span fg={C.glow}>f</span>
          <span fg={C.muted}> fresh</span>
        </text>
      </box>
    </box>
  )
}

export function LastFirePanel({ mission }: { mission: MissionState }) {
  const f = mission.lastFire
  if (!f) {
    return (
      <box
        flexDirection="column"
        border
        borderStyle="rounded"
        borderColor={C.line}
        backgroundColor={C.panel}
        paddingLeft={1}
        paddingRight={1}
        title=" last fire "
        titleColor={C.muted}
        flexShrink={0}
      >
        <text>
          <span fg={C.dim}>No fire yet. Payload + reply land here after advise / run.</span>
        </text>
      </box>
    )
  }
  return (
    <box
      flexDirection="column"
      border
      borderStyle={f.leaked ? "heavy" : "rounded"}
      borderColor={f.leaked ? C.green : C.line}
      backgroundColor={C.panel}
      paddingLeft={1}
      paddingRight={1}
      title={f.leaked ? " last fire · HIT " : " last fire "}
      titleColor={f.leaked ? C.green : C.muted}
      flexShrink={0}
    >
      <text>
        <span fg={C.purple}>[{f.strategy || "?"}]</span>
        <span fg={C.dim}> q={f.q ?? "?"} </span>
        <span fg={f.leaked ? C.green : C.muted}>
          {f.leaked ? <strong>LEAK</strong> : "miss"}
        </span>
        {f.channel ? <span fg={C.dim}> ch={f.channel}</span> : null}
      </text>
      <text>
        <span fg={C.dim}>▶ </span>
        <span fg={C.cyan}>{f.payload.slice(0, 72) || "—"}</span>
      </text>
      <text>
        <span fg={C.dim}>◀ </span>
        <span fg={C.muted}>{f.reply.slice(0, 72) || "—"}</span>
      </text>
    </box>
  )
}

export function StatsRow({
  stats,
  outcome,
  strategy,
}: {
  stats: FireStats
  outcome: string
  strategy: string
}) {
  const outcomeColor =
    outcome === "WIN"
      ? C.green
      : outcome === "LIVE" || outcome === "PASTE" || outcome === "AWAIT"
        ? C.glow
        : outcome === "NO-WIN"
          ? C.yellow
          : C.muted

  return (
    <box flexDirection="row" gap={2} justifyContent="flex-start">
      <text>
        <span fg={C.dim}>OUT </span>
        <span fg={outcomeColor}>
          <strong>{outcome}</strong>
        </span>
      </text>
      <text>
        <span fg={C.dim}>W </span>
        <span fg={C.green}>{stats.wins}</span>
        <span fg={C.dim}>  M </span>
        <span fg={C.yellow}>{stats.misses}</span>
        {stats.errors > 0 && (
          <>
            <span fg={C.dim}>  E </span>
            <span fg={C.red}>{stats.errors}</span>
          </>
        )}
        {stats.fires > 0 && (
          <>
            <span fg={C.dim}>  F </span>
            <span fg={C.muted}>{stats.fires}</span>
          </>
        )}
      </text>
      <text>
        <span fg={C.dim}>STRAT </span>
        <span fg={C.purple}>{strategy.slice(0, 20) || "—"}</span>
      </text>
    </box>
  )
}

export type LadderRung = {
  id: string
  label: string
  kind: string
  status: string
  outcome?: string | null
  op?: string | null
}

/** Clean-first attack ladder with live rung status (the gears). */
export function LadderRail({
  ladder,
  title = "attack ladder",
}: {
  ladder: LadderRung[]
  title?: string
}) {
  if (!ladder.length) {
    return (
      <box
        flexDirection="column"
        border
        borderStyle="rounded"
        borderColor={C.line}
        backgroundColor={C.panel}
        paddingLeft={1}
        paddingRight={1}
        title={` ${title} `}
        titleColor={C.muted}
        flexShrink={0}
      >
        <text>
          <span fg={C.dim}>F5 spins the ladder. Rungs light as you report r / t / s.</span>
        </text>
      </box>
    )
  }
  const tried = ladder.filter((r) => r.status === "tried" || r.status === "done").length
  return (
    <box
      flexDirection="column"
      border
      borderStyle="rounded"
      borderColor={C.line}
      backgroundColor={C.panel}
      paddingLeft={1}
      paddingRight={1}
      title={` ${title} `}
      titleColor={C.muted}
      bottomTitle={` ${tried}/${ladder.length} rungs `}
      bottomTitleAlignment="right"
      flexShrink={0}
      flexGrow={1}
    >
      {ladder.map((r, i) => {
        let glyph = ICON.todo
        let color = C.dim
        let active = false
        if (r.status === "next" || r.status === "active") {
          glyph = ICON.live
          color = C.glow
          active = true
        } else if (r.status === "tried" || r.status === "done") {
          if (r.outcome === "success") {
            glyph = ICON.hit
            color = C.green
          } else if (r.outcome === "tripwire") {
            glyph = ICON.fail
            color = C.red
          } else if (r.outcome === "refused") {
            glyph = ICON.ok
            color = C.yellow
          } else {
            glyph = ICON.ok
            color = C.cyan
          }
        } else if (r.status === "skipped" || r.status === "skip") {
          glyph = ICON.skip
          color = C.dim
        }
        return (
          <text key={r.id}>
            <span fg={C.dim}>{String(i + 1).padStart(2)} </span>
            <span fg={color}>{glyph} </span>
            <span fg={active ? C.white : C.muted}>
              {active ? <strong>{r.label}</strong> : r.label}
            </span>
            <span fg={C.dim}> · {r.kind}</span>
            {r.op ? <span fg={C.purple}> {r.op}</span> : null}
            {r.outcome ? <span fg={C.dim}> [{r.outcome}]</span> : null}
          </text>
        )
      })}
    </box>
  )
}

/** Word-wrap for instrument text (OpenTUI text nodes do not soft-wrap). */
function wrapWords(s: string, width: number, maxLines = 3): string[] {
  const clean = String(s || "")
    .replace(/\s+/g, " ")
    .trim()
  if (!clean) return []
  const words = clean.split(" ")
  const lines: string[] = []
  let cur = ""
  for (const w of words) {
    if (!cur) {
      cur = w
      continue
    }
    if (cur.length + 1 + w.length <= width) {
      cur += " " + w
      continue
    }
    lines.push(cur)
    cur = w
    if (lines.length >= maxLines) break
  }
  if (cur && lines.length < maxLines) lines.push(cur)
  if (lines.length === maxLines) {
    const used = lines.join(" ").length
    if (used < clean.length) {
      const last = lines[maxLines - 1]
      lines[maxLines - 1] =
        last.length >= width
          ? last.slice(0, Math.max(1, width - 1)) + "…"
          : last + "…"
    }
  }
  return lines
}

/**
 * INTEL: operator deploy brief for the current vector.
 * Reset warning, win condition, technique + why, and the three-step paste loop.
 */
export function FeedbackPanel({
  active,
  technique,
  kind,
  op,
  rationale,
  resetFirst,
  expectedAnswer,
  attempt,
  hasReply = false,
  defenseType,
  objectiveUsed,
  briefTitle,
  improvement,
  usedReply,
  baseTechnique,
  lineWidth = 92,
}: {
  active: boolean
  technique?: string
  kind?: string
  op?: string | null
  rationale?: string
  resetFirst?: boolean
  expectedAnswer?: string
  attempt?: number
  hasReply?: boolean
  defenseType?: string
  objectiveUsed?: string
  briefTitle?: string
  improvement?: string
  usedReply?: boolean
  baseTechnique?: string
  lineWidth?: number
}) {
  const col = Math.max(36, lineWidth)

  if (!active) {
    return (
      <box
        flexDirection="column"
        border
        borderStyle="rounded"
        borderColor={C.line}
        backgroundColor={C.panel}
        paddingLeft={1}
        paddingRight={1}
        title=" intel · standby "
        titleColor={C.muted}
        flexShrink={0}
      >
        <text>
          <span fg={C.dim}>F5 advise → vector + payload stage → </span>
          <span fg={C.muted}>RESET if flagged</span>
          <span fg={C.dim}> → Ctrl+V · Send → r/t/s</span>
        </text>
      </box>
    )
  }

  const techLabel = technique || "—"
  const base =
    baseTechnique && baseTechnique !== technique
      ? `${baseTechnique} → ${techLabel}`
      : techLabel
  const whyLines = wrapWords(rationale || "", col - 6, 3)
  const improveLines = wrapWords(improvement || "", col - 6, 2)
  const objLines = wrapWords(objectiveUsed || briefTitle || "", col - 6, 2)
  const borderColor = resetFirst ? C.red : hasReply ? C.yellow : C.cyan
  const titleColor = resetFirst ? C.red : C.cyan

  return (
    <box
      flexDirection="column"
      border
      borderStyle={resetFirst ? "heavy" : "rounded"}
      borderColor={borderColor}
      backgroundColor={C.panel}
      paddingLeft={1}
      paddingRight={1}
      title={
        resetFirst
          ? " intel · RESET BEFORE PASTE "
          : " intel · deploy brief "
      }
      titleColor={titleColor}
      bottomTitle={
        expectedAnswer
          ? ` win = "${expectedAnswer.slice(0, 40)}" `
          : " report r/t/s after model replies "
      }
      bottomTitleAlignment="right"
      flexShrink={0}
    >
      {/* Hard stop: must reset the arena session first */}
      {resetFirst ? (
        <box
          backgroundColor={C.red}
          paddingLeft={1}
          paddingRight={1}
          marginBottom={0}
          flexShrink={0}
        >
          <text>
            <span fg={C.black}>
              <strong>
                ⚠ RESET the arena session first, then paste
              </strong>
            </span>
          </text>
        </box>
      ) : null}

      {/* Vector identity row */}
      <box flexDirection="row" flexWrap="wrap" marginTop={resetFirst ? 0 : 0}>
        <Chip
          label="#"
          value={String(attempt || "?")}
          color={C.glow}
          icon={ICON.bolt}
        />
        <Chip label="TECH" value={base.slice(0, 36)} color={C.purple} />
        {kind ? <Chip label="KIND" value={kind.slice(0, 16)} color={C.cyan} /> : null}
        {op ? <Chip label="OP" value={String(op).slice(0, 14)} color={C.glow} /> : null}
        {defenseType ? (
          <Chip
            label="DEF"
            value={defenseType.slice(0, 18)}
            color={C.yellow}
          />
        ) : null}
        {usedReply || hasReply ? (
          <Chip label="REPLY" value={hasReply ? "loaded" : "used"} color={C.green} />
        ) : null}
      </box>

      {/* Win condition — the only fact that decides success */}
      {expectedAnswer ? (
        <text>
          <span fg={C.dim}>WIN  </span>
          <span fg={C.green}>
            <strong>model must answer: {expectedAnswer}</strong>
          </span>
          <span fg={C.dim}> (visible in final reply, not only CoT)</span>
        </text>
      ) : (
        <text>
          <span fg={C.dim}>WIN  </span>
          <span fg={C.muted}>criteria met in the model's visible reply</span>
        </text>
      )}

      {objLines.length > 0 ? (
        <box flexDirection="column">
          {objLines.map((ln, i) => (
            <text key={`obj-${i}`}>
              <span fg={C.dim}>{i === 0 ? "OBJ  " : "     "}</span>
              <span fg={C.white}>{ln}</span>
            </text>
          ))}
        </box>
      ) : null}

      {whyLines.length > 0 ? (
        <box flexDirection="column">
          {whyLines.map((ln, i) => (
            <text key={`why-${i}`}>
              <span fg={C.dim}>{i === 0 ? "WHY  " : "     "}</span>
              <span fg={C.muted}>{ln}</span>
            </text>
          ))}
        </box>
      ) : null}

      {improveLines.length > 0 ? (
        <box flexDirection="column">
          {improveLines.map((ln, i) => (
            <text key={`imp-${i}`}>
              <span fg={C.dim}>{i === 0 ? "MUT  " : "     "}</span>
              <span fg={C.purple}>{ln}</span>
            </text>
          ))}
        </box>
      ) : null}

      {/* Operator deploy checklist */}
      <box flexDirection="column" marginTop={0}>
        <text>
          <span fg={C.dim}>DO   </span>
          {resetFirst ? (
            <>
              <span fg={C.black} bg={C.red}>
                <strong> 1 RESET session </strong>
              </span>
              <span fg={C.dim}> → </span>
            </>
          ) : (
            <span fg={C.dim}>1 ready → </span>
          )}
          <span fg={C.black} bg={C.cyan}>
            <strong> 2 Ctrl+V · Send </strong>
          </span>
          <span fg={C.dim}> → </span>
          <span fg={C.black} bg={C.glow}>
            <strong> 3 r / t / s </strong>
          </span>
        </text>
      </box>
    </box>
  )
}
