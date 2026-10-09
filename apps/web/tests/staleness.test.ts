import { afterEach, describe, expect, it, vi } from 'vitest'
import { get } from 'svelte/store'
import { TERMINAL_TTL_MS, isStale, live, stopLiveUpdates, type LiveJob } from '../src/lib/live'
import { STALE_AFTER_MS } from '../src/lib/jobState'

function entry(overrides: Partial<LiveJob> = {}): LiveJob {
  return {
    job_id: 'job-1',
    state: 'DOWNLOADING',
    stage: 'download',
    percentage: 10,
    downloadedBytes: null,
    totalBytes: null,
    speed: null,
    eta: null,
    updatedAt: 1_000_000,
    ...overrides,
  }
}

afterEach(() => {
  stopLiveUpdates()
  live.set({})
})

describe('isStale', () => {
  it('stays fresh inside the stage budget', () => {
    const now = 1_000_000 + STALE_AFTER_MS.download - 1
    expect(isStale(entry(), now)).toBe(false)
  })

  it('goes stale once the stage exceeds its budget', () => {
    const now = 1_000_000 + STALE_AFTER_MS.download + 1
    expect(isStale(entry(), now)).toBe(true)
  })

  it('gives FFmpeg a far longer budget than the download stage', () => {
    // ffmpeg can run a long stretch emitting nothing; a shared short budget
    // would cry wolf on every long transcode and teach the reader to ignore it.
    expect(STALE_AFTER_MS.process).toBeGreaterThan(STALE_AFTER_MS.download * 3)
    expect(STALE_AFTER_MS.download).toBeLessThanOrEqual(20_000)
  })

  it('never calls a finished job stale', () => {
    const longAgo = 1_000_000 + STALE_AFTER_MS.download * 100
    expect(isStale(entry({ state: 'COMPLETED' }), longAgo)).toBe(false)
    expect(isStale(entry({ state: 'FAILED' }), longAgo)).toBe(false)
    expect(isStale(entry({ state: 'CANCELLED' }), longAgo)).toBe(false)
  })

  it('does not call a pre-pipeline job stale', () => {
    const longAgo = 1_000_000 + STALE_AFTER_MS.download * 100
    expect(isStale(entry({ state: 'QUEUED', stage: null }), longAgo)).toBe(false)
  })
})

describe('terminal purging', () => {
  it('keeps a terminal entry briefly so its final state can paint', () => {
    const now = Date.now()
    live.set({ 'job-1': entry({ state: 'COMPLETED', updatedAt: now }) })
    // Before the TTL the entry must survive: dropping it instantly would make a
    // just-finished job blink back to its stale snapshot.
    expect(get(live)['job-1']).toBeDefined()
    expect(TERMINAL_TTL_MS).toBeGreaterThan(0)
  })

  it('holds a recent timestamp in seconds, not milliseconds', () => {
    // A unit mistake here would purge every entry immediately and reintroduce
    // the stale-progress bug this whole mechanism exists to prevent.
    expect(TERMINAL_TTL_MS).toBeGreaterThanOrEqual(1000)
    expect(TERMINAL_TTL_MS).toBeLessThanOrEqual(60_000)
  })
})

describe('clock', () => {
  it('only ticks while work is in flight', async () => {
    vi.useFakeTimers()
    const { clock, startLiveUpdates } = await import('../src/lib/live')

    class FakeEventSource {
      static instances: FakeEventSource[] = []
      addEventListener(): void {}
      close(): void {}
      constructor() {
        FakeEventSource.instances.push(this)
      }
    }
    vi.stubGlobal('EventSource', FakeEventSource)
    live.set({})

    const before = get(clock)
    startLiveUpdates()
    // An idle queue must not wake subscribers every second.
    vi.advanceTimersByTime(3000)
    expect(get(clock)).toBe(before)

    live.set({ 'job-1': entry({ state: 'DOWNLOADING' }) })
    vi.advanceTimersByTime(1000)
    expect(get(clock)).toBeGreaterThan(before)

    vi.unstubAllGlobals()
    vi.useRealTimers()
  })
})
