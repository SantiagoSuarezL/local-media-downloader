import { describe, expect, it } from 'vitest'
import {
  STATE_TONE,
  formatBytes,
  formatDuration,
  formatEta,
  formatRelativeTime,
  isTerminal,
} from '../src/lib/format'

describe('formatBytes', () => {
  it('formats bytes without decimals', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(999)).toBe('999 B')
  })

  it('scales through units with one decimal', () => {
    expect(formatBytes(1024)).toBe('1.0 KB')
    expect(formatBytes(1536)).toBe('1.5 KB')
    expect(formatBytes(1024 * 1024)).toBe('1.0 MB')
    expect(formatBytes(2.5 * 1024 ** 3)).toBe('2.5 GB')
  })

  it('renders absence as an em dash, never a fake zero', () => {
    expect(formatBytes(null)).toBe('—')
    expect(formatBytes(undefined)).toBe('—')
  })
})

describe('formatDuration', () => {
  it('formats minutes and seconds', () => {
    expect(formatDuration(0)).toBe('0:00')
    expect(formatDuration(65)).toBe('1:05')
    expect(formatDuration(59.4)).toBe('0:59')
  })

  it('adds hours only when needed', () => {
    expect(formatDuration(3599)).toBe('59:59')
    expect(formatDuration(3661)).toBe('1:01:01')
  })

  it('renders absence as an em dash', () => {
    expect(formatDuration(null)).toBe('—')
    expect(formatDuration(undefined)).toBe('—')
  })
})

describe('formatEta', () => {
  it('delegates to the duration format', () => {
    expect(formatEta(90)).toBe('1:30')
  })

  it('treats negative and missing ETAs as unknown', () => {
    expect(formatEta(-1)).toBe('—')
    expect(formatEta(null)).toBe('—')
    expect(formatEta(undefined)).toBe('—')
  })
})

describe('isTerminal', () => {
  it('matches the backend terminal set exactly', () => {
    expect(isTerminal('COMPLETED')).toBe(true)
    expect(isTerminal('FAILED')).toBe(true)
    expect(isTerminal('CANCELLED')).toBe(true)
  })

  it('rejects every non-terminal state', () => {
    for (const state of [
      'CREATED',
      'RESOLVING',
      'READY',
      'QUEUED',
      'DOWNLOADING',
      'PROCESSING',
      'VALIDATING',
      'COMMITTING',
      'CANCEL_REQUESTED',
      'RETRY_WAIT',
      'RECOVERY_REQUIRED',
    ]) {
      expect(isTerminal(state)).toBe(false)
    }
  })
})

describe('STATE_TONE', () => {
  it('covers every state the UI can render', () => {
    for (const state of [
      'COMPLETED',
      'FAILED',
      'CANCELLED',
      'RECOVERY_REQUIRED',
      'RETRY_WAIT',
      'DOWNLOADING',
      'PROCESSING',
      'QUEUED',
    ]) {
      expect(STATE_TONE[state]).toBeTruthy()
    }
  })
})

describe('formatRelativeTime', () => {
  const now = new Date('2026-10-08T12:00:00Z').getTime()

  it('reads as "just now" for the last few seconds', () => {
    expect(formatRelativeTime('2026-10-08T11:59:58Z', now)).toBe('just now')
  })

  it('scales from seconds to days', () => {
    expect(formatRelativeTime('2026-10-08T11:59:30Z', now)).toBe('30s ago')
    expect(formatRelativeTime('2026-10-08T11:57:00Z', now)).toBe('3 min ago')
    expect(formatRelativeTime('2026-10-08T09:00:00Z', now)).toBe('3h ago')
    expect(formatRelativeTime('2026-10-06T12:00:00Z', now)).toBe('2d ago')
  })

  it('falls back to the absolute date beyond a month', () => {
    expect(formatRelativeTime('2026-08-01T12:00:00Z', now)).not.toMatch(/ago$/)
  })

  it('renders an unparseable date as an em dash, never "NaN ago"', () => {
    expect(formatRelativeTime('not-a-date', now)).toBe('—')
  })
})
