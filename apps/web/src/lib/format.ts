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

export const STATE_TONE: Record<string, string> = {
  COMPLETED: 'text-emerald-400',
  FAILED: 'text-red-400',
  CANCELLED: 'text-neutral-500',
  RECOVERY_REQUIRED: 'text-amber-400',
  RETRY_WAIT: 'text-amber-400',
  DOWNLOADING: 'text-sky-400',
  PROCESSING: 'text-sky-400',
  VALIDATING: 'text-sky-400',
  COMMITTING: 'text-sky-400',
  QUEUED: 'text-neutral-400',
  CANCEL_REQUESTED: 'text-amber-400',
}
