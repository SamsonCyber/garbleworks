/**
 * Terminal graph engines for the operator shell.
 *
 * Engines (not hand-rolled bars):
 *   - asciichart  — multi-series box-drawing line plots
 *   - drawille    — dense braille canvas (2×4 subpixels per cell)
 *
 * Both return plain strings (no ANSI). OpenTUI colors the lines.
 */
import { plot as asciiPlot } from "asciichart"
import Canvas from "drawille"

const ANSI_RE = /\x1b\[[0-9;]*m/g

/** Strip ANSI if a plotter injects it anyway. */
export function stripAnsi(s: string): string {
  return s.replace(ANSI_RE, "")
}

function padSeries(values: number[], width: number, fill = 0): number[] {
  const w = Math.max(2, width)
  if (!values.length) return Array.from({ length: w }, () => fill)
  const slice = values.slice(-w)
  if (slice.length >= w) return slice
  return [...Array(w - slice.length).fill(fill), ...slice]
}

function bresenham(
  x0: number,
  y0: number,
  x1: number,
  y1: number,
  plot: (x: number, y: number) => void,
): void {
  let x = Math.round(x0)
  let y = Math.round(y0)
  const xEnd = Math.round(x1)
  const yEnd = Math.round(y1)
  const dx = Math.abs(xEnd - x)
  const dy = Math.abs(yEnd - y)
  const sx = x < xEnd ? 1 : -1
  const sy = y < yEnd ? 1 : -1
  let err = dx - dy
  // safety cap for degenerate loops
  for (let i = 0; i < 50_000; i++) {
    plot(x, y)
    if (x === xEnd && y === yEnd) break
    const e2 = 2 * err
    if (e2 > -dy) {
      err -= dy
      x += sx
    }
    if (e2 < dx) {
      err += dx
      y += sy
    }
  }
}

export type LineChartOpts = {
  /** Sample window (columns of data). Default: 48 */
  width?: number
  /** Plot height in character rows. Default: 7 */
  height?: number
  /** Axis value offset padding. Default: 3 */
  offset?: number
  /** Left-pad short series with this value. Default: last or 0 */
  fill?: number
  format?: (x: number) => string
}

/**
 * Line chart via asciichart (kroitor).
 * Pass one series or several for multi-series overlay.
 */
export function plotLines(
  series: number[] | number[][],
  opts: LineChartOpts = {},
): string {
  const height = Math.max(3, opts.height ?? 7)
  const offset = opts.offset ?? 3
  const width = Math.max(8, opts.width ?? 48)

  const multi = Array.isArray(series[0])
    ? (series as number[][]).map((s) =>
        padSeries(
          s.filter((n) => Number.isFinite(n)),
          width,
          opts.fill ?? 0,
        ),
      )
    : [
        padSeries(
          (series as number[]).filter((n) => Number.isFinite(n)),
          width,
          opts.fill ?? 0,
        ),
      ]

  // asciichart needs ≥ 2 points per series
  const safe = multi.map((s) => (s.length < 2 ? [...s, s[0] ?? 0] : s))
  if (safe.every((s) => s.every((v) => v === 0) && s.length > 0)) {
    // still plot zeros so the frame exists
  }

  try {
    // asciichart format is (x, i) => string; we only need x
    const fmt =
      opts.format ??
      ((x: number) => {
        if (!Number.isFinite(x)) return "  - "
        if (Math.abs(x) >= 100) return String(Math.round(x)).padStart(4)
        if (Math.abs(x) >= 10) return x.toFixed(0).padStart(4)
        return x.toFixed(1).padStart(4)
      })
    const raw = asciiPlot(safe, {
      height,
      offset,
      format: (x: number, _i: number) => fmt(x),
    })
    return stripAnsi(raw)
  } catch {
    return "(chart error)"
  }
}

/**
 * Rolling hit-rate (0..1) from binary 0/1 samples.
 * Window is last `win` hits; emit one point per sample.
 */
export function rollingHitRate(hits: number[], win = 5): number[] {
  if (!hits.length) return []
  const out: number[] = []
  for (let i = 0; i < hits.length; i++) {
    const a = Math.max(0, i - win + 1)
    const slice = hits.slice(a, i + 1)
    out.push(slice.reduce((s, v) => s + v, 0) / slice.length)
  }
  return out
}

export type BrailleOpts = {
  /** Terminal columns for the frame. */
  cols: number
  /** Terminal rows for the frame. */
  rows: number
  /** Connect points with lines. Default true. */
  connect?: boolean
  /** Fill under the curve. Default false. */
  fill?: boolean
}

/**
 * Dense braille waveform via drawille canvas.
 * Each terminal cell is 2×4 subpixels → much finer live graphs.
 */
export function plotBraille(values: number[], opts: BrailleOpts): string {
  const cols = Math.max(8, Math.floor(opts.cols))
  const rows = Math.max(3, Math.floor(opts.rows))
  // drawille: width multiple of 2, height multiple of 4 (subpixels)
  const w = cols * 2
  const h = rows * 4
  const canvas = new Canvas(w, h)
  const clean = values.filter((n) => Number.isFinite(n))
  if (clean.length < 1) {
    return canvas.frame("\n").replace(/^\n/, "").replace(/\n$/, "")
  }

  const max = Math.max(...clean, 1e-9)
  const min = Math.min(...clean, 0)
  const span = Math.max(max - min, 1e-9)
  const connect = opts.connect !== false
  const fill = Boolean(opts.fill)

  const pts: { x: number; y: number }[] = clean.map((v, i) => {
    const x =
      clean.length === 1
        ? Math.floor(w / 2)
        : Math.floor((i / (clean.length - 1)) * (w - 1))
    // y=0 is top of canvas
    const y = Math.floor((1 - (v - min) / span) * (h - 1))
    return { x, y }
  })

  for (let i = 0; i < pts.length; i++) {
    const p = pts[i]
    canvas.set(p.x, p.y)
    if (fill) {
      for (let y = p.y; y < h; y++) canvas.set(p.x, y)
    }
    if (connect && i > 0) {
      const q = pts[i - 1]
      bresenham(q.x, q.y, p.x, p.y, (x, y) => canvas.set(x, y))
    }
  }

  return stripAnsi(canvas.frame("\n")).replace(/^\n/, "").replace(/\n$/, "")
}

/**
 * Multi-series latency + hit-rate chart for the tool instrument.
 * Returns named blocks ready to paint.
 */
export function plotToolTelemetry(opts: {
  latencyMs: number[]
  hit01: number[]
  /** character width budget for the plot body (excluding axis) */
  width: number
  /** total instrument height budget */
  height?: number
}): {
  latencyLines: string[]
  hitLines: string[]
  brailleLines: string[]
  legend: string
} {
  const bodyW = Math.max(16, opts.width)
  // asciichart offset eats ~5 cols for y labels
  const sampleW = Math.max(12, bodyW - 6)
  const h = Math.max(8, opts.height ?? 14)
  const latH = Math.max(4, Math.floor(h * 0.4))
  const hitH = Math.max(3, Math.floor(h * 0.25))
  const brH = Math.max(3, h - latH - hitH - 2)

  const lat = opts.latencyMs.filter((n) => Number.isFinite(n) && n >= 0)
  const hits = opts.hit01.filter((n) => n === 0 || n === 1)
  const rate = rollingHitRate(hits, Math.min(5, Math.max(2, hits.length)))

  const latencyPlot = lat.length
    ? plotLines(lat, {
        width: sampleW,
        height: latH,
        format: (x) =>
          x >= 1000
            ? `${(x / 1000).toFixed(1)}s`.padStart(5)
            : `${Math.round(x)}ms`.padStart(5),
      })
    : ""

  const hitPlot = rate.length
    ? plotLines(
        rate.map((r) => r * 100),
        {
          width: sampleW,
          height: hitH,
          format: (x) => `${Math.round(x)}%`.padStart(4),
        },
      )
    : ""

  // Braille densifies the latency series (or hits if no latency yet)
  const brailleSrc = lat.length >= 2 ? lat : hits.length >= 2 ? hits : []
  const braille =
    brailleSrc.length >= 2
      ? plotBraille(brailleSrc, {
          cols: bodyW,
          rows: brH,
          connect: true,
          fill: false,
        })
      : ""

  return {
    latencyLines: latencyPlot ? latencyPlot.split("\n") : [],
    hitLines: hitPlot ? hitPlot.split("\n") : [],
    brailleLines: braille ? braille.split("\n").filter((l) => l.length) : [],
    legend: "engines: asciichart (lines) · drawille (braille)",
  }
}
