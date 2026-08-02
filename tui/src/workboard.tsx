/**
 * Workboard: plan checklist + progress graph + activity feed (ops rail).
 */
import { C, MeterBar, meter } from "./widgets"
import type { ActivityItem, PlanStep, ProgressState } from "./bridge"

function statusGlyph(s: string): { g: string; color: string } {
  switch (s) {
    case "win":
      return { g: "◆", color: C.green }
    case "done":
      return { g: "●", color: C.cyan }
    case "active":
      return { g: "►", color: C.glow }
    case "skip":
      return { g: "○", color: C.dim }
    case "fail":
      return { g: "✕", color: C.red }
    default:
      return { g: "·", color: C.dim }
  }
}

function isTerminal(status: string): boolean {
  return ["done", "win", "skip", "fail"].includes(status)
}

export function PlanChecklist({ steps }: { steps: PlanStep[] }) {
  if (!steps.length) {
    return (
      <box flexDirection="column" paddingLeft={1}>
        <text>
          <span fg={C.dim}>No plan yet. F5 / Ctrl+Enter to run.</span>
        </text>
      </box>
    )
  }
  const done = steps.filter((s) => isTerminal(s.status)).length
  const bar = meter(done / steps.length, 12)
  return (
    <box flexDirection="column" paddingLeft={1} paddingRight={1}>
      <text>
        <span fg={C.muted}>plan  </span>
        <span fg={C.cyan}>{bar}</span>
        <span fg={C.dim}>
          {" "}
          {done}/{steps.length}
        </span>
      </text>
      {steps.map((s) => {
        const { g, color } = statusGlyph(s.status)
        return (
          <text key={s.id}>
            <span fg={color}>{g} </span>
            <span fg={s.status === "active" ? C.white : C.text}>{s.label}</span>
            {s.status === "active" && <span fg={C.glow}> ←</span>}
            {s.queries != null && s.queries > 0 && (
              <span fg={C.dim}> q={s.queries}</span>
            )}
            {s.note && s.status !== "pending" && (
              <span fg={C.muted}> {String(s.note).slice(0, 20)}</span>
            )}
          </text>
        )
      })}
    </box>
  )
}

export function StepGraph({ steps }: { steps: PlanStep[] }) {
  if (!steps.length) {
    return (
      <text>
        <span fg={C.dim}>░░░░</span>
      </text>
    )
  }
  return (
    <box flexDirection="column" paddingLeft={1} paddingRight={1}>
      <text>
        <span fg={C.muted}>steps </span>
        {steps.map((s) => {
          let ch = "░"
          let color = C.dim
          if (s.status === "win") {
            ch = "█"
            color = C.green
          } else if (s.status === "done") {
            ch = "█"
            color = C.cyan
          } else if (s.status === "active") {
            ch = "▓"
            color = C.glow
          } else if (s.status === "fail") {
            ch = "▒"
            color = C.red
          } else if (s.status === "skip") {
            ch = "░"
            color = C.muted
          }
          return (
            <span key={s.id} fg={color}>
              {ch}
            </span>
          )
        })}
        <span fg={C.dim}>
          {" "}
          {steps.filter((s) => isTerminal(s.status)).length}/{steps.length}
        </span>
      </text>
    </box>
  )
}

export function ProgressGraph({
  progress,
  steps,
}: {
  progress: ProgressState
  steps: PlanStep[]
}) {
  const total = Math.max(1, progress.total)
  const cur = Math.min(progress.current, total)
  const ratio = progress.ratio || cur / total
  const segs = 12
  const filled = Math.round(ratio * segs)
  let track = ""
  for (let i = 0; i < segs; i++) {
    track += i < filled ? "█" : i === filled ? "▓" : "░"
  }

  const term = steps.filter((s) => isTerminal(s.status)).length
  const win = steps.filter((s) => s.status === "win").length
  const active = steps.filter((s) => s.status === "active").length
  const pending = steps.filter((s) => s.status === "pending").length

  return (
    <box flexDirection="column" paddingLeft={1} paddingRight={1}>
      <text>
        <span fg={C.glow}>{track}</span>
        <span fg={C.white}> {Math.round(ratio * 100)}%</span>
      </text>
      <text>
        <span fg={C.dim}>
          {progress.label || "—"} {cur}/{total}
          {progress.detail ? ` · ${progress.detail}` : ""}
        </span>
      </text>
      <MeterBar label="rung" value={cur} max={total} width={10} color={C.green} />
      {steps.length > 0 && (
        <text>
          <span fg={C.green}>done {term}</span>
          <span fg={C.dim}> · </span>
          <span fg={C.glow}>live {active}</span>
          <span fg={C.dim}> · </span>
          <span fg={C.muted}>todo {pending}</span>
          {win > 0 && (
            <>
              <span fg={C.dim}> · </span>
              <span fg={C.green}>win {win}</span>
            </>
          )}
        </text>
      )}
      <StepGraph steps={steps} />
    </box>
  )
}

function levelColor(level: string): string {
  if (level === "win") return C.green
  if (level === "warn") return C.yellow
  if (level === "error") return C.red
  return C.text
}

export function ActivityFeed({
  items,
  maxItems = 10,
  compact = false,
}: {
  items: ActivityItem[]
  maxItems?: number
  compact?: boolean
}) {
  const tail = items.slice(-maxItems)
  return (
    <box
      flexGrow={1}
      flexDirection="column"
      border
      borderStyle="rounded"
      borderColor={C.line}
      backgroundColor={C.panel}
      paddingLeft={1}
      paddingRight={1}
      title=" telemetry "
      titleColor={C.muted}
    >
      {tail.length === 0 ? (
        <text>
          <span fg={C.dim}>
            {compact
              ? "Strategies · fires stream here once you run."
              : "Strategies · fires · model path stream here once you run."}
          </span>
        </text>
      ) : (
        tail.map((a, i) => {
          const gear = /^(TOOL|AGENT|GEAR|MORPH|HARNESS|BRANCH|NEXT|OPERATOR|FEEDBACK|OUTCOME)/.test(
            a.message,
          )
          const dot =
            a.level === "win"
              ? "◆"
              : a.level === "error"
                ? "✕"
                : a.level === "warn"
                  ? "▲"
                  : "·"
          return (
          <box key={i} flexDirection="column">
            <text>
              <span fg={gear ? C.glow : levelColor(a.level)}>{dot} </span>
              <span fg={C.dim}>
                {a.ts
                  ? new Date(a.ts * 1000).toISOString().slice(11, 19)
                  : "--:--:--"}{" "}
              </span>
              {a.strategy && <span fg={C.purple}>[{a.strategy}] </span>}
              <span fg={gear ? C.glow : levelColor(a.level)}>
                {a.message.slice(0, compact ? 40 : 54)}
              </span>
            </text>
            {!compact && a.payload && (
              <text>
                <span fg={C.dim}>  → </span>
                <span fg={C.cyan}>{a.payload.slice(0, 52)}</span>
              </text>
            )}
            {!compact && a.reply && (
              <text>
                <span fg={C.dim}>  ← </span>
                <span fg={C.muted}>{a.reply.slice(0, 52)}</span>
              </text>
            )}
          </box>
          )
        })
      )}
    </box>
  )
}

export function Workboard({
  steps,
  activity,
  progress,
  compact = false,
}: {
  steps: PlanStep[]
  activity: ActivityItem[]
  progress: ProgressState
  compact?: boolean
}) {
  return (
    <box
      flexDirection="column"
      flexGrow={1}
      gap={0}
      minWidth={compact ? 28 : 36}
      width={compact ? 32 : 40}
    >
      <box
        flexDirection="column"
        border
        borderStyle="rounded"
        borderColor={C.line}
        backgroundColor={C.panel}
        title=" work plan "
        titleColor={C.muted}
        flexShrink={0}
      >
        <PlanChecklist steps={steps} />
        <box>
          <ProgressGraph progress={progress} steps={steps} />
        </box>
      </box>
      <ActivityFeed items={activity} maxItems={compact ? 6 : 10} compact={compact} />
    </box>
  )
}
