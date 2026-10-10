// @vitest-environment jsdom
import type { JobDto } from '@lmd/contracts'
import { cleanup, fireEvent, render, screen } from '@testing-library/svelte'
import { get } from 'svelte/store'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../src/lib/api'
import { live, stopLiveUpdates } from '../src/lib/live'
import JobDetails from '../src/screens/JobDetails.svelte'

vi.mock('../src/lib/api', () => ({
  api: { getJob: vi.fn(), cancelJob: vi.fn(), retryJob: vi.fn(), setPriority: vi.fn() },
}))

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
}

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

const downloading = makeJob({ state: 'DOWNLOADING', progress: 0.5, current_stage: 'download' })
const completed = makeJob({
  state: 'COMPLETED',
  title: 'Finished video',
  progress: 1,
  current_stage: 'completed',
  output_path: '/out/v.mp4',
})

beforeEach(() => {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
})

afterEach(() => {
  cleanup()
  stopLiveUpdates()
  live.set({})
  vi.unstubAllGlobals()
  vi.resetAllMocks()
})

function source(): FakeEventSource {
  return FakeEventSource.instances[0]
}

describe('JobDetails ghost-download regression', () => {
  it('stays finished after the live entry is purged', async () => {
    // Durable record: still downloading on open, completed once re-read.
    vi.mocked(api.getJob).mockResolvedValueOnce(downloading).mockResolvedValue(completed)

    render(JobDetails, { props: { jobId: 'job-1' } })
    await screen.findByText('Some video')
    expect(screen.getByText('Cancel job')).toBeTruthy()

    // Stream paints the terminal state; the screen must re-read the durable
    // record instead of trusting its first snapshot forever. Waiting for the
    // reloaded title (not just the streamed 'Finished') proves the reload
    // itself landed on screen.
    source().emit('state', { job_id: 'job-1', state: 'COMPLETED', percentage: 100 })
    await screen.findByText('Finished video')
    expect(screen.getByText('Finished')).toBeTruthy()
    expect(vi.mocked(api.getJob).mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(screen.queryByText('Cancel job')).toBeNull()

    // Simulate the 5s terminal purge: the live entry vanishes. Without the
    // revalidation above this snaps back to the stale DOWNLOADING snapshot
    // (ghost progress bar + dead Cancel button).
    const callsAfterFinish = vi.mocked(api.getJob).mock.calls.length
    live.set({})
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.getByText('Finished video')).toBeTruthy()
    expect(screen.getByText('Finished')).toBeTruthy()
    expect(screen.queryByText('Cancel job')).toBeNull()
    expect(vi.mocked(api.getJob).mock.calls).toHaveLength(callsAfterFinish)
  })

  it('resyncs the durable record when cancel loses the race with completion', async () => {
    vi.mocked(api.getJob).mockResolvedValue(downloading)
    vi.mocked(api.cancelJob).mockRejectedValue(
      new Error('job job-1 is not cancellable from COMPLETED'),
    )

    render(JobDetails, { props: { jobId: 'job-1' } })
    await screen.findByText('Some video')

    await fireEvent.click(screen.getByText('Cancel job'))
    await screen.findByText(/not cancellable from COMPLETED/)
    // The failed cancel re-reads the job instead of leaving the stale
    // snapshot (and its dead button) on screen.
    expect(vi.mocked(api.getJob).mock.calls.length).toBeGreaterThanOrEqual(2)
  })

  it('keeps no scheduler-only zombie entries alive', async () => {
    vi.mocked(api.getJob).mockResolvedValue(downloading)
    render(JobDetails, { props: { jobId: 'job-1' } })
    await screen.findByText('Some video')

    source().emit('scheduler', { event: 'job_finished', job_id: 'job-1' })
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(get(live)).toEqual({})
  })
})
