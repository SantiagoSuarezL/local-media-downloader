import type { JobDto } from '@lmd/contracts'
import { get } from 'svelte/store'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { live, mergeLive, startLiveUpdates, stopLiveUpdates, type LiveJob } from '../src/lib/live'

type Listener = (message: { data: string }) => void

class FakeEventSource {
  static instances: FakeEventSource[] = []

  listeners = new Map<string, Listener[]>()
  closed = false
  url: string

  constructor(url: string) {
    this.url = url
    FakeEventSource.instances.push(this)
  }

  addEventListener(kind: string, listener: Listener): void {
    const list = this.listeners.get(kind) ?? []
    list.push(listener)
    this.listeners.set(kind, list)
  }

  close(): void {
    this.closed = true
  }

  emit(kind: string, payload: unknown): void {
    for (const listener of this.listeners.get(kind) ?? []) {
      listener({ data: JSON.stringify(payload) })
    }
  }

  emitRaw(kind: string, data: string): void {
    for (const listener of this.listeners.get(kind) ?? []) {
      listener({ data })
    }
  }
}

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterEach(() => {
  stopLiveUpdates()
  live.set({})
  vi.unstubAllGlobals()
})

function makeJob(overrides: Partial<JobDto> = {}): JobDto {
  return {
    id: 'job-1',
    state: 'QUEUED',
    created_at: '2026-10-07T00:00:00Z',
    updated_at: '2026-10-07T00:00:00Z',
    source_url: 'https://example.com/v',
    title: 'Some video',
    progress: 0,
    current_stage: null,
    error_code: null,
    error_message: null,
    output_path: null,
    priority: 0,
    attempt_count: 0,
    ...overrides,
  }
}

describe('startLiveUpdates', () => {
  it('opens one stream on the events endpoint', () => {
    startLiveUpdates()
    startLiveUpdates()
    expect(FakeEventSource.instances).toHaveLength(1)
    expect(FakeEventSource.instances[0].url).toBe('/api/v1/events')
  })

  it('ingests progress frames into the shared store', () => {
    startLiveUpdates()
    FakeEventSource.instances[0].emit('progress', {
      job_id: 'a',
      state: 'DOWNLOADING',
      stage: 'download',
      percentage: 50,
      downloaded_bytes: 100,
      total_bytes: 200,
      speed_bytes_per_second: 10,
      eta_seconds: 5,
    })
    expect(get(live)['a']).toEqual({
      job_id: 'a',
      state: 'DOWNLOADING',
      stage: 'download',
      percentage: 50,
      downloadedBytes: 100,
      totalBytes: 200,
      speed: 10,
      eta: 5,
      updatedAt: expect.any(Number),
    })
  })

  it('merges partial frames without losing earlier fields', () => {
    startLiveUpdates()
    const source = FakeEventSource.instances[0]
    source.emit('progress', { job_id: 'a', percentage: 25 })
    source.emit('state', { job_id: 'a', state: 'PROCESSING' })
    expect(get(live)['a']).toEqual({
      job_id: 'a',
      state: 'PROCESSING',
      stage: null,
      percentage: 25,
      downloadedBytes: null,
      totalBytes: null,
      speed: null,
      eta: null,
      updatedAt: expect.any(Number),
    })
  })

  it('ignores frames without a string job id', () => {
    startLiveUpdates()
    const source = FakeEventSource.instances[0]
    source.emit('progress', { percentage: 99 })
    source.emit('progress', { job_id: 42, percentage: 99 })
    expect(get(live)).toEqual({})
  })

  it('ignores scheduler lifecycle frames without progress data', () => {
    startLiveUpdates()
    const source = FakeEventSource.instances[0]
    source.emit('scheduler', { event: 'job_started', job_id: 'a' })
    source.emit('scheduler', { event: 'job_finished', job_id: 'a' })
    // A scheduler-only frame must never create a `state: null` zombie entry:
    // it is informational, not liveness.
    expect(get(live)).toEqual({})
  })

  it('does not let scheduler frames bump a finished entry', () => {
    startLiveUpdates()
    const source = FakeEventSource.instances[0]
    const now = vi.spyOn(Date, 'now')
    now.mockReturnValueOnce(1000).mockReturnValueOnce(2000).mockReturnValueOnce(3000)
    try {
      source.emit('progress', { job_id: 'a', state: 'DOWNLOADING', percentage: 50 })
      source.emit('state', { job_id: 'a', state: 'COMPLETED', percentage: 100 })
      expect(get(live)['a']?.updatedAt).toBe(2000)
      source.emit('scheduler', { event: 'job_finished', job_id: 'a' })
      const after = get(live)['a']
      expect(after?.state).toBe('COMPLETED')
      expect(after?.percentage).toBe(100)
      // The terminal purge relies on `updatedAt` going stale; a scheduler
      // frame must not refresh it and keep the entry (ghost) alive.
      expect(after?.updatedAt).toBe(2000)
    } finally {
      now.mockRestore()
    }
  })

  it('ignores malformed JSON instead of breaking the stream', () => {
    startLiveUpdates()
    const source = FakeEventSource.instances[0]
    source.emitRaw('progress', 'not-json{{{')
    expect(get(live)).toEqual({})
    source.emit('progress', { job_id: 'a', percentage: 10 })
    expect(get(live)['a']?.percentage).toBe(10)
  })
})

describe('stopLiveUpdates', () => {
  it('closes the stream and allows a fresh start', () => {
    startLiveUpdates()
    stopLiveUpdates()
    expect(FakeEventSource.instances[0].closed).toBe(true)
    startLiveUpdates()
    expect(FakeEventSource.instances).toHaveLength(2)
  })
})

function makeLive(overrides: Partial<LiveJob> = {}): LiveJob {
  return {
    job_id: 'job-1',
    state: null,
    stage: null,
    percentage: null,
    downloadedBytes: null,
    totalBytes: null,
    speed: null,
    eta: null,
    updatedAt: 0,
    ...overrides,
  }
}

describe('mergeLive', () => {
  it('returns the job untouched without live data', () => {
    const job = makeJob()
    expect(mergeLive(job, undefined)).toBe(job)
  })

  it('overrides state, stage and progress from the stream', () => {
    const merged = mergeLive(
      makeJob({ progress: 0.1 }),
      makeLive({
        state: 'DOWNLOADING',
        stage: 'download',
        percentage: 50,
        downloadedBytes: 5,
        totalBytes: 10,
        speed: 1,
        eta: 2,
      }),
    )
    expect(merged.state).toBe('DOWNLOADING')
    expect(merged.current_stage).toBe('download')
    expect(merged.progress).toBe(0.5)
  })

  it('clamps out-of-range percentages instead of breaking the bar', () => {
    const over = mergeLive(makeJob(), makeLive({ percentage: 150 }))
    expect(over.progress).toBe(1)
    const under = mergeLive(makeJob({ progress: 0.3 }), makeLive({ percentage: -20 }))
    expect(under.progress).toBe(0)
  })

  it('falls back to the stored job when the stream has gaps', () => {
    const merged = mergeLive(makeJob({ progress: 0.3, current_stage: 'queued' }), makeLive())
    expect(merged.state).toBe('QUEUED')
    expect(merged.progress).toBe(0.3)
    expect(merged.current_stage).toBe('queued')
  })
})
