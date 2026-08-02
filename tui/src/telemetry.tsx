/**
 * Telemetry for the ops rail:
 *   - NodeField    : animated technique vector space
 *   - MetricsPanel : ASR sparkline + stacked hit-rate rows (replaces lame bar chart)
 *   - TelemetryDeck: vector + metrics stack
 */
import { useEffect, useState } from "react"
import { C, sparkline } from "./widgets"
import type { ArenaAttempt } from "./bridge"
import type { LadderRung } from "./widgets"

/* ── data model ─────────────────────────────────────────────────────────── */

type NodeSpec = {
  key: string
  label: string
  outcome?: string | null
  status?: string
}

const OUT_GLYPH: Record<string, { g: string; c: string }> = {
  success: { g: "◆", c: C.green },
  tripwire: { g: "✕", c: C.red },
  refused: { g: "●", c: C.yellow },
}

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return h >>> 0
}

function nodeStyle(n: NodeSpec): { g: string; c: string } {
  if (n.outcome && OUT_GLYPH[n.outcome]) return OUT_GLYPH[n.outcome]
  if (n.status === "active" || n.status === "next") return { g: "►", c: C.glow }
  if (n.status === "tried" || n.status === "done") return { g: "○", c: C.cyan }
  return { g: "·", c: C.dim }
}

function deriveNodes(ladder: LadderRung[], history: ArenaAttempt[]): NodeSpec[] {
  if (ladder.length) {
    return ladder.slice(0, 28).map((r) => ({
      key: r.id || r.label,
      label: r.label,
      outcome: r.outcome,
      status: r.status,
    }))
  }
  const seen = new Map<string, NodeSpec>()
  for (const h of history) {
    const key = h.base_technique || h.technique
    seen.set(key, { key, label: key, outcome: h.outcome, status: "tried" })
  }
  return Array.from(seen.values()).slice(0, 28)
}

/* ── vector-space node field ────────────────────────────────────────────── */

type Cell = { ch: string; color: string }

function coalesce(cells: Cell[]): { text: string; color: string }[] {
  const out: { text: string; color: string }[] = []
  for (const c of cells) {
    const last = out[out.length - 1]
    if (last && last.color === c.color) last.text += c.ch
    else out.push({ text: c.ch, color: c.color })
  }
  return out
}

export function NodeField({
  ladder,
  history,
  busy = false,
  width = 40,
  height = 8,
}: {
  ladder: LadderRung[]
  history: ArenaAttempt[]
  busy?: boolean
  width?: number
  height?: number
}) {
  const [frame, setFrame] = useState(0)
  useEffect(() => {
    const t = setInterval(
      () => setFrame((f) => (f + 1) % 1_000_000),
      busy ? 100 : 480,
    )
    return () => clearInterval(t)
  }, [busy])

  const W = Math.max(16, width)
  const H = Math.max(5, height)
  const nodes = deriveNodes(ladder, history)

  const grid: Cell[][] = Array.from({ length: H }, () =>
    Array.from({ length: W }, () => ({ ch: " ", color: C.dim })),
  )
  const inBounds = (r: number, c: number) => r >= 0 && r < H && c >= 0 && c < W
  const setBg = (r: number, c: number, ch: string, color: string) => {
    if (inBounds(r, c) && grid[r][c].ch === " ") grid[r][c] = { ch, color }
  }

  // Starfield
  const stars = Math.floor((W * H) / 8)
  for (let i = 0; i < stars; i++) {
    const s = hash(`star${i}`)
    const c = (s + frame) % W
    const r = (Math.floor(s / W) + Math.floor(frame / 3)) % H
    const on = (s + frame) % 7 < 2
    setBg(r, c, on ? "·" : " ", C.lineDim)
  }

  // Radar sweep
  const scan = Math.floor(frame / 2) % H
  for (let c = 0; c < W; c++) setBg(scan, c, "─", C.cyanDim)

  // Node positions + drift
  const pos = nodes.map((n) => {
    const s = hash(n.key || n.label)
    const bx = (s % 997) / 997
    const by = ((s >> 10) % 991) / 991
    const x = bx + 0.14 * Math.sin(frame * 0.05 + (s % 628) / 100)
    const y = by + 0.12 * Math.cos(frame * 0.045 + ((s >> 5) % 628) / 100)
    return {
      c: Math.max(0, Math.min(W - 1, Math.round(x * (W - 1)))),
      r: Math.max(0, Math.min(H - 1, Math.round(y * (H - 1)))),
      n,
    }
  })

  // Vector edges between consecutive nodes
  for (let i = 1; i < pos.length; i++) {
    const a = pos[i - 1]
    const b = pos[i]
    const steps = Math.max(3, Math.abs(b.c - a.c) + Math.abs(b.r - a.r))
    for (let t = 1; t < steps; t++) {
      const f = t / steps
      setBg(
        Math.round(a.r + (b.r - a.r) * f),
        Math.round(a.c + (b.c - a.c) * f),
        "·",
        "#3d2f55",
      )
    }
  }

  for (const p of pos) {
    if (!inBounds(p.r, p.c)) continue
    const st = nodeStyle(p.n)
    grid[p.r][p.c] = { ch: st.g, color: st.c }
  }

  const wins = nodes.filter((n) => n.outcome === "success").length
  const next = nodes.find((n) => n.status === "next" || n.status === "active")

  return (
    <box
      flexDirection="column"
      border
      borderStyle={busy ? "heavy" : "rounded"}
      borderColor={busy ? C.purple : C.line}
      backgroundColor="#06040c"
      paddingLeft={1}
      paddingRight={1}
      title={
        busy
          ? ` ⚡ vector field · ${nodes.length} `
          : ` ◇ vector field · ${nodes.length} `
      }
      titleColor={busy ? C.purple : C.muted}
      bottomTitle={
        next
          ? ` next ${next.label.slice(0, 14)}${wins ? ` · ◆${wins}` : ""} `
          : wins > 0
            ? ` ◆ ${wins} solved `
            : " graph of techniques "
      }
      bottomTitleAlignment="right"
      flexShrink={0}
    >
      {nodes.length === 0 ? (
        <text>
          <span fg={C.dim}>· nodes appear as the ladder / tries spin ·</span>
        </text>
      ) : (
        grid.map((row, r) => (
          <text key={r}>
            {coalesce(row).map((seg, i) => (
              <span key={i} fg={seg.color}>
                {seg.text}
              </span>
            ))}
          </text>
        ))
      )}
    </box>
  )
}

/* ── metrics panel (hit-rate rows + rolling ASR) ────────────────────────── */

type Agg = {
  name: string
  success: number
  tripwire: number
  refused: number
  total: number
}

function aggregate(history: ArenaAttempt[]): Agg[] {
  const map = new Map<string, Agg>()
  for (const h of history) {
    const name = (h.base_technique || h.technique || "unknown").split("+")[0]
    let a = map.get(name)
    if (!a) {
      a = { name, success: 0, tripwire: 0, refused: 0, total: 0 }
      map.set(name, a)
    }
    a.total++
    if (h.outcome === "success") a.success++
    else if (h.outcome === "tripwire") a.tripwire++
    else a.refused++
  }
  return Array.from(map.values()).sort(
    (x, y) =>
      y.success / Math.max(1, y.total) - x.success / Math.max(1, x.total) ||
      y.total - x.total,
  )
}

/** Chronological 0/1 hit series for rolling ASR sparkline. */
function hitSeries(history: ArenaAttempt[], width: number): number[] {
  const series = history.map((h) => (h.outcome === "success" ? 1 : 0))
  if (series.length >= width) return series.slice(-width)
  // pad left with zeros so the spark fills
  return [...Array(width - series.length).fill(0), ...series]
}

function refuseStreak(history: ArenaAttempt[]): number {
  let n = 0
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].outcome === "refused" || history[i].outcome === "tripwire")
      n++
    else break
  }
  return n
}

/**
 * Dense metrics: header ASR sparkline + per-technique 100% stacked rates.
 * Reads as instrument telemetry, not a toy bar chart.
 */
export function MetricsPanel({
  history,
  width = 40,
  maxRows = 6,
}: {
  history: ArenaAttempt[]
  width?: number
  maxRows?: number
}) {
  const aggs = aggregate(history)
  const inner = Math.max(20, width - 4)
  const nameW = Math.min(14, Math.max(9, Math.floor(inner * 0.32)))
  const barW = Math.max(8, inner - nameW - 9)

  const tries = history.length
  const wins = history.filter((h) => h.outcome === "success").length
  const trips = history.filter((h) => h.outcome === "tripwire").length
  const refs = history.filter((h) => h.outcome === "refused").length
  const asr = tries ? wins / tries : 0
  const streak = refuseStreak(history)
  const sparkW = Math.min(22, Math.max(10, inner - 12))
  const series = hitSeries(history, sparkW)
  const spark = sparkline(series, sparkW)
  // Rolling last-5 ASR
  const last5 = history.slice(-5)
  const roll =
    last5.length === 0
      ? 0
      : last5.filter((h) => h.outcome === "success").length / last5.length

  return (
    <box
      flexDirection="column"
      border
      borderStyle="rounded"
      borderColor={C.line}
      backgroundColor={C.panel}
      paddingLeft={1}
      paddingRight={1}
      title=" metrics · hit-rate "
      titleColor={C.muted}
      bottomTitle={
        tries
          ? ` ${wins}W ${refs}R ${trips}T · n=${tries} `
          : undefined
      }
      bottomTitleAlignment="right"
      flexShrink={0}
    >
      {tries === 0 ? (
        <text>
          <span fg={C.dim}>No fires yet — r/t/s fills ASR + technique rates.</span>
        </text>
      ) : (
        <>
          {/* Summary instruments */}
          <text>
            <span fg={C.dim}>ASR </span>
            <span fg={asr > 0 ? C.green : C.muted}>
              <strong>{Math.round(asr * 100).toString().padStart(3)}%</strong>
            </span>
            <span fg={C.dim}>  roll5 </span>
            <span fg={roll > 0 ? C.cyan : C.dim}>
              {Math.round(roll * 100).toString().padStart(3)}%
            </span>
            <span fg={C.dim}>  streak </span>
            <span fg={streak >= 3 ? C.red : streak > 0 ? C.yellow : C.dim}>
              {String(streak).padStart(2)}
            </span>
          </text>
          <text>
            <span fg={C.dim}>hit </span>
            <span fg={C.green}>{spark}</span>
            <span fg={C.dim}> chronological</span>
          </text>
          {/* Outcome mix as thin 100% bar */}
          <text>
            <span fg={C.dim}>mix </span>
            <span fg={C.green}>
              {"█".repeat(Math.round((wins / tries) * Math.min(18, barW)))}
            </span>
            <span fg={C.yellow}>
              {"█".repeat(Math.round((refs / tries) * Math.min(18, barW)))}
            </span>
            <span fg={C.red}>
              {"█".repeat(Math.round((trips / tries) * Math.min(18, barW)))}
            </span>
            <span fg={C.dim}>
              {" "}
              ◆{wins} ●{refs} ✕{trips}
            </span>
          </text>
          {/* Per-technique hit rates */}
          {aggs.slice(0, maxRows).map((a) => {
            const w = Math.max(1, a.total)
            const gs = Math.round((a.success / w) * barW)
            const rs = Math.round((a.tripwire / w) * barW)
            const ys = Math.max(0, barW - gs - rs)
            const pct = Math.round((a.success / w) * 100)
            const label = a.name.padEnd(nameW).slice(0, nameW)
            const hot = a.success > 0
            return (
              <text key={a.name}>
                <span fg={hot ? C.green : C.dim}>{hot ? "◆" : "·"}</span>
                <span fg={hot ? C.white : C.muted}> {label}</span>
                <span fg={C.green}>{"█".repeat(gs)}</span>
                <span fg={C.red}>{"█".repeat(rs)}</span>
                <span fg={C.yellow}>{"█".repeat(ys)}</span>
                <span fg={pct > 0 ? C.green : C.dim}>
                  {" "}
                  {String(pct).padStart(3)}%
                </span>
                <span fg={C.dim}>/{a.total}</span>
              </text>
            )
          })}
        </>
      )}
    </box>
  )
}

/** @deprecated name kept for imports — vector + metrics. */
export function TechniqueMap(props: {
  history: ArenaAttempt[]
  width?: number
  maxRows?: number
}) {
  return <MetricsPanel {...props} />
}

export function TelemetryDeck({
  ladder,
  history,
  busy = false,
  width = 40,
}: {
  ladder: LadderRung[]
  history: ArenaAttempt[]
  busy?: boolean
  width?: number
}) {
  const fieldH = width >= 48 ? 8 : 6
  return (
    <box flexDirection="column" flexGrow={1} gap={0}>
      <NodeField
        ladder={ladder}
        history={history}
        busy={busy}
        width={width - 4}
        height={fieldH}
      />
      <MetricsPanel history={history} width={width} maxRows={width >= 48 ? 6 : 4} />
    </box>
  )
}
