import type { JobState } from '@lmd/contracts'

export const TERMINAL_STATES: JobState[] = ['COMPLETED', 'FAILED', 'CANCELLED']

export function isTerminal(state: string): boolean {
  return TERMINAL_STATES.includes(state as JobState)
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null) {
    return '—'
  }
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  return `${value.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) {
    return '—'
  }
  const total = Math.round(seconds)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number): string => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`
}

export function formatEta(seconds: number | null | undefined): string {
  if (seconds == null || seconds < 0) {
    return '—'
  }
  return formatDuration(seconds)
}

export function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString()
}

/**
 * Readable human time. "3 min ago" says whether a row is fresh; an absolute
 * timestamp makes the reader do that subtraction themselves, which is exactly
 * the work a stale table should not be asking of someone.
 */
export function formatRelativeTime(value: string, now: number = Date.now()): string {
  const then = new Date(value).getTime()
  if (Number.isNaN(then)) {
    return '—'
  }
  const seconds = Math.round((now - then) / 1000)
  if (seconds < 5) {
    return 'just now'
  }
  if (seconds < 60) {
    return `${seconds}s ago`
  }
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) {
    return `${minutes} min ago`
  }
  const hours = Math.round(minutes / 60)
  if (hours < 24) {
    return `${hours}h ago`
  }
  const days = Math.round(hours / 24)
  if (days < 30) {
    return `${days}d ago`
  }
  return formatTimestamp(value)
}

/**
 * State words mapped to tone classes.
 *
 * Superseded by `jobState.ts`'s `toneFor` plus the `StateBadge` component,
 * which carries state with a lamp and a word instead of colour alone. Kept
 * because it is a plain lookup that costs nothing and other screens may still
 * want a single colour class; delete it once nothing imports it.
 */
export const STATE_TONE: Record<string, string> = {
  COMPLETED: 'text-ok',
  FAILED: 'text-crit',
  CANCELLED: 'text-ink-3',
  RECOVERY_REQUIRED: 'text-warn',
  RETRY_WAIT: 'text-warn',
  DOWNLOADING: 'text-accent',
  PROCESSING: 'text-accent',
  VALIDATING: 'text-accent',
  COMMITTING: 'text-accent',
  QUEUED: 'text-ink-3',
  CANCEL_REQUESTED: 'text-warn',
}
