/**
 * Transparent, low-chrome palette for the agent chat shell.
 * No solid panels. Colors are for text only so the terminal shows through.
 */
export const T = {
  /** Fully transparent — terminal wallpaper / theme shows through. */
  clear: "transparent",
  text: "#e8eaed",
  muted: "#9aa0a6",
  dim: "#5f6368",
  accent: "#8ab4f8",
  success: "#81c995",
  danger: "#f28b82",
  warn: "#fdd663",
  info: "#78d9ec",
  you: "#fdd663",
  agent: "#e8eaed",
  tool: "#8ab4f8",
  system: "#9aa0a6",
  error: "#f28b82",
  result: "#81c995",
  cursor: "#8ab4f8",
} as const

export function roleColor(role: string): string {
  switch (role) {
    case "agent":
      return T.agent
    case "tool":
      return T.tool
    case "system":
      return T.system
    case "error":
      return T.error
    case "result":
      return T.result
    case "operator":
      return T.you
    case "event":
    default:
      return T.muted
  }
}

export function roleTag(role: string): string {
  switch (role) {
    case "operator":
      return "you"
    case "agent":
      return "brain"
    case "tool":
      return "tool"
    case "system":
      return "sys"
    case "error":
      return "err"
    case "result":
      return "out"
    case "event":
      return "evt"
    default:
      return role.slice(0, 5)
  }
}

export function successColor(success: boolean | null): string {
  if (success === true) return T.success
  if (success === false) return T.danger
  return T.muted
}
